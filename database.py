"""
نظام قاعدة البيانات لبوت إرسال البطاقات
"""
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from cryptography.fernet import Fernet
import os

class Database:
    def __init__(self, db_path: str = "bot_data.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        
        # مفتاح التشفير للبيانات الحساسة
        encryption_key = os.getenv("DB_ENCRYPTION_KEY", "").strip()
        
        if not encryption_key:
            # توليد مفتاح جديد إذا لم يكن موجود
            new_key = Fernet.generate_key()
            encryption_key = new_key.decode()
            print(f"⚠️ مفتاح تشفير جديد: {encryption_key}")
            print("احفظه في متغير البيئة DB_ENCRYPTION_KEY")
            self.cipher = Fernet(new_key)
        else:
            # استخدام المفتاح الموجود
            try:
                # تأكد من أن المفتاح بصيغة bytes
                if isinstance(encryption_key, str):
                    key_bytes = encryption_key.encode('utf-8')
                else:
                    key_bytes = encryption_key
                self.cipher = Fernet(key_bytes)
            except Exception as e:
                print(f"❌ خطأ في مفتاح التشفير: {e}")
                print("سيتم توليد مفتاح جديد...")
                new_key = Fernet.generate_key()
                encryption_key = new_key.decode()
                print(f"⚠️ مفتاح تشفير جديد: {encryption_key}")
                print("احفظه في متغير البيئة DB_ENCRYPTION_KEY")
                self.cipher = Fernet(new_key)
        
        self.connect()
        self.create_tables()
    
    def connect(self):
        """الاتصال بقاعدة البيانات"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
    
    def create_tables(self):
        """إنشاء الجداول"""
        # جدول الجلسات
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                api_id TEXT NOT NULL,
                api_hash TEXT NOT NULL,
                session_string TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # جدول المهام
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                session_id INTEGER NOT NULL,
                target_bot TEXT NOT NULL,
                command TEXT NOT NULL,
                cards_file TEXT NOT NULL,
                interval_seconds INTEGER DEFAULT 6,
                is_running INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
        """)
        
        # جدول الإحصائيات
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                total_sent INTEGER DEFAULT 0,
                total_success INTEGER DEFAULT 0,
                total_failed INTEGER DEFAULT 0,
                last_card_index INTEGER DEFAULT 0,
                started_at TEXT,
                finished_at TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks (id)
            )
        """)
        
        # جدول السجلات
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                card_data TEXT,
                response TEXT,
                status TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks (id)
            )
        """)
        
        self.conn.commit()
    
    def encrypt_data(self, data: str) -> str:
        """تشفير البيانات"""
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """فك تشفير البيانات"""
        return self.cipher.decrypt(encrypted_data.encode()).decode()
    
    # ========== إدارة الجلسات ==========
    
    def add_session(self, name: str, phone: str, api_id: str, api_hash: str, session_string: str) -> int:
        """إضافة جلسة جديدة"""
        encrypted_session = self.encrypt_data(session_string)
        encrypted_api_hash = self.encrypt_data(api_hash)
        
        self.cursor.execute("""
            INSERT INTO sessions (name, phone, api_id, api_hash, session_string)
            VALUES (?, ?, ?, ?, ?)
        """, (name, phone, api_id, encrypted_api_hash, encrypted_session))
        
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_sessions(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """الحصول على قائمة الجلسات"""
        query = "SELECT * FROM sessions"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY created_at DESC"
        
        self.cursor.execute(query)
        rows = self.cursor.fetchall()
        
        sessions = []
        for row in rows:
            sessions.append({
                'id': row['id'],
                'name': row['name'],
                'phone': row['phone'],
                'api_id': row['api_id'],
                'is_active': bool(row['is_active']),
                'created_at': row['created_at']
            })
        
        return sessions
    
    def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """الحصول على جلسة محددة"""
        self.cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = self.cursor.fetchone()
        
        if not row:
            return None
        
        return {
            'id': row['id'],
            'name': row['name'],
            'phone': row['phone'],
            'api_id': row['api_id'],
            'api_hash': self.decrypt_data(row['api_hash']),
            'session_string': self.decrypt_data(row['session_string']),
            'is_active': bool(row['is_active']),
            'created_at': row['created_at']
        }
    
    def toggle_session(self, session_id: int) -> bool:
        """تفعيل/تعطيل جلسة"""
        self.cursor.execute("SELECT is_active FROM sessions WHERE id = ?", (session_id,))
        row = self.cursor.fetchone()
        
        if not row:
            return False
        
        new_status = 0 if row['is_active'] else 1
        self.cursor.execute("UPDATE sessions SET is_active = ? WHERE id = ?", (new_status, session_id))
        self.conn.commit()
        return True
    
    def delete_session(self, session_id: int) -> bool:
        """حذف جلسة"""
        self.cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    # ========== إدارة المهام ==========
    
    def add_task(self, name: str, session_id: int, target_bot: str, 
                 command: str, cards_file: str, interval_seconds: int) -> int:
        """إضافة مهمة جديدة"""
        self.cursor.execute("""
            INSERT INTO tasks (name, session_id, target_bot, command, cards_file, interval_seconds)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, session_id, target_bot, command, cards_file, interval_seconds))
        
        task_id = self.cursor.lastrowid
        
        # إنشاء سجل إحصائيات للمهمة
        self.cursor.execute("""
            INSERT INTO stats (task_id) VALUES (?)
        """, (task_id,))
        
        self.conn.commit()
        return task_id
    
    def get_tasks(self, running_only: bool = False) -> List[Dict[str, Any]]:
        """الحصول على قائمة المهام"""
        query = """
            SELECT t.*, s.name as session_name 
            FROM tasks t
            LEFT JOIN sessions s ON t.session_id = s.id
        """
        if running_only:
            query += " WHERE t.is_running = 1"
        query += " ORDER BY t.created_at DESC"
        
        self.cursor.execute(query)
        rows = self.cursor.fetchall()
        
        tasks = []
        for row in rows:
            tasks.append({
                'id': row['id'],
                'name': row['name'],
                'session_id': row['session_id'],
                'session_name': row['session_name'],
                'target_bot': row['target_bot'],
                'command': row['command'],
                'cards_file': row['cards_file'],
                'interval_seconds': row['interval_seconds'],
                'is_running': bool(row['is_running']),
                'created_at': row['created_at']
            })
        
        return tasks
    
    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """الحصول على مهمة محددة"""
        self.cursor.execute("""
            SELECT t.*, s.name as session_name 
            FROM tasks t
            LEFT JOIN sessions s ON t.session_id = s.id
            WHERE t.id = ?
        """, (task_id,))
        
        row = self.cursor.fetchone()
        if not row:
            return None
        
        return {
            'id': row['id'],
            'name': row['name'],
            'session_id': row['session_id'],
            'session_name': row['session_name'],
            'target_bot': row['target_bot'],
            'command': row['command'],
            'cards_file': row['cards_file'],
            'interval_seconds': row['interval_seconds'],
            'is_running': bool(row['is_running']),
            'created_at': row['created_at']
        }
    
    def set_task_running(self, task_id: int, is_running: bool) -> bool:
        """تعيين حالة تشغيل المهمة"""
        status = 1 if is_running else 0
        self.cursor.execute("UPDATE tasks SET is_running = ? WHERE id = ?", (status, task_id))
        self.conn.commit()
        return True
    
    def delete_task(self, task_id: int) -> bool:
        """حذف مهمة"""
        # حذف الإحصائيات والسجلات المرتبطة
        self.cursor.execute("DELETE FROM stats WHERE task_id = ?", (task_id,))
        self.cursor.execute("DELETE FROM logs WHERE task_id = ?", (task_id,))
        self.cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()
        return True
    
    # ========== إدارة الإحصائيات ==========
    
    def update_stats(self, task_id: int, sent: int = 0, success: int = 0, 
                     failed: int = 0, last_index: int = None):
        """تحديث إحصائيات المهمة"""
        updates = []
        params = []
        
        if sent > 0:
            updates.append("total_sent = total_sent + ?")
            params.append(sent)
        
        if success > 0:
            updates.append("total_success = total_success + ?")
            params.append(success)
        
        if failed > 0:
            updates.append("total_failed = total_failed + ?")
            params.append(failed)
        
        if last_index is not None:
            updates.append("last_card_index = ?")
            params.append(last_index)
        
        if updates:
            params.append(task_id)
            query = f"UPDATE stats SET {', '.join(updates)} WHERE task_id = ?"
            self.cursor.execute(query, params)
            self.conn.commit()
    
    def get_stats(self, task_id: int) -> Optional[Dict[str, Any]]:
        """الحصول على إحصائيات مهمة"""
        self.cursor.execute("SELECT * FROM stats WHERE task_id = ?", (task_id,))
        row = self.cursor.fetchone()
        
        if not row:
            return None
        
        return {
            'task_id': row['task_id'],
            'total_sent': row['total_sent'],
            'total_success': row['total_success'],
            'total_failed': row['total_failed'],
            'last_card_index': row['last_card_index'],
            'started_at': row['started_at'],
            'finished_at': row['finished_at']
        }
    
    def get_task_stats(self, task_id: int) -> Optional[Dict[str, Any]]:
        """الحصول على إحصائيات مهمة (اسم بديل لـ get_stats)"""
        return self.get_stats(task_id)
    
    def start_task_stats(self, task_id: int):
        """بدء تسجيل إحصائيات المهمة"""
        now = datetime.now().isoformat()
        self.cursor.execute("""
            UPDATE stats SET started_at = ?, finished_at = NULL 
            WHERE task_id = ?
        """, (now, task_id))
        self.conn.commit()
    
    def finish_task_stats(self, task_id: int):
        """إنهاء تسجيل إحصائيات المهمة"""
        now = datetime.now().isoformat()
        self.cursor.execute("UPDATE stats SET finished_at = ? WHERE task_id = ?", (now, task_id))
        self.conn.commit()
    
    # ========== إدارة السجلات ==========
    
    def add_log(self, task_id: int, card_data: str, response: str, status: str):
        """إضافة سجل"""
        self.cursor.execute("""
            INSERT INTO logs (task_id, card_data, response, status)
            VALUES (?, ?, ?, ?)
        """, (task_id, card_data, response, status))
        self.conn.commit()
    
    def get_logs(self, task_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """الحصول على سجلات مهمة"""
        self.cursor.execute("""
            SELECT * FROM logs 
            WHERE task_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (task_id, limit))
        
        rows = self.cursor.fetchall()
        logs = []
        for row in rows:
            logs.append({
                'id': row['id'],
                'task_id': row['task_id'],
                'card_data': row['card_data'],
                'response': row['response'],
                'status': row['status'],
                'created_at': row['created_at']
            })
        
        return logs
    
    def close(self):
        """إغلاق الاتصال بقاعدة البيانات"""
        if self.conn:
            self.conn.close()
