"""
معالج إضافة الجلسات للمستخدمين
"""
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

# حالات المحادثة
USER_ADD_SESSION_PHONE, USER_ADD_SESSION_API, USER_ADD_SESSION_CODE, USER_ADD_SESSION_PASSWORD = range(4)

async def cmd_addsession_user(update: Update, context: ContextTypes.DEFAULT_TYPE, db) -> int:
    """بدء إضافة جلسة للمستخدم"""
    user_id = update.effective_user.id
    
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("⛔ لست مسجلاً في النظام!\n\n📞 اتصل بالمدير: @tkttx")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📱 **إضافة جلسة**\n\n"
        "سأطلب منك المعلومات التالية:\n"
        "1. رقم الهاتف\n"
        "2. API ID\n"
        "3. API Hash\n"
        "4. كود التحقق\n\n"
        "💡 احصل على API ID و Hash من:\n"
        "https://my.telegram.org/apps\n\n"
        "📞 أرسل رقم هاتفك الآن (مثال: +1234567890):",
        parse_mode='Markdown'
    )
    
    return USER_ADD_SESSION_PHONE

async def user_add_session_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استلام رقم الهاتف"""
    phone = update.message.text.strip()
    
    if not phone.startswith('+'):
        await update.message.reply_text(
            "❌ رقم الهاتف يجب أن يبدأ بـ +\n\n"
            "مثال: +1234567890\n\n"
            "أرسل رقم هاتفك مرة أخرى:"
        )
        return USER_ADD_SESSION_PHONE
    
    context.user_data['user_session_phone'] = phone
    
    await update.message.reply_text(
        "✅ تم حفظ رقم الهاتف!\n\n"
        "🔑 الآن أرسل **API ID** (رقم فقط):",
        parse_mode='Markdown'
    )
    
    return USER_ADD_SESSION_API

async def user_add_session_api(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استلام API ID و API Hash"""
    text = update.message.text.strip()
    
    # إذا كان API ID (رقم)
    if 'user_session_api_id' not in context.user_data:
        if not text.isdigit():
            await update.message.reply_text(
                "❌ API ID يجب أن يكون رقماً!\n\n"
                "أرسل API ID مرة أخرى:"
            )
            return USER_ADD_SESSION_API
        
        context.user_data['user_session_api_id'] = text
        
        await update.message.reply_text(
            "✅ تم حفظ API ID!\n\n"
            "🔐 الآن أرسل **API Hash**:",
            parse_mode='Markdown'
        )
        
        return USER_ADD_SESSION_API
    
    # إذا كان API Hash
    context.user_data['user_session_api_hash'] = text
    
    # بدء عملية تسجيل الدخول
    from session_manager import SessionManager
    session_manager = SessionManager()
    
    phone = context.user_data['user_session_phone']
    api_id = context.user_data['user_session_api_id']
    api_hash = context.user_data['user_session_api_hash']
    
    try:
        # إرسال كود التحقق
        result = await session_manager.create_session(phone, api_id, api_hash)
        
        if result['status'] != 'code_sent':
            await update.message.reply_text(
                f"❌ {result['message']}\n\n"
                "جرّب مرة أخرى: /addsession"
            )
            context.user_data.clear()
            return ConversationHandler.END
        
        # حفظ phone_code_hash
        context.user_data['phone_code_hash'] = result['phone_code_hash']
        
        await update.message.reply_text(
            "✅ تم إرسال كود التحقق!\n\n"
            "📲 تحقق من تطبيق تليجرام وأرسل الكود هنا:",
            parse_mode='Markdown'
        )
        
        return USER_ADD_SESSION_CODE
        
    except Exception as e:
        logger.error(f"خطأ في إرسال الكود: {e}")
        await update.message.reply_text(
            f"❌ خطأ في إرسال الكود:\n{str(e)}\n\n"
            "جرّب مرة أخرى: /addsession"
        )
        context.user_data.clear()
        return ConversationHandler.END

