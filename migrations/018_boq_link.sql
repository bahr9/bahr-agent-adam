-- ============================================================
-- 018 — ربط بند المقايسة بسطر الحصر
-- ============================================================
-- التاريخ: 2026-08-11
--
-- قرار أحمد: «أملا بنود الحصر، ثم تلقائيًا ألاقي المقايسات اتملت».
--
-- ## ليه كود نصي مش مفتاح أجنبي
--
-- `replace_phase_items` و`replace_quantity_items` **بيمسحوا كل الصفوف
-- ويكتبوها من أول** مع كل حفظ (دي طريقتهم عشان الاستبدال يبقى معاملة
-- واحدة -- ميجريشن 016 و017). يعني:
--
--   • الـ`id` بيتولد جديد كل حفظة  -> مفتاح أجنبي بيتكسر فورًا
--   • الـ`position` بيتغير لما تضيف بند
--   • الوصف الحر بيتغير لما تتعدّل الصياغة
--
-- فالربط لازم يبقى على حاجة **المستخدم بيحددها وبتتنقل مع الصف في كل
-- كتابة**. الكود بيتبعت في الـpayload زي أي عمود تاني، فبيعيش.
--
-- وأحمد بيفكر بالأكواد دي أصلاً: ملفات حصره اسمها `plaster` و`painting`
-- و`concrete` و`cove for light`.
--
-- ## العلاقة واحد-لكتير بالقصد
--
-- القياس الواحد بيغذّي أكتر من بند. من داتا روك إيدن:
--   مساحة أرضيات الريسبشن 90.59
--     ├─ تركيب بورسيلين الريسبشن  90.59 × 150   (مصنعية)
--     └─ توريد بورسيلين هندى       90    × 395   (خامة)
--
-- عشان كده الكود على سطر الحصر، والبنود بتشاور عليه -- مش العكس.
--
-- ## اللي الميجريشن دي **مابتعملهوش**
--
-- مابتحركش ولا رقم. الربط بيتعمل من الشاشة بند بند، ولو الكميتين
-- مختلفين الشاشة بتقف وتسأل. مقايسات روك إيدن معتمدة، ومحدش يلمسها
-- من غير ما أحمد يقول.

begin;

-- كود سطر الحصر. فاضي = سطر مالوش كود لسه (والبنود مش بتشاور عليه).
alter table public.project_quantity_items
    add column if not exists code text;

comment on column public.project_quantity_items.code is
    'كود قصير ثابت للسطر (plaster · painting …). بند المقايسة بيشاور '
    'عليه في `source_code`. نصي مش مفتاح أجنبي لأن الصفوف بتتمسح '
    'وتتكتب مع كل حفظ، فالـid مابيعيشش.';

-- من مين البند بياخد كميته. NULL = مالوش مصدر (فاتورة/مقطوعية/مشتريات).
alter table public.project_phase_items
    add column if not exists source_code text;

comment on column public.project_phase_items.source_code is
    'كود سطر الحصر اللي الكمية جاية منه. NULL = البند مالوش قياس '
    '(فاتورة أو مقطوعية أو مشتريات) وكميته بتتكتب بالإيد.';

-- بحث سريع: «البنود اللي بتاخد من الكود ده»
create index if not exists project_phase_items_source_code_idx
    on public.project_phase_items (source_code)
    where source_code is not null;


-- ============================================================
-- الدالتين لازم ينقلوا العمودين
-- ============================================================
-- ⚠️ لولا كده، أول حفظ بعد الميجريشن بيمسح كل الأكواد والروابط في
--    صمت -- لأن الاستبدال بيكتب الأعمدة اللي في الطلب بس.

create or replace function public.replace_phase_items(
    p_project_id   text,
    p_phase        text,
    p_client_text  text,
    p_project_text text,
    p_area_text    text,
    p_items        jsonb
)
returns bigint
language plpgsql
security invoker
as $$
declare
    v_estimate_id uuid;
    v_count       bigint;
