# height_preferences.py - Quản lý độ cao theo người dùng
import os
import sqlite3
import time
from datetime import datetime
import threading
import logging

# Cấu hình logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Đường dẫn đến cơ sở dữ liệu
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_PATH, "data", "usage_stats.db")

class HeightPreferences:
    def __init__(self):
        """Khởi tạo quản lý độ cao"""
        self.db_lock = threading.Lock()
        self._init_database()
        
    def _init_database(self):
        """Khởi tạo cơ sở dữ liệu"""
        try:
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            with self.db_lock:
                with sqlite3.connect(DB_PATH, timeout=10) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS user_heights (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id TEXT,
                            sitting_height REAL,
                            standing_height REAL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES sessions(user_id)
                        )
                    ''')
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS height_history (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id TEXT,
                            position TEXT,
                            height REAL,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES sessions(user_id)
                        )
                    ''')
                    conn.commit()
                    logging.info("Khởi tạo cơ sở dữ liệu height_preferences thành công")
        except Exception as e:
            logging.error(f"Lỗi khởi tạo cơ sở dữ liệu: {e}")
            raise
    
    def save_height(self, user_id, sitting_height=None, standing_height=None):
        """Lưu độ cao cho người dùng"""
        if not user_id:
            logging.error("Không thể lưu độ cao: Thiếu user_id")
            return False
            
        try:
            with self.db_lock:
                with sqlite3.connect(DB_PATH, timeout=10) as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT * FROM user_heights WHERE user_id = ?', (user_id,))
                    user_heights = cursor.fetchone()
                    
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                    
                    if user_heights:
                        update_fields = []
                        params = []
                        
                        if sitting_height is not None:
                            update_fields.append("sitting_height = ?")
                            params.append(sitting_height)
                            cursor.execute(
                                'INSERT INTO height_history (user_id, position, height, timestamp) VALUES (?, ?, ?, ?)',
                                (user_id, 'sit', sitting_height, timestamp)
                            )
                        
                        if standing_height is not None:
                            update_fields.append("standing_height = ?")
                            params.append(standing_height)
                            cursor.execute(
                                'INSERT INTO height_history (user_id, position, height, timestamp) VALUES (?, ?, ?, ?)',
                                (user_id, 'stand', standing_height, timestamp)
                            )
                        
                        if update_fields:
                            update_fields.append("updated_at = ?")
                            params.append(timestamp)
                            params.append(user_id)
                            
                            query = f"UPDATE user_heights SET {', '.join(update_fields)} WHERE user_id = ?"
                            cursor.execute(query, params)
                    else:
                        if sitting_height is None:
                            sitting_height = 0
                        if standing_height is None:
                            standing_height = 0
                        
                        cursor.execute(
                            'INSERT INTO user_heights (user_id, sitting_height, standing_height, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                            (user_id, sitting_height, standing_height, timestamp, timestamp)
                        )
                        
                        if sitting_height > 0:
                            cursor.execute(
                                'INSERT INTO height_history (user_id, position, height, timestamp) VALUES (?, ?, ?, ?)',
                                (user_id, 'sit', sitting_height, timestamp)
                            )
                        
                        if standing_height > 0:
                            cursor.execute(
                                'INSERT INTO height_history (user_id, position, height, timestamp) VALUES (?, ?, ?, ?)',
                                (user_id, 'stand', standing_height, timestamp)
                            )
                    
                    conn.commit()
                    logging.info(f"Đã lưu độ cao cho user_id={user_id}: sitting={sitting_height}, standing={standing_height}")
                    return True
        except Exception as e:
            logging.error(f"Lỗi khi lưu độ cao: {e}")
            return False
    
    def get_heights(self, user_id):
        """Lấy độ cao của người dùng"""
        if not user_id:
            logging.warning("Không có user_id để lấy độ cao")
            return {'sitting': 0, 'standing': 0}
            
        try:
            with self.db_lock:
                with sqlite3.connect(DB_PATH, timeout=10) as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT sitting_height, standing_height FROM user_heights WHERE user_id = ?', (user_id,))
                    result = cursor.fetchone()
                    
                    if result:
                        logging.debug(f"Đã lấy độ cao cho user_id={user_id}: sitting={result[0]}, standing={result[1]}")
                        return {'sitting': result[0], 'standing': result[1]}
                    else:
                        logging.debug(f"Không tìm thấy độ cao cho user_id={user_id}")
                        return {'sitting': 0, 'standing': 0}
        except Exception as e:
            logging.error(f"Lỗi khi lấy độ cao: {e}")
            return {'sitting': 0, 'standing': 0}
    
    def get_all_user_heights(self):
        """Lấy tất cả độ cao của người dùng"""
        try:
            with self.db_lock:
                with sqlite3.connect(DB_PATH, timeout=10) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT uh.user_id, s.user_name, uh.sitting_height, uh.standing_height, uh.updated_at
                        FROM user_heights uh
                        LEFT JOIN sessions s ON uh.user_id = s.user_id
                        GROUP BY uh.user_id
                        ORDER BY s.user_name
                    ''')
                    results = cursor.fetchall()
                    logging.debug(f"All user heights: {results}")
                    return results
        except Exception as e:
            logging.error(f"Lỗi khi lấy tất cả độ cao: {e}")
            return []
    
    def get_height_history(self, user_id=None, limit=10):
        """Lấy lịch sử thay đổi độ cao"""
        try:
            with self.db_lock:
                with sqlite3.connect(DB_PATH, timeout=10) as conn:
                    cursor = conn.cursor()
                    if user_id:
                        cursor.execute('''
                            SELECT h.id, h.user_id, s.user_name, h.position, h.height, h.timestamp
                            FROM height_history h
                            LEFT JOIN sessions s ON h.user_id = s.user_id
                            WHERE h.user_id = ?
                            ORDER BY h.timestamp DESC
                            LIMIT ?
                        ''', (user_id, limit))
                    else:
                        cursor.execute('''
                            SELECT h.id, h.user_id, s.user_name, h.position, h.height, h.timestamp
                            FROM height_history h
                            LEFT JOIN sessions s ON h.user_id = s.user_id
                            ORDER BY h.timestamp DESC
                            LIMIT ?
                        ''', (limit,))
                    results = cursor.fetchall()
                    logging.debug(f"Height history: {results}")
                    return results
        except Exception as e:
            logging.error(f"Lỗi khi lấy lịch sử độ cao: {e}")
            return []

# Tạo instance toàn cục để sử dụng
height_prefs = HeightPreferences()