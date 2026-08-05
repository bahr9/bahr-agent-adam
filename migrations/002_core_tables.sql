-- ============================================================
-- 002 -- الجداول الأساسية في Supabase
-- ============================================================
-- التاريخ: 2026-08-05
-- الحالة: 🟡 للمراجعة -- متشغلش قبل ما التصدير الكامل يتأكد
--
-- المستبعَد من الملف ده عن قصد: projects و bahrSites -- دول بيتكتبوا من
-- فرونت Bahr OS، وشكل items/deductionRates/finaldata لسه بيتفحص. هييجوا
-- في 003 بعد ما نعرف شكلهم بالظبط.
--
-- ============================================================
-- القواعد المطبّقة في كل جدول هنا
-- ============================================================
-- 1. كل عمود وقت = timestamptz. مفيش epoch ولا نصوص تواريخ.
-- 2. كل جدول فيه firestore_id (عمود الجسر) -- بيربط الصف بالمستند الأصلي،
--    وبيخلي الـ dual-write والتحقق بعد الهجرة ممكنين.
-- 3. الأعمدة المشتقة اللي كانت موجودة عشان قيود فهرسة Firestore بتتشال
--    (entity_key, type_attribute_key) -- الفهارس المركّبة بتغني عنها.
-- 4. الأسماء العربية بتتحوّل لإنجليزي مع توثيق الأصل.
-- 5. NULL هو التمثيل الوحيد للغياب -- مش "" ومش 0.
-- ============================================================

begin;

create extension if not exists pgcrypto;   -- gen_random_uuid()


-- ============================================================
-- 1. adam_events -- سجل الأحداث (أهم جدول)
-- ============================================================
create table public.adam_events (
    id              uuid primary key default gen_random_uuid(),
    firestore_id    text unique,
    event_id        uuid not null unique,

    entity_type     text not null,
    entity_id       text not null,
    attribute       text not null,

    -- متعدد الأنواع بالتصميم: bool | str | dict | list | null
    previous_value  jsonb,
    new_value       jsonb,

    source          text not null default 'unknown',
    actor           text not null default '',
    chat_id         text,                       -- كان int أو str
    raw_context     jsonb not null default '{}',
    metadata        jsonb not null default '{}',

    occurred_at     timestamptz not null
);

-- بيحلّوا محل entity_key و type_attribute_key المشتقين
create index adam_events_entity_idx
    on public.adam_events (entity_type, entity_id, occurred_at desc);
create index adam_events_type_attribute_idx
    on public.adam_events (entity_type, attribute, occurred_at desc);

comment on table public.adam_events is
    'سجل أحداث append-only. القاعدة: مفيش تعبير عن حالة من غير حدث يدعمه.';
comment on column public.adam_events.firestore_id is
    'معرّف المستند الأصلي في Firestore -- عمود جسر للهجرة والتحقق';


-- ============================================================
-- 2. memory_notes -- أكبر مجموعة، وأهم تطبيع
-- ============================================================
-- المواعيد كانت متخزنة **جوه النص** بصيغة "[Deadline: YYYY-MM-DD]"
-- وبتتستخرج بـ regex. دلوقتي بقى ليها عمود حقيقي.
create table public.memory_notes (
    id                uuid primary key default gen_random_uuid(),
    firestore_id      text unique,

    user_id           text not null,
    text              text not null,          -- بعد شيل لاحقة الـ Deadline
    deadline          date,                   -- ← اتطلع من جوه النص
    category          text,                   -- كان "" -> بقى NULL
    related_to        text,                   -- كان "" -> بقى NULL
    status            text not null default 'active',   -- الغياب كان معناه active
    urgent_alert_sent boolean not null default false,

    created_at        timestamptz not null,
    updated_at        timestamptz,

    constraint memory_notes_status_valid
        check (status in ('active', 'outdated', 'cancelled'))
);

create index memory_notes_user_idx
    on public.memory_notes (user_id, created_at desc);
create index memory_notes_deadline_idx
    on public.memory_notes (deadline) where deadline is not null;
create index memory_notes_category_idx
    on public.memory_notes (user_id, category) where category is not null;

-- timestamp_str اتشال: نسخة تانية زايدة من نفس اللحظة، وبتوقيت السيرفر
-- (UTC) مش القاهرة -- يعني كانت بتختلف عن created_at بساعتين/تلاتة.


