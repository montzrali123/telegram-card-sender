"""
البوت الرئيسي لإدارة إرسال البطاقات
"""
import logging
import os
import time
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
# from telegram.constants import ParseMode  # تم إزالته لتجنب أخطاء parsing

from database import Database
from session_manager import SessionManager
from task_manager import CardFileManager, TaskRunner
from group_monitor import GroupMonitor, CardExtractor
from monitor_handlers import show_monitors_menu, handle_monitor_callback

# إعداد السجلات
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# حالات المحادثة
(MAIN_MENU, SESSION_MENU, ADD_SESSION_PHONE, ADD_SESSION_CODE, ADD_SESSION_PASSWORD,
 TASK_MENU, CREATE_TASK_NAME, CREATE_TASK_SESSION, CREATE_TASK_BOT, CREATE_TASK_COMMAND,
 CREATE_TASK_FILE, CREATE_TASK_INTERVAL,
 MONITOR_MENU, ADD_MONITOR_NAME, ADD_MONITOR_SESSION, ADD_MONITOR_CHAT, 
 ADD_MONITOR_BOT, ADD_MONITOR_COMMAND) = range(18)

# تهيئة الأنظمة
db = Database()
session_manager = SessionManager()
card_manager = CardFileManager()
task_runner = TaskRunner(db, session_manager, card_manager)
group_monitor = GroupMonitor(session_manager, db)

# معرف المالك
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

def is_owner(user_id: int) -> bool:
    """التحقق من أن المستخدم هو المالك"""
    return user_id == OWNER_ID