async def user_add_session_code(update: Update, context: ContextTypes.DEFAULT_TYPE, db, session_manager) -> int:
    """استلام كود التحقق"""
    code = update.message.text.strip().replace('-', '').replace(' ', '')
    
    phone = context.user_data['user_session_phone']
    api_id = context.user_data['user_session_api_id']
    api_hash = context.user_data['user_session_api_hash']
    phone_code_hash = context.user_data['phone_code_hash']
    
    try:
        # التحقق من الكود
        result = await session_manager.verify_code(phone, code, phone_code_hash, api_id, api_hash)
        
        if result['status'] == 'password_required':
            # يحتاج كلمة مرور - حفظ الكود للاستخدام لاحقاً
            context.user_data['code'] = code
            await update.message.reply_text(
                "🔐 **كلمة المرور مطلوبة**\n\n"
                "أرسل كلمة مرور التحقق بخطوتين:",
                parse_mode='Markdown'
            )
            return USER_ADD_SESSION_PASSWORD
        
        if result['status'] != 'success':
            await update.message.reply_text(
                f"❌ {result['message']}\n\n"
                "جرّب مرة أخرى: /addsession"
            )
            context.user_data.clear()
            return ConversationHandler.END
        
        session_string = result['session_string']
        
        # حفظ الجلسة
        session_id = db.add_session(
            name=f"User_{update.effective_user.id}",
            phone=phone,
            api_id=api_id,
            api_hash=api_hash,
            session_string=session_string
        )
        
        # ربط الجلسة بالمستخدم
        db.update_user_session(update.effective_user.id, session_id)
        
        await update.message.reply_text(
            "✅ **تم إضافة الجلسة بنجاح!**\n\n"
            "🎉 الآن يمكنك فحص البطاقات!\n\n"
            "💳 أرسل بطاقة أو كومبو للبدء:",
            parse_mode='Markdown'
        )
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"خطأ في تسجيل الدخول: {e}")
        await update.message.reply_text(
            f"❌ خطأ في تسجيل الدخول:\n{str(e)}\n\n"
            "تأكد من الكود وجرّب مرة أخرى: /addsession"
        )
        context.user_data.clear()
        return ConversationHandler.END

async def user_add_session_password(update: Update, context: ContextTypes.DEFAULT_TYPE, db, session_manager) -> int:
    """استلام كلمة المرور"""
    password = update.message.text.strip()
    
    phone = context.user_data['user_session_phone']
    api_id = context.user_data['user_session_api_id']
    api_hash = context.user_data['user_session_api_hash']
    
    try:
        # التحقق من كلمة المرور فقط
        result = await session_manager.verify_password(phone, password)
        
        if result['status'] != 'success':
            await update.message.reply_text(
                f"❌ {result['message']}\n\n"
                "جرّب مرة أخرى: /addsession"
            )
            context.user_data.clear()
            return ConversationHandler.END
        
        session_string = result['session_string']
        
        # حفظ الجلسة
        session_id = db.add_session(
            name=f"User_{update.effective_user.id}",
            phone=phone,
            api_id=api_id,
            api_hash=api_hash,
            session_string=session_string
        )
        
        # ربط الجلسة بالمستخدم
        db.update_user_session(update.effective_user.id, session_id)
        
        await update.message.reply_text(
            "✅ **تم إضافة الجلسة بنجاح!**\n\n"
            "🎉 الآن يمكنك فحص البطاقات!\n\n"
            "💳 أرسل بطاقة أو كومبو للبدء:",
            parse_mode='Markdown'
        )
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"خطأ في تسجيل الدخول بكلمة المرور: {e}")
        await update.message.reply_text(
            f"❌ خطأ في تسجيل الدخول:\n{str(e)}\n\n"
            "تأكد من كلمة المرور وجرّب مرة أخرى: /addsession"
        )
        context.user_data.clear()
        return ConversationHandler.END

async def cancel_user_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """إلغاء إضافة الجلسة"""
    await update.message.reply_text(
        "❌ تم إلغاء إضافة الجلسة.\n\n"
        "يمكنك المحاولة مرة أخرى: /addsession"
    )
    context.user_data.clear()
    return ConversationHandler.END
