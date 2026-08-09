-- 007: ربط البريف بمشروع BAHR OS
--
-- المشروع بيتولد في BAHR OS وبس (قرار أحمد 2026-08-09: "even if I ask adam
-- to start a project, he must start from BAHR OS"). آدم **مش كاتب موازي** --
-- هو الجسر، لأنه الوحيد اللي شايف Supabase و Firestore مع بعض.
--
-- العمود بيشيل معرّف Firestore زي ما هو (PRJ-MRE9OHLK / PRJ-260805-K3F /
-- PRJ-A3F91B2C) -- نص حر، **ممنوع أي parser يفترض شكل واحد** (نفس تحذير 003).
-- مفيش foreign key: الجدول المشار إليه في داتابيز تانية أصلًا.

alter table client_briefs add column if not exists project_id text;

-- الربط بيتعمل على مستوى الجلسة (كل لقطات البريف الواحد)، فالفهرس عليها.
create index if not exists client_briefs_project_idx
    on client_briefs (project_id) where project_id is not null;
