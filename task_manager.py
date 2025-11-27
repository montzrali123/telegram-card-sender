"""
نظام إدارة المهام والبطاقات
"""
import asyncio
import os
from typing import Optional, List, Dict
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class CardFileManager:
    """إدارة ملفات البطاقات"""
    
    def __init__(self, cards_dir: str = "cards"):
        self.cards_dir = cards_dir
        os.makedirs(cards_dir, exist_ok=True)
    
    def save_cards_file(self, file_content: str, filename: str) -> str:
        """حفظ ملف البطاقات"""
        filepath = os.path.join(self.cards_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(file_content)
        
        return filepath
    
    def read_cards(self, filepath: str) -> List[str]:
        """قراءة البطاقات من الملف"""
        if not os.path.exists(filepath):
            return []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            cards = [line.strip() for line in f if line.strip()]
        
        return cards
    
    def count_cards(self, filepath: str) -> int:
        """عد البطاقات في الملف"""
        return len(self.read_cards(filepath))
    
    def get_card_at_index(self, filepath: str, index: int) -> Optional[str]:
        """الحصول على بطاقة في موضع محدد"""
        cards = self.read_cards(filepath)
        if 0 <= index < len(cards):
            return cards[index]
        return None
    
    def delete_file(self, filepath: str) -> bool:
        """حذف ملف البطاقات"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
            return False
        except Exception as e:
            logger.error(f"خطأ في حذف الملف: {e}")
            return False


class TaskRunner:
    """تشغيل المهام"""
    
    def __init__(self, database, session_manager, card_manager):
        self.db = database
        self.session_manager = session_manager
        self.card_manager = card_manager
        self.running_tasks: Dict[int, asyncio.Task] = {}
        self.stop_flags: Dict[int, bool] = {}
    
    async def start_task(self, task_id: int) -> Dict[str, str]:
        """بدء تشغيل مهمة"""
        try:
            # التحقق من أن المهمة ليست قيد التشغيل
            if task_id in self.running_tasks:
                return {
                    'status': 'error',
                    'message': 'المهمة قيد التشغيل بالفعل'
                }
            
            # الحصول على بيانات المهمة
            task = self.db.get_task(task_id)
            if not task:
                return {
                    'status': 'error',
                    'message': 'المهمة غير موجودة'
                }
            
            # الحصول على بيانات الجلسة
            session = self.db.get_session(task['session_id'])
            if not session:
                return {
                    'status': 'error',
                    'message': 'الجلسة غير موجودة'
                }
            
            if not session['is_active']:
                return {
                    'status': 'error',
                    'message': 'الجلسة غير مفعلة'
                }
            
            # تحميل الجلسة إذا لم تكن محملة
            if not self.session_manager.is_session_loaded(session['id']):
                loaded = await self.session_manager.load_session(
                    session['id'],
                    session['api_id'],
                    session['api_hash'],
                    session['session_string']
                )
                
                if not loaded:
                    return {
                        'status': 'error',
                        'message': 'فشل تحميل الجلسة'
                    }
            
            # تحديث حالة المهمة
            self.db.set_task_running(task_id, True)
            self.db.start_task_stats(task_id)
            
            # إنشاء علم الإيقاف
            self.stop_flags[task_id] = False
            
            # بدء المهمة في الخلفية
            task_coroutine = self._run_task(task_id, task, session)
            self.running_tasks[task_id] = asyncio.create_task(task_coroutine)
            
            logger.info(f"تم بدء المهمة {task_id}")
            
            return {
                'status': 'success',
                'message': f'تم بدء المهمة: {task["name"]}'
            }
        
        except Exception as e:
            logger.error(f"خطأ في بدء المهمة {task_id}: {e}")
            return {
                'status': 'error',
                'message': f'خطأ: {str(e)}'
            }
    
    async def _run_task(self, task_id: int, task: Dict, session: Dict):
        """تشغيل المهمة الفعلي"""
        try:
            # قراءة البطاقات
            cards = self.card_manager.read_cards(task['cards_file'])
            total_cards = len(cards)
            
            if total_cards == 0:
                logger.warning(f"المهمة {task_id}: لا توجد بطاقات في الملف")
                self.db.set_task_running(task_id, False)
                return
            
            # الحصول على آخر موضع
            stats = self.db.get_stats(task_id)
            start_index = stats['last_card_index'] if stats else 0
            
            logger.info(f"المهمة {task_id}: بدء الإرسال من البطاقة {start_index}/{total_cards}")
            
            # إرسال البطاقات
            for i in range(start_index, total_cards):
                # التحقق من علم الإيقاف
                if self.stop_flags.get(task_id, False):
                    logger.info(f"المهمة {task_id}: تم إيقافها بواسطة المستخدم")
                    break
                
                card = cards[i]
                
                # تكوين الرسالة
                message = f"{task['command']} {card}"
                
                # إرسال الرسالة
                result = await self.session_manager.send_message(
                    session['id'],
                    task['target_bot'],
                    message
                )
                
                # تسجيل النتيجة
                if result['status'] == 'success':
                    self.db.update_stats(task_id, sent=1, success=1, last_index=i+1)
                    self.db.add_log(task_id, card, result.get('response', ''), 'success')
                    logger.info(f"المهمة {task_id}: تم إرسال البطاقة {i+1}/{total_cards} بنجاح")
                else:
                    self.db.update_stats(task_id, sent=1, failed=1, last_index=i+1)
                    self.db.add_log(task_id, card, result.get('message', ''), 'failed')
                    logger.error(f"المهمة {task_id}: فشل إرسال البطاقة {i+1}/{total_cards}")
                
                # الانتظار حسب الفاصل الزمني
                if i < total_cards - 1:  # لا ننتظر بعد آخر بطاقة
                    await asyncio.sleep(task['interval_seconds'])
            
            # إنهاء المهمة
            self.db.set_task_running(task_id, False)
            self.db.finish_task_stats(task_id)
            
            logger.info(f"المهمة {task_id}: اكتملت بنجاح")
        
        except Exception as e:
            logger.error(f"خطأ في تشغيل المهمة {task_id}: {e}")
            self.db.set_task_running(task_id, False)
        
        finally:
            # تنظيف
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            if task_id in self.stop_flags:
                del self.stop_flags[task_id]
    
    async def stop_task(self, task_id: int) -> Dict[str, str]:
        """إيقاف مهمة"""
        try:
            if task_id not in self.running_tasks:
                return {
                    'status': 'error',
                    'message': 'المهمة ليست قيد التشغيل'
                }
            
            # تعيين علم الإيقاف
            self.stop_flags[task_id] = True
            
            # الانتظار حتى تتوقف المهمة
            await asyncio.sleep(1)
            
            # تحديث حالة المهمة
            self.db.set_task_running(task_id, False)
            
            logger.info(f"تم إيقاف المهمة {task_id}")
            
            return {
                'status': 'success',
                'message': 'تم إيقاف المهمة بنجاح'
            }
        
        except Exception as e:
            logger.error(f"خطأ في إيقاف المهمة {task_id}: {e}")
            return {
                'status': 'error',
                'message': f'خطأ: {str(e)}'
            }
    
    async def stop_all_tasks(self):
        """إيقاف جميع المهام"""
        for task_id in list(self.running_tasks.keys()):
            await self.stop_task(task_id)
    
    def get_running_tasks_count(self) -> int:
        """الحصول على عدد المهام قيد التشغيل"""
        return len(self.running_tasks)
    
    def is_task_running(self, task_id: int) -> bool:
        """التحقق من تشغيل المهمة"""
        return task_id in self.running_tasks
