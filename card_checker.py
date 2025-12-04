"""
نظام فحص البطاقات للمستخدمين
"""
import logging
import asyncio
import re
import time
from typing import List, Dict, Optional
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

class CardChecker:
    def __init__(self, db, session_manager):
        self.db = db
        self.session_manager = session_manager
    
    def parse_card(self, card_line: str) -> Optional[Dict[str, str]]:
        """استخراج معلومات البطاقة من النص"""
        # تنسيق: 4532015112830366|12|2027|123
        # ✅ تحسين: استخدام word boundaries لمنع التطابق الجزئي
        pattern = r'(?<!\d)(\d{15,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})(?!\d)'
        match = re.search(pattern, card_line)
        
        if not match:
            return None
        
        return {
            'number': match.group(1),
            'month': match.group(2).zfill(2),
            'year': match.group(3),
            'cvv': match.group(4)  # ✅ إصلاح: كان group(3) خطأ
        }
    
    def parse_cards(self, text: str) -> List[Dict[str, str]]:
        """استخراج جميع البطاقات من النص"""
        cards = []
        lines = text.strip().split('\n')
        
        for line in lines:
            card = self.parse_card(line)
            if card:
                cards.append(card)
        
        return cards
    
    async def check_card(self, card: Dict[str, str], checker_bot: str, session_id: int) -> Dict[str, any]:
        """فحص بطاقة واحدة"""
        try:
            # تنسيق البطاقة أولاً (للاستخدام في حالات الخطأ)
            card_text = f"{card['number']}|{card['month']}|{card['year']}|{card['cvv']}"
            
            # تحميل الجلسة
            session = self.db.get_session(session_id)
            if not session:
                return {
                    'card': card,
                    'card_text': card_text,  # ✅ إضافة
                    'status': 'error',
                    'response': 'الجلسة غير موجودة'
                }
            
            # تحميل client
            success = await self.session_manager.load_session(
                session_id,
                session['api_id'],
                session['api_hash'],
                session['session_string']
            )
            
            if not success:
                return {
                    'card': card,
                    'card_text': card_text,  # ✅ إضافة
                    'status': 'error',
                    'response': 'فشل تحميل الجلسة'
                }
            
            # ✅ إصلاح: استخدام active_clients مباشرة
            if session_id not in self.session_manager.active_clients:
                return {
                    'card': card,
                    'card_text': card_text,  # ✅ إضافة
                    'status': 'error',
                    'response': 'الجلسة غير محملة'
                }
            
            client = self.session_manager.active_clients[session_id]
            
            # ✅ إضافة: استخدام lock لحماية من Race Conditions
            lock = await self.session_manager.get_lock(session_id)
            
            # ✅ حفظ وقت الإرسال
            import time
            send_time = time.time()
            
            # إرسال للبوت المستهدف (داخل lock)
            async with lock:
                try:
                    # ✅ إضافة: إرسال أمر الفحص قبل البطاقة
                    message_to_send = f"/chk {card_text}"
                    await client.send_message(checker_bot, message_to_send)
                    # ✅ تحديث وقت الاستخدام
                    self.session_manager.update_last_used(session_id)
                except ValueError as e:
                    # ✅ معالجة خاصة: البوت غير صحيح
                    logger.error(f"البوت غير صحيح: {checker_bot}")
                    return {
                        'card': card,
                        'card_text': card_text,
                        'status': 'error',
                        'response': f'البوت غير صحيح: {checker_bot}'
                    }
                except Exception as e:
                    # ✅ معالجة خاصة: أخطاء أخرى
                    logger.error(f"فشل إرسال الرسالة: {e}")
                    return {
                        'card': card,
                        'card_text': card_text,
                        'status': 'error',
                        'response': f'فشل إرسال الرسالة: {str(e)}'
                    }
            
            # ✅ الانتظار (خارج lock) - للسماح لمستخدمين آخرين بالاستخدام
            await asyncio.sleep(13)
            
            # الحصول على الرد (داخل lock)
            async with lock:
                # ✅ الحصول على عدة رسائل للتأكد
                messages = await client.get_messages(checker_bot, limit=5)
                
                # ✅ البحث عن الرسالة الصحيحة (بعد وقت الإرسال)
                response_text = None
                my_id = (await client.get_me()).id
                
                for msg in messages:
                    # التحقق من أن الرسالة بعد وقت الإرسال
                    if msg.date.timestamp() > send_time:
                        # التحقق من أن الرسالة من البوت (وليس منا)
                        if msg.sender_id != my_id:
                            response_text = msg.text
                            break
                
                # إذا لم نجد رسالة صحيحة، استخدم الأحدث
                if not response_text and messages:
                    response_text = messages[0].text
                
                messages = [type('obj', (object,), {'text': response_text})()] if response_text else []
            
            if not messages:
                return {
                    'card': card,
                    'card_text': card_text,  # ✅ إضافة
                    'status': 'error',
                    'response': 'لم يرد البوت'
                }
            
            response_text = messages[0].text
            
            # تحليل النتيجة
            status = self.analyze_response(response_text)
            
            return {
                'card': card,
                'card_text': card_text,
                'status': status,
                'response': response_text
            }
            
        except Exception as e:
            logger.error(f"خطأ في فحص البطاقة: {e}")
            # ✅ محاولة تنسيق card_text إذا كان card موجود
            try:
                card_text = f"{card['number']}|{card['month']}|{card['year']}|{card['cvv']}"
            except:
                card_text = str(card)
            return {
                'card': card,
                'card_text': card_text,  # ✅ إضافة
                'status': 'error',
                'response': str(e)
            }
    
    def analyze_response(self, response: str) -> str:
        """تحليل رد البوت لتحديد النتيجة"""
        response_lower = response.lower()
        
        # ✅ كلمات الفشل (تُفحص أولاً - أكثر أهمية!)
        failure_keywords = ['declined', 'failed', 'error', 'insufficient', 'فشل', 'dead', 'invalid']
        
        # ✅ كلمات النجاح (بدون 'live' - غامضة)
        success_keywords = ['approved', 'success', 'charged', 'نجح', 'authenticated']
        
        # ✅ فحص الفشل أولاً!
        for keyword in failure_keywords:
            if keyword in response_lower:
                return 'declined'
        
        # ✅ ثم فحص النجاح
        for keyword in success_keywords:
            if keyword in response_lower:
                return 'approved'
        
        return 'unknown'
    
    def extract_info(self, response: str) -> Dict[str, str]:
        """استخراج معلومات إضافية من الرد"""
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
        
        # استخراج Response
        response_match = re.search(r'Response[:\s]+([^\n]+)', response, re.IGNORECASE)
        if response_match:
            info['message'] = response_match.group(1).strip()
        
        return info
    
    async def check_cards_batch(self, cards: List[Dict[str, str]], checker_bot: str, 
                                session_id: int, delay: int = 13, 
                                on_result_callback=None) -> List[Dict[str, any]]:
        """فحص مجموعة بطاقات
        
        Args:
            on_result_callback: دالة يتم استدعاؤها فوراً عند نجاح أي بطاقة
        """
        results = []
        
        for i, card in enumerate(cards, 1):
            logger.info(f"فحص البطاقة {i}/{len(cards)}")
            
            result = await self.check_card(card, checker_bot, session_id)
            results.append(result)
            
            # ✅ إرسال فوري عند النجاح
            if on_result_callback and result['status'] == 'approved':
                await on_result_callback(result)
            
            # ✅ إزالة الانتظار المضاعف - الانتظار موجود بالفعل في check_card
            # لا حاجة للانتظار هنا
        
        return results
    
    def format_result(self, result: Dict[str, any]) -> str:
        """تنسيق نتيجة الفحص للعرض"""
        card_text = result.get('card_text', '')
        status = result['status']
        
        if status == 'approved':
            emoji = "✅"
            status_text = "ناجحة"
        elif status == 'declined':
            emoji = "❌"
            status_text = "فاشلة"
        else:
            emoji = "❓"
            status_text = "غير محدد"
        
        text = f"{emoji} **{status_text}**\n\n"
        text += f"💳 البطاقة: `{card_text}`\n"
        
        # استخراج معلومات إضافية
        info = self.extract_info(result['response'])
        
        if 'bank' in info:
            text += f"🏦 البنك: {info['bank']}\n"
        if 'country' in info:
            text += f"🌍 الدولة: {info['country']}\n"
        if 'gateway' in info:
            text += f"🔗 Gateway: {info['gateway']}\n"
        if 'message' in info:
            text += f"📝 الرد: {info['message']}\n"
        
        return text
    
    def format_summary(self, results: List[Dict[str, any]]) -> str:
        """تنسيق ملخص النتائج"""
        approved = sum(1 for r in results if r['status'] == 'approved')
        declined = sum(1 for r in results if r['status'] == 'declined')
        errors = sum(1 for r in results if r['status'] == 'error')
        unknown = sum(1 for r in results if r['status'] == 'unknown')
        
        text = "📊 **ملخص النتائج:**\n\n"
        text += f"✅ ناجحة: {approved}\n"
        text += f"❌ فاشلة: {declined}\n"
        
        if unknown > 0:
            text += f"❓ غير محدد: {unknown}\n"
        if errors > 0:
            text += f"⚠️ أخطاء: {errors}\n"
        
        text += f"\n**المجموع: {len(results)} بطاقة**"
        
        return text
