-- ============================================================
-- 017 — مسار كتابة الحصر
-- ============================================================
-- التاريخ: 2026-08-10
--
-- حاجتين:
--
-- ## 1. عمود is_sub
-- بنود المقايسة ليها `is_sub`، وبنود الحصر لأ -- والفرونت بيحفظ
-- `sub` للاتنين (`row.dataset.sub === '1'`). فأي بند فرعي في الحصر
-- كان هيتنقل ويفقد إنه فرعي في صمت.
--
-- الجدول نسي العمود، مش الفرونت اللي زوّده. والصمت هنا هو الخطر:
-- البند بيتنقل وبيتعدّ صح، وبيفقد علاقته باللي فوقه من غير ما
-- أي عدّاد يزعق -- نفس نمط الترتيب اللي اتحرس عليه في النقل.
--
-- ## 2. دالة الاستبدال
-- نفس منطق `replace_phase_items` (ميجريشن 016): الحفظ بيحصل مع كل
-- ضغطة زرار، والاستبدال لازم يبقى معاملة واحدة وإلا قطع نت في النص
-- بيسيب الحصر فاضي.
--
-- ⚠️ اللي مش هنا بالقصد: الصور. دلوقتي base64 جوه المستند، ومكانها
--    `project_quantity_item_images` بمسار في تخزين الكائنات. رفعها
--    شغلانة لوحدها -- والحصر بيتنقل من غيرها، وده مقصود مش نسيان.

begin;

alter table public.project_quantity_items
    add column if not exists is_sub boolean not null default false;

comment on column public.project_quantity_items.is_sub is
    'البند تابع للي فوقه. اتضاف 2026-08-10 لما مسار الكتابة اتوصّل '
    'ولقى الفرونت بيحفظ الخاصية دي والجدول مش شايلها.';


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

    -- الأبعاد بتتنقل زي ما هي. الوحدة هي اللي بتحدد أنهي بُعد له معنى،
    -- والحساب مكانه وقت العرض مش وقت التخزين.
    insert into public.project_quantity_items
        (quantity_id, position, description, unit,
         length, width, height, count, wastage_pct, phase, is_sub)
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
        nullif(item->>'phase', ''),          -- '' معناها "متجمّعش في مرحلة"
        coalesce((item->>'is_sub')::boolean, false)
    from jsonb_array_elements(coalesce(p_items, '[]'::jsonb)) as item;

    get diagnostics v_count = row_count;
    return v_count;
end;
$$;

commit;


-- ============================================================
-- التأكد بعد التشغيل
-- ============================================================
--   select proname, prosecdef as is_definer
--     from pg_proc
--    where proname in ('replace_phase_items', 'replace_quantity_items');
--
-- صفّين، والاتنين is_definer = false.
-- ============================================================
