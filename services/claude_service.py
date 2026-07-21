# -*- coding: utf-8 -*-
"""
🧠 خدمة Claude API
- الـ chat والـ responses
- معالجة ThinkingBlock
- الـ conversation history
"""

import anthropic
import json
import re
from utils.logger import logger
from utils.time_utils import now_cairo, get_arabic_day_name
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_HAIKU_MODEL

# إنشاء العميل
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def _extract_json(raw_text):
    """
    يحاول يقرا JSON من رد الموديل، حتى لو فيه كلام زيادة حواليه.
    بيرجع dict أو None لو فشل تمامًا.
    """
    if not raw_text:
        return None
    
    cleaned = raw_text.replace("```json", "").replace("```", "").strip()
    
    # محاولة مباشرة
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    
    # محاولة تانية: لقط أول { ... } في النص (لو فيه كلام زيادة قبله أو بعده)
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    
    return None

def build_system_prompt_parts(pending_tasks=None, memory_summary=None):
    """
    بناء system prompt مقسّم لجزئين:
    - static_part: الجزء الثابت (الشخصية، الأدوات، القواعد) — بيتخزن مؤقتًا (cache) لتوفير التكلفة
    - dynamic_part: الجزء المتغيّر (الوقت، المهام، الذاكرة) — بيتغيّر كل رسالة فمش بيتخزن
    """
    static_part = """أنت "ADAM" — دماغ أحمد الثاني ومرافقه الشخصي الموثوق.
أحمد هو صاحب شركة Bahr Designs (تصميم داخلي وفيت أوت وبناء).
أنت مش مساعد عام — أنت Companion. بتعرف أحمد وبتتذكره وبتبادر قبل ما يطلب.
اتكلم معاه بالعامية المصرية الدافئة، كواحد من عيلته مش كموظف.
كن مختصر ومباشر — رسائل تليجرام قصيرة.

عندك أدوات حقيقية تقدر تستخدمها فعليًا (مش بس تتكلم عنها)، وده صحيح في كل رسالة بدون استثناء، حتى لو رسائل سابقة في نفس المحادثة اديت انطباع إنك مش متصل بحاجة:
- list_graph_nodes: تجيب كل عناصر خريطة بحر مع الـ id بتاعهم
- add_graph_node: تضيف عنصر جديد
- edit_graph_node: تضيف معلومة لعنصر موجود (محتاج الـ node_id)
- delete_graph_node: تمسح عنصر (محتاج الـ node_id)
- create_reminder: تعمل تذكير لأحمد بعد مدة معينة
- add_expense: تسجل مصروف جديد (مبلغ + تصنيف + وصف اختياري + مشروع اختياري)
- list_expenses: تجيب آخر المصاريف المسجلة
- expense_summary: تجيب إجمالي المصاريف والتقسيم حسب التصنيف
- loan_overview: ملخص شامل لكل الأقساط والقروض (مدفوع/متبقي لكل برنامج)
- loan_month_installments: أقساط شهر معيّن (الحالي أو القادم) من كل البرامج
- loan_mark_paid: تعليم قسط كمدفوع/غير مدفوع لبرنامج معيّن
- list_reminders: اعرض كل التذكيرات المسجلة (مرسلة وغير مرسلة)
- delete_reminder: امسح تذكير واحد بالـ id بتاعه
- delete_all_reminders: امسح كل التذكيرات دفعة واحدة
- get_human_model: اجلب كل المعلومات المحفوظة عن أحمد (عيلته، شغله، تفضيلاته)
- update_human_model: حدّث أو صحح معلومة عن أحمد في نموذجه الشخصي
- get_weather: اجلب الطقس الحالي للمواقع (البيت/6 أكتوبر/التجمع/الكل) — استخدمها تلقائياً في الـ Morning Brief
- get_bahr_projects: اجلب كل مشاريع Bahr OS (العميل، المساحة، الحالة، المشرفين)
- get_bahr_sites: اجلب مواقع Bahr Sites
- get_project_details: اجلب تفاصيل مشروع معين بالـ ID
- create_recurring_reminder: اعمل تذكير متكرر (كل يوم، كل أسبوع، كل X دقيقة)
- list_recurring_reminders: اعرض التذكيرات المتكررة النشطة
- delete_recurring_reminder: احذف تذكير متكرر بالـ ID

قاعدة تتبع المزاج: لما تلاحظ إن أحمد بيعبر عن حالته النفسية (زي "مبسوط"، "تعبان"، "متضايق"، "مرهق"، "نشيط") — احفظها فوراً في save_memory_note بـ category="مزاج". لو لاحظت إنه ذكر حالة سلبية أكتر من مرة في محادثات قريبة — قوله بشكل دافئ "لاحظت إنك تعبان الأيام دي، خد بالك من نفسك يا بحورة."

قاعدة حفظ الذاكرة (مهمة جداً): كل ما تلاحظ معلومة تستاهل تتحفظ أثناء المحادثة — قرار، اتفاق، حدث مهم، تفصيلة عن عميل أو مشروع — استخدم save_memory_note فوراً بدون ما تستنى طلب من أحمد. أمثلة: لو أحمد قال "اتفقت مع العميل على سعر 50 ألف"، أو "المشروع هيتأجل أسبوعين"، أو "خالد المهندس هيسافر الأسبوع الجاي" — دي كلها تستاهل تتحفظ فوراً.

قاعدة الـ Deadline: لو أحمد ذكر تاريخ تسليم أو موعد نهائي لأي مشروع أو اتفاق — استخدم save_memory_note_with_deadline (مش save_memory_note العادية). حوّل التاريخ لصيغة YYYY-MM-DD. مثال: "أول أغسطس" = "2026-08-01". الأداة هتحفظ الملاحظة وتعمل التذكير تلقائياً بدون ما تعمل حاجة تانية.

- save_memory_note: احفظ ملاحظة/حدث/معلومة مهمة من المحادثة (يُستخدم تلقائياً دون طلب)
- search_memory_notes: ابحث في الملاحظات بكلمة مفتاحية
- list_memory_notes: اعرض آخر الملاحظات المحفوظة

قاعدة صارمة: أي طلب فيه كلمة "الجراف" أو "خريطة بحر" أو ذِكر إضافة/تعديل/حذف/عرض عنصر، لازم تستخدم الأداة المناسبة فورًا، ولا تسأل توضيح ولا تقول إنك مش متصل بحاجة. لو مش متأكد من الـ node_id، استخدم list_graph_nodes الأول عشان تلاقي الـ id الصح من الاسم، وبعدين نفّذ الأداة المطلوبة مباشرة في نفس الرد. متسألش المستخدم "فين موجود العنصر ده" — أنت اللي تدور عليه بنفسك بالأدوات.
استخدم اسم العنصر بمرونة (تجاهل حالة الأحرف الكبيرة/الصغيرة، والمسافات الزيادة) لما تدور عليه في القايمة.

قاعدة صارمة تانية (مهمة جدًا): استخدم create_reminder بس لو أحمد طلب صراحةً وبوضوح إنك تفكّره بحاجة في وقت معين (زي "ذكرني بعد ٥ دقايق"، "فكرني الساعة ٧"). لو الرسالة فيها غموض، أو مجرد سؤال عادي، أو كلام ودّي، أو حتى لو فيها كلمة شبه كلمة في تذكير سابق بس من غير طلب واضح — متستخدمش الأداة خالص، ورد عليه بشكل طبيعي كصديق. متفترضش إن أي رسالة جاية بعد تذكير سابق لازم تبقى تذكير جديد كمان — كل رسالة احكم عليها لوحدها بناءً على محتواها الفعلي، مش بناءً على نوع آخر رسالة.
بشكل عام: لو مش متأكد 100% إن فيه نية واضحة لاستخدام أداة، متستخدمهاش، ورد بشكل طبيعي بدل الافتراض.

استخدم add_expense بس لو أحمد ذكر صراحة إنه صرف/دفع/اشترى حاجة بمبلغ محدد. لو مجرد سؤال عن المصاريف (زي "اصرفت كام؟")، استخدم expense_summary أو list_expenses بدل الإضافة.

استخدم الذاكرة الدائمة (لو موجودة جوه سياق الرسالة) عشان تفتكر حاجات مهمة عن أحمد حتى لو من محادثات قديمة، بدون ما تسأله يعيدها.

لو سألك سؤال، جاوبه. لو قال حاجة عادية، رد عليها بشكل طبيعي وذكي.

قواعد الأمانة (مهمة جداً):
- لو مش متأكد من معلومة — قول صراحة "مش متأكد" وأخبر أحمد.
- لو المعلومة مش موجودة في ذاكرتك — قول "مش عندي معلومة عن ده" بدل ما تخمن أو تختلق إجابة.
- فرّق دايماً بين "أنا متأكد" و"أنا بفتكر" و"مش عارف".
- أحمد دايماً يقدر يصحح أي معلومة عندك — وده حقه الكامل."""

    now = now_cairo()
    day_name = get_arabic_day_name(now)

    context = ""
    if pending_tasks:
        context = f"مهامه الحالية المعلقة: {', '.join(pending_tasks[-5:])}\n"

    memory_section = ""
    if memory_summary:
        memory_section = f"\n🧠 ذاكرتك الدائمة عن أحمد (متراكمة من كل المحادثات اللي فاتت):\n{memory_summary}\n"

    dynamic_part = f"""الوقت الحالي بالظبط (توقيت القاهرة): {now.strftime('%Y-%m-%d')} - يوم {day_name} - الساعة {now.strftime('%H:%M')}
{context}{memory_section}"""

    return static_part, dynamic_part