begin
    if p_phase not in ('foundation', 'finish', 'final') then
        raise exception 'مرحلة مش معروفة: %', p_phase;
    end if;

    insert into public.project_phase_estimates
        (project_id, phase, client_text, project_text, area_text)
    values
        (p_project_id, p_phase, p_client_text, p_project_text, p_area_text)
    on conflict (project_id, phase) do update
        set client_text  = excluded.client_text,
            project_text = excluded.project_text,
            area_text    = excluded.area_text
    returning id into v_estimate_id;

    delete from public.project_phase_items where estimate_id = v_estimate_id;

    insert into public.project_phase_items
        (estimate_id, position, description, unit, qty, price, is_sub, source_code)
    select
        v_estimate_id,
        (item->>'position')::integer,
        coalesce(item->>'description', ''),
        item->>'unit',
        coalesce((item->>'qty')::numeric, 0),
        coalesce((item->>'price')::numeric, 0),
        coalesce((item->>'is_sub')::boolean, false),
        nullif(item->>'source_code', '')
    from jsonb_array_elements(coalesce(p_items, '[]'::jsonb)) as item;

    get diagnostics v_count = row_count;
    return v_count;
end;
$$;


create or replace function public.replace_quantity_items(
    p_project_id   text,
    p_client_text  text,
    p_project_text text,
    p_area_text    text,
    p_items        jsonb
)
returns bigint
language plpgsql
security invoker
as $$
declare
    v_quantity_id uuid;
    v_count       bigint;
begin
    insert into public.project_quantity
        (project_id, client_text, project_text, area_text)
    values
        (p_project_id, p_client_text, p_project_text, p_area_text)
    on conflict (project_id) do update
        set client_text  = excluded.client_text,
            project_text = excluded.project_text,
            area_text    = excluded.area_text
    returning id into v_quantity_id;

    delete from public.project_quantity_items where quantity_id = v_quantity_id;

    insert into public.project_quantity_items
        (quantity_id, position, description, unit,
         length, width, height, count, wastage_pct, phase, is_sub, code)
    select
        v_quantity_id,
        (item->>'position')::integer,
        coalesce(item->>'description', ''),
        item->>'unit',
        coalesce((item->>'length')::numeric, 0),
        coalesce((item->>'width')::numeric, 0),
        coalesce((item->>'height')::numeric, 0),
        coalesce((item->>'count')::numeric, 1),
        coalesce((item->>'wastage_pct')::numeric, 0),
        nullif(item->>'phase', ''),
        coalesce((item->>'is_sub')::boolean, false),
        nullif(item->>'code', '')
    from jsonb_array_elements(coalesce(p_items, '[]'::jsonb)) as item;

    get diagnostics v_count = row_count;
    return v_count;
end;
$$;

commit;


-- ============================================================
-- التأكد بعد التشغيل
-- ============================================================
-- ١. العمودين موجودين:
--
--   select table_name, column_name
--     from information_schema.columns
--    where (table_name = 'project_quantity_items' and column_name = 'code')
--       or (table_name = 'project_phase_items'    and column_name = 'source_code');
--
--   لازم صفّين.
--
-- ٢. الدالتين بينقلوا العمودين (الفحص الحقيقي -- الوجود مش كفاية):
--
--   select replace_phase_items('PRJ-TEST','foundation','','','',
--     '[{"position":0,"description":"ت","unit":"م²","qty":1,"price":2,
--        "is_sub":false,"source_code":"plaster"}]'::jsonb);
--   select source_code from project_phase_items
--     where estimate_id = (select id from project_phase_estimates
--                           where project_id='PRJ-TEST');
--   -- لازم ترجّع 'plaster'. لو رجّعت NULL، الدالة اتشغّلت بالنسخة القديمة.
--   delete from project_phase_estimates where project_id = 'PRJ-TEST';
-- ============================================================
