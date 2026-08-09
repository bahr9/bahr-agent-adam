-- 011: الاتجاه المحسوب متخزن على البريف
--
-- الاتجاه بيتحسب في بايثون بقواعد التوقيع (direction_service). كتابته تاني
-- بجافاسكريبت عشان الصفحة تعرضه = محركين للقواعد بيتفرّعوا عن بعض، وهي
-- بالظبط المشكلة اللي القوانين بتحاربها.
--
-- فآدم بيحسب ويخزّن، والصفحة بتقرا وتعرض. مصدر واحد.

alter table client_briefs add column if not exists direction jsonb;
alter table client_briefs add column if not exists direction_at timestamptz;