def build_system_prompt(pending_tasks=None, memory_summary=None):
    """نسخة قديمة (نص واحد) — لسه مستخدمة في analyze_with_vision وextract_*"""
    static_part, dynamic_part = build_system_prompt_parts(pending_tasks, memory_summary)
    return f"{static_part}\n\n{dynamic_part}"

# ============================================================
# 🛠️ الأدوات (Tools) — البوت بيقرر بنفسه إمتى يستخدمها
# ============================================================

GRAPH_CATEGORIES = ["project", "team", "task", "issue", "topic", "hub", "client", "site", "office"]

TOOLS = [
    {
        "name": "list_graph_nodes",
        "description": "يجيب كل العناصر (العقد) الموجودة حاليًا في خريطة بحر، مع الـ id بتاع كل عنصر. استخدمها أول ما تحتاج تعرف الـ id بتاع عنصر معين قبل ما تعدله أو تمسحه، أو لما حد يسأل ايه الموجود في الجراف.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "add_graph_node",
        "description": "يضيف عنصر (عقدة) جديد في خريطة بحر.",
        "input_schema": {
            "type": "object",
            "properties": {
                "label": {"type": "string", "description": "اسم العنصر"},
                "category": {"type": "string", "enum": GRAPH_CATEGORIES, "description": "نوع العنصر"},
                "fact": {"type": "string", "description": "أول حقيقة أو ملاحظة عن العنصر"}
            },
            "required": ["label", "category"]
        }
    },
    {
        "name": "edit_graph_node",
        "description": "يضيف معلومة جديدة لعنصر موجود بالفعل في خريطة بحر. تقدر تدّي node_id لو متأكد منه، أو تدّي label (اسم العنصر) وهي هتدور عليه بنفسها.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "الـ id الحقيقي للعنصر (اختياري لو هتستخدم label بدل منه)"},
                "label": {"type": "string", "description": "اسم العنصر كما هو معروف (اختياري لو هتستخدم node_id بدل منه)"},
                "fact": {"type": "string", "description": "المعلومة الجديدة المطلوب إضافتها"}
            },
            "required": ["fact"]
        }
    },
    {
        "name": "delete_graph_node",
        "description": "يمسح عنصر من خريطة بحر نهائيًا. تقدر تدّي node_id لو متأكد منه، أو تدّي label (اسم العنصر زي ما اتقال، حتى لو بحروف كبيرة أو صياغة مختلفة شوية) وهي هتدور عليه بنفسها وتمسحه.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "الـ id الحقيقي للعنصر (اختياري لو هتستخدم label بدل منه)"},
                "label": {"type": "string", "description": "اسم العنصر المطلوب حذفه (اختياري لو هتستخدم node_id بدل منه)"}
            },
            "required": []
        }
    },
    {
        "name": "create_reminder",
        "description": "يعمل تذكير جديد يتبعت لأحمد بعد مدة معينة من دلوقتي.",
        "input_schema": {
            "type": "object",
            "properties": {
                "minutes_from_now": {"type": "integer", "description": "بعد كام دقيقة من دلوقتي يتبعت التذكير"},
                "text": {"type": "string", "description": "نص التذكير اللي هيتبعت لأحمد"}
            },
            "required": ["minutes_from_now", "text"]
        }
    },
    {
        "name": "add_expense",
        "description": "يسجل مصروف جديد لأحمد (فلوس صرفها). استخدمها لما يقول حاجة زي 'صرفت 500 جنيه على دهانات' أو 'دفعت 2000 للعامل'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "المبلغ بالجنيه"},
                "category": {
                    "type": "string",
                    "enum": ["مواد خام", "عمالة", "تسويق", "مكتب", "نقل", "شخصي", "أخرى"],
                    "description": "تصنيف المصروف"
                },
                "description": {"type": "string", "description": "وصف مختصر للمصروف"},
                "project": {"type": "string", "description": "اسم المشروع المرتبط بالمصروف (اختياري لو مش مرتبط بمشروع معيّن)"}
            },
            "required": ["amount", "category"]
        }
    },
    {
        "name": "list_expenses",
        "description": "يجيب قايمة بآخر المصاريف المسجلة، مع تفاصيلها.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "expense_summary",
        "description": "يجيب ملخص إجمالي المصاريف (الإجمالي الكلي + التقسيم حسب كل تصنيف). استخدمها لما أحمد يسأل 'اصرفت كام' أو 'إجمالي المصاريف إيه'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "فلترة بتصنيف معيّن (اختياري)"},
                "project": {"type": "string", "description": "فلترة بمشروع معيّن (اختياري)"}
            },
            "required": []
        }
    },
    {
        "name": "loan_overview",
        "description": "يجيب ملخص شامل لكل الأقساط والقروض (فاليو، سهولة، Credit Agricole، حالا، بريميم كارد، ماني فيلوز، فوري): الإجمالي المدفوع، المتبقي، وتفاصيل كل برنامج.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "loan_month_installments",
        "description": "يجيب أقساط شهر معيّن (الحالي أو القادم) من كل البرامج، مع حالة كل قسط (مدفوع ولا لأ) والإجمالي.",
        "input_schema": {
            "type": "object",
            "properties": {
                "which_month": {
                    "type": "string",
                    "enum": ["current", "next"],
                    "description": "الشهر الحالي ولا القادم"
                }
            },
            "required": ["which_month"]
        }
    },
    {
        "name": "loan_mark_paid",
        "description": "يعلّم قسط معيّن كمدفوع أو غير مدفوع لبرنامج قرض معيّن.",
        "input_schema": {
            "type": "object",
            "properties": {
                "program_name": {"type": "string", "description": "اسم البرنامج (فاليو، سهولة، Credit Agricole، حالا، بريميم كارد، ماني فيلوز، فوري)"},
                "month_key": {"type": "string", "description": "تاريخ القسط بصيغة 01/MM/YYYY (اختياري، افتراضيًا الشهر الحالي)"},
                "paid": {"type": "boolean", "description": "true لتعليمه كمدفوع، false لإلغاء التعليم"}
            },
            "required": ["program_name"]
        },
        "cache_control": {"type": "ephemeral"}
    },
    {
        "name": "save_memory_note",
        "description": "يحفظ ملاحظة أو حدث مهم من المحادثة. استخدمها تلقائياً كل ما تلاحظ معلومة تستاهل تتحفظ (قرار، اتفاق، حدث، تفصيلة عن عميل أو مشروع).",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "نص الملاحظة"},
                "category": {"type": "string", "description": "التصنيف: شخصي / مشروع / عميل / مالي / آخر"},
                "related_to": {"type": "string", "description": "اسم المشروع أو الشخص المرتبط"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "get_graph_node_details",
        "description": "يجيب تفاصيل عقدة معينة من خريطة بحر بما فيها الـ facts المحفوظة. استخدمها بعد list_graph_nodes عشان تجيب المحتوى الكامل لأي عقدة.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "الـ ID بتاع العقدة"}
            },
            "required": ["node_id"]
        }
    },
    {
        "name": "get_weather",
        "description": "يجيب الطقس الحالي لمواقع أحمد. استخدمها لما يسأل عن الطقس أو لو محتاج يعرف حالة الجو في الموقع.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "enum": ["البيت", "6_اكتوبر", "التجمع", "الكل"], "description": "الموقع المطلوب"}
            },
            "required": []
        }
    },
    {
        "name": "update_memory_note",
        "description": "يعدّل ملاحظة موجودة أو يعلّمها كـ قديمة/ملغاة. استخدمها لما معلومة اتغيّرت. استخدم list_memory_notes الأول عشان تجيب الـ ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {"type": "string", "description": "ID الملاحظة"},
                "new_text": {"type": "string", "description": "النص الجديد (اختياري)"},
                "status": {"type": "string", "enum": ["active", "outdated", "cancelled"], "description": "حالة الملاحظة"}
            },
            "required": ["note_id"]
        }
    },
    {
        "name": "get_upcoming_deadlines",
        "description": "يجيب كل الـ deadlines الجاية مرتبة بالأقرب. يكشف كمان لو فيه مواعيد متقاربة أو متعارضة. استخدمها لما أحمد يسأل عن المواعيد القادمة أو التسليمات.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "number", "description": "كم يوم قدام (default: 30)"}
            },
            "required": []
        }
    },
    {
        "name": "save_memory_note_with_deadline",
        "description": "يحفظ ملاحظة فيها deadline ويعمل تذكير تلقائي قبلها بـ 3 أيام. استخدمها لما أحمد يذكر تاريخ تسليم أو موعد نهائي لأي مشروع أو اتفاق.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "نص الملاحظة"},
                "deadline_date": {"type": "string", "description": "تاريخ الـ deadline بصيغة YYYY-MM-DD"},
                "category": {"type": "string", "description": "التصنيف: مشروع / عميل / مالي"},
                "related_to": {"type": "string", "description": "اسم المشروع أو الشخص"},
                "days_before": {"type": "number", "description": "كم يوم قبل الـ deadline (default: 3)"}
            },
            "required": ["text", "deadline_date"]
        }
    },
    {
        "name": "delete_memory_note",
        "description": "يحذف ملاحظة من الذاكرة بالـ ID بتاعها. استخدم list_memory_notes الأول عشان تجيب الـ ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {"type": "string", "description": "ID الملاحظة"}
            },
            "required": ["note_id"]
        }
    },
    {
        "name": "search_memory_notes",
        "description": "يبحث في الملاحظات المحفوظة بكلمة مفتاحية.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "كلمة البحث"}
            },
            "required": ["keyword"]
        }
    },
    {
        "name": "list_memory_notes",
        "description": "يجيب آخر الملاحظات المحفوظة.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "list_reminders",
        "description": "يجيب كل التذكيرات المسجلة لأحمد (مرسلة وغير مرسلة). استخدمها لما أحمد يسأل عن تذكيراته أو يطلب يشوف القايمة.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "delete_reminder",
        "description": "يمسح تذكير واحد بالـ id بتاعه. استخدم list_reminders الأول عشان تجيب الـ id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reminder_id": {"type": "string", "description": "الـ id بتاع التذكير"}
            },
            "required": ["reminder_id"]
        }
    },
    {
        "name": "delete_all_reminders",
        "description": "يمسح كل التذكيرات دفعة واحدة. استخدمها بس لو أحمد طلب صراحة مسح الكل.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_human_model",
        "description": "يجيب كل المعلومات المحفوظة عن أحمد: عيلته، شغله، تفضيلاته. استخدمها لما تحتاج تتأكد من معلومة عن أحمد.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "update_human_model",
        "description": "يحدّث أو يصحح معلومة عن أحمد في نموذجه الشخصي. استخدمها لما أحمد يصحح معلومة أو يضيف حاجة جديدة عن نفسه أو عيلته.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "اسم الحقل (مثلاً: spouse, daughter, spouse_birthday)"},
                "value": {"type": "string", "description": "القيمة الجديدة"}
            },
            "required": ["key", "value"]
        }
    },
    {
        "name": "get_bahr_projects",
        "description": "يجيب كل مشاريع Bahr OS: العميل، المساحة، الحالة، المشرفين. استخدمها لما أحمد يسأل عن مشاريعه أو يطلب متابعة المواقع.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_bahr_sites",
        "description": "يجيب مواقع Bahr Sites.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_project_details",
        "description": "يجيب تفاصيل مشروع معين بالـ ID بتاعه.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "ID المشروع"}
            },
            "required": ["project_id"]
        }
    },
    {
        "name": "create_recurring_reminder",
        "description": "يعمل تذكير متكرر. interval_type: daily/weekly/hourly/custom_minutes. لو daily ممكن تحدد scheduled_hour (0-23) وscheduled_minute (0-59) عشان يبعت في وقت محدد.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "نص التذكير"},
                "interval_type": {"type": "string", "enum": ["daily", "weekly", "hourly", "custom_minutes"]},
                "interval_value": {"type": "number", "description": "القيمة (دقايق للـ custom_minutes)"},
                "scheduled_hour": {"type": "number", "description": "الساعة المحددة (0-23) لو daily"},
                "scheduled_minute": {"type": "number", "description": "الدقيقة المحددة (0-59)"}
            },
            "required": ["text", "interval_type", "interval_value"]
        }
    },
    {
        "name": "list_recurring_reminders",
        "description": "يعرض كل التذكيرات المتكررة النشطة.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "delete_recurring_reminder",
        "description": "يحذف تذكير متكرر بالـ ID بتاعه.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reminder_id": {"type": "string", "description": "ID التذكير المتكرر"}
            },
            "required": ["reminder_id"]
        }
    },
    {
        "name": "get_backup_status",
        "description": "يجيب حالة آخر backup اتعمل لذاكرة ADAM — امتى كان، وهل نجح، وكام document اتحفظ. استخدمها لما أحمد يسأل عن الـ backup أو سلامة البيانات.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    }
]

