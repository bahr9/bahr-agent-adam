# -*- coding: utf-8 -*-
"""
🌅 ADAM Morning Brief
=====================================================
ADAM يبادر كل يوم الساعة 8.

المبدأ:
- مفيش قوالب ثابتة
- ADAM يفكر ويصيغ بناءً على اللي شايفه فعلاً
- بيراقب ويلاحظ من تلقاء نفسه
"""

from utils.logger import logger
from utils.time_utils import now_cairo

# التصنيفات اللي تستاهل تتقال في بداية يوم شغل (قرار أحمد 2026-08-08).
#
# «مشروع» **مستبعد عن قصد** رغم إن اسمه يوحي بالعكس: جرد الـ183 ملاحظة لقى
# 146 منهم مصنّفين «مشروع» و**كلهم عن بناء آدم ومداد وهوب** -- «مراجعة
# تصميم Truth→Meaning»، «تنظيف طابور مداد»، «ADR 0002»، «مشكلة /start في
# تيليجرام». الخانة دي بقت بحكم الأمر الواقع سلة ملاحظات النظام، فأحمد كان
# بيفتح يومه على تفاصيل تنفيذ داخلية بدل عميل أو مشروع.
#
# ده مش حكم على المحتوى -- الملاحظات دي بتتسجل وبتترد لما تتطلب. الحكم على
# «هل ده مناسب لبداية يوم شغل».
#
# ملحوظة صادقة: «مالي» نفسها مخلوطة (قاعدة التسعير 20% وحد المصاريف الشهري
# شغل حقيقي، وتقارير صحة الأدوات مش). مفيش فصل مثالي في البيانات الحالية،
# والنسبة هنا أحسن بكتير من صفر مفيد من 146.
BRIEF_NOTE_CATEGORIES = ("عميل", "مالي", "شخصي")


def build_morning_context(chat_id: str) -> dict:
    """
    جمع السياق اللي ADAM محتاجه للـ Morning Brief.
    بيجيب المعلومات الحقيقية من Firebase.
    """
    context = {}

    # 1. Upcoming Deadlines
    try:
        from services.firebase_service import get_upcoming_deadlines
        deadlines_data = get_upcoming_deadlines(str(chat_id), days_ahead=14)
        context["deadlines"] = deadlines_data.get("deadlines", [])
        context["conflicts"] = deadlines_data.get("conflicts", [])
    except Exception as e:
        logger.error(f"❌ Deadlines error: {e}")
        context["deadlines"] = []
        context["conflicts"] = []

    # 2. Upcoming Loans
    try:
        from services.loan_service import get_month_installments, get_current_month_key, get_overdue_installments
        month_key = get_current_month_key()
        installments, total = get_month_installments(month_key)
        pending = [i for i in installments if not i.get("paid")]
        context["pending_loans"] = pending[:3]  # أول 3 بس
    except Exception as e:
        logger.error(f"❌ Loans error: {e}")
        context["pending_loans"] = []

    # 2b. Overdue Loans (من الشهر إلي فات، لسه مدفوعتش)
    try:
        from services.loan_service import get_overdue_installments
        overdue, overdue_total, overdue_month_key = get_overdue_installments()
        context["overdue_loans"] = overdue[:3]
        context["overdue_month_key"] = overdue_month_key
    except Exception as e:
        logger.error(f"❌ Overdue loans error: {e}")
        context["overdue_loans"] = []
        context["overdue_month_key"] = ""

    # 3. Recent Memory Notes
    try:
        from services.firebase_service import list_memory_notes
        notes = list_memory_notes(str(chat_id), limit=30)
        # الفلترة هنا مش عند العرض: لو اتفلترت بعدين، الـlimit بياخد
        # آخر 10 (وكلهم غالبًا ملاحظات نظام) ويرجّع صفر ملاحظة شغل.
        context["recent_notes"] = [
            n for n in notes
            if (n or {}).get("category") in BRIEF_NOTE_CATEGORIES
        ]
    except Exception as e:
        logger.error(f"❌ Notes error: {e}")
        context["recent_notes"] = []

    # 4. Human Model
    try:
        from services.firebase_service import get_human_model
        human = get_human_model()
        context["human"] = human
    except Exception as e:
        context["human"] = {}

    # 5. Bahr OS Projects
    try:
        from services.firebase_service import get_bahr_projects
        projects = get_bahr_projects(limit=5)
        context["projects"] = projects
    except Exception as e:
        context["projects"] = []

    # 5b. خيط الانتباه -- إيه المفتوح، من إمتى، وآدم قال عنه إيه (2026-08-08)
    #
    # الفجوة اللي ده بيسدها: آدم بنى حواس كاملة الأسبوع اللي فات (خيط
    # الانتباه، حلقة المبادرة، محرك الحالة) وكلهم اتوصلوا **كأدوات** --
    # يعني بيقولهم لما أحمد يسأل، ومبيقولهمش لما هو يبادر. والبريف هو
    # اللحظة الوحيدة اللي آدم بيتكلم فيها من نفسه كل يوم، وكان بيعدي
    # عليهم كلهم: بيبعت مواعيد وأقساط وطقس، وبيسيب بره إن فيه شغل
    # اتبعت لمداد من يوم ومحدش خده، والتزامات قالها من ٦ أيام ومحصلش رد.
    #
    # الاعتماد على إن الموديل ينده الأداة بنفسه هو نفس الفخ اللي النظام
    # كله اتبنى عشان يتفاداه -- فالخيط بيدخل السياق مضمون، مش اختياري.
    try:
        from services import attention_thread
        context["attention"] = attention_thread.describe_open_threads()
    except Exception as e:
        logger.warning("⚠️ خيط الانتباه فشل -- البريف هيكمّل من غيره: " + str(e)[:80])
        context["attention"] = ""

    # 6. Weather
    try:
        from weather_service import get_weather_for_morning_brief
        context["weather"] = get_weather_for_morning_brief()
    except Exception as e:
        context["weather"] = ""

    # 7. Mood History
    try:
        from services.firebase_service import get_mood_history
        context["mood"] = get_mood_history(str(chat_id), days=7)
    except Exception as e:
        context["mood"] = {"needs_attention": False}

    return context


