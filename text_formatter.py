"""
نظام تنسيق النصوص الآمن
"""
from telegram.constants import ParseMode
from html import escape as html_escape
import re

class TextFormatter:
    """تنسيق النصوص بشكل آمن لتجنب أخطاء parsing"""
    
    @staticmethod
    def escape_markdown_v2(text: str) -> str:
        """تنظيف النص لـ MarkdownV2"""
        # الأحرف الخاصة في MarkdownV2
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        
        return text
    
    @staticmethod
    def escape_html(text: str) -> str:
        """تنظيف النص لـ HTML"""
        return html_escape(text, quote=False)
    
    @staticmethod
    def format_task_details(task: dict, stats: dict, use_html: bool = False) -> str:
        """تنسيق تفاصيل المهمة بشكل آمن"""
        status = "قيد التشغيل ▶️" if task['is_running'] else "متوقفة ⏸️"
        
        if use_html:
            # استخدام HTML (أكثر أماناً)
            text = (
                f"📋 <b>المهمة: {html_escape(task['name'])}</b>\n\n"
                f"الجلسة: {html_escape(task['session_name'])}\n"
                f"البوت المستهدف: {html_escape(task['target_bot'])}\n"
                f"الأمر: <code>{html_escape(task['command'])}</code>\n"
                f"الفاصل الزمني: {task['interval_seconds']}ث\n"
                f"الحالة: {status}\n\n"
                f"📊 <b>الإحصائيات:</b>\n"
                f"المرسل: {stats['total_sent']}\n"
                f"الناجح: {stats['total_success']}\n"
                f"الفاشل: {stats['total_failed']}\n\n"
                f"ℹ️ اضغط '🔄 تحديث الإحصائيات' للتحديث"
            )
            return text, ParseMode.HTML
        else:
            # بدون تنسيق (الأكثر أماناً)
            text = (
                f"📋 المهمة: {task['name']}\n\n"
                f"الجلسة: {task['session_name']}\n"
                f"البوت المستهدف: {task['target_bot']}\n"
                f"الأمر: {task['command']}\n"
                f"الفاصل الزمني: {task['interval_seconds']}ث\n"
                f"الحالة: {status}\n\n"
                f"📊 الإحصائيات:\n"
                f"المرسل: {stats['total_sent']}\n"
                f"الناجح: {stats['total_success']}\n"
                f"الفاشل: {stats['total_failed']}\n\n"
                f"ℹ️ اضغط '🔄 تحديث الإحصائيات' للتحديث"
            )
            return text, None
    
    @staticmethod
    def format_session_details(session: dict, use_html: bool = False) -> str:
        """تنسيق تفاصيل الجلسة بشكل آمن"""
        status = "مفعلة ✅" if session['is_active'] else "معطلة ❌"
        
        # معالجة تاريخ الإضافة
        created_at = session.get('created_at', 'غير متوفر')
        if created_at and created_at != 'غير متوفر':
            created_at = created_at[:10]
        
        if use_html:
            text = (
                f"📱 <b>الجلسة: {html_escape(session['name'])}</b>\n\n"
                f"رقم الهاتف: <code>{html_escape(session['phone'])}</code>\n"
                f"الحالة: {status}\n"
                f"تاريخ الإضافة: {created_at}"
            )
            return text, ParseMode.HTML
        else:
            text = (
                f"📱 الجلسة: {session['name']}\n\n"
                f"رقم الهاتف: {session['phone']}\n"
                f"الحالة: {status}\n"
                f"تاريخ الإضافة: {created_at}"
            )
            return text, None
    
    @staticmethod
    def safe_send_message(text: str, force_plain: bool = False):
        """
        إرجاع النص والـ parse_mode المناسب
        
        Args:
            text: النص المراد إرساله
            force_plain: إجبار إرسال بدون تنسيق
        
        Returns:
            tuple: (text, parse_mode)
        """
        if force_plain:
            # إزالة جميع علامات HTML/Markdown
            text = re.sub(r'<[^>]+>', '', text)  # إزالة HTML tags
            text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # إزالة **bold**
            text = re.sub(r'__([^_]+)__', r'\1', text)  # إزالة __italic__
            text = re.sub(r'`([^`]+)`', r'\1', text)  # إزالة `code`
            return text, None
        
        # محاولة استخدام HTML
        try:
            # التحقق من وجود HTML tags
            if '<' in text and '>' in text:
                return text, ParseMode.HTML
        except:
            pass
        
        # إذا فشل، إرسال بدون تنسيق
        return text, None