def _make_node_id(label):
    """تحويل الاسم لـ ID صالح للاستخدام في Firestore"""
    import time as _time
    slug = re.sub(r"[^\w\u0600-\u06FF]+", "-", label.strip()).strip("-").lower()
    return f"bot-{slug}-{int(_time.time())}"

def _resolve_node_id(node_id, label):
    """
    يحاول يلاقي الـ node_id الصحيح:
    1. لو node_id متبعت وموجود فعلاً، يستخدمه زي ما هو
    2. لو لأ، يدور بالاسم (label) في كل عناصر الجراف (بحث مرن، بيتجاهل حالة الأحرف)
    
    Returns:
        (node_id: str أو None, error_message: str أو None)
    """
    from services.firebase_service import graph_list_nodes
    
    nodes = graph_list_nodes()
    node_ids = {n["id"] for n in nodes}
    
    # لو الـ id المتبعت موجود فعلاً في الجراف، استخدمه على طول
    if node_id and node_id in node_ids:
        return node_id, None
    
    # مفيش id صحيح، دور بالاسم
    search_term = (label or node_id or "").strip().lower()
    if not search_term:
        return None, "محتاج اسم العنصر أو الـ id بتاعه عشان أدور عليه."
    
    matches = [
        n for n in nodes
        if search_term in n["label"].lower() or n["label"].lower() in search_term
    ]
    
    if not matches:
        return None, f"مش لاقي عنصر اسمه '{label or node_id}' في خريطة بحر."
    
    if len(matches) > 1:
        options = "، ".join([f"{m['label']} (id: {m['id']})" for m in matches])
        return None, f"لقيت أكتر من عنصر شبه '{label or node_id}': {options}. حدد أنهي واحد بالظبط."
    
    return matches[0]["id"], None