-- ============================================================
-- 3. conversation_messages -- من مصفوفة متداخلة لجدول ابن
-- ============================================================
-- كان: مستند واحد لكل مستخدم فيه messages: list، بيتقص لـ 100 لما يوصل 200
-- (إعادة كتابة المصفوفة كلها + سباق ArrayUnion).
create table public.conversation_messages (
    id             bigint generated always as identity primary key,
    user_id        text not null,
    user_text      text not null,
    assistant_text text not null,
    occurred_at    timestamptz not null
);

create index conversation_messages_user_idx
    on public.conversation_messages (user_id, occurred_at desc);

-- القص بقى سياسة احتفاظ (delete ... where) مش إعادة كتابة عند كل رسالة.


-- ============================================================
-- 4. loan_installment_status -- من خريطة في مستند لصفوف
-- ============================================================
-- كان: مستند واحد "paid_status" فيه paid: {"valu_0": true, ...}
create table public.loan_installment_status (
    identity_key      text primary key,         -- "{program_id}_{index}"
    program_id        text not null,
    installment_index integer not null,
    paid              boolean not null,
    updated_at        timestamptz not null default now()
);

-- ⚠️ لازم يتحافظ عليه في طبقة الوصول: التفرقة بين
--    (أ) قراءة ناجحة وفيها بيانات
--    (ب) قراءة ناجحة ومفيش صفوف
--    (ج) **فشل قراءة**
-- الحالة (ج) لازم ترمي، متترجمش لـ "صفر مدفوع". ده اتصلح في أوديت
-- 2026-08-05 وهو اللي بيمنع الملخص يقول لأحمد إنه مدين بشهور دفعها.


-- ============================================================
-- 5. project_files + الحقائق
-- ============================================================
create table public.project_files (
    id            uuid primary key default gen_random_uuid(),
    firestore_id  text unique,
    display_name  text not null,
    created_at    timestamptz not null,
    updated_at    timestamptz
);

create unique index project_files_display_name_idx
    on public.project_files (lower(display_name));

create table public.project_file_facts (
    id               bigint generated always as identity primary key,
    project_file_id  uuid not null
        references public.project_files(id) on delete cascade,
    category         text not null,
    key              text not null,
    value            text not null,
    source           text not null default 'ahmed',
    -- NULL معناه "مش محسوبة" -- **مش صفر**. الكود بيفرّق بينهم صراحة.
    computed_area_m2 double precision,
    updated_at       timestamptz not null,

    unique (project_file_id, category, key),
    constraint project_file_facts_category_valid
        check (category in ('فراغات', 'أبعاد', 'قرارات', 'ميزانية', 'عميل', 'ملاحظات'))
);


-- ============================================================
-- 6. price_base -- السعر بقى رقم
-- ============================================================
-- كان str(price).strip() -- رقم متخزن كنص.
-- ⚠️ قبل الاستيراد: لازم كل القيم الموجودة تتفحص إنها بتتحوّل لرقم.
--    أي قيمة مش قابلة للتحويل توقف الاستيراد، متتحوّلش لـ NULL بصمت.
create table public.price_base (
    id            uuid primary key default gen_random_uuid(),
    firestore_id  text unique,
    item          text not null,
    normalized    text not null,          -- كان جزء من الـ doc id (sha1)
    price         numeric(14, 2) not null,
    unit          text,
    note          text,
    source        text not null default 'ahmed',
    updated_at    timestamptz not null
);

create unique index price_base_normalized_idx on public.price_base (normalized);

-- التاريخ كان مصفوفة جوه المستند -> بقى جدول
create table public.price_base_history (
    id            bigint generated always as identity primary key,
    price_base_id uuid not null references public.price_base(id) on delete cascade,
    price         numeric(14, 2),         -- nullable: سجلات قديمة قيمتها ""
    recorded_at   timestamptz             -- nullable: كانت "" في أول تحديث
);

create index price_base_history_item_idx
    on public.price_base_history (price_base_id, recorded_at desc);


-- ============================================================
-- 7. expenses -- مع تصحيح انحراف الوقت
-- ============================================================
-- ⚠️ الحقل date كان datetime.now() (توقيت الحاوية = UTC) مش now_cairo().
--    يعني كل المصاريف اللي اتسجلت بين 21:00 و23:59 بتوقيت القاهرة
--    اتسجلت على اليوم اللي فات.
--    الاستيراد لازم يضيف إزاحة القاهرة (+2 شتاءً / +3 صيفًا حسب تاريخ
--    الصف نفسه) -- مش إزاحة ثابتة.
create table public.expenses (
    id            uuid primary key default gen_random_uuid(),
    firestore_id  text unique,
    amount        numeric(14, 2) not null,
    category      text not null,
    description   text,                   -- كان "" -> NULL
    project       text,                   -- كان None بالفعل
    occurred_at   timestamptz not null,   -- كان "date" النص الساذج، مصحّح
    created_at    timestamptz not null
);

create index expenses_created_idx on public.expenses (created_at desc);
create index expenses_occurred_idx on public.expenses (occurred_at desc);
create index expenses_category_idx on public.expenses (category);
create index expenses_project_idx on public.expenses (project) where project is not null;

-- تنبيه المصاريف الشهري كان بيقارن date.startswith("YYYY-MM").
-- دلوقتي: where date_trunc('month', occurred_at) = date_trunc('month', now())


-- ============================================================
-- 8. decision_ledger
-- ============================================================
create table public.decision_ledger (
    id            uuid primary key default gen_random_uuid(),
    firestore_id  text unique,
    decision      text not null,
    project       text,                   -- كان "" -> NULL (توحيد مع expenses)
    status        text not null,
    reason        text,
    source        text not null default 'conversation',
    occurred_at   timestamptz not null,   -- كان "date" الساذج، مصحّح
    created_at    timestamptz not null,

    constraint decision_ledger_status_valid
        check (status in ('accepted', 'rejected', 'pending'))
);

create index decision_ledger_created_idx on public.decision_ledger (created_at desc);
create index decision_ledger_project_idx on public.decision_ledger (project) where project is not null;
create index decision_ledger_status_idx on public.decision_ledger (status);

-- كان بيجيب 20 صف الأول وبعدين يفلتر project/status في بايثون -- يعني
-- الفلترة كانت بترجع أقل من المطلوب. دلوقتي WHERE قبل LIMIT.


-- ============================================================
-- 9. reminders
-- ============================================================
create table public.reminders (
    id            uuid primary key default gen_random_uuid(),
    firestore_id  text unique,
    user_id       text not null,          -- كان int في مسار و str في التاني
    text          text not null,
    send_at       timestamptz not null,
    sent          boolean not null default false,
    kind          text,                   -- كان "type"، وموجود بس في تذكير المواعيد
    created_at    timestamptz not null
);

create index reminders_pending_idx on public.reminders (sent, send_at);
create index reminders_send_at_idx on public.reminders (send_at);


-- ============================================================
-- 10. personal_tasks + ideas -- الأسماء العربية اتحوّلت
-- ============================================================
-- كان: "نص" و "تم" -- أسماء أعمدة عربية محتاجة اقتباس في كل استعلام.
create table public.personal_tasks (
    id            uuid primary key default gen_random_uuid(),
    firestore_id  text unique,
    text          text not null,          -- كان "نص"
    done          boolean not null default false,   -- كان "تم"
    created_at    timestamptz not null
);
create index personal_tasks_open_idx on public.personal_tasks (done, created_at);

create table public.ideas (
    id            uuid primary key default gen_random_uuid(),
    firestore_id  text unique,
    text          text not null,          -- كان "نص"
    created_at    timestamptz not null
);
create index ideas_created_idx on public.ideas (created_at desc);


-- ============================================================
-- 11. client_followups
-- ============================================================
create table public.client_followups (
    id                  uuid primary key default gen_random_uuid(),
    firestore_id        text unique,        -- فيه مستند شبح معروف اسمه "محمد علي"
    client_id           text,
    name                text,
    phone               text,
    kind                text default 'lead',      -- كان "type"
    status              text default 'interested',
    last_contact_date   date,
    last_contact_method text,
    last_reply          text,
    next_followup_date  date,               -- تاريخ مجرد، مش لحظة زمنية
    project_id          text,
    notes               text,
    created_at          timestamptz,        -- nullable: مستندات التحديث-فقط مالهاش
    updated_at          timestamptz
);

create index client_followups_status_idx on public.client_followups (status);
create index client_followups_next_idx
    on public.client_followups (next_followup_date) where next_followup_date is not null;


-- ============================================================
-- 12. agent_tasks
-- ============================================================
create table public.agent_tasks (
    id                 uuid primary key default gen_random_uuid(),
    firestore_id       text unique,
    task_id            text not null unique,
    source             text not null default 'ADAM',
    target             text not null,
    action             text not null,
    payload            jsonb not null default '{}',
    status             text not null default 'pending',
    result             jsonb,
    reported_to_ahmed  boolean not null default false,
    created_at         timestamptz not null,
    updated_at         timestamptz not null,

    constraint agent_tasks_status_valid
        check (status in ('pending', 'in_progress', 'done', 'failed'))
);

create index agent_tasks_queue_idx on public.agent_tasks (target, status, created_at desc);

-- كان .limit(500) وكل الفلترة والترتيب في بايثون على نص ISO.


-- ============================================================
-- 13. ain_al_khabeer_logs
-- ============================================================
create table public.ain_al_khabeer_logs (
    id            uuid primary key default gen_random_uuid(),
    firestore_id  text unique,
    question      text not null default '',
    answer        text not null default '',
    client        text,
    source        text not null default 'whatsapp',
    occurred_at   timestamptz not null
);
create index ain_al_khabeer_logs_time_idx on public.ain_al_khabeer_logs (occurred_at desc);


-- ============================================================
-- 14. bahr_graph_nodes
-- ============================================================
create table public.bahr_graph_nodes (
    id            uuid primary key default gen_random_uuid(),
    firestore_id  text unique,            -- الشكل القديم: bot-{slug}-{epoch}
    label         text not null,
    category      text not null,
    facts         text[] not null default '{}',
    links         text[] not null default '{}',
    size          integer not null default 16,   -- تلميح عرض للفرونت
    deleted       boolean not null default false,
    updated_at    timestamptz not null,

    constraint bahr_graph_nodes_category_valid check (category in
        ('project','team','task','issue','topic','hub','client','site','office'))
);
create index bahr_graph_nodes_live_idx on public.bahr_graph_nodes (deleted, label);


-- ============================================================
-- 15. الذاكرة والنموذج البشري -- صف واحد لكل واحد
-- ============================================================
create table public.user_memory (
    user_id     text primary key,
    summary     text not null default '',
    updated_at  timestamptz not null
);

-- المفاتيح مفتوحة: update_human_model(key, value) بيقبل أي مفتاح، فمفيش
-- مجموعة أعمدة مقفولة ممكن تتحدد من الكود.
create table public.human_model (
    user_key    text primary key,          -- "ahmed_gowaida"
    data        jsonb not null default '{}',
    created_at  timestamptz not null,
    updated_at  timestamptz
);


-- ============================================================
-- 16. system_flags -> اتفكّت لتلاتة
-- ============================================================
-- المجموعة القديمة كانت فيها تلات أشكال مستندات مالهمش أي علاقة،
-- متفرقين بنمط المعرّف بس.

create table public.app_settings (
    key         text primary key,
    value       jsonb not null,
    updated_at  timestamptz not null default now()
);
-- بيستوعب: chat_id، وعدّاد learning_fallback

-- كان monthly_alert_{YYYY-MM} -- الشهر كان متخزن في **معرّف المستند**
create table public.monthly_alerts_sent (
    month     date primary key,           -- أول يوم في الشهر
    total     numeric(14, 2) not null,
    sent_at   timestamptz not null default now()
);


-- ============================================================
-- 17. صحة الأدوات والتشخيص
-- ============================================================
create table public.tool_health_checks (
    id                       uuid primary key default gen_random_uuid(),
    firestore_id             text unique,
    tool_name                text not null,
    checked_at               timestamptz not null,
    result                   text not null,
    latency_ms               integer,
    error_type               text,        -- NULL عند النجاح
    sanitized_error_summary  text,        -- NULL عند النجاح
    probe_version            text not null default 'v1',
    evidence_event_id        uuid,        -- -> adam_events.event_id

    constraint tool_health_checks_result_valid
        check (result in ('success', 'failure', 'timeout'))
);
create index tool_health_checks_window_idx on public.tool_health_checks (checked_at desc);
create index tool_health_checks_tool_idx on public.tool_health_checks (tool_name, checked_at desc);

