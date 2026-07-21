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
        from services.loan_service import LoanService
        loan_service = LoanService()
        installments = loan_service.get_month_installments()
        # فلتر الأقساط اللي لسه متدفعتش
        pending = [i for i in installments if not i.get("paid")]
        context["pending_loans"] = pending[:3]  # أول 3 بس
    except Exception as e:
        logger.error(f"❌ Loans error: {e}")
        context["pending_loans"] = []

    # 3. Recent Memory Notes
    try:
        from services.firebase_service import list_memory_notes
        notes = list_memory_notes(str(chat_id), limit=10)
        context["recent_notes"] = notes
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

        weather_text = ctx.get("weather", "")

        prompt = f"""أنت ADAM — دماغ أحمد التاني.

دلوقتي الساعة {now.strftime('%H:%M')} يوم {now.strftime('%A %d/%m/%Y')}.

السياق الحقيقي دلوقتي:
{weather_text}
{deadlines_text}
{loans_text}
{conflicts_text}
{notes_text}
{mood_text}

اكتب رسالة صباحية لأحمد (بحورة) بالعامية المصرية.

القواعد:
- ☀️ ابدأ بترحيب بسيط ومختلف كل يوم
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
        bot.send_message(chat_id, message)
        logger.info("✅ Morning Brief sent")
    except Exception as e:
        logger.error(f"❌ Morning Brief send error: {e}")
