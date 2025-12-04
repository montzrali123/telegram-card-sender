"""
نظام إدارة جلسات Telegram
"""
import asyncio
import time
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self):
        self.active_clients: Dict[int, TelegramClient] = {}
        self.temp_clients: Dict[str, TelegramClient] = {}  # للاحتفاظ بالـ clients المؤقتة
        self.session_locks: Dict[int, asyncio.Lock] = {}  # ✅ إضافة: locks لكل جلسة
        self.last_used: Dict[int, float] = {}  # ✅ إضافة: آخر استخدام لكل جلسة
    
    async def create_session(self, phone: str, api_id: str, api_hash: str) -> Dict[str, str]:
        """
        إنشاء جلسة جديدة
        يعيد: {'session_string': str, 'status': str, 'message': str}
        """
        try:
            # إنشاء عميل مؤقت
            client = TelegramClient(StringSession(), api_id, api_hash)
            await client.connect()
            
            # إرسال كود التحقق
            result = await client.send_code_request(phone)
            
            # حفظ الـ client للاستخدام لاحقاً
            self.temp_clients[phone] = client
            
            return {
                'status': 'code_sent',
                'message': 'تم إرسال كود التحقق. أدخل الكود الآن.',
                'phone_code_hash': result.phone_code_hash
            }
        
        except Exception as e:
            logger.error(f"خطأ في إنشاء الجلسة: {e}")
            return {
                'status': 'error',
                'message': f'خطأ: {str(e)}'
            }
    
    async def verify_code(self, phone: str, code: str, phone_code_hash: str, 
                          api_id: str, api_hash: str, password: Optional[str] = None) -> Dict[str, str]:
        """
        التحقق من كود التأكيد والحصول على session string
        """
        try:
            # استخدام الـ client المحفوظ
            if phone not in self.temp_clients:
                logger.error(f"Client not found for phone: {phone}")
                return {
                    'status': 'error',
                    'message': 'الجلسة منتهية. ابدأ من جديد بـ /addsession'
                }
            
            client = self.temp_clients[phone]
            
            try:
                # تسجيل الدخول بالكود
                logger.info(f"Attempting sign_in for {phone}")
                await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
                logger.info(f"Sign_in successful for {phone}")
                
            except SessionPasswordNeededError:
                logger.info(f"Password required for {phone}")
                if password:
                    # تسجيل الدخول بكلمة المرور
                    logger.info(f"Attempting sign_in with password for {phone}")
                    await client.sign_in(password=password)
                    logger.info(f"Sign_in with password successful for {phone}")
                else:
                    # كلمة المرور مطلوبة - لا تحذف الـ client
                    logger.info(f"Returning password_required for {phone}")
                    return {
                        'status': 'password_required',
                        'message': 'الحساب محمي بكلمة مرور. أدخل كلمة المرور.'
                    }
            
            # الحصول على session string
            session_string = client.session.save()
            logger.info(f"Session string obtained for {phone}")
            
            # الحصول على معلومات المستخدم
            me = await client.get_me()
            logger.info(f"User info obtained: {me.first_name}")
            
            # قطع الاتصال
            await client.disconnect()
            logger.info(f"Client disconnected for {phone}")
            
            # حذف الـ client المؤقت (فقط بعد النجاح الكامل)
            if phone in self.temp_clients:
                del self.temp_clients[phone]
                logger.info(f"Temp client deleted for {phone}")
            
            return {
                'status': 'success',
                'message': f'تم تسجيل الدخول بنجاح كـ {me.first_name}',
                'session_string': session_string,
                'user_id': me.id,
                'username': me.username or 'بدون معرف'
            }
        
        except PhoneCodeInvalidError:
            logger.error(f"Invalid phone code for {phone}")
            return {
                'status': 'error',
                'message': 'كود التحقق غير صحيح. حاول مرة أخرى.'
            }
        except Exception as e:
            logger.error(f"خطأ في التحقق من الكود: {e}", exc_info=True)
            return {
                'status': 'error',
                'message': f'خطأ: {str(e)}'
            }
    
    async def verify_password(self, phone: str, password: str) -> Dict[str, str]:
        """
        التحقق من كلمة المرور بعد طلبها
        """
        try:
            # استخدام الـ client المحفوظ
            if phone not in self.temp_clients:
                logger.error(f"Client not found for phone: {phone}")
                return {
                    'status': 'error',
                    'message': 'الجلسة منتهية. ابدأ من جديد بـ /addsession'
                }
            
            client = self.temp_clients[phone]
            logger.info(f"Attempting sign_in with password for {phone}")
            
            try:
                # تسجيل الدخول بكلمة المرور
                await client.sign_in(password=password)
                logger.info(f"Sign_in with password successful for {phone}")
                
            except Exception as e:
                logger.error(f"Password sign_in failed: {e}")
                return {
                    'status': 'error',
                    'message': f'كلمة المرور غير صحيحة. حاول مرة أخرى.'
                }
            
            # الحصول على session string
            session_string = client.session.save()
            logger.info(f"Session string obtained for {phone}")
            
            # الحصول على معلومات المستخدم
            me = await client.get_me()
            logger.info(f"User info obtained: {me.first_name}")
            
            # قطع الاتصال
            await client.disconnect()
            logger.info(f"Client disconnected for {phone}")
            
            # حذف الـ client المؤقت
            if phone in self.temp_clients:
                del self.temp_clients[phone]
                logger.info(f"Temp client deleted for {phone}")
            
            return {
                'status': 'success',
                'message': f'تم تسجيل الدخول بنجاح كـ {me.first_name}',
                'session_string': session_string,
                'user_id': me.id,
                'username': me.username or 'بدون معرّف'
            }
            
        except Exception as e:
            logger.error(f"خطأ في التحقق من كلمة المرور: {e}", exc_info=True)
            return {
                'status': 'error',
                'message': f'خطأ: {str(e)}'
            }
    
    async def load_session(self, session_id: int, api_id: str, api_hash: str, 
                          session_string: str) -> bool:
        """تحميل جلسة موجودة"""
        try:
            if session_id in self.active_clients:
                return True
            
            client = TelegramClient(StringSession(session_string), api_id, api_hash)
            await client.connect()
            
            # التحقق من صلاحية الجلسة
            if not await client.is_user_authorized():
                logger.error(f"الجلسة {session_id} غير مصرح بها")
                return False
            
            self.active_clients[session_id] = client
            self.update_last_used(session_id)  # ✅ تحديث وقت الاستخدام
            logger.info(f"تم تحميل الجلسة {session_id} بنجاح")
            return True
        
        except Exception as e:
            logger.error(f"خطأ في تحميل الجلسة {session_id}: {e}")
            return False
    
    async def send_message(self, session_id: int, target_bot: str, message: str) -> Dict[str, any]:
        """إرسال رسالة من جلسة محددة"""
        try:
            if session_id not in self.active_clients:
                return {
                    'status': 'error',
                    'message': 'الجلسة غير محملة'
                }
            
            client = self.active_clients[session_id]
            
            # إرسال الرسالة
            result = await client.send_message(target_bot, message)
            
            # انتظار الرد (اختياري)
            await asyncio.sleep(1)
            
            # محاولة الحصول على آخر رسالة من البوت
            messages = await client.get_messages(target_bot, limit=1)
            response_text = messages[0].text if messages else "لا يوجد رد"
            
            return {
                'status': 'success',
                'message': 'تم الإرسال بنجاح',
                'response': response_text,
                'message_id': result.id
            }
        
        except Exception as e:
            logger.error(f"خطأ في إرسال الرسالة: {e}")
            return {
                'status': 'error',
                'message': f'خطأ: {str(e)}',
                'response': None
            }
    
    async def unload_session(self, session_id: int):
        """إلغاء تحميل جلسة"""
        if session_id in self.active_clients:
            client = self.active_clients[session_id]
            await client.disconnect()
            del self.active_clients[session_id]
            logger.info(f"تم إلغاء تحميل الجلسة {session_id}")
    
    async def unload_all_sessions(self):
        """إلغاء تحميل جميع الجلسات"""
        for session_id in list(self.active_clients.keys()):
            await self.unload_session(session_id)
    
    def is_session_loaded(self, session_id: int) -> bool:
        """التحقق من تحميل الجلسة"""
        return session_id in self.active_clients
    
    async def get_lock(self, session_id: int) -> asyncio.Lock:
        """✅ الحصول على lock للجلسة (لحماية من Race Conditions)"""
        if session_id not in self.session_locks:
            self.session_locks[session_id] = asyncio.Lock()
        return self.session_locks[session_id]
    
    def update_last_used(self, session_id: int):
        """✅ تحديث وقت آخر استخدام للجلسة"""
        self.last_used[session_id] = time.time()
    
    async def cleanup_inactive_sessions(self, timeout: int = 3600):
        """✅ إغلاق الجلسات غير المستخدمة لأكثر من timeout ثانية"""
        current_time = time.time()
        sessions_to_unload = []
        
        for session_id, last_used_time in self.last_used.items():
            if current_time - last_used_time > timeout:
                sessions_to_unload.append(session_id)
        
        for session_id in sessions_to_unload:
            logger.info(f"✅ إغلاق جلسة غير مستخدمة: {session_id}")
            await self.unload_session(session_id)
            if session_id in self.last_used:
                del self.last_used[session_id]
            if session_id in self.session_locks:
                del self.session_locks[session_id]