# ============= القائمة الرئيسية =============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """بدء البوت"""
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await update.message.reply_text("⛔ عذراً، هذا البوت خاص.")
        return ConversationHandler.END
    
    keyboard = [
        ["👥 إدارة الجلسات", "📋 إدارة المهام"],
        ["👁️ مراقبة القروبات", "📊 الإحصائيات"],
        ["ℹ️ المساعدة"]
    ]
    
    await update.message.reply_text(
        f"🎉 مرحباً {update.effective_user.first_name}!\n\n"
        "🤖 بوت إرسال البطاقات الاحترافي\n\n"
        "✅ البوت جاهز للعمل!\n"
        "📱 اختر من القائمة:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    
    return MAIN_MENU

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج القائمة الرئيسية"""
    text = update.message.text
    
    if text == "👥 إدارة الجلسات":
        return await show_sessions_menu(update, context)
    elif text == "📋 إدارة المهام":
        return await show_tasks_menu(update, context)
    elif text == "👁️ مراقبة القروبات":
        return await show_monitors_menu_wrapper(update, context)
    elif text == "📊 الإحصائيات":
        return await show_stats(update, context)
    elif text == "ℹ️ المساعدة":
        return await show_help(update, context)
    else:
        await update.message.reply_text("اختر من القائمة من فضلك.")
        return MAIN_MENU

# ============= مراقبة القروبات =============

async def show_monitors_menu_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """غلاف لعرض قائمة المراقبات"""
    return await show_monitors_menu(update, context, db, group_monitor)

async def add_monitor_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """بدء إضافة مراقبة جديدة"""
    await update.message.reply_text(
        "⚡ **إضافة مراقبة جديدة**\n\n"
        "📝 أدخل اسم المراقبة:\n"
        "مثال: قروب البطاقات الرئيسي\n\n"
        "أو اضغط /cancel للإلغاء"
    )
    return ADD_MONITOR_NAME

async def add_monitor_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """حفظ اسم المراقبة"""
    context.user_data['monitor_name'] = update.message.text
    
    # عرض قائمة الجلسات
    sessions = db.get_sessions(active_only=True)
    
    if not sessions:
        await update.message.reply_text(
            "❌ لا توجد جلسات نشطة!\n\n"
            "أضف جلسة أولاً من 'إدارة الجلسات'"
        )
        return ConversationHandler.END
    
    text = "👥 **اختر الجلسة:**\n\n"
    for i, session in enumerate(sessions, 1):
        text += f"{i}. 📱 {session['name']} - {session['phone']}\n"
    
    text += "\nأرسل رقم الجلسة:"
    
    context.user_data['available_sessions'] = sessions
    await update.message.reply_text(text)
    return ADD_MONITOR_SESSION

async def add_monitor_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """حفظ الجلسة"""
    try:
        session_num = int(update.message.text)
        sessions = context.user_data.get('available_sessions', [])
        
        if 1 <= session_num <= len(sessions):
            context.user_data['monitor_session_id'] = sessions[session_num - 1]['id']
            
            await update.message.reply_text(
                "🎯 **معرّف القروب/القناة:**\n\n"
                "📝 أدخل معرّف القروب أو القناة:\n\n"
                "🔹 إذا كان عام: @groupname\n"
                "🔹 إذا كان خاص: -1001234567890\n\n"
                "💡 **كيف تحصل على المعرّف:**\n"
                "1. أضف @userinfobot للقروب\n"
                "2. سيرسل لك المعرّف"
            )
            return ADD_MONITOR_CHAT
        else:
            await update.message.reply_text("❌ رقم غير صحيح. حاول مرة أخرى.")
            return ADD_MONITOR_SESSION
    except ValueError:
        await update.message.reply_text("❌ أدخل رقماً صحيحاً.")
        return ADD_MONITOR_SESSION

async def add_monitor_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """حفظ معرّف القروب"""
    context.user_data['monitor_chat_id'] = update.message.text
    
    await update.message.reply_text(
        "🤖 **البوت المستهدف:**\n\n"
        "📝 أدخل username البوت الذي سيفحص البطاقات:\n"
        "مثال: BotFather\n\n"
        "⚠️ بدون @ في البداية"
    )
    return ADD_MONITOR_BOT

async def add_monitor_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """حفظ البوت المستهدف"""
    bot_username = update.message.text.strip().replace('@', '')
    context.user_data['monitor_bot'] = bot_username
    
    await update.message.reply_text(
        "⚡ **الأمر:**\n\n"
        "📝 أدخل الأمر الذي سيرسل للبوت:\n"
        "مثال: /chk أو /start\n\n"
        "💡 هذا الأمر سيرسل قبل البطاقة"
    )
    return ADD_MONITOR_COMMAND

async def add_monitor_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """حفظ الأمر وإضافة المراقبة"""
    command = update.message.text.strip()
    
    # حفظ المراقبة في قاعدة البيانات
    monitor_id = db.add_monitor(
        name=context.user_data['monitor_name'],
        session_id=context.user_data['monitor_session_id'],
        chat_id=context.user_data['monitor_chat_id'],
        target_bot=context.user_data['monitor_bot'],
        target_command=command,
        auto_send=True
    )
    
    await update.message.reply_text(
        "✅ **تم إضافة المراقبة بنجاح!**\n\n"
        f"👁️ الاسم: {context.user_data['monitor_name']}\n"
        f"🎯 القروب: {context.user_data['monitor_chat_id']}\n"
        f"🤖 البوت: {context.user_data['monitor_bot']}\n"
        f"⚡ الأمر: {command}\n\n"
        "💡 **الخطوة التالية:**\n"
        "اذهب إلى 'مراقبة القروبات' وشغّل المراقبة!",
        reply_markup=ReplyKeyboardMarkup([
            ["👥 إدارة الجلسات", "📋 إدارة المهام"],
            ["👁️ مراقبة القروبات", "📊 الإحصائيات"],
            ["ℹ️ المساعدة"]
        ], resize_keyboard=True)
    )
    
    context.user_data.clear()
    return MAIN_MENU

# ============= إدارة الجلسات =============

async def show_sessions_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """عرض قائمة الجلسات"""
    sessions = db.get_sessions()
    
    text = "👥 **إدارة الجلسات**\n\n"
    
    if sessions:
        text += "الجلسات المتاحة:\n\n"
        for session in sessions:
            status = "🟢" if session['is_active'] else "🔴"
            text += f"{status} **{session['name']}**\n"
            text += f"   📱 {session['phone']}\n"
            text += f"   📅 {session['created_at'][:10]}\n\n"
    else:
        text += "لا توجد جلسات مضافة.\n\n"
    
    keyboard = [
        ["➕ إضافة جلسة", "📋 عرض الجلسات"],
        ["🔙 القائمة الرئيسية"]
    ]
    
    await update.message.reply_text(
        text,
        
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    
    return SESSION_MENU

async def session_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج قائمة الجلسات"""
    text = update.message.text
    
    if text == "➕ إضافة جلسة":
        await update.message.reply_text(
            "📱 **إضافة جلسة جديدة**\n\n"
            "أرسل رقم الهاتف بالصيغة الدولية:\n"
            "مثال: +9647XXXXXXXXX\n\n"
            "أو اضغط /cancel للإلغاء",
            
            reply_markup=ReplyKeyboardRemove()
        )
        return ADD_SESSION_PHONE
    
    elif text == "📋 عرض الجلسات":
        return await show_sessions_list(update, context)
    
    elif text == "🔙 القائمة الرئيسية":
        return await start(update, context)
    
    return SESSION_MENU

async def show_sessions_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """عرض قائمة الجلسات مع أزرار التحكم"""
    sessions = db.get_sessions()
    
    if not sessions:
        await update.message.reply_text("لا توجد جلسات مضافة.")
        return SESSION_MENU
    
    keyboard = []
    for session in sessions:
        status = "🟢" if session['is_active'] else "🔴"
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {session['name']} - {session['phone']}", 
                callback_data=f"session_{session['id']}"
            )
        ])
    
    await update.message.reply_text(
        "اختر جلسة للتحكم بها:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return SESSION_MENU

async def add_session_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استقبال رقم الهاتف"""
    phone = update.message.text.strip()
    
    # التحقق من صيغة الرقم
    if not phone.startswith('+') or len(phone) < 10:
        await update.message.reply_text(
            "❌ صيغة الرقم غير صحيحة.\n"
            "أرسل الرقم بالصيغة الدولية مثل: +9647XXXXXXXXX"
        )
        return ADD_SESSION_PHONE
    
    # حفظ البيانات
    context.user_data['session_phone'] = phone
    
    await update.message.reply_text(
        "📝 أدخل **API ID** الخاص بك:\n\n"
        "يمكنك الحصول عليه من: https://my.telegram.org",
        
    )
    
    # سنطلب API ID و API Hash
    context.user_data['waiting_for'] = 'api_id'
    return ADD_SESSION_CODE

async def add_session_api_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استقبال API ID و API Hash"""
    text = update.message.text.strip()
    
    if context.user_data.get('waiting_for') == 'api_id':
        context.user_data['api_id'] = text
        context.user_data['waiting_for'] = 'api_hash'
        
        await update.message.reply_text(
            "📝 الآن أدخل **API Hash**:",
            
        )
        return ADD_SESSION_CODE
    
    elif context.user_data.get('waiting_for') == 'api_hash':
        context.user_data['api_hash'] = text
        
        # إرسال كود التحقق
        await update.message.reply_text("⏳ جاري إرسال كود التحقق...")
        
        result = await session_manager.create_session(
            context.user_data['session_phone'],
            context.user_data['api_id'],
            context.user_data['api_hash']
        )
        
        if result['status'] == 'code_sent':
            context.user_data['phone_code_hash'] = result['phone_code_hash']
            context.user_data['waiting_for'] = 'code'
            
            await update.message.reply_text(
                "✅ تم إرسال كود التحقق إلى تيليجرام.\n\n"
                "📱 أدخل الكود الآن:"
            )
            return ADD_SESSION_CODE
        else:
            await update.message.reply_text(
                f"❌ {result['message']}\n\n"
                "جرب مرة أخرى بـ /start"
            )
            return ConversationHandler.END
    
    elif context.user_data.get('waiting_for') == 'code':
        code = text.strip()
        
        await update.message.reply_text("⏳ جاري التحقق...")
        
        result = await session_manager.verify_code(
            context.user_data['session_phone'],
            code,
            context.user_data['phone_code_hash'],
            context.user_data['api_id'],
            context.user_data['api_hash']
        )
        
        if result['status'] == 'password_required':
            context.user_data['waiting_for'] = 'password'
            await update.message.reply_text(
                "🔐 الحساب محمي بكلمة مرور.\n"
                "أدخل كلمة المرور:"
            )
            return ADD_SESSION_PASSWORD
        
        elif result['status'] == 'success':
            # حفظ الجلسة في قاعدة البيانات
            session_name = f"{result.get('username', 'Session')}_{context.user_data['session_phone'][-4:]}"
            
            session_id = db.add_session(
                session_name,
                context.user_data['session_phone'],
                context.user_data['api_id'],
                context.user_data['api_hash'],
                result['session_string']
            )
            
            await update.message.reply_text(
                f"✅ {result['message']}\n\n"
                f"تم حفظ الجلسة بنجاح!\n"
                f"📝 الاسم: {session_name}",
                reply_markup=ReplyKeyboardMarkup([
                    ["👥 إدارة الجلسات", "📋 إدارة المهام"],
                    ["👁️ مراقبة القروبات", "📊 الإحصائيات"],
                    ["ℹ️ المساعدة"]
                ], resize_keyboard=True)
            )
            
            # تنظيف البيانات المؤقتة
            context.user_data.clear()
            
            return MAIN_MENU
        
        else:
            await update.message.reply_text(
                f"❌ {result['message']}\n\n"
                "جرب مرة أخرى بـ /start"
            )
            return ConversationHandler.END

async def add_session_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استقبال كلمة المرور"""
    password = update.message.text.strip()
    
    await update.message.reply_text("⏳ جاري التحقق...")
    
    result = await session_manager.verify_code(
        context.user_data['session_phone'],
        context.user_data.get('last_code', ''),
        context.user_data['phone_code_hash'],
        context.user_data['api_id'],
        context.user_data['api_hash'],
        password=password
    )
    
    if result['status'] == 'success':
        session_name = f"{result.get('username', 'Session')}_{context.user_data['session_phone'][-4:]}"
        
        session_id = db.add_session(
            session_name,
            context.user_data['session_phone'],
            context.user_data['api_id'],
            context.user_data['api_hash'],
            result['session_string']
        )
        
        await update.message.reply_text(
            f"✅ تم تسجيل الدخول بنجاح!\n\n"
            f"📝 الاسم: {session_name}",
            reply_markup=ReplyKeyboardMarkup([
                ["👥 إدارة الجلسات", "📋 إدارة المهام"],
                ["👁️ مراقبة القروبات", "📊 الإحصائيات"],
                ["ℹ️ المساعدة"]
            ], resize_keyboard=True)
        )
        
        context.user_data.clear()
        return MAIN_MENU
    else:
        await update.message.reply_text(f"❌ {result['message']}")
        return ConversationHandler.END

# ============= إدارة المهام =============

async def show_tasks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """عرض قائمة المهام"""
    tasks = db.get_tasks()
    
    text = "📋 **إدارة المهام**\n\n"
    
    if tasks:
        text += "المهام المتاحة:\n\n"
        for task in tasks:
            status = "▶️" if task['is_running'] else "⏸️"
            text += f"{status} **{task['name']}**\n"
            text += f"   🎯 البوت: {task['target_bot']}\n"
            text += f"   ⏱️ الفاصل: {task['interval_seconds']}ث\n\n"
    else:
        text += "لا توجد مهام مضافة.\n\n"
    
    keyboard = [
        ["➕ إنشاء مهمة", "📋 عرض المهام"],
        ["🔙 القائمة الرئيسية"]
    ]
    
    await update.message.reply_text(
        text,
        
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    
    return TASK_MENU

async def task_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج قائمة المهام"""
    text = update.message.text
    
    if text == "➕ إنشاء مهمة":
        await update.message.reply_text(
            "📝 **إنشاء مهمة جديدة**\n\n"
            "أدخل اسم المهمة:",
            
            reply_markup=ReplyKeyboardRemove()
        )
        return CREATE_TASK_NAME
    
    elif text == "📋 عرض المهام":
        return await show_tasks_list(update, context)
    
    elif text == "🔙 القائمة الرئيسية":
        return await start(update, context)
    
    return TASK_MENU

async def show_tasks_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """عرض قائمة المهام مع أزرار التحكم"""
    tasks = db.get_tasks()
    
    if not tasks:
        await update.message.reply_text("لا توجد مهام مضافة.")
        return TASK_MENU
    
    keyboard = []
    for task in tasks:
        status = "▶️" if task['is_running'] else "⏸️"
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {task['name']}", 
                callback_data=f"task_{task['id']}"
            )
        ])
    
    await update.message.reply_text(
        "اختر مهمة للتحكم بها:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return TASK_MENU

async def create_task_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استقبال اسم المهمة"""
    context.user_data['task_name'] = update.message.text.strip()
    
    # عرض الجلسات المتاحة
    sessions = db.get_sessions(active_only=True)
    
    if not sessions:
        await update.message.reply_text(
            "❌ لا توجد جلسات مفعلة!\n"
            "أضف جلسة أولاً من قائمة الجلسات.",
            reply_markup=ReplyKeyboardMarkup([
                ["🔙 القائمة الرئيسية"]
            ], resize_keyboard=True)
        )
        return MAIN_MENU
    
    keyboard = []
    for session in sessions:
        keyboard.append([f"{session['id']}. {session['name']} - {session['phone']}"])
    keyboard.append(["🔙 إلغاء"])
    
    await update.message.reply_text(
        "اختر الجلسة المستخدمة:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    
    context.user_data['available_sessions'] = sessions
    return CREATE_TASK_SESSION

async def create_task_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استقبال الجلسة"""
    text = update.message.text
    
    if text == "🔙 إلغاء":
        return await start(update, context)
    
    # البحث عن الجلسة
    sessions = context.user_data.get('available_sessions', [])
    selected_session = None
    
    for session in sessions:
        # دعم كلا التنسيقين: القديم والجديد
        if (f"{session['name']} - {session['phone']}" == text or 
            f"{session['id']}. {session['name']} - {session['phone']}" == text or
            text.startswith(f"{session['id']}.")):  # دعم الاختيار بالرقم فقط
            selected_session = session
            break
    
    if not selected_session:
        await update.message.reply_text("❌ جلسة غير صحيحة. اختر من القائمة.")
        return CREATE_TASK_SESSION
    
    context.user_data['task_session_id'] = selected_session['id']
    
    await update.message.reply_text(
        "أدخل معرف البوت المستهدف:\n"
        "مثال: @YourTargetBot",
        reply_markup=ReplyKeyboardRemove()
    )
    
    return CREATE_TASK_BOT

async def create_task_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استقبال البوت المستهدف"""
    bot_username = update.message.text.strip()
    
    if not bot_username.startswith('@'):
        bot_username = '@' + bot_username
    
    context.user_data['task_bot'] = bot_username
    
    await update.message.reply_text(
        "أدخل الأمر المطلوب:\n"
        "مثال: /pain"
    )
    
    return CREATE_TASK_COMMAND

async def create_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استقبال الأمر"""
    context.user_data['task_command'] = update.message.text.strip()
    
    await update.message.reply_text(
        "📄 الآن أرسل ملف البطاقات (.txt) أو البطاقات مباشرة:\n\n"
        "📝 التنسيق المطلوب (كل سطر = بطاقة):\n"
        "4519912222608202|08|2029|649\n"
        "1234567890123456|12|2025|123\n\n"
        "✅ يمكنك إرسال ملف .txt أو نسخ ولصق البطاقات مباشرة!"
    )
    
    return CREATE_TASK_FILE

async def create_task_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استقبال ملف البطاقات أو رسالة نصية"""
    
    # حالة 1: رسالة نصية (بطاقات مباشرة)
    if update.message.text:
        text = update.message.text.strip()
        
        # التحقق من أن الرسالة تحتوي على بطاقات
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # التحقق من أن السطر الأول يحتوي على بطاقة
        if lines and '|' in lines[0]:
            # حفظ البطاقات في ملف
            filename = f"cards_{update.effective_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = card_manager.save_cards_file(text, filename)
            
            # عد البطاقات
            cards_count = card_manager.count_cards(filepath)
            
            context.user_data['task_file'] = filepath
            
            await update.message.reply_text(
                f"✅ تم استقبال البطاقات بنجاح!\n"
                f"📊 عدد البطاقات: {cards_count}\n\n"
                f"⏱️ أدخل الفاصل الزمني بالثواني:\n"
                f"مثال: 6"
            )
            
            return CREATE_TASK_INTERVAL
        else:
            await update.message.reply_text(
                "❌ الرسالة لا تحتوي على بطاقات صحيحة!\n\n"
                "📝 التنسيق المطلوب:\n"
                "1234567890123456|12|2025|123\n"
                "9876543210987654|11|2026|456\n\n"
                "أو أرسل ملف .txt"
            )
            return CREATE_TASK_FILE
    
    # حالة 2: ملف نصي
    elif update.message.document:
        # تحميل الملف
        file = await update.message.document.get_file()
        file_content = await file.download_as_bytearray()
        
        # حفظ الملف
        filename = f"cards_{update.effective_user.id}_{update.message.document.file_name}"
        filepath = card_manager.save_cards_file(file_content.decode('utf-8'), filename)
        
        # عد البطاقات
        cards_count = card_manager.count_cards(filepath)
        
        context.user_data['task_file'] = filepath
    else:
        await update.message.reply_text(
            "❌ يرجى إرسال ملف نصي أو رسالة تحتوي على البطاقات.\n\n"
            "📝 مثال على رسالة نصية:\n"
            "1234567890123456|12|2025|123\n"
            "9876543210987654|11|2026|456"
        )
        return CREATE_TASK_FILE
    
    await update.message.reply_text(
        f"✅ تم رفع الملف بنجاح!\n"
        f"📊 عدد البطاقات: {cards_count}\n\n"
        f"⏱️ أدخل الفاصل الزمني بالثواني:\n"
        f"مثال: 6"
    )
    
    return CREATE_TASK_INTERVAL

async def create_task_interval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استقبال الفاصل الزمني وإنشاء المهمة"""
    try:
        interval = int(update.message.text.strip())
        
        if interval < 1:
            await update.message.reply_text("❌ الفاصل الزمني يجب أن يكون 1 ثانية على الأقل.")
            return CREATE_TASK_INTERVAL
        
        # إنشاء المهمة
        task_id = db.add_task(
            context.user_data['task_name'],
            context.user_data['task_session_id'],
            context.user_data['task_bot'],
            context.user_data['task_command'],
            context.user_data['task_file'],
            interval
        )
        
        await update.message.reply_text(
            f"✅ تم إنشاء المهمة بنجاح!\n\n"
            f"📝 الاسم: {context.user_data['task_name']}\n"
            f"🎯 البوت: {context.user_data['task_bot']}\n"
            f"📋 الأمر: {context.user_data['task_command']}\n"
            f"⏱️ الفاصل: {interval}ث\n\n"
            f"يمكنك تشغيلها من قائمة المهام.",
            reply_markup=ReplyKeyboardMarkup([
                ["👥 إدارة الجلسات", "📋 إدارة المهام"],
                ["👁️ مراقبة القروبات", "📊 الإحصائيات"],
                ["ℹ️ المساعدة"]
            ], resize_keyboard=True)
        )
        
        context.user_data.clear()
        return MAIN_MENU
    
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال رقم صحيح.")
        return CREATE_TASK_INTERVAL

# ============= معالجات الأزرار =============

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج ضغطات الأزرار"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    try:
        if data.startswith("session_"):
            session_id = int(data.split("_")[1])
            session = db.get_session(session_id)
            
            if not session:
                await query.edit_message_text("❌ الجلسة غير موجودة.")
                return
            
            keyboard = [
                [InlineKeyboardButton("🔄 تفعيل/تعطيل", callback_data=f"toggle_session_{session_id}")],
                [InlineKeyboardButton("🗑️ حذف", callback_data=f"delete_session_{session_id}")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="back_sessions")]
            ]
            
            from text_formatter import TextFormatter
            text, parse_mode = TextFormatter.format_session_details(session, use_html=False)
            
            await query.edit_message_text(
                text,
                parse_mode=parse_mode,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif data.startswith("toggle_session_"):
            session_id = int(data.split("_")[2])
            db.toggle_session(session_id)
            
            session = db.get_session(session_id)
            
            keyboard = [
                [InlineKeyboardButton("🔄 تفعيل/تعطيل", callback_data=f"toggle_session_{session_id}")],
                [InlineKeyboardButton("🗑️ حذف", callback_data=f"delete_session_{session_id}")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="back_sessions")]
            ]
            
            from text_formatter import TextFormatter
            text, parse_mode = TextFormatter.format_session_details(session, use_html=False)
            
            await query.edit_message_text(
                text,
                parse_mode=parse_mode,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif data.startswith("delete_session_"):
            session_id = int(data.split("_")[2])
            db.delete_session(session_id)
            
            await query.edit_message_text("✅ تم حذف الجلسة بنجاح!")
        
        elif data.startswith("task_"):
            task_id = int(data.split("_")[1])
            task = db.get_task(task_id)
            
            if not task:
                await query.edit_message_text("❌ المهمة غير موجودة.")
                return
            
            stats = db.get_task_stats(task_id)
            
            keyboard = []
            if task['is_running']:
                keyboard.append([InlineKeyboardButton("⏸️ إيقاف", callback_data=f"stop_task_{task_id}")])
            else:
                keyboard.append([InlineKeyboardButton("▶️ تشغيل", callback_data=f"start_task_{task_id}")])
            
            keyboard.append([InlineKeyboardButton("🔄 تحديث الإحصائيات", callback_data=f"refresh_stats_{task_id}")])
            keyboard.append([InlineKeyboardButton("🗑️ حذف", callback_data=f"delete_task_{task_id}")])
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_tasks")])
            
            status = "قيد التشغيل ▶️" if task['is_running'] else "متوقفة ⏸️"
            
            from text_formatter import TextFormatter
            
            # استخدام التنسيق الآمن
            text, parse_mode = TextFormatter.format_task_details(task, stats, use_html=False)
            
            await query.edit_message_text(
                text,
                parse_mode=parse_mode,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif data.startswith("start_task_"):
            task_id = int(data.split("_")[2])
            result = await task_runner.start_task(task_id)
            
            if result:
                await query.answer("✅ تم تشغيل المهمة!")
                db.update_task_status(task_id, True)
            else:
                await query.answer("❌ فشل تشغيل المهمة!")
        
        elif data.startswith("stop_task_"):
            task_id = int(data.split("_")[2])
            await task_runner.stop_task(task_id)
            db.update_task_status(task_id, False)
            
            await query.answer("⏸️ تم إيقاف المهمة!")
        
        elif data.startswith("refresh_stats_"):
            task_id = int(data.split("_")[2])
            task = db.get_task(task_id)
            stats = db.get_task_stats(task_id)
            
            keyboard = []
            if task['is_running']:
                keyboard.append([InlineKeyboardButton("⏸️ إيقاف", callback_data=f"stop_task_{task_id}")])
            else:
                keyboard.append([InlineKeyboardButton("▶️ تشغيل", callback_data=f"start_task_{task_id}")])
            
            keyboard.append([InlineKeyboardButton("🔄 تحديث الإحصائيات", callback_data=f"refresh_stats_{task_id}")])
            keyboard.append([InlineKeyboardButton("🗑️ حذف", callback_data=f"delete_task_{task_id}")])
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_tasks")])
            
            from text_formatter import TextFormatter
            text, parse_mode = TextFormatter.format_task_details(task, stats, use_html=False)
            
            await query.edit_message_text(
                text,
                parse_mode=parse_mode,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            await query.answer("🔄 تم تحديث الإحصائيات!")
        
        elif data.startswith("delete_task_"):
            task_id = int(data.split("_")[2])
            
            # إيقاف المهمة أولاً إذا كانت قيد التشغيل
            result = await task_runner.delete_task(task_id)
            
            # حذف من قاعدة البيانات
            db.delete_task(task_id)
            
            await query.edit_message_text("✅ تم حذف المهمة بنجاح!")
        
        # معالجة callbacks المراقبة
        elif data == "start_add_monitor":
            # بدء إضافة مراقبة جديدة - عرض الجلسات مباشرة
            sessions = db.get_sessions(active_only=True)
            
            if not sessions:
                await query.message.reply_text(
                    "❌ لا توجد جلسات نشطة!\n\n"
                    "أضف جلسة أولاً من 'إدارة الجلسات'"
                )
                await query.answer()
                return ConversationHandler.END
            
            text = "⚡ **إضافة مراقبة جديدة**\n\n👥 **اختر الجلسة:**\n\n"
            for i, session in enumerate(sessions, 1):
                text += f"{i}. 📱 {session['name']} - {session['phone']}\n"
            
            text += "\nأرسل رقم الجلسة:"
            
            context.user_data['available_sessions'] = sessions
            context.user_data['monitor_name'] = "Monitor_" + str(int(time.time()))  # اسم تلقائي
            await query.message.reply_text(text)
            await query.answer()
            return ADD_MONITOR_SESSION
        elif data.startswith(("monitor_", "add_monitor", "start_monitor_", "stop_monitor_", "delete_monitor_")):
            await handle_monitor_callback(query, data, db, group_monitor)
    
    except Exception as e:
        # معالجة أي خطأ يحدث
        error_msg = str(e)
        
        # تجاهل خطأ "Message is not modified" لأنه ليس خطأ حقيقي
        if "Message is not modified" in error_msg:
            logger.info(f"تم تجاهل خطأ 'Message is not modified' - المحتوى لم يتغير")
            return
        
        logger.error(f"خطأ في button_callback: {e}")
        try:
            await query.edit_message_text(
                "❌ حدث خطأ! الرجاء المحاولة مرة أخرى."
            )
        except:
            # إذا فشل edit_message_text
            try:
                await query.message.reply_text(
                    "❌ حدث خطأ! الرجاء المحاولة مرة أخرى."
                )
            except:
                pass

# ============= الإحصائيات والمساعدة =============

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """عرض الإحصائيات العامة"""
    sessions_count = len(db.get_sessions())
    tasks_count = len(db.get_tasks())
    running_tasks = len(db.get_tasks(running_only=True))
    
    text = "📊 **الإحصائيات العامة**\n\n"
    text += f"👥 عدد الجلسات: {sessions_count}\n"
    text += f"📋 عدد المهام: {tasks_count}\n"
    text += f"▶️ المهام قيد التشغيل: {running_tasks}\n"
    
    await update.message.reply_text(text)
    return MAIN_MENU

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """عرض المساعدة"""
    text = """
ℹ️ **دليل الاستخدام**

**1. إدارة الجلسات:**
• أضف جلسة تيليجرام الخاصة بك
• ستحتاج API ID و API Hash من my.telegram.org
• يمكنك إضافة عدة جلسات

**2. إدارة المهام:**
• أنشئ مهمة جديدة
• اختر الجلسة والبوت المستهدف
• حدد الأمر والفاصل الزمني
• ارفع ملف البطاقات

**3. تشغيل المهام:**
• من قائمة المهام، اختر المهمة
• اضغط تشغيل
• راقب الإحصائيات

**للدعم:** @YourSupport
    """
    
    await update.message.reply_text(text)
    return MAIN_MENU

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """إلغاء المحادثة"""
    await update.message.reply_text(
        "تم الإلغاء.",
        reply_markup=ReplyKeyboardMarkup([
            ["👥 إدارة الجلسات", "📋 إدارة المهام"],
            ["👁️ مراقبة القروبات", "📊 الإحصائيات"],
            ["ℹ️ المساعدة"]
        ], resize_keyboard=True)
    )
    context.user_data.clear()
    return MAIN_MENU

# ============= البرنامج الرئيسي =============

def main():
    """تشغيل البوت"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN غير مضبوط!")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # المحادثة الرئيسية
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler)],
            SESSION_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, session_menu_handler)],
            ADD_SESSION_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_session_phone)],
            ADD_SESSION_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_session_api_data)],
            ADD_SESSION_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_session_password)],
            TASK_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_menu_handler)],
            CREATE_TASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_task_name)],
            CREATE_TASK_SESSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_task_session)],
            CREATE_TASK_BOT: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_task_bot)],
            CREATE_TASK_COMMAND: [MessageHandler(filters.TEXT, create_task_command)],
            CREATE_TASK_FILE: [MessageHandler(filters.Document.ALL | filters.TEXT & ~filters.COMMAND, create_task_file)],
            CREATE_TASK_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_task_interval)],
            ADD_MONITOR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_monitor_name)],
            ADD_MONITOR_SESSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_monitor_session)],
            ADD_MONITOR_CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_monitor_chat)],
            ADD_MONITOR_BOT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_monitor_bot)],
            ADD_MONITOR_COMMAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_monitor_command)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # إضافة CallbackQueryHandler قبل ConversationHandler لإعطائه الأولوية
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(conv_handler)
    
    logger.info("🚀 البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
