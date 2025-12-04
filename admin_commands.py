"""
أوامر المدير لإدارة المستخدمين
"""
import logging
import os
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# معرّف المدير من متغير البيئة
OWNER_ID = int(os.getenv('OWNER_ID', 0))

def is_admin(user_id: int) -> bool:
    """التحقق من أن المستخدم هو المدير"""
    return user_id == OWNER_ID

async def cmd_adduser(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """إضافة مستخدم جديد: /adduser @username BotName"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ هذا الأمر للمدير فقط!")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ الاستخدام الصحيح:\n\n"
            "/adduser @username BotName\n"
            "أو\n"
            "/adduser 123456789 BotName"
        )
        return
    
    # استخراج المعلومات
    user_input = context.args[0]
    checker_bot = context.args[1]
    
    # تحديد telegram_id و username
    if user_input.startswith('@'):
        username = user_input
        telegram_id = None  # سنحصل عليه لاحقاً
        await update.message.reply_text(
            "⚠️ لإضافة مستخدم بالـ username، يجب أن يرسل /start للبوت أولاً!\n\n"
            "استخدم معرّف التليجرام بدلاً من ذلك:\n"
            f"/adduser [telegram_id] {checker_bot}"
        )
        return
    else:
        try:
            telegram_id = int(user_input)
            username = None
        except ValueError:
            await update.message.reply_text("❌ معرّف التليجرام يجب أن يكون رقماً!")
            return
    
    # إضافة المستخدم
    success = db.add_user(telegram_id, username, checker_bot, user_id)
    
    if success:
        await update.message.reply_text(
            f"✅ تم إضافة المستخدم!\n\n"
            f"👤 المعرّف: {telegram_id}\n"
            f"🤖 البوت: {checker_bot}\n"
            f"📅 التاريخ: الآن\n\n"
            f"💡 الآن المستخدم يستطيع فحص البطاقات!"
        )
        logger.info(f"تم إضافة مستخدم: {telegram_id} - {checker_bot}")
    else:
        await update.message.reply_text("❌ المستخدم موجود مسبقاً!")

async def cmd_listusers(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """عرض جميع المستخدمين: /listusers"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ هذا الأمر للمدير فقط!")
        return
    
    users = db.get_all_users()
    
    if not users:
        await update.message.reply_text("📭 لا يوجد مستخدمين مسجلين بعد!")
        return
    
    text = "👥 **المستخدمين المسجلين:**\n\n"
    
    for i, user in enumerate(users, 1):
        status = "✅" if user['is_active'] else "❌"
        username_display = f"@{user['username']}" if user['username'] else f"ID: {user['telegram_id']}"
        session_status = "📱 جلسة مضافة" if user['session_id'] else "⚠️ لم يضف جلسة"
        
        text += (
            f"{i}. {username_display} {status}\n"
            f"   🤖 البوت: {user['checker_bot']}\n"
            f"   {session_status}\n"
            f"   📅 {user['added_at'][:10]}\n\n"
        )
    
    text += f"**المجموع: {len(users)} مستخدم**"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def cmd_removeuser(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """حذف مستخدم: /removeuser @username أو /removeuser 123456789"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ هذا الأمر للمدير فقط!")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text(
            "❌ الاستخدام الصحيح:\n\n"
            "/removeuser @username\n"
            "أو\n"
            "/removeuser 123456789"
        )
        return
    
    user_input = context.args[0]
    
    # تحديد telegram_id
    if user_input.startswith('@'):
        await update.message.reply_text(
            "⚠️ استخدم معرّف التليجرام بدلاً من username:\n"
            "/removeuser [telegram_id]"
        )
        return
    else:
        try:
            telegram_id = int(user_input)
        except ValueError:
            await update.message.reply_text("❌ معرّف التليجرام يجب أن يكون رقماً!")
            return
    
    # حذف المستخدم
    success = db.remove_user(telegram_id)
    
    if success:
        await update.message.reply_text(f"✅ تم حذف المستخدم {telegram_id} بنجاح!")
        logger.info(f"تم حذف مستخدم: {telegram_id}")
    else:
        await update.message.reply_text("❌ المستخدم غير موجود!")

async def cmd_toggleuser(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """تفعيل/تعطيل مستخدم: /toggleuser 123456789"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ هذا الأمر للمدير فقط!")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text(
            "❌ الاستخدام الصحيح:\n\n"
            "/toggleuser 123456789"
        )
        return
    
    try:
        telegram_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ معرّف التليجرام يجب أن يكون رقماً!")
        return
    
    # تفعيل/تعطيل المستخدم
    success = db.toggle_user(telegram_id)
    
    if success:
        user = db.get_user(telegram_id)
        status = "مفعّل ✅" if user['is_active'] else "معطّل ❌"
        await update.message.reply_text(f"✅ المستخدم {telegram_id} الآن {status}")
        logger.info(f"تم تغيير حالة مستخدم: {telegram_id} - {status}")
    else:
        await update.message.reply_text("❌ المستخدم غير موجود!")
