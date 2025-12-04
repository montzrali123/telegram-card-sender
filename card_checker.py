"""
نظام فحص البطاقات للمستخدمين
"""
import logging
import asyncio
import re
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
        pattern = r'(\d{15,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})'
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
            # تحميل الجلسة
            session = self.db.get_session(session_id)
            if not session:
                return {
                    'card': card,
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
                    'status': 'error',
                    'response': 'فشل تحميل الجلسة'
                }
            
            # ✅ إصلاح: استخدام active_clients مباشرة
            if session_id not in self.session_manager.active_clients:
                return {
                    'card': card,
                    'status': 'error',
                    'response': 'الجلسة غير محملة'
                }
            
            client = self.session_manager.active_clients[session_id]
            
            # تنسيق البطاقة
            card_text = f"{card['number']}|{card['month']}|{card['year']}|{card['cvv']}"
            
            # إرسال للبوت المستهدف
            # ✅ تحسين: دعم أوامر مختلفة
            await client.send_message(checker_bot, card_text)
            
            # ✅ تحسين: وقت انتظار 13 ثانية (كما حدده المستخدم)
            await asyncio.sleep(13)
            
            # الحصول على آخر رسالة من البوت
            messages = await client.get_messages(checker_bot, limit=1)
            
            if not messages:
                return {
                    'card': card,
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
            return {
                'card': card,
                'status': 'error',
                'response': str(e)
            }
    
    def analyze_response(self, response: str) -> str:
        """تحليل رد البوت لتحديد النتيجة"""
        response_lower = response.lower()
        
        # كلمات النجاح
        success_keywords = ['approved', 'success', 'charged', 'نجح', 'live']
        
        # كلمات الفشل
        failure_keywords = ['declined', 'failed', 'error', 'insufficient', 'فشل', 'dead']
        
        for keyword in success_keywords:
            if keyword in response_lower:
                return 'approved'
        
        for keyword in failure_keywords:
            if keyword in response_lower:
                return 'declined'
        
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
                                session_id: int, delay: int = 13) -> List[Dict[str, any]]:
        """فحص مجموعة بطاقات"""
        results = []
        
        for i, card in enumerate(cards, 1):
            logger.info(f"فحص البطاقة {i}/{len(cards)}")
            
            result = await self.check_card(card, checker_bot, session_id)
            results.append(result)
            
            # تأخير بين البطاقات (إلا الأخيرة)
            if i < len(cards):
                await asyncio.sleep(delay)
        
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
