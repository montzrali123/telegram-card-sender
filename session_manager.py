"""
نظام إدارة جلسات Telegram
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self):
        self.active_clients: Dict[int, TelegramClient] = {}
    
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
            
            return {
                'status': 'code_sent',
                'message': 'تم إرسال كود التحقق. أدخل الكود الآن.',
                'phone_code_hash': result.phone_code_hash,
                'client_id': id(client)  # معرف مؤقت للعميل
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
            client = TelegramClient(StringSession(), api_id, api_hash)
            await client.connect()
            
            try:
                # تسجيل الدخول بالكود
                await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                if password:
                    await client.sign_in(password=password)
                else:
                    return {
                        'status': 'password_required',
                        'message': 'الحساب محمي بكلمة مرور. أدخل كلمة المرور.'
                    }
            
            # الحصول على session string
            session_string = client.session.save()
            
            # الحصول على معلومات المستخدم
            me = await client.get_me()
            
            await client.disconnect()
            
            return {
                'status': 'success',
                'message': f'تم تسجيل الدخول بنجاح كـ {me.first_name}',
                'session_string': session_string,
                'user_id': me.id,
                'username': me.username or 'بدون معرف'
            }
        
        except PhoneCodeInvalidError:
            return {
                'status': 'error',
                'message': 'كود التحقق غير صحيح. حاول مرة أخرى.'
            }
        except Exception as e:
            logger.error(f"خطأ في التحقق من الكود: {e}")
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
