-- ============================================================
-- 003 -- المشاريع وبيانات الموقع (فرونت Bahr OS)
-- ============================================================
-- التاريخ: 2026-08-05
-- الحالة: 🟡 للمراجعة -- متشغلش قبل ما التصدير الكامل يتأكد
--
-- الملف ده شايل البيانات اللي **مشتركة بين آدم وفرونت Bahr OS**، زايد
-- تلات مجموعات فرعية ومجموعتين أب آدم مكانش عارفهم خالص:
--
--     projects/{code}/invoices/{phase}      -- كل الفواتير
--     projects/{code}/siteReports/{date}    -- كل تقارير الموقع
--     projects/{code}/purchases/{id}        -- كل أوامر الشراء
--     users/{uid}                           -- عضوية المستخدم في المشاريع
--     notifications/{id}                    -- تنبيهات طلبات الشراء
--
-- ⚠️ الجداول دي مينفعش تشتغل عليها الهجرة من غير تنسيق مع فرونت Bahr OS
--    -- هو كاتب أساسي فيها، مش آدم.
-- ============================================================

begin;


-- ============================================================
-- 1. projects
-- ============================================================
-- المعرّف نص حر: تلات صيغ موجودة فعلًا في البيانات --
--   PRJ-M8K2QP4Z   (الفرونت المنشور: base36 من epoch)
--   PRJ-260805-K3F (فرونت v2: تاريخ + عشوائي)
--   PRJ-A3F91B2C   (آدم: uuid4)
-- ممنوع أي parser يفترض شكل واحد.
--
-- كل الأعمدة nullable عن قصد: كل كتابة في الفرونت `.set(merge:true)`،
-- فمجموعة حقول المستند هي **اللي المستخدم صادف إنه لمسه**. صف فيه
-- quantity من غير finaldata، أو finaldata من غير name -- حالات صحيحة.

create table public.projects (
    id                    text primary key,        -- معرّف Firestore زي ما هو
    name                  text,                    -- الفرونت بس (آدم مابيكتبهوش)
    client                text,                    -- الاتنين
    area                  numeric(12, 2),          -- الفرونت parseFloat، آدم float
    level                 text,                    -- الفرونت بس: اقتصادي/متوسط/راقي/فاخر/ملكي
    status                text,                    -- آدم بس (الفرونت مالوش مفهوم status للمشروع)
    allowed_supervisors   text[] not null default '{}',
    note                  text,                    -- ← الفرونت (مفرد)
    adam_notes            text,                    -- ← آدم (جمع) -- عمودين لنفس المفهوم
    created_by            text,                    -- uid | "ADAM" | إيميل -- تلات نطاقات
    created_by_kind       text,                    -- 'firebase_uid' | 'adam' | 'email'
    deadline              date,                    -- آدم بس
    completion            text,                    -- آدم بس، مدخل LLM خام غير مُتحقَّق
    last_report           text,                    -- آدم بس
    created_at            timestamptz,
    updated_at            timestamptz,             -- تحويله محتاج تفريع حسب النوع، تحت

    constraint projects_level_valid check (level is null or level in
        ('اقتصادي', 'متوسط', 'راقي', 'فاخر', 'ملكي'))
);

create index projects_updated_idx on public.projects (updated_at desc nulls last);
create index projects_status_idx on public.projects (status) where status is not null;

comment on column public.projects.note is
    'ملاحظة الفرونت (note مفرد). آدم بيكتب adam_notes -- ولا واحد شايف التاني.';
comment on column public.projects.updated_at is
    'باگ إنتاج حي: الفرونت بيكتب Date.now() رقم، وآدم بيكتب ISO نص. Firestore '
    'بيرتّب كل الأرقام قبل كل النصوص، والاستعلام الأساسي orderBy(updatedAt desc) '
    '-- يعني أي مشروع آدم لمسه بيترتّب بعد كل مشاريع الفرونت مهما كان أحدث. '
    'التحويل لازم يفرّع حسب نوع القيمة: رقم -> to_timestamp(v/1000)، نص -> ::timestamptz. '
    'وآدم كان بيكتب كمان last_updated -- نسخة تانية من نفس المعنى، بتتدمج هنا.';

-- ⚠️ اتشال عن قصد: `items` (آدم بيكتبه [] ومابيملاهوش أبدًا -- عمود وهمي)
--                  `siteReports` كخريطة (الفرونت المنشور بيقراها ومحدش بيكتبها --
--                   البيانات الحقيقية في المجموعة الفرعية تحت)


-- ============================================================
-- 2. تقديرات المراحل -- foundationdata / finishdata / finaldata
-- ============================================================
-- ⚠️ تصحيح فهم: `finaldata` **مش** ملخص ولا بيانات نهائية. دي تقدير
--    مرحلة "الفينيش والديكور"، مطابقة في الشكل للمرحلتين التانيتين.
--    آدم في get_project_details بيعرضها كـ final_data كأنها ملخص -- غلط.

create table public.project_phase_estimates (
    id            uuid primary key default gen_random_uuid(),
    project_id    text not null references public.projects(id) on delete cascade,
    phase         text not null,

    -- دول حقول نصية **مستقلة** يكتبها المستخدم في كل تبويب -- مش نسخة
    -- مخزّنة من بيانات المشروع، وبيختلفوا عنها فعلاً
    client_text   text,
    project_text  text,
    area_text     text,          -- نص خام: الفرونت مابيعملهوش parseFloat هنا

    unique (project_id, phase),
    constraint project_phase_valid check (phase in ('foundation', 'finish', 'final'))
);

create table public.project_phase_items (
    id             bigint generated always as identity primary key,
    estimate_id    uuid not null
        references public.project_phase_estimates(id) on delete cascade,

    -- 🔴 الترتيب حامل معنى: عنصر sub=true تابع لأقرب عنصر قبله sub=false.
    --    مفيش أي مفتاح بيربطهم -- الترتيب في المصفوفة هو العلاقة.
    --    من غير العمود ده الهرم بيتدمر بالكامل.
    position       integer not null,

    description    text not null default '',
    unit           text not null,
    qty            numeric(14, 3) not null default 0,
    price          numeric(14, 2) not null default 0,
    is_sub         boolean not null default false,

    unique (estimate_id, position),
    constraint project_phase_items_unit_valid
        check (unit in ('مقطوعية', 'م.ط', 'م²', 'م³'))
);


-- ============================================================
-- 3. حصر الكميات -- quantity
-- ============================================================
create table public.project_quantity (
    id            uuid primary key default gen_random_uuid(),
    project_id    text not null unique references public.projects(id) on delete cascade,
    client_text   text,
    project_text  text,
    area_text     text
);

create table public.project_quantity_items (
    id           bigint generated always as identity primary key,
    quantity_id  uuid not null
        references public.project_quantity(id) on delete cascade,
    position     integer not null,        -- نفس منطق التبعية بالترتيب

    description  text not null default '',
    unit         text not null,

    -- 🔴 الأبعاد الخام لازم تفضل زي ما هي. الوحدة هي اللي بتحدد أنهي بُعد
    --    له معنى، والباقي بيفضل شايل اللي المستخدم كتبه:
    --      م³   -> length × width × height × count
    --      م²   -> length × width × count          (height متجاهَل)
    --      م.ط  -> length × count                  (width و height متجاهَلين)
    --      مقطوعية -> count
    --    تطبيعهم لعمود كمية واحد بيمنع إعادة الحساب والمراجعة.
    length       numeric(12, 3) not null default 0,
    width        numeric(12, 3) not null default 0,
    height       numeric(12, 3) not null default 0,
    count        numeric(12, 3) not null default 1,   -- ملحوظة: افتراضي 1 مش 0
    wastage_pct  numeric(6, 2) not null default 0,

    phase        text,                    -- '' -> NULL: يعني "متجمّعش في أي مرحلة"

    unique (quantity_id, position),
    constraint project_quantity_items_unit_valid
        check (unit in ('مقطوعية', 'م.ط', 'م²', 'م³')),
    constraint project_quantity_items_phase_valid
        check (phase is null or phase in ('foundation', 'finish', 'final'))
);

-- 🔴 الصور كانت base64 متخزنة **جوه المستند** (data:image/jpeg;base64,...).
--    حد مستند Firestore 1 ميجا، فمشروع بصور كتير قريب من الحد أصلاً.
--    بتتنقل لتخزين كائنات، والجدول ده بيشيل المرجع بس.
create table public.project_quantity_item_images (
    id            bigint generated always as identity primary key,
    item_id       bigint not null
        references public.project_quantity_items(id) on delete cascade,
    position      integer not null,
    storage_path  text not null,          -- بعد الرفع لتخزين الكائنات
    unique (item_id, position)
);


-- ============================================================
-- 4. الفواتير -- projects/{code}/invoices/{phase}
-- ============================================================
create table public.invoices (
    id              uuid primary key default gen_random_uuid(),
    project_id      text not null references public.projects(id) on delete cascade,
    phase           text not null,       -- كان **معرّف المستند** نفسه

    period_from     date,
    period_to       date,
    status          text not null default 'draft',
    execution_rate  numeric(5, 2),       -- 0-100

    -- 🔴 الملخص لقطة تاريخية، **مش** محسوب من الأسطر:
    --    (أ) بيتخزن Math.round صحيح، بينما أسطر الفاتورة float --
    --        يعني Σ أسطر ≠ الملخص. المخزّن هو المرجع.
    --    (ب) النسب اتصوّرت وقت التوليد من الواجهة، **مش** من
    --        projects.deductionRates. ممنوع نربطها FK بالنسبة الحالية
    --        للمشروع -- ده هيعيد كتابة فواتير صدرت خلاص.
    total_labor        numeric(14, 2),
    total_purchases    numeric(14, 2),
    total_invoice      numeric(14, 2),
    supervision_rate   numeric(6, 2),    -- نسبة مئوية صحيحة: 20 يعني 20٪
    supervision_amount numeric(14, 2),
    insurance_rate     numeric(6, 2),
    insurance_amount   numeric(14, 2),
    net                numeric(14, 2),

    notes           text,
    created_by      text,                -- إيميل هنا (بينما projects.created_by بيبقى uid)

    -- علامة مراجعة: النسخة المنشورة كان فيها باگ -- getLaborData بيقرا من
    -- localStorage بدل مستند المشروع، يعني فاتورة ممكن تكون اتولدت من
    -- أسطر **مشروع تاني** كان مفتوح في نفس التبويب. v2 صلّحه.
    -- الاستيراد بيقدر يعلّم الصفوف المشكوك فيها من غير ما نغيّر الجداول.
    needs_review    boolean not null default false,
    review_reason   text,

    created_at      timestamptz,
    updated_at      timestamptz,

    unique (project_id, phase),
    constraint invoices_phase_valid
        check (phase in ('foundation', 'finish', 'final', 'finalAll')),
    constraint invoices_status_valid
        check (status in ('draft', 'submitted', 'approved', 'rejected'))
);

comment on table public.invoices is
    'المعادلة اللي لازم تتحافظ: الخصومات بتتحسب على total_labor **بس**، '
    'مش على total_purchases. net = total_labor*(1 - s/100 - i/100) + total_purchases. '
    'أي عمود محسوب بيطبّق الخصم على الإجمالي بيغيّر كل رقم في كل فاتورة.';

create table public.invoice_items (
    id                bigint generated always as identity primary key,
    invoice_id        uuid not null references public.invoices(id) on delete cascade,
    position          integer not null,       -- كان itemId = 'item1'.. ترتيبي مش مفتاح ثابت

    name              text not null default '',
    unit              text,
    total_qty         numeric(14, 3),
    executed_qty      numeric(14, 3),
    executed_percent  numeric(5, 2),
    unit_price        numeric(14, 2),
    total             numeric(14, 2),         -- float في الأصل، مش مقرّب
    phase             text,

    unique (invoice_id, position)
);

-- 🔴 نقطة الضعف: الربط بين سطر التقدير ونسبة التنفيذ **مطابقة نصية
--    عربية تقريبية**، مش مفتاح. سطر وصفه مابيطابقش أي عنصر من الـ 12
--    بياخد executed=0 -> total=0 -> بيختفي من الفاتورة **من غير أي خطأ**.
--    إضافة مفتاح ثابت بتصلح الهشاشة دي، بس بتغيّر مخرجات الفواتير --
--    قرار شغل، مش تنظيف schema.

create table public.invoice_item_purchases (
    id              bigint generated always as identity primary key,
    invoice_item_id bigint not null references public.invoice_items(id) on delete cascade,
    position        integer not null,
    name            text,
    quantity        numeric(14, 3),
    unit            text,
    unique (invoice_item_id, position)
);
-- ملحوظة: cost و price في الأصل كانوا null دايمًا (مكتوبين hardcoded) -- اتشالوا.

create table public.invoice_signatures (
    id           bigint generated always as identity primary key,
    invoice_id   uuid not null references public.invoices(id) on delete cascade,
    role         text not null,
    signer_name  text,
    signed_date  date,
    storage_path text,                    -- كان base64 PNG جوه المستند
    unique (invoice_id, role),
    constraint invoice_signatures_role_valid
        check (role in ('contractor', 'consultant', 'owner'))
);


-- ============================================================
-- 5. تقارير الموقع -- projects/{code}/siteReports/{YYYY-MM-DD}
-- ============================================================
create table public.site_reports (
    id                uuid primary key default gen_random_uuid(),
    project_id        text not null references public.projects(id) on delete cascade,
    report_date       date not null,          -- كان **معرّف المستند**
    supervisor        text,

    attendance_in     timestamptz,
    attendance_out    timestamptz,
    -- كان نص واحد "30.123456, 31.234567" -- مش geopoint ولا رقمين
    gps_lat           numeric(10, 6),
    gps_lng           numeric(10, 6),

    daily_completed   text,
    daily_delayed     text,
    daily_plan        text,

    signature_path    text,                   -- كان base64 PNG (وأحيانًا نص 'null' حرفيًا)
    updated_at        timestamptz,

    unique (project_id, report_date)
);

-- 🔴 handover كانت خريطة مستويين: {item_id: {check_index: bool}}
--    والمفاتيح **متفرقة** -- الخطوة اللي اتلمست بس بتظهر.
--
--    والأخطر: نصوص الخطوات موجودة **بس** في سورس تطبيق المشرف
--    (site.html)، و addSubStep/deleteStep بيعيدوا ترقيم القيم المخزّنة
--    في مكانها. يعني `check_index` مالوش معنى من غير نسخة site.html
--    اللي كتبته. عشان كده بنـ denormalize نص الخطوة والمرجع هنا --
--    من غيرهم البيانات دي بتبقى غير قابلة للقراءة بعد أول تعديل.
create table public.site_report_handover (
    id            bigint generated always as identity primary key,
    site_report_id uuid not null references public.site_reports(id) on delete cascade,
    item_id       text not null,            -- item1..item12
    check_index   integer not null,
    checked       boolean not null,
    step_text     text,                     -- منقول وقت الهجرة من site.html
    step_ref      text,                     -- مرجع الكود المصري للبناء
    unique (site_report_id, item_id, check_index)
);

create table public.site_report_images (
    id             bigint generated always as identity primary key,
    site_report_id uuid not null references public.site_reports(id) on delete cascade,
    position       integer not null,
    storage_path   text not null,           -- دي كانت روابط Storage أصلاً (مش base64)
    unique (site_report_id, position)
);


-- ============================================================
-- 6. أوامر الشراء -- projects/{code}/purchases/{autoId}
-- ============================================================
create table public.purchases (
    id                    uuid primary key default gen_random_uuid(),
    firestore_id          text unique,
    project_id            text not null references public.projects(id) on delete cascade,

    supervisor            text,
    supervisor_email      text,
    phase                 text,
    notes                 text,
    required_by           date,
    status                text not null default 'pending',
    source                text,                  -- 'ocr' | 'manual'
    raw_image_path        text,

    total_cost            numeric(14, 2) not null default 0,   -- عمرها ما اتحدّثت بعد الإنشاء
    supplier              text,                                -- محدش بيملاها
    advance_amount        numeric(14, 2),
    advance_sent_at       timestamptz,
    approved_by           text,
    approved_at           timestamptz,
    rejected_at           timestamptz,
    actual_spent          numeric(14, 2),
    receipts_submitted_at timestamptz,
    settled_at            timestamptz,

    requested_at          timestamptz,

    constraint purchases_status_valid check (status in
        ('pending', 'advance_sent', 'receipts_submitted', 'settled', 'rejected')),
    constraint purchases_phase_valid
        check (phase is null or phase in ('foundation', 'finish', 'final'))
);

-- الاستعلامات الأصلية كانت collectionGroup مرتبة بـ requestedAt، وكمان
-- (phase == x AND status == 'settled') -- الفهرسين دول بيقابلوهم
create index purchases_requested_idx on public.purchases (requested_at desc);
create index purchases_phase_status_idx on public.purchases (project_id, phase, status);

-- رصيد العهدة = advance_amount - actual_spent

create table public.purchase_items (
    id           bigint generated always as identity primary key,
    purchase_id  uuid not null references public.purchases(id) on delete cascade,
    position     integer not null,
    name         text not null default '',      -- ملحوظة: name/quantity هنا،
    quantity     numeric(14, 3),                --  بينما desc/qty في التقديرات
    unit         text,
    unique (purchase_id, position)
);

create table public.purchase_receipt_images (
    id           bigint generated always as identity primary key,
    purchase_id  uuid not null references public.purchases(id) on delete cascade,
    position     integer not null,
    storage_path text not null,
    unique (purchase_id, position)
);


-- ============================================================
-- 7. bahrSites -- آدم هو الكاتب الوحيد
-- ============================================================
-- الفرونت **مابيلمسهاش خالص**. تبويب "المواقع" في Bahr OS هو عرض على
-- مجموعة projects، مش مجموعة منفصلة.
create table public.bahr_sites (
    id                  text primary key,            -- SITE-XXXXXXXX
    project_id          text references public.projects(id) on delete set null,
    name                text,
    allowed_supervisors text[] not null default '{}',
    status              text not null default 'نشط',
    created_at          timestamptz
);

-- ⚠️ آدم بيقرا client و area من هنا و**محدش بيكتبهم أبدًا** -- كل موقع
--    بيرجع "" للاتنين. مش أعمدة ناقصة: القارئ غلط. الإصلاح إما join
--    على projects عبر project_id، أو نشيلهم من القارئ.
-- ⚠️ items هنا وهمي برضه -- آدم بيكتبه [] ومحدش بيملاه.


-- ============================================================
-- 8. عضوية المستخدمين في المشاريع -- users/{uid}.projects[]
-- ============================================================
create table public.user_projects (
    user_id    text not null,
    project_id text not null,
    primary key (user_id, project_id)
);
-- كانت مصفوفة بتتدار بـ arrayUnion/arrayRemove ومحدش بيقراها -- يعني
-- على الأغلب مش متسقة مع الواقع أصلاً. تتهاجر كأرشيف وتتراجع بعدين.


-- ============================================================
-- 9. التنبيهات -- notifications
-- ============================================================
create table public.notifications (
    id           uuid primary key default gen_random_uuid(),
    firestore_id text unique,
    project_id   text,
    kind         text not null default 'purchase_request',
    message      text,
    purchase_id  text,
    target_role  text not null default 'admin',
    read         boolean not null default false,
    created_at   timestamptz
);
create index notifications_unread_idx on public.notifications (target_role, read, created_at desc);
-- بتتكتب ومحدش بيقراها ولا بيعلّمها مقروءة -- read دايمًا false، ونمو بلا حدود.


commit;


-- ============================================================
-- قرارات لسه مفتوحة (مش مانعة إنشاء الجداول)
-- ============================================================
-- 1. الفواتير المتأثرة بباگ الـ localStorage: تتهاجر زي ما هي (أمانة
--    تاريخية) ولا تتعلّم needs_review؟ العمود موجود، فالقرار ممكن
--    يتأجل لوقت الاستيراد من غير تعديل schema.
--
-- 2. projects.note (الفرونت) مقابل projects.adam_notes (آدم): ندمجهم
--    في عمود واحد ولا نسيبهم منفصلين؟ الدمج الصامت ممكن يضيّع الأقدم.
--
-- 3. مفتاح ثابت يربط سطر التقدير بعناصر PROJECT_ITEMS: بيصلح هشاشة
--    حقيقية، بس بيغيّر مخرجات الفواتير -- قرار شغل مش schema.
