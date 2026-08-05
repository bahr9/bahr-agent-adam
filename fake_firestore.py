# -*- coding: utf-8 -*-
"""
🧪 Firestore مزيّف للاختبارات -- بديل كامل في الذاكرة، صفر شبكة.

القاعدة (2026-08-05): **أي اختبار بيلمس Firestore لازم يستخدم الملف ده من
البداية.** ممنوع أي اختبار يكتب على قاعدة البيانات الحقيقية.

السبب مش نظري: `test_loan_commands.py` كان بيكتب حدثين حقيقيين في
`adam_events` عند كل تشغيلة. الحدثين دول بيخلوا تلات اختبارات تانية
(`test_loan_conflict_observer`, `test_conflict_resolution_flow`,
`test_tracking_stability`) ترفض تشتغل لأنها بتشترط دخول نضيف على نفس
الكيان -- يعني تشغيلة واحدة كانت بتكسر باقي السويت، وبتسيب أثر دائم في
سجل أحداث الإنتاج (اللي هو append-only بطبيعته).

الاستخدام:

    from fake_firestore import FakeFirestore, use_fake_firestore

    with use_fake_firestore() as db:
        db.seed("loans", "paid_status", {"paid": {"ca_0": True}})
        ...                       # أي كود بينادي firestore_db هيشوف الـ fake
    # هنا كل حاجة رجعت زي ما كانت

بيغطي الجزء المستخدم فعليًا من واجهة Firestore: document get/set/delete،
الاستعلام بـ where + order_by + limit، والـ batch الذري.
"""

import copy
import uuid
from contextlib import contextmanager


class FakeDocumentSnapshot:
    """لقطة مستند -- زي DocumentSnapshot بتاعة Firestore."""

    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return copy.deepcopy(self._data) if self._data is not None else None


class FakeDocumentRef:
    def __init__(self, store, collection_name, doc_id):
        self._store = store
        self._collection = collection_name
        self.id = doc_id

    def get(self):
        data = self._store._data.get(self._collection, {}).get(self.id)
        return FakeDocumentSnapshot(self.id, copy.deepcopy(data) if data else None)

    def set(self, data, merge=False):
        self._store._apply_set(self._collection, self.id, data, merge)

    def update(self, data):
        self._store._apply_set(self._collection, self.id, data, merge=True)

    def delete(self):
        self._store._data.get(self._collection, {}).pop(self.id, None)


class FakeQuery:
    """استعلام قابل للتسلسل: where -> order_by -> limit -> stream."""

    def __init__(self, store, collection_name, filters=None, order=None, limit_n=None):
        self._store = store
        self._collection = collection_name
        self._filters = list(filters or [])
        self._order = order
        self._limit = limit_n

    def _clone(self, **changes):
        return FakeQuery(
            self._store,
            self._collection,
            changes.get("filters", self._filters),
            changes.get("order", self._order),
            changes.get("limit_n", self._limit),
        )

    def where(self, field=None, op=None, value=None, filter=None):
        if filter is not None:
            field = filter.field_path
            op = filter.op_string
            value = filter.value
        if op != "==":
            raise NotImplementedError(f"الـ fake بيدعم '==' بس، مش '{op}'")
        return self._clone(filters=self._filters + [(field, value)])

    def order_by(self, field, direction="ASCENDING"):
        return self._clone(order=(field, direction))

    def limit(self, count):
        return self._clone(limit_n=count)

    def stream(self):
        docs = [
            (doc_id, data)
            for doc_id, data in self._store._data.get(self._collection, {}).items()
            if all(data.get(field) == value for field, value in self._filters)
        ]

        if self._order:
            field, direction = self._order
            docs.sort(
                key=lambda item: (item[1].get(field) is None, item[1].get(field)),
                reverse=(direction == "DESCENDING"),
            )
        else:
            # Firestore بيرجع بترتيب الـ document id لما مفيش order_by
            docs.sort(key=lambda item: item[0])

        if self._limit is not None:
            docs = docs[: self._limit]

        return iter([FakeDocumentSnapshot(d, copy.deepcopy(v)) for d, v in docs])


class FakeCollectionRef(FakeQuery):
    def document(self, doc_id=None):
        """doc_id=None بيولّد معرّف تلقائي -- زي Firestore بالظبط."""
        if doc_id is None:
            doc_id = uuid.uuid4().hex[:20]
        return FakeDocumentRef(self._store, self._collection, doc_id)

    def add(self, data):
        """بيضيف مستند بمعرّف تلقائي، وبيرجع (timestamp, ref) زي Firestore."""
        ref = self.document()
        ref.set(data)
        return None, ref


class FakeBatch:
    """batch ذري -- ولا كتابة بتتطبق غير عند commit()."""

    def __init__(self, store):
        self._store = store
        self._pending = []

    def set(self, ref, data, merge=False):
        self._pending.append((ref._collection, ref.id, copy.deepcopy(data), merge))

    def commit(self):
        for collection, doc_id, data, merge in self._pending:
            self._store._apply_set(collection, doc_id, data, merge)
        self._pending = []


class FakeFirestore:
    """قاعدة بيانات في الذاكرة بواجهة Firestore."""

    def __init__(self):
        self._data = {}

    # ---------- واجهة Firestore ----------

    def collection(self, name):
        return FakeCollectionRef(self, name)

    def batch(self):
        return FakeBatch(self)

    # ---------- أدوات للاختبارات ----------

    def seed(self, collection_name, doc_id, data):
        """يحط مستند جاهز قبل الاختبار."""
        self._data.setdefault(collection_name, {})[doc_id] = copy.deepcopy(data)

    def all_docs(self, collection_name):
        """كل مستندات collection كـ dict."""
        return copy.deepcopy(self._data.get(collection_name, {}))

    def count(self, collection_name):
        return len(self._data.get(collection_name, {}))

    # ---------- داخلي ----------

    def _apply_set(self, collection_name, doc_id, data, merge):
        bucket = self._data.setdefault(collection_name, {})
        if merge and doc_id in bucket:
            bucket[doc_id] = _deep_merge(bucket[doc_id], copy.deepcopy(data))
        else:
            bucket[doc_id] = copy.deepcopy(data)


def _deep_merge(base, incoming):
    """دمج متداخل -- زي set(merge=True) في Firestore."""
    result = copy.deepcopy(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def install_fake_firestore(seed=None):
    """يبدّل firestore_db بـ fake لبقية العملية، وبيرجّع الـ fake.

    للاختبارات اللي على شكل سكريبت (`python test_x.py`) -- fake واحد لكل
    عملية، ومفيش داعي لـ teardown لأن العملية بتنتهي أصلاً. لو محتاج عزل
    داخل نفس العملية، استخدم use_fake_firestore() كـ context manager.
    """
    import services.firebase_service as firebase_service

    fake = FakeFirestore()
    for collection_name, documents in (seed or {}).items():
        for doc_id, data in documents.items():
            fake.seed(collection_name, doc_id, data)

    firebase_service.firestore_db = fake
    return fake


@contextmanager
def use_fake_firestore(seed=None):
    """يبدّل firestore_db بـ fake طول الـ block، ويرجّع الأصلي في الآخر.

    seed: dict اختياري بالشكل {collection: {doc_id: data}}
    """
    import services.firebase_service as firebase_service

    fake = FakeFirestore()
    for collection_name, documents in (seed or {}).items():
        for doc_id, data in documents.items():
            fake.seed(collection_name, doc_id, data)

    original = firebase_service.firestore_db
    firebase_service.firestore_db = fake
    try:
        yield fake
    finally:
        firebase_service.firestore_db = original