def generate_morning_brief(chat_id: str) -> str:
    """
    توليد رسالة الصبح.
    ADAM يفكر ويكتب بناءً على السياق الحقيقي.
    """
    try:
        from services.claude_service import ask_claude_agentic
        from services.memory_service import get_memory

        # جمع السياق
        ctx = build_morning_context(chat_id)
        memory_summary = get_memory(chat_id)
        now = now_cairo()

        # بناء الـ prompt
        deadlines_text = ""
        if ctx["deadlines"]:
            lines = []
            for d in ctx["deadlines"][:3]:
                urgent = "🔴 عاجل" if d.get("urgent") else "🟡"
                lines.append(f"  {urgent} {d['text']} — بعد {d['days_remaining']} يوم ({d['deadline']})")
            deadlines_text = "Deadlines قريبة:\n" + "\n".join(lines)

        loans_text = ""
        if ctx["pending_loans"]:
            lines = [f"  - {l.get('program', '')}: {l.get('amount', '')} جنيه" for l in ctx["pending_loans"]]
            loans_text = "أقساط مستحقة:\n" + "\n".join(lines)

        overdue_text = ""
        if ctx.get("overdue_loans"):
            lines = [f"  - {l.get('program', '')}: {l.get('amount', '')} جنيه" for l in ctx["overdue_loans"]]
            overdue_text = f"⚠️ أقساط متأخرة من {ctx.get('overdue_month_key', 'الشهر إلي فات')} لسه مدفوعتش:\n" + "\n".join(lines)

        conflicts_text = ""
        if ctx["conflicts"]:
            conflicts_text = f"⚠️ تعارض مواعيد: {len(ctx['conflicts'])} حالة"

        notes_text = ""
        if ctx["recent_notes"]:
            recent = ctx["recent_notes"][:3]
            notes_text = "آخر الملاحظات:\n" + "\n".join([f"  - {n['text'][:60]}" for n in recent])

        mood_text = ""
        mood_data = ctx.get("mood", {})
        if mood_data.get("needs_attention"):
            mood_text = f"⚠️ تنبيه مزاج: أحمد عنده {mood_data['negative_count']} حالات سلبية في الأسبوع الأخير — ذكره بدفء إنه يهتم بنفسه"

        # المشاريع كانت بتتجاب وتتحط في السياق و**مبتوصلش للبرومبت أبدًا**
        # (2026-08-08): السطور اللي بتنده get_bahr_projects كانت المرة الوحيدة
        # اللي كلمة projects بتظهر فيها في الملف. يعني آدم كان ماسك كل صبح
        # مشروع عصام فرج وحالته "delayed" وبيرمي المعلومة قبل ما يكتب حرف.
        # مش قسم فاضي -- قسم بيتجاب ويتزقّ.
        projects_text = ""
        active = [p for p in (ctx.get("projects") or []) if p.get("client")]
        if active:
            lines = []
            for p in active[:4]:
                bits = [str(p.get("client"))]
                if p.get("area"):
                    bits.append(str(p["area"]) + " م²")
                status = str(p.get("status") or "").strip()
                if status:
                    bits.append("⚠️ " + status if status == "delayed" else status)
                lines.append("  - " + " · ".join(bits))
            projects_text = "مشاريع بحر الشغالة:\n" + "\n".join(lines)

        weather_text = ctx.get("weather", "")

        attention_text = ""
        raw_attention = (ctx.get("attention") or "").strip()
        if raw_attention and "مفيش حاجة مفتوحة" not in raw_attention:
            attention_text = (
                "🧵 مفتوح عندك دلوقتي (كل مدة هنا محسوبة من تاريخ مخزّن، "
                "مش تقدير -- انقلها زي ما هي وممنوع تقرّبها أو تزوّدها):\n"
                + raw_attention
            )

        prompt = f"""أنت ADAM — دماغ أحمد التاني.

دلوقتي الساعة {now.strftime('%H:%M')} يوم {now.strftime('%A %d/%m/%Y')}.

السياق الحقيقي دلوقتي:
{attention_text}
{projects_text}
{weather_text}
{deadlines_text}
{overdue_text}
{loans_text}
{conflicts_text}
{notes_text}
{mood_text}

اكتب رسالة صباحية لأحمد (بحورة) بالعامية المصرية.

القواعد:
- ☀️ ابدأ بترحيب بسيط ومختلف كل يوم
- 🧵 **لو فيه حاجة في "مفتوح عندك دلوقتي" — دي أهم حاجة في الرسالة ولازم تتقال.** ده اللي بيفرّق بين إنك بتبلّغ وإنك بتتابع. وبالذات اللي مكتوب عنه "قلت عنها من كذا يوم ومحصلش رد" — قوله بصراحة إنك فاتحه معاه قبل كده ومردش عليك؛ ده كلام فرد أسرة مش تقرير. وأي حاجة "بعتها ومحدش خدها" معناها إن نظام تاني (مداد/عين الخبير) واقف مستني قرار منه.
- ⚡️ لو فيه حاجة عاجلة — حطها الأول بوضوح
- 📌 اذكر أقرب حاجة أو اتنين بس (مش كل القايمة)
- 💰 لو فيه قسط قريب — اذكره، غير كده تجاهله
- 🧠 لو لاحظت حاجة مهمة — قولها بشكل طبيعي
- 🗣️ خاتمة حرة تختلف كل يوم حسب الموقف
- مفيش قوالب ثابتة — فكر وصُغ من جديد
- الرسالة قصيرة ومركزة — مش أكتر من 10 سطور"""

        reply = ask_claude_agentic(
            prompt,
            chat_id,
            conversation_history=[],
            memory_summary=memory_summary
        )

        return reply

    except Exception as e:
        logger.error(f"❌ Morning Brief generation error: {e}")
        now = now_cairo()
        return f"🌅 صباح الخير يا بحورة! ({now.strftime('%H:%M')})"


def send_morning_brief(bot, chat_id: int):
    """إرسال Morning Brief"""
    try:
        message = generate_morning_brief(str(chat_id))
        from services import verified_expression
        message = verified_expression.verify_and_finalize(chat_id, message)
        bot.send_message(chat_id, message)
        logger.info("✅ Morning Brief sent")
    except Exception as e:
        logger.error(f"❌ Morning Brief send error: {e}")