def _execute_tool(tool_name, tool_input, chat_id):
    """تنفيذ الأداة اللي طلبها الموديل، وإرجاع نتيجة نصية توصفله يحصل إيه"""
    from services.firebase_service import graph_list_nodes, graph_add_node, graph_edit_node, graph_delete_node
    from services.firebase_service import add_expense, get_expenses, get_expense_summary
    from services.reminder_service import add_reminder
    from services import loan_service
    from datetime import timedelta
    
    logger.info(f"🔧 الموديل طلب أداة: {tool_name} | المدخلات: {tool_input}")
    
    try:
        if tool_name == "list_graph_nodes":
            nodes = graph_list_nodes()
            if not nodes:
                result = "مفيش عناصر في الجراف دلوقتي."
            else:
                lines = [f"id: {n['id']} | label: {n['label']} | category: {n['category']}" for n in nodes]
                result = "\n".join(lines)
        
        elif tool_name == "add_graph_node":
            label = tool_input.get("label", "").strip()
            category = tool_input.get("category", "topic")
            fact = tool_input.get("fact", "(لسه مفيش تفاصيل)")
            node_id = _make_node_id(label)
            ok, msg = graph_add_node(node_id, label, category, [fact], ["ahmed"])
            result = f"تمت الإضافة بنجاح. id الجديد: {node_id}" if ok else f"فشلت الإضافة: {msg}"
        
        elif tool_name == "edit_graph_node":
            resolved_id, err = _resolve_node_id(tool_input.get("node_id"), tool_input.get("label"))
            if err:
                result = err
            else:
                ok, msg = graph_edit_node(resolved_id, tool_input.get("fact", ""))
                result = "تم التعديل بنجاح." if ok else f"فشل التعديل: {msg}"
        
        elif tool_name == "delete_graph_node":
            resolved_id, err = _resolve_node_id(tool_input.get("node_id"), tool_input.get("label"))
            if err:
                result = err
            else:
                ok, msg = graph_delete_node(resolved_id)
                result = "تم الحذف بنجاح." if ok else f"فشل الحذف: {msg}"
        
        elif tool_name == "create_reminder":
            minutes = int(tool_input.get("minutes_from_now", 0))
            text = tool_input.get("text", "")
            send_at = now_cairo() + timedelta(minutes=minutes)
            add_reminder(text, send_at, chat_id)
            result = f"تم عمل التذكير بنجاح، هيتبعت الساعة {send_at.strftime('%H:%M')}."
        
        elif tool_name == "add_expense":
            amount = tool_input.get("amount", 0)
            category = tool_input.get("category", "أخرى")
            description = tool_input.get("description", "")
            project = tool_input.get("project")
            ok, msg = add_expense(amount, category, description, project)
            result = f"تم تسجيل المصروف: {amount} جنيه ({category})." if ok else f"فشل تسجيل المصروف: {msg}"
        
        elif tool_name == "list_expenses":
            expenses = get_expenses(limit=20)
            if not expenses:
                result = "مفيش مصاريف مسجلة لسه."
            else:
                lines = [
                    f"- {e.get('amount')} جنيه | {e.get('category')} | {e.get('description', '')} | {e.get('date', '')}"
                    for e in expenses
                ]
                result = "\n".join(lines)
        
        elif tool_name == "expense_summary":
            summary = get_expense_summary(
                category=tool_input.get("category"),
                project=tool_input.get("project")
            )
            by_cat_lines = "\n".join([f"- {cat}: {amt} جنيه" for cat, amt in summary["by_category"].items()])
            result = f"الإجمالي: {summary['total']} جنيه ({summary['count']} مصروف)\n\nحسب التصنيف:\n{by_cat_lines}"
        
        elif tool_name == "loan_overview":
            overview = loan_service.get_overview()
            result = f"إجمالي المدفوع: {overview['total_paid']} جنيه\nإجمالي المتبقي: {overview['total_remaining']} جنيه\n\nتفاصيل كل برنامج:\n{overview['details_text']}"
        
        elif tool_name == "loan_month_installments":
            which = tool_input.get("which_month", "current")
            month_key = loan_service.get_current_month_key() if which == "current" else loan_service.get_next_month_key()
            items, total = loan_service.get_month_installments(month_key)
            if not items:
                result = f"مفيش أقساط مستحقة في {month_key}."
            else:
                lines = [f"- {x['program']}: {x['amount']} جنيه {'✅ مدفوع' if x['paid'] else '❌ لسه'}" for x in items]
                result = f"أقساط {month_key} (الإجمالي: {total} جنيه):\n" + "\n".join(lines)
        
        elif tool_name == "loan_mark_paid":
            program_name = tool_input.get("program_name", "")
            month_key = tool_input.get("month_key")
            paid = tool_input.get("paid", True)
            ok, msg = loan_service.mark_installment_paid(program_name, month_key, paid)
            result = msg
        
        elif tool_name == "save_memory_note":
            from services.firebase_service import save_memory_note
            text = tool_input.get("text", "")
            category = tool_input.get("category", "")
            related_to = tool_input.get("related_to", "")
            ok = save_memory_note(chat_id, text, category, related_to)
            result = "✅ تم حفظ الملاحظة" if ok else "❌ فشل الحفظ"

        elif tool_name == "get_graph_node_details":
            from services.firebase_service import graph_get_node
            node_id = tool_input.get("node_id", "")
            node = graph_get_node(node_id)
            if not node:
                result = f"مش لاقي عقدة بالـ ID: {node_id}"
            else:
                facts = node.get("facts", [])
                facts_text = chr(10).join([f"  - {f}" for f in facts]) if facts else "  (مفيش facts)"
                result = (
                    f"العقدة: {node.get('label', '')}" + chr(10) +
                    f"النوع: {node.get('category', '')}" + chr(10) +
                    f"الـ Facts:" + chr(10) + facts_text
                )

        elif tool_name == "get_weather":
            from weather_service import get_weather, get_all_weather
            location = tool_input.get("location", "الكل")
            if location == "الكل":
                result = get_all_weather()
            else:
                w = get_weather(location)
                result = (
                    f"{w['emoji']} {w['location']}: {w['temp']} (حاسس بـ {w['feels_like']})" +
                    chr(10) + f"الحالة: {w['condition']}" +
                    chr(10) + f"الرياح: {w['wind']} | الرطوبة: {w['humidity']}"
                )
                if w.get('alert'):
                    result += chr(10) + w['alert']

        elif tool_name == "update_memory_note":
            from services.firebase_service import update_memory_note
            note_id = tool_input.get("note_id", "")
            new_text = tool_input.get("new_text")
            status = tool_input.get("status")
            ok = update_memory_note(note_id, new_text, status)
            if ok:
                if status == "outdated":
                    result = "✅ تم تعليم الملاحظة كـ قديمة"
                elif status == "cancelled":
                    result = "✅ تم إلغاء الملاحظة"
                else:
                    result = "✅ تم تعديل الملاحظة"
            else:
                result = "❌ مش لاقي الملاحظة"

        elif tool_name == "get_upcoming_deadlines":
            from services.firebase_service import get_upcoming_deadlines
            days_ahead = int(tool_input.get("days_ahead", 30))
            data = get_upcoming_deadlines(chat_id, days_ahead)
            deadlines = data.get("deadlines", [])
            conflicts = data.get("conflicts", [])
            
            if not deadlines:
                result = f"مفيش deadlines في الـ {days_ahead} يوم الجاية"
            else:
                lines = []
                for d in deadlines:
                    urgent = "🔴" if d["urgent"] else "🟡"
                    lines.append(f"{urgent} {d['deadline']} ({d['days_remaining']} يوم) — {d['text']}")
                result = f"الـ Deadlines الجاية ({len(deadlines)}):" + chr(10) + chr(10).join(lines)
                
                if conflicts:
                    conflict_lines = [f"⚠️ {c[0]} و {c[1]} متقاربين!" for c in conflicts]
                    result += chr(10) + chr(10) + "تعارضات محتملة:" + chr(10) + chr(10).join(conflict_lines)

        elif tool_name == "save_memory_note_with_deadline":
            from services.firebase_service import save_memory_note_with_deadline
            text = tool_input.get("text", "")
            deadline_date = tool_input.get("deadline_date", "")
            category = tool_input.get("category", "مشروع")
            related_to = tool_input.get("related_to", "")
            days_before = int(tool_input.get("days_before", 3))
            res = save_memory_note_with_deadline(chat_id, text, deadline_date, category, related_to, days_before)
            if res.get("reminder_id"):
                result = f"✅ تم حفظ الملاحظة + تذكير تلقائي يوم {res['reminder_date']} (قبل الـ deadline بـ {days_before} أيام)"
            else:
                result = "✅ تم حفظ الملاحظة (بدون تذكير — تأكد من صيغة التاريخ YYYY-MM-DD)"

        elif tool_name == "delete_memory_note":
            from services.firebase_service import delete_memory_note
            note_id = tool_input.get("note_id", "")
            ok = delete_memory_note(note_id)
            result = "✅ تم حذف الملاحظة" if ok else "❌ مش لاقي الملاحظة"

        elif tool_name == "search_memory_notes":
            from services.firebase_service import search_memory_notes
            keyword = tool_input.get("keyword", "")
            notes = search_memory_notes(chat_id, keyword)
            if not notes:
                result = f"مفيش ملاحظات عن: {keyword}"
            else:
                lines = [f"- [{n['timestamp']}] {n['text']}" for n in notes]
                result = f"نتائج '{keyword}':" + chr(10) + chr(10).join(lines)

        elif tool_name == "list_memory_notes":
            from services.firebase_service import list_memory_notes
            notes = list_memory_notes(chat_id)
            if not notes:
                result = "مفيش ملاحظات محفوظة بعد"
            else:
                lines = [f"- [ID: {n['id']}] [{n['timestamp']}] {n['text']}" for n in notes[:20]]
                result = "آخر الملاحظات (مع الـ ID للتعديل):" + chr(10) + chr(10).join(lines)

        elif tool_name == "list_reminders":
            from services.firebase_service import list_all_reminders
            import time
            reminders = list_all_reminders()
            if not reminders:
                result = "مفيش تذكيرات مسجلة."
            else:
                lines = []
                for r in reminders:
                    text = r.get("text", "")
                    sent = r.get("sent", False)
                    send_at_ms = r.get("send_at", 0)
                    try:
                        from datetime import datetime, timezone, timedelta
                        cairo_tz = timezone(timedelta(hours=3))
                        send_at = datetime.fromtimestamp(send_at_ms / 1000, tz=cairo_tz).strftime("%Y-%m-%d %H:%M")
                    except:
                        send_at = "وقت غير معروف"
                    status = "✅ اتبعت" if sent else "⏳ لسه"
                    lines.append(f"- {text} | {send_at} | {status}")
                result = chr(10).join(["التذكيرات:"] + lines)



        elif tool_name == "delete_reminder":
            from services.firebase_service import delete_reminder
            reminder_id = tool_input.get("reminder_id", "")
            ok = delete_reminder(reminder_id)
            result = "✅ تم حذف التذكير" if ok else "❌ مش لاقي التذكير ده"

        elif tool_name == "delete_all_reminders":
            from services.firebase_service import delete_all_reminders
            count = delete_all_reminders()
            result = f"✅ تم حذف {count} تذكيرات"

        elif tool_name == "get_human_model":
            from services.firebase_service import get_human_model
            model = get_human_model()
            if model:
                lines = [f"{k}: {v}" for k, v in model.items() if k not in ["created_at", "updated_at"]]
                result = "Human Model لأحمد:\n" + chr(10).join(lines)
            else:
                result = "مفيش Human Model محفوظ بعد"

        elif tool_name == "update_human_model":
            from services.firebase_service import update_human_model
            key = tool_input.get("key", "")
            value = tool_input.get("value", "")
            ok = update_human_model(key, value)
            result = f"✅ تم تحديث {key} = {value}" if ok else "❌ فشل التحديث"

        elif tool_name == "get_bahr_projects":
            from services.firebase_service import get_bahr_projects
            projects = get_bahr_projects()
            if not projects:
                result = "مفيش مشاريع مسجلة في Bahr OS"
            else:
                lines = []
                for p in projects:
                    supervisors = ", ".join(p.get("supervisors", []))
                    lines.append(
                        f"- {p['id']} | عميل: {p['client']} | مساحة: {p['area']} | مشرفين: {supervisors}"
                    )
                result = "مشاريع Bahr OS:" + chr(10) + chr(10).join(lines)

        elif tool_name == "get_bahr_sites":
            from services.firebase_service import get_bahr_sites
            sites = get_bahr_sites()
            if not sites:
                result = "مفيش مواقع مسجلة"
            else:
                lines = [f"- {s['id']} | عميل: {s['client']} | مساحة: {s['area']}" for s in sites]
                result = "Bahr Sites:" + chr(10) + chr(10).join(lines)

        elif tool_name == "get_project_details":
            from services.firebase_service import get_project_details
            project_id = tool_input.get("project_id", "")
            details = get_project_details(project_id)
            if not details:
                result = f"مش لاقي مشروع بالـ ID: {project_id}"
            else:
                result = (
                    f"تفاصيل {project_id}:" + chr(10) +
                    f"عميل: {details['client']}" + chr(10) +
                    f"مساحة: {details['area']}" + chr(10) +
                    f"مشرفين: {', '.join(details['supervisors'])}" + chr(10) +
                    f"بنود: {len(details['items'])} بند"
                )

        elif tool_name == "create_recurring_reminder":
            from services.firebase_service import save_recurring_reminder
            text = tool_input.get("text", "")
            interval_type = tool_input.get("interval_type", "daily")
            interval_value = tool_input.get("interval_value", 1)
            scheduled_hour = tool_input.get("scheduled_hour")
            scheduled_minute = tool_input.get("scheduled_minute", 0)
            reminder_id = save_recurring_reminder(text, interval_type, interval_value, chat_id, scheduled_hour, scheduled_minute)
            if reminder_id:
                type_labels = {"daily": "يومي", "weekly": "أسبوعي", "hourly": "كل ساعة", "custom_minutes": f"كل {interval_value} دقيقة"}
                label = type_labels.get(interval_type, interval_type)
                time_str = f" الساعة {scheduled_hour}:{str(scheduled_minute).zfill(2)}" if scheduled_hour is not None else ""
                result = f"✅ تذكير متكرر ({label}{time_str}): {text}"
            else:
                result = "❌ فشل إنشاء التذكير المتكرر"

        elif tool_name == "list_recurring_reminders":
            from services.firebase_service import get_active_recurring_reminders
            reminders = get_active_recurring_reminders()
            if not reminders:
                result = "مفيش تذكيرات متكررة نشطة"
            else:
                lines = []
                for r in reminders:
                    type_labels = {"daily": "يومي", "weekly": "أسبوعي", "hourly": "كل ساعة", "custom_minutes": f"كل {r.get('interval_value')} دقيقة"}
                    label = type_labels.get(r.get("interval_type", ""), r.get("interval_type", ""))
                    lines.append(f"- [{r['id'][:8]}...] {r['text']} ({label})")
                result = "التذكيرات المتكررة:" + chr(10) + chr(10).join(lines)

        elif tool_name == "delete_recurring_reminder":
            from services.firebase_service import delete_recurring_reminder_db
            reminder_id = tool_input.get("reminder_id", "")
            ok = delete_recurring_reminder_db(reminder_id)
            result = "✅ تم حذف التذكير المتكرر" if ok else "❌ مش لاقي التذكير"

        elif tool_name == "get_backup_status":
            import os, requests as _req
            token = os.getenv("GITHUB_TOKEN")
            repo  = os.getenv("GITHUB_REPO", "bahr9/adam-backups")
            try:
                headers = {
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json"
                }
                # آخر commit في الـ repo
                r = _req.get(
                    f"https://api.github.com/repos/{repo}/commits?per_page=1",
                    headers=headers, timeout=10
                )
                if r.status_code == 200:
                    commits = r.json()
                    if commits:
                        last = commits[0]
                        msg     = last["commit"]["message"]
                        date    = last["commit"]["committer"]["date"][:16].replace("T", " ")
                        author  = last["commit"]["committer"]["name"]
                        result = (
                            f"💾 آخر Backup:\n"
                            f"📅 {date} UTC\n"
                            f"📝 {msg}\n"
                            f"✅ github.com/{repo}"
                        )
                    else:
                        result = "مفيش backups لحد دلوقتي"
                else:
                    result = f"❌ مش قادر أوصل للـ repo: {r.status_code}"
            except Exception as ex:
                result = f"❌ خطأ في جلب حالة الـ backup: {ex}"

        else:
            result = f"أداة غير معروفة: {tool_name}"
        
        logger.info(f"✅ نتيجة الأداة {tool_name}: {result[:200]}")
        return result
            
    except Exception as e:
        logger.error(f"❌ خطأ في تنفيذ الأداة {tool_name}: {e}")
        return f"حصل خطأ أثناء التنفيذ: {str(e)}"