create table public.tool_failures_log (
    id                       uuid primary key default gen_random_uuid(),
    firestore_id             text unique,
    tool_name                text not null,
    failed_at                timestamptz not null,
    execution_source         text not null default 'real_use',
    error_type               text,
    sanitized_error_summary  text,
    latency_ms               integer,
    chat_id_present          boolean not null default false,   -- عمدًا مش الـ chat_id نفسه
    evidence_event_id        uuid
);
create index tool_failures_log_window_idx on public.tool_failures_log (failed_at desc);
create index tool_failures_log_tool_idx on public.tool_failures_log (tool_name, failed_at desc);

-- ⚠️ الجدولين دول بيكبروا بلا حدود ومفيش job تنظيف. دي كانت سبب استهلاك
--    53 ألف قراءة في يوم واحد على Firestore. لازم سياسة احتفاظ من أول يوم.

create table public.tool_health_alert_state (
    tool_name        text primary key,
    last_status      text not null,
    last_cause       text,
    last_alerted_at  timestamptz not null,
    last_alert_kind  text not null
);
-- ⚠️ الدلالة: "آخر حالة **اتبعت عنها تنبيه فعلاً**"، مش آخر حالة اترصدت.
--    الكتابة ممنوعة عند القمع بالـ cooldown أو عند فشل الإرسال.

create table public.project_status_alert_state (
    project_id       text primary key,
    last_status      text not null,
    last_alerted_at  timestamptz not null,
    last_alert_kind  text not null
);
-- نفس الدلالة بالظبط.


-- ============================================================
-- 18. الحالة الذاتية وأثر التعبير
-- ============================================================
create table public.decision_engine_state (
    key          text primary key default 'singleton',
    last_levels  jsonb not null default '{}',
    updated_at   timestamptz not null default now()
);

-- محدش بيقراهم في الإنتاج، بس دول أثر الدليل اللي الدستور قايم عليه:
-- "مفيش تعبير عن حالة من غير دليل قابل للرصد". حذفهم بيشيل خاصية أمان
-- مقصودة، فبيتهاجروا.
create table public.state_snapshots (
    id           uuid primary key default gen_random_uuid(),
    firestore_id text unique,
    state_id     uuid not null unique,
    computed_at  timestamptz not null,
    dimensions   jsonb not null default '{}'
);

create table public.expressions (
    id             uuid primary key default gen_random_uuid(),
    firestore_id   text unique,
    expression_id  uuid not null unique,
    state_id       uuid references public.state_snapshots(state_id),
    dimension      text not null,
    level          text not null,
    mode           text not null,
    template_key   text,
    rendered_text  text not null,
    verified       boolean not null,
    sent_at        timestamptz not null,
    chat_id        text,

    -- القيد ده كان ضمني في الكود: المفتاح بيبقى NULL بالظبط لما verified=false
    constraint expressions_template_key_matches_verified
        check ((verified and template_key is not null)
            or (not verified and template_key is null))
);
create index expressions_sent_idx on public.expressions (sent_at desc);


-- ============================================================
-- 19. eye_expert_config -- مع تاريخ إصدارات
-- ============================================================
-- الكتابة القديمة كانت .set() بلا merge -- استبدال كامل، **صفر تاريخ**.
-- (وعشان كده فيه نسخ .txt يدوية في الريبو.)
create table public.eye_expert_prompt (
    id          bigint generated always as identity primary key,
    content     text not null,
    updated_at  timestamptz not null default now(),
    updated_by  text not null default 'adam'
);
create index eye_expert_prompt_latest_idx on public.eye_expert_prompt (updated_at desc);
-- أحدث صف = البرومبت الحالي. كل تعديل بيضيف صف، فالرجوع لنسخة قديمة ممكن.


commit;


-- ============================================================
-- المتبقي في 003 (متوقف على فحص فرونت Bahr OS)
-- ============================================================
--   projects   -- items[] و deductionRates و finaldata
--   bahrSites  -- هل client و area موجودين فعلاً؟
--
-- المجموعات الميتة (clients, office_tasks, site_projects,
-- recurring_tasks) **مالهاش جداول** عن قصد -- بتتصدّر للأرشيف بس.
