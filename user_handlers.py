"""
معالجات المستخدمين العاديين
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def handle_check_cards(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                             db, card_checker, notifier):
    """معالج فحص البطاقات للمستخدمين"""
    user_id = update.effective_user.id
    
    # التحقق من المستخدم
    user = db.get_user(user_id)
    
    if not user:
        await update.message.reply_text("⛔ لست مسجلاً في النظام!")
        return
    
    if not user['is_active']:
        await update.message.reply_text("⛔ حسابك معطّل!")
        return
    
    # التحقق من الجلسة
    if not user['session_id']:
        await update.message.reply_text(
            "⚠️ لم تضف جلسة بعد!\n\n"
            "استخدم /addsession لإضافة جلستك."
        )
        return
    
    # استخراج البطاقات
    text = ""
    
    # إذا كان ملف
    if update.message.document:
        file = await update.message.document.get_file()
        file_content = await file.download_as_bytearray()
        text = file_content.decode('utf-8', errors='ignore')
    # إذا كان نص
    elif update.message.text:
        text = update.message.text
    
    cards = card_checker.parse_cards(text)
    
    if not cards:
        await update.message.reply_text(
            "❌ لم أجد بطاقات صحيحة!\n\n"
            "التنسيق الصحيح:\n"
            "`4532015112830366|12|2027|123`",
            parse_mode='Markdown'
        )
        return
    
    # التحقق من الحد الأقصى
    max_cards = user['max_cards_per_check']
    if len(cards) > max_cards:
        await update.message.reply_text(
            f"⚠️ الحد الأقصى: {max_cards} بطاقة!\n\n"
            f"أنت أرسلت {len(cards)} بطاقة."
        )
        return
    
    # إرسال رسالة البدء
    progress_msg = await update.message.reply_text(
        f"⏳ جاري الفحص...\n\n"
        f"📊 البطاقات: {len(cards)}\n"
        f"🤖 البوت: {user['checker_bot']}"
    )
    
    # ✅ دالة callback لإرسال البطاقات الناجحة فوراً
    async def on_approved_card(result):
        # إرسال للمستخدم
        result_text = card_checker.format_result(result)
        await update.message.reply_text(result_text, parse_mode='Markdown')
        
        # إشعار المدير
        if notifier:
            await notifier.notify_approved_card(user, result)
    
    # فحص البطاقات مع callback
    results = await card_checker.check_cards_batch(
        cards,
        user['checker_bot'],
        user['session_id'],
        user['delay_between_cards'],
        on_result_callback=on_approved_card  # ✅ إرسال فوري
    )
    
    # إرسال النتائج المتبقية (الفاشلة وغير المحددة)
    for i, result in enumerate(results, 1):
        # تخطي الناجحة (تم إرسالها فوراً)
        if result['status'] != 'approved':
            result_text = card_checker.format_result(result)
            await update.message.reply_text(result_text, parse_mode='Markdown')
    
    # إرسال الملخص
    summary = card_checker.format_summary(results)
    await update.message.reply_text(summary, parse_mode='Markdown')
    
    # حذف رسالة التقدم
    try:
        await progress_msg.delete()
    except:
        pass
    
    logger.info(f"تم فحص {len(cards)} بطاقة للمستخدم {user_id}")

async def cmd_addsession_user(update: Update, context: ContextTypes.DEFAULT_TYPE, db, session_manager):
    """إضافة جلسة للمستخدم"""
    user_id = update.effective_user.id
    
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("⛔ لست مسجلاً في النظام!")
        return
    
    await update.message.reply_text(
        "📱 **إضافة جلسة**\n\n"
        "سأطلب منك المعلومات التالية:\n"
        "1. رقم الهاتف\n"
        "2. API ID\n"
        "3. API Hash\n"
        "4. كود التحقق\n\n"
        "💡 احصل على API ID و Hash من:\n"
        "https://my.telegram.org/apps\n\n"
        "أرسل /cancel للإلغاء",
        parse_mode='Markdown'
    )
    
    # هنا يمكن إضافة ConversationHandler لإضافة الجلسة
    # لكن لتبسيط الأمور، سنتركه للمرحلة التالية

async def show_user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """عرض إحصائيات المستخدم"""
    user_id = update.effective_user.id
    
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("⛔ لست مسجلاً في النظام!")
        return
    
    text = "📊 **إحصائياتك:**\n\n"
    text += f"👤 المعرّف: {user['telegram_id']}\n"
    text += f"🤖 البوت: {user['checker_bot']}\n"
    text += f"📅 تاريخ التسجيل: {user['added_at'][:10]}\n"
    text += f"🔢 الحد الأقصى: {user['max_cards_per_check']} بطاقة\n"
    text += f"⏱️ التأخير: {user['delay_between_cards']} ثانية\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')