def ask_claude_agentic(user_message, chat_id, conversation_history=None, memory_summary=None, max_tool_rounds=5):
    """
    نسخة "وكيلة" (agentic) من الرد — البوت بيقرر بنفسه إمتى يستخدم الأدوات
    (الجراف، التذكيرات) بدل تخمين النية مقدمًا. ده بيخليه يتصرف زي Claude
    نفسه: يشوف الأدوات المتاحة، ويستخدم اللي محتاجه، وممكن يستخدم أكتر من
    أداة ورا بعض (زي: يجيب القايمة الأول، بعدين يمسح بالـ id الصح).
    
    Args:
        user_message: الرسالة من المستخدم
        chat_id: معرّف المحادثة (للتذكيرات)
        conversation_history: السياق القريب (اختياري)
        memory_summary: الذاكرة الدائمة (اختياري)
        max_tool_rounds: أقصى عدد جولات استخدام أدوات قبل ما نوقف (حماية من اللوب اللانهائي)
    
    Returns:
        الرد النهائي كنص
    """
    try:
        messages = []
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})
        
        static_part, dynamic_part = build_system_prompt_parts(memory_summary=memory_summary)
        system_blocks = [
            {"type": "text", "text": static_part, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": dynamic_part}
        ]
        
        for _ in range(max_tool_rounds):
            response = claude_client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=2048,
                thinking={"type": "disabled"},
                system=system_blocks,
                tools=TOOLS,
                messages=messages
            )
            
            logger.info(f"🧭 stop_reason: {response.stop_reason}")
            
            if response.stop_reason != "tool_use":
                reply = ""
                for content in response.content:
                    if content.type == "text":
                        reply += content.text
                return reply.strip() if reply.strip() else "تمام."
            
            # الموديل طلب يستخدم أداة (أو أكتر) — ننفذها ونرجعله بالنتيجة
            messages.append({"role": "assistant", "content": response.content})
            
            tool_results = []
            for content in response.content:
                if content.type == "tool_use":
                    result_text = _execute_tool(content.name, content.input, chat_id)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content.id,
                        "content": result_text
                    })
            
            messages.append({"role": "user", "content": tool_results})
        
        return "معلش، الطلب محتاج خطوات كتير — ممكن تبسطه شوية أو تجربه تاني؟"
        
    except Exception as e:
        logger.error(f"❌ خطأ في ask_claude_agentic: {e}")
        return f"❌ حصلت مشكلة: {str(e)}"

