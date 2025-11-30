"""
نظام مراقبة القروبات/القنوات واستخراج البطاقات تلقائياً
"""
import re
import logging
import asyncio
from typing import Optional, List, Dict, Any
from telethon import TelegramClient, events
from telethon.tl.types import Message

logger = logging.getLogger(__name__)


class CardExtractor:
    """استخراج ذكي للبطاقات من النصوص"""
    
    # Pattern للبطاقات: 16 رقم|شهر|سنة|CVV
    CARD_PATTERN = re.compile(
        r'(\d{13,19})\s*[\|:;,\-]\s*(\d{1,2})\s*[\|:;,\-]\s*(\d{2,4})\s*[\|:;,\-]\s*(\d{3,4})'
    )
    
    @staticmethod
    def extract_cards(text: str) -> List[str]:
        """
        استخراج جميع البطاقات من النص
        
        Args:
            text: النص المراد البحث فيه
            
        Returns:
            قائمة بالبطاقات بالتنسيق: card|mm|yyyy|cvv
        """
        if not text:
            return []
        
        cards = []
        matches = CardExtractor.CARD_PATTERN.findall(text)
        
        for match in matches:
            card_number, month, year, cvv = match
            
            # تنظيف البيانات
            card_number = card_number.strip()
            month = month.strip().zfill(2)  # إضافة 0 إذا كان رقم واحد
            year = year.strip()
            cvv = cvv.strip()
            
            # تحويل السنة إلى 4 أرقام إذا كانت رقمين
            if len(year) == 2:
                year = '20' + year
            
            # التحقق من صحة البيانات
            if (13 <= len(card_number) <= 19 and
                1 <= int(month) <= 12 and
                2024 <= int(year) <= 2050 and
                len(cvv) in [3, 4]):
                
                # تنسيق البطاقة
                card = f"{card_number}|{month}|{year}|{cvv}"
                cards.append(card)
        
        return cards
    
    @staticmethod
    def extract_first_card(text: str) -> Optional[str]:
        """استخراج أول بطاقة من النص"""
        cards = CardExtractor.extract_cards(text)
        return cards[0] if cards else None


