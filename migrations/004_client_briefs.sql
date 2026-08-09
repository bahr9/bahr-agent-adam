-- 004: استبيان العميل (brief.html) → صندوق بريد write-only
-- الصفحة العامة بتكتب بالـ anon key، ومفيش أي policy قراءة للـ anon:
-- يعني حتى لو المفتاح اتشاف في السورس، أقصى حاجة حد يعملها إنه يبعت استبيان.
-- القراءة من جانب آدم بالـ secret key (بيتخطى RLS).

create table if not exists client_briefs (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    session_id uuid,                     -- جلسة العميل: كل اللقطات بتاعته بنفس القيمة
    is_final boolean not null default false,  -- false = لقطة مرحلية (أوتوسيف)، true = دوس إرسال
    client_name text,
    phone text,
    unit_location text,
    answers jsonb not null,
    source text not null default 'brief.html',
    status text not null default 'new'   -- new → seen → linked_to_project
);

-- لو الجدول اتعمل قبل اللقطات المرحلية: الأعمدة الجديدة تتضاف بأمان
alter table client_briefs add column if not exists session_id uuid;
alter table client_briefs add column if not exists is_final boolean not null default false;

-- القراءة من جانب آدم: أحدث لقطة لكل جلسة
-- select distinct on (session_id) * from client_briefs order by session_id, created_at desc;
create index if not exists client_briefs_session_idx on client_briefs (session_id, created_at desc);

alter table client_briefs enable row level security;

-- إدخال بس للـ anon. مفيش select/update/delete policies = مقفولين بالـ RLS.
drop policy if exists "anon insert briefs" on client_briefs;
create policy "anon insert briefs"
    on client_briefs for insert
    to anon
    with check (true);