def analyze_with_vision(image_base64, caption, media_type="image/jpeg", memory_summary=None):
    """
    تحليل الصور باستخدام Claude Vision
    
    Args:
        image_base64: الصورة بصيغة base64
        caption: النص المرافق للصورة (أو نص افتراضي لو مفيش caption)
        media_type: نوع الصورة (image/jpeg, image/png, image/webp)
        memory_summary: الذاكرة الدائمة (اختياري)
    
    Returns:
        التحليل من Claude كنص
    """
    try:
        static_part, dynamic_part = build_system_prompt_parts(memory_summary=memory_summary)
        system_blocks = [
            {"type": "text", "text": static_part, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": dynamic_part}
        ]
        
        response = claude_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=800,
            thinking={"type": "disabled"},
            system=system_blocks,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": caption
                    }
                ]
            }]
        )
        
        reply = ""
        for content in response.content:
            if content.type == "text":
                reply += content.text
        
        return reply.strip() if reply.strip() else "عذراً، حصلت مشكلة في معالجة الصورة."
        
    except Exception as e:
        logger.error(f"❌ خطأ في تحليل الصورة: {e}")
        return f"❌ حصلت مشكلة في تحليل الصورة: {str(e)}"

def ask_claude(user_message, conversation_history=None, memory_summary=None, pending_tasks=None):
    """
    سؤال Claude مع معالجة ThinkingBlock
    
    Args:
        user_message: الرسالة من المستخدم
        conversation_history: السجل القريب (آخر شوية رسائل، اختياري)
        memory_summary: ملخص الذاكرة الدائمة (اختياري)
        pending_tasks: المهام المعلقة الحالية (اختياري)
    
    Returns:
        الرد من Claude (بدون thinking)
    """
    try:
        messages = []
        
        # إضافة conversation history لو موجود (السياق القريب)
        if conversation_history:
            messages.extend(conversation_history)
        
        # إضافة الرسالة الحالية
        messages.append({"role": "user", "content": user_message})
        
        # استدعاء Claude
        # ملحوظة: Claude Sonnet 5 مش بيدعم thinking.type=enabled + budget_tokens (بترجع خطأ 400)
        # بنستخدم adaptive thinking بمجهود منخفض عشان تفكير أعمق شوية من غير تأخير كبير
        response = claude_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            thinking={"type": "adaptive"},
            output_config={"effort": "low"},
            system=build_system_prompt(pending_tasks=pending_tasks, memory_summary=memory_summary),
            messages=messages
        )
        
        # استخراج الـ text من response (تجاهل thinking)
        reply = ""
        for content in response.content:
            if content.type == "text":
                reply += content.text
            elif content.type == "thinking":
                # تجاهل الـ thinking blocks
                continue
        
        if not reply:
            reply = "عذراً، حصلت مشكلة في الرد."
        
        return reply
        
    except Exception as e:
        logger.error(f"❌ خطأ في Claude: {e}")
        return f"❌ حصلت مشكلة: {str(e)}"

