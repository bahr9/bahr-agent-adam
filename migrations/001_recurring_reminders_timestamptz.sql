-- ============================================================
-- 001 -- تحويل أعمدة الوقت في recurring_reminders لـ timestamptz
-- ============================================================
-- التاريخ: 2026-08-05
-- القرار: كل أعمدة الوقت في Supabase تبقى timestamptz من البداية، مش
--         bigint (epoch ms) زي ما الجدول التجريبي اتعمل.
--
-- ليه: timestamptz بيدّي مقارنات وفهارس ودوال تاريخ صح، ومعالجة التوقيت
-- الصيفي مجانًا. والقاهرة بتتنقل بين +02:00 و+03:00، فتخزين الوقت كرقم
-- بيخلي كل حسبة تاريخ في SQL شغل يدوي معرّض للغلط.
--
-- ⚠️ الترتيب مهم -- اقرا القسم اللي تحت قبل ما تشغّل أي حاجة.
--
-- ============================================================
-- الترتيب الآمن للتنفيذ
-- ============================================================
-- 1. انشر الكود الأول (كوميت "Both timestamp shapes...") -- هو بيقرا
--    ويكتب الشكلين الاتنين، فبيشتغل قبل التحويل وبعده من غير أي فرق.
-- 2. شغّل الملف ده من Supabase SQL Editor.
-- 3. شغّل استعلام التحقق في الآخر وتأكد من النتيجة.
--
-- لو عكست الترتيب (حوّلت قبل ما تنشر)، التذكيرات المتكررة هتقف لحد ما
-- الكود ينزل -- لأن الكود القديم بيكتب رقم في عمود بقى timestamptz.
--
-- ============================================================


-- ------------------------------------------------------------
-- قبل التحويل: شوف اللي هيتغير
-- ------------------------------------------------------------
select
    id,
    text,
    created_at                              as created_at_raw,
    to_timestamp(created_at / 1000.0)       as created_at_after,
    last_sent                               as last_sent_raw,
    case when last_sent is null then null
         else to_timestamp(last_sent / 1000.0) end
                                            as last_sent_after
from public.recurring_reminders
order by created_at;


-- ------------------------------------------------------------
-- التحويل نفسه
-- ------------------------------------------------------------
-- to_timestamp بياخد ثواني، والقيم متخزنة بالميلي -- القسمة على 1000.0
-- (بعشرية عشان مانفقدش الكسور).
--
-- النتيجة بتترجع بتوقيت UTC داخليًا -- ودي الطريقة الصح: timestamptz
-- بيخزن لحظة مطلقة، والعرض بيتحوّل لتوقيت العميل وقت القراءة.

begin;

-- تصحيح 2026-08-05 مساءً (خطأ 42804 ظهر عند التنفيذ الفعلي): العمود
-- القديم عليه DEFAULT رقمي (epoch)، وPostgres مش بيعرف يحوّل الـ default
-- تلقائيًا مع تغيير النوع. لازم الـ default يتشال الأول، بعدين التحويل،
-- بعدين default جديد مناسب للنوع الجديد.
alter table public.recurring_reminders
    alter column created_at drop default;
alter table public.recurring_reminders
    alter column last_sent drop default;

alter table public.recurring_reminders
    alter column created_at type timestamptz
        using to_timestamp(created_at / 1000.0),

    alter column last_sent type timestamptz
        using case when last_sent is null
                   then null
                   else to_timestamp(last_sent / 1000.0)
              end;

-- الصفوف الجديدة تاخد وقتها من قاعدة البيانات بدل ما التطبيق يحسبه
alter table public.recurring_reminders
    alter column created_at set default now();

commit;


-- ------------------------------------------------------------
-- التحقق -- شغّله بعد التحويل
-- ------------------------------------------------------------
-- المتوقع: النوع timestamptz، وعدد الصفوف زي ما هو، ومفيش تاريخ
-- خرج عن نطاق معقول (يعني القسمة على 1000 اتعملت صح).

select
    column_name,
    data_type,
    column_default
from information_schema.columns
where table_schema = 'public'
  and table_name   = 'recurring_reminders'
  and column_name in ('created_at', 'last_sent')
order by column_name;

select
    count(*)                                             as total_rows,
    count(created_at)                                    as with_created_at,
    min(created_at)                                      as oldest,
    max(created_at)                                      as newest,
    count(*) filter (where created_at < '2020-01-01')    as suspiciously_old,
    count(*) filter (where created_at > now() + interval '1 day')
                                                         as suspiciously_future
from public.recurring_reminders;

-- suspiciously_old و suspiciously_future المفروض يكونوا **صفر**.
-- لو طلعوا أكبر من صفر، يبقى القسمة على 1000 مكانتش صح لبعض الصفوف
-- (يعني كان فيه قيم متخزنة بالثواني مش بالميلي) -- وقف واسأل.
