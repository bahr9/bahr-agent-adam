-- ============================================================
-- 016 — استبدال بنود المرحلة في معاملة واحدة
-- ============================================================
-- التاريخ: 2026-08-10
--
-- ## المشكلة
-- BAHR OS بيحفظ المقايسة مع كل ضغطة زرار. في Firestore دي كتابة
-- مستند واحد. في Postgres المقابل هو «امسح بنود المرحلة وادخلهم
-- من تاني» -- وده عبر REST بيبقى طلبين منفصلين.
--
-- ولو الإدخال وقع بعد ما المسح نجح، **المرحلة تفضل فاضية**.
-- ستة وخمسين بند يروحوا لأن النت قطع في نص عمليتين.
--
-- ## الحل
-- دالة واحدة: بتعمل الـupsert للمرحلة، تمسح بنودها، وتدخل الجداد --
-- كله جوه معاملة واحدة. إما تنجح كلها أو مايحصلش حاجة.
--
-- ## ليه الترتيب مبيتحسبش هنا
-- `position` بييجي من المنادي زي ما هو، لأنه **حامل معنى التبعية**:
-- البند الفرعي بيتبع اللي قبله بترتيبه مش بمفتاح. إعادة ترقيمه في
-- القاعدة معناها إن هرم المقايسة يتحدد في مكانين.
--
-- ## الأمان
-- `security invoker` بالقصد: الدالة بتشتغل بصلاحية اللي نادى عليها،
-- فسياسات RLS بتفضل شغالة. لو اتعملت `security definer` كانت هتبقى
-- باب خلفي حوالين الحماية اللي اتعملت في 014.

begin;

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
        (estimate_id, position, description, unit, qty, price, is_sub)
    select
        v_estimate_id,
        (item->>'position')::integer,
        coalesce(item->>'description', ''),
        item->>'unit',
        coalesce((item->>'qty')::numeric, 0),
        coalesce((item->>'price')::numeric, 0),
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
-- لازم ترجّع صف واحد:
--
--   select proname, prosecdef as is_definer
--     from pg_proc
--    where proname = 'replace_phase_items';
--
-- is_definer لازم تكون false. لو true، الدالة بتتخطى RLS -- وده باب
-- خلفي حوالين حماية 014 ولازم يتصلح قبل أي استخدام.
-- ============================================================