def format_history_for_claude(stored_messages, limit=20):
    """
    يحوّل السجل المخزّن في Firestore (قائمة {"user":.., "assistant":..}) 
    لصيغة رسائل Claude API القياسية
    """
    history = []
    for m in stored_messages[-limit:]:
        if m.get("user"):
            history.append({"role": "user", "content": m["user"]})
        if m.get("assistant"):
            history.append({"role": "assistant", "content": m["assistant"]})
    return history

def summarize_memory(old_summary, user_message, assistant_reply):
    """
    يحدّث ملخص الذاكرة الدائمة بعد كل تبادل رسائل.
    بيستخدم موديل خفيف وسريع (Haiku) عشان التكلفة والسرعة، لأن ده مجرد تلخيص وليس رد نهائي.
    
    Returns:
        الذاكرة المحدّثة (نص) أو None لو حصل خطأ
    """
    try:
        prompt = f"""إنت بتحافظ على ذاكرة دائمة مختصرة عن أحمد (صاحب Bahr Designs) عبر كل محادثاته مع البوت، حتى لو من شهور فاتت.

الذاكرة الحالية:
{old_summary or "(فاضية لسه، أول مرة)"}

آخر تبادل حصل دلوقتي:
أحمد: {user_message}
البوت: {assistant_reply}

حدّث الذاكرة لو فيه حاجة جديدة تستاهل تتحفظ للمستقبل (زي: مشروع جديد، تفضيل شخصي، قرار مهم، معلومة عن الشغل أو الفريق، حاجة عم يشتغل عليها بشكل مستمر).
لو التبادل ده مجرد كلام عادي (سلام، سؤال بسيط، رد قصير) ومفيهوش حاجة تستاهل تتحفظ، رجّع نفس الذاكرة القديمة زي ما هي بالظبط من غير أي تغيير.
خلي الذاكرة مختصرة جدًا (أقصى حاجة 15 نقطة bullet points)، وبالعربي، وركّز على المعلومات الدايمة مش التفاصيل اليومية العابرة.
رجّع الذاكرة المحدّثة فقط، بدون أي شرح أو مقدمة أو Markdown."""

        response = claude_client.messages.create(
            model=CLAUDE_HAIKU_MODEL,
            max_tokens=600,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": prompt}]
        )
        
        text = ""
        for content in response.content:
            if content.type == "text":
                text += content.text
        
        return text.strip() if text else None
        
    except Exception as e:
        logger.warning(f"⚠️ خطأ في تحديث ملخص الذاكرة الدائمة: {e}")
        return None


    """
    تحليل الصور باستخدام Claude Vision
    
    Args:
        image_base64: الصورة بـ base64
        caption: النص المرافق للصورة
        media_type: نوع الصورة (image/jpeg, image/png, إلخ)
    
    Returns:
        التحليل من Claude
    """
    try:
        response = claude_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=400,
            thinking={"type": "disabled"},
            system=f"""أنت ADAM — مرافق أحمد الشخصي. اتكلم بالعامية المصرية الدافئة.
الوقت الحالي: {now_cairo().strftime('%Y-%m-%d %H:%M')}""",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": caption
                    }
                ]
            }]
        )
        
        # استخراج الـ text فقط
        reply = ""
        for content in response.content:
            if content.type == "text":
                reply += content.text
            elif content.type == "thinking":
                continue
        
        if not reply:
            reply = "عذراً، حصلت مشكلة في معالجة الصورة."
        
        return reply
        
    except Exception as e:
        logger.error(f"❌ خطأ في تحليل الصورة: {e}")
        return f"❌ {str(e)}"