class GroupMonitor:
    """مراقبة القروبات/القنوات واستخراج البطاقات"""
    
    def __init__(self, session_manager, db):
        """
        Args:
            session_manager: مدير الجلسات
            db: قاعدة البيانات
        """
        self.session_manager = session_manager
        self.db = db
        self.active_monitors = {}  # {monitor_id: client}
        self.card_extractor = CardExtractor()
    
    async def start_monitor(self, monitor_id: int) -> bool:
        """
        بدء مراقبة قروب/قناة
        
        Args:
            monitor_id: معرف المراقبة
            
        Returns:
            True إذا نجح البدء
        """
        try:
            # جلب معلومات المراقبة
            monitor = self.db.get_monitor(monitor_id)
            if not monitor:
                logger.error(f"المراقبة {monitor_id} غير موجودة")
                return False
            
            # تحميل الجلسة
            session = self.db.get_session(monitor['session_id'])
            if not session:
                logger.error(f"الجلسة {monitor['session_id']} غير موجودة")
                return False
            
            success = await self.session_manager.load_session(
                monitor['session_id'],
                session['api_id'],
                session['api_hash'],
                session['session_string']
            )
            if not success:
                logger.error(f"فشل تحميل الجلسة {monitor['session_id']}")
                return False
            
            client = self.session_manager.get_client(monitor['session_id'])
            if not client:
                logger.error(f"فشل الحصول على client للجلسة {monitor['session_id']}")
                return False
            
            # إعداد معالج الرسائل
            @client.on(events.NewMessage(chats=monitor['chat_id']))
            async def message_handler(event: events.NewMessage.Event):
                await self._handle_new_message(monitor_id, event)
            
            # حفظ الـ client
            self.active_monitors[monitor_id] = client
            
            # تحديث حالة المراقبة
            self.db.update_monitor_status(monitor_id, True)
            
            logger.info(f"✅ بدأت مراقبة {monitor_id} للقروب {monitor['chat_id']}")
            return True
            
        except Exception as e:
            logger.error(f"خطأ في بدء المراقبة {monitor_id}: {e}")
            return False
    
    async def stop_monitor(self, monitor_id: int):
        """إيقاف مراقبة قروب/قناة"""
        try:
            if monitor_id in self.active_monitors:
                client = self.active_monitors[monitor_id]
                # إزالة معالج الرسائل
                client.remove_event_handler(client.list_event_handlers()[0])
                del self.active_monitors[monitor_id]
                
                # تحديث حالة المراقبة
                self.db.update_monitor_status(monitor_id, False)
                
                logger.info(f"⏸️ تم إيقاف المراقبة {monitor_id}")
        except Exception as e:
            logger.error(f"خطأ في إيقاف المراقبة {monitor_id}: {e}")
    
    async def _handle_new_message(self, monitor_id: int, event: events.NewMessage.Event):
        """معالجة رسالة جديدة من القروب/القناة"""
        try:
            message: Message = event.message
            text = message.text or message.message or ""
            
            if not text:
                return
            
            # استخراج البطاقات من الرسالة
            cards = self.card_extractor.extract_cards(text)
            
            if not cards:
                return
            
            logger.info(f"🔍 تم العثور على {len(cards)} بطاقة في المراقبة {monitor_id}")
            
            # جلب معلومات المراقبة
            monitor = self.db.get_monitor(monitor_id)
            if not monitor:
                return
            
            # معالجة كل بطاقة
            for card in cards:
                await self._process_card(monitor, card)
                
        except Exception as e:
            logger.error(f"خطأ في معالجة الرسالة للمراقبة {monitor_id}: {e}")
    
    async def _process_card(self, monitor: Dict[str, Any], card: str):
        """معالجة بطاقة مستخرجة"""
        try:
            # حفظ البطاقة في قاعدة البيانات
            self.db.add_extracted_card(
                monitor['id'],
                card,
                monitor['target_bot'],
                monitor['target_command']
            )
            
            # إرسال البطاقة للبوت المستهدف
            if monitor['auto_send']:
                await self._send_to_target_bot(monitor, card)
            
            logger.info(f"✅ تمت معالجة البطاقة: {card[:4]}****")
            
        except Exception as e:
            logger.error(f"خطأ في معالجة البطاقة: {e}")
    
    async def _send_to_target_bot(self, monitor: Dict[str, Any], card: str):
        """إرسال البطاقة للبوت المستهدف"""
        try:
            # الحصول على الجلسة النشطة
            client = self.session_manager.get_client(monitor['session_id'])
            if not client:
                logger.error(f"الجلسة {monitor['session_id']} غير نشطة")
                return
            
            # إرسال الأمر للبوت
            await client.send_message(
                monitor['target_bot'],
                monitor['target_command']
            )
            
            # انتظار قصير
            await asyncio.sleep(1)
            
            # إرسال البطاقة
            await client.send_message(
                monitor['target_bot'],
                card
            )
            
            logger.info(f"📤 تم إرسال البطاقة إلى {monitor['target_bot']}")
            
        except Exception as e:
            logger.error(f"خطأ في إرسال البطاقة للبوت المستهدف: {e}")
    
    async def start_all_monitors(self):
        """بدء جميع المراقبات النشطة"""
        try:
            monitors = self.db.get_monitors(active_only=True)
            
            for monitor in monitors:
                await self.start_monitor(monitor['id'])
            
            logger.info(f"✅ تم بدء {len(monitors)} مراقبة")
            
        except Exception as e:
            logger.error(f"خطأ في بدء جميع المراقبات: {e}")
    
    async def stop_all_monitors(self):
        """إيقاف جميع المراقبات"""
        try:
            monitor_ids = list(self.active_monitors.keys())
            
            for monitor_id in monitor_ids:
                await self.stop_monitor(monitor_id)
            
            logger.info(f"⏸️ تم إيقاف جميع المراقبات")
            
        except Exception as e:
            logger.error(f"خطأ في إيقاف جميع المراقبات: {e}")