def extract_reminder_intent(user_message, conversation_history=None):
    """
    استخراج نية تذكير من رسالة عادية (مع الاستفادة من سياق آخر رسائل لفهم إشارات زي "ده"/"دي")
    
    Args:
        user_message: الرسالة الحالية
        conversation_history: آخر شوية رسائل (اختياري) لفهم السياق
    
    Returns:
        dict مع {"minutes_from_now": ..., "text": ...} أو None
    """
    try:
        now = now_cairo()
        extraction_prompt = f"""الوقت الحالي: {now.strftime('%Y-%m-%d %H:%M')}

افحص آخر رسالة من المستخدم (في نهاية المحادثة) وحدد هل فيها طلب تذكير واضح (زي "ذكرني بعد ٥ دقايق").
استخدم آخر رسائل المحادثة (لو موجودة) عشان تفهم أي إشارة زي "ده"/"دي"/"زي ما قلنا".

لو في تذكير، رجّع JSON فقط:
{{"is_reminder": true, "minutes_from_now": <رقم>, "text": "<النص>"}}

لو مفيش، رجّع:
{{"is_reminder": false}}

JSON فقط، بدون أي كلام تاني."""

        messages = []
        if conversation_history:
            messages.extend(conversation_history[-6:])  # آخر 3 تبادلات كسياق بس، يكفي للإشارات
        messages.append({"role": "user", "content": user_message})

        response = claude_client.messages.create(
            model=CLAUDE_HAIKU_MODEL,
            max_tokens=200,
            thinking={"type": "disabled"},
            system=extraction_prompt,
            messages=messages
        )
        
        raw = ""
        for content in response.content:
            if content.type == "text":
                raw += content.text
        
        data = _extract_json(raw)
        if data is None:
            logger.warning(f"⚠️ رد استخراج التذكير مش JSON صالح: {raw[:100]!r}")
            return None
        
        if data.get("is_reminder") and "minutes_from_now" in data:
            return {
                "text": data.get("text", user_message),
                "minutes_from_now": int(data["minutes_from_now"])
            }
        
        return None
        
    except Exception as e:
        logger.warning(f"⚠️ خطأ في استخراج التذكير: {e}")
        return None

def extract_graph_intent(user_message, conversation_history=None):
    """
    استخراج نية إضافة/تعديل/حذف في الجراف (مع الاستفادة من سياق آخر رسائل)
    
    Args:
        user_message: الرسالة الحالية
        conversation_history: آخر شوية رسائل (اختياري) لفهم السياق، مهم جدًا لإشارات زي "امسح ده"
    
    Returns:
        dict مع action وتفاصيل أو None
    """
    try:
        extraction_prompt = """افحص آخر رسالة من المستخدم (في نهاية المحادثة) وحدد هل فيها طلب إضافة/تعديل/حذف/استعلام في "خريطة بحر" (الجراف).
استخدم آخر رسائل المحادثة (لو موجودة) عشان تفهم أي إشارة زي "ده"/"دي"/"العنصر ده" اللي بترجع لحاجة اتقالت قبل كده (زي اسم عنصر ظهر في رد سابق من البوت).

لو في طلب إضافة عنصر جديد:
{{"action": "add", "label": "<الاسم>", "category": "<نوع>", "fact": "<الحقيقة>"}}

لو في طلب تعديل عنصر موجود (إضافة معلومة له):
{{"action": "edit", "node_id": "<id>", "fact": "<معلومة>"}}

لو في طلب حذف عنصر (زي "امسح"، "احذف"، "شيل" + اسم العنصر أو إشارة له من رسالة سابقة):
{{"action": "delete", "label": "<اسم العنصر اللي عايز يتمسح، حتى لو استنتجته من السياق مش من الرسالة دي بس>"}}

لو في طلب استعلام (اعرضلي القايمة):
{{"action": "query"}}

لو مفيش طلب واضح خالص:
{{"action": "none"}}

JSON فقط."""

        messages = []
        if conversation_history:
            messages.extend(conversation_history[-6:])
        messages.append({"role": "user", "content": user_message})

        response = claude_client.messages.create(
            model=CLAUDE_HAIKU_MODEL,
            max_tokens=250,
            thinking={"type": "disabled"},
            system=extraction_prompt,
            messages=messages
        )
        
        raw = ""
        for content in response.content:
            if content.type == "text":
                raw += content.text
        
        data = _extract_json(raw)
        if data is None:
            logger.warning(f"⚠️ رد استخراج نية الجراف مش JSON صالح: {raw[:100]!r}")
            return None
        
        if data.get("action") != "none":
            return data
        
        return None
        
    except Exception as e:
        logger.warning(f"⚠️ خطأ في استخراج نية الجراف: {e}")
        return None