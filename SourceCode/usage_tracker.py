# usage_tracker.py - Theo dõi thời gian sử dụng
import os
import sqlite3
import time
from datetime import datetime
import threading
import logging

# Cấu hình logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Đường dẫn đến file database
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_PATH, "data", "usage_stats.db")

class UsageTracker:
    def __init__(self):
        """Khởi tạo theo dõi thời gian sử dụng"""
        self.tracking_active = False
        self.current_session = None
        self.tracking_thread = None
        self.stop_thread = False
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
                        CREATE TABLE IF NOT EXISTS sessions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id TEXT UNIQUE,
                            user_name TEXT,
                            start_time TIMESTAMP,
                            end_time TIMESTAMP,
                            duration REAL,
                            notes TEXT
                        )
                    ''')
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS positions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            session_id INTEGER,
                            user_id TEXT,
                            position TEXT,
                            start_time TIMESTAMP,
                            end_time TIMESTAMP,
                            duration REAL,
                            FOREIGN KEY (session_id) REFERENCES sessions(id)
                        )
                    ''')
                    conn.commit()
                    logging.info("Khởi tạo cơ sở dữ liệu usage_tracker thành công")
        except Exception as e:
            logging.error(f"Lỗi khởi tạo cơ sở dữ liệu: {e}")
            raise
    
    def start_tracking(self, user_id=None, user_name=None, position=None):
        """Bắt đầu theo dõi thời gian sử dụng"""
        try:
            if self.tracking_active:
                self.stop_tracking()
            
            if user_id is None:
                with self.db_lock:
                    with sqlite3.connect(DB_PATH, timeout=10) as conn:
                        cursor = conn.cursor()
                        if user_name:
                            cursor.execute('SELECT user_id FROM sessions WHERE user_name = ? GROUP BY user_id', (user_name,))
                            result = cursor.fetchone()
                            if result:
                                user_id = result[0]
                        if user_id is None:
                            cursor.execute('SELECT MAX(user_id) FROM sessions')
                            result = cursor.fetchone()
                            user_id = str(int(result[0]) + 1 if result[0] else 1)
            
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            self.current_session = {
                'user_id': user_id,
                'user_name': user_name or f"Người dùng {user_id}",
                'start_time': current_time,
                'position': position or "unknown"
            }
            
            self.tracking_active = True
            self.stop_thread = False
            
            self.tracking_thread = threading.Thread(target=self._tracking_thread)
            self.tracking_thread.daemon = True
            self.tracking_thread.start()
            
            logging.info(f"Bắt đầu theo dõi thời gian cho {self.current_session['user_name']} (ID: {user_id})")
            return self.current_session
        except Exception as e:
            logging.error(f"Lỗi khi bắt đầu theo dõi: {e}")
            raise
    
    def stop_tracking(self):
        """Dừng theo dõi và lưu thông tin"""
        if not self.tracking_active:
            logging.warning("Không có phiên đang hoạt động để dừng")
            return None
        
        try:
            self.tracking_active = False
            self.stop_thread = True
            
            if self.tracking_thread and self.tracking_thread.is_alive():
                self.tracking_thread.join(timeout=2)
            
            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            start_time_obj = datetime.strptime(self.current_session['start_time'], "%Y-%m-%d %H:%M:%S.%f")
            end_time_obj = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S.%f")
            duration = (end_time_obj - start_time_obj).total_seconds()
            
            self.current_session['end_time'] = end_time
            self.current_session['duration'] = duration
            
            with self.db_lock:
                with sqlite3.connect(DB_PATH, timeout=10) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO sessions (user_id, user_name, start_time, end_time, duration, notes)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        self.current_session['user_id'],
                        self.current_session['user_name'],
                        self.current_session['start_time'],
                        self.current_session['end_time'],
                        self.current_session['duration'],
                        self.current_session.get('notes', '')
                    ))
                    
                    session_id = cursor.lastrowid
                    
                    cursor.execute('''
                        INSERT INTO positions (session_id, user_id, position, start_time, end_time, duration)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        session_id,
                        self.current_session['user_id'],
                        self.current_session['position'],
                        self.current_session['start_time'],
                        self.current_session['end_time'],
                        self.current_session['duration']
                    ))
                    
                    conn.commit()
                    logging.info(f"Kết thúc theo dõi cho {self.current_session['user_name']} sau {duration:.1f} giây")
            
            session_data = self.current_session.copy()
            self.current_session = None
            return session_data
        except Exception as e:
            logging.error(f"Lỗi khi dừng theo dõi: {e}")
            raise
    
    def update_position(self, position):
        """Cập nhật vị trí ngồi/đứng"""
        if not self.tracking_active or not self.current_session:
            logging.warning("Không có phiên hoạt động để cập nhật vị trí")
            return
        
        try:
            if self.current_session['position'] == position:
                return
            
            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            start_time_obj = datetime.strptime(self.current_session['start_time'], "%Y-%m-%d %H:%M:%S.%f")
            end_time_obj = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S.%f")
            duration = (end_time_obj - start_time_obj).total_seconds()
            
            with self.db_lock:
                with sqlite3.connect(DB_PATH, timeout=10) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT id FROM sessions 
                        WHERE user_id = ? 
                        ORDER BY start_time DESC LIMIT 1
                    ''', (self.current_session['user_id'],))
                    
                    result = cursor.fetchone()
                    if result:
                        session_id = result[0]
                        cursor.execute('''
                            INSERT INTO positions (session_id, user_id, position, start_time, end_time, duration)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            session_id,
                            self.current_session['user_id'],
                            self.current_session['position'],
                            self.current_session['start_time'],
                            end_time,
                            duration
                        ))
                        conn.commit()
            
            self.current_session['position'] = position
            self.current_session['start_time'] = end_time
            logging.info(f"Đã cập nhật vị trí thành {position} cho user_id={self.current_session['user_id']}")
        except Exception as e:
            logging.error(f"Lỗi khi cập nhật vị trí: {e}")
            raise
    
    def log_position(self, user_id, position):
        """Ghi trạng thái vị trí ngồi/đứng"""
        try:
            with self.db_lock:
                with sqlite3.connect(DB_PATH, timeout=10) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT id FROM sessions 
                        WHERE user_id = ? AND end_time IS NULL
                        ORDER BY start_time DESC LIMIT 1
                    ''', (user_id,))
                    result = cursor.fetchone()
                    if not result:
                        logging.warning(f"Không tìm thấy phiên đang hoạt động cho user_id={user_id}")
                        return
                    session_id = result[0]
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                    cursor.execute('''
                        INSERT INTO positions (session_id, user_id, position, start_time, end_time, duration)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        session_id,
                        user_id,
                        position,
                        current_time,
                        current_time,
                        0
                    ))
                    conn.commit()
                    logging.info(f"Đã ghi trạng thái {position} cho user_id={user_id}, session_id={session_id}")
        except Exception as e:
            logging.error(f"Lỗi khi ghi trạng thái vị trí: {e}")
            raise
    
    def add_notes(self, notes):
        """Thêm ghi chú cho phiên hiện tại"""
        if self.tracking_active and self.current_session:
            self.current_session['notes'] = notes
            logging.info(f"Đã thêm ghi chú: {notes}")
    
    def _tracking_thread(self):
        """Thread theo dõi thời gian"""
        save_interval = 60
        last_save_time = time.time()
        
        while not self.stop_thread:
            current_time = time.time()
            
            if current_time - last_save_time >= save_interval:
                self._save_session_state()
                last_save_time = current_time
            
            time.sleep(1)
    
    def _save_session_state(self):
        """Lưu trạng thái phiên hiện tại"""
        if not self.tracking_active or not self.current_session:
            return
        
        try:
            now = datetime.now()
            start_time_obj = datetime.strptime(self.current_session['start_time'], "%Y-%m-%d %H:%M:%S.%f")
            temp_duration = (now - start_time_obj).total_seconds()
            
            with self.db_lock:
                with sqlite3.connect(DB_PATH, timeout=10) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT id FROM sessions 
                        WHERE user_id = ? AND end_time IS NULL
                        ORDER BY start_time DESC LIMIT 1
                    ''', (self.current_session['user_id'],))
                    
                    result = cursor.fetchone()
                    
                    if result:
                        session_id = result[0]
                        cursor.execute('''
                            UPDATE sessions 
                            SET duration = ? 
                            WHERE id = ?
                        ''', (temp_duration, session_id))
                    else:
                        cursor.execute('''
                            INSERT INTO sessions (user_id, user_name, start_time, duration, notes)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            self.current_session['user_id'],
                            self.current_session['user_name'],
                            self.current_session['start_time'],
                            temp_duration,
                            self.current_session.get('notes', '')
                        ))
                        
                        session_id = cursor.lastrowid
                        
                        cursor.execute('''
                            INSERT INTO positions (session_id, user_id, position, start_time, duration)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            session_id,
                            self.current_session['user_id'],
                            self.current_session['position'],
                            self.current_session['start_time'],
                            temp_duration
                        ))
                    
                    conn.commit()
                    logging.debug(f"Đã lưu trạng thái phiên cho user_id={self.current_session['user_id']}")
        except Exception as e:
            logging.error(f"Lỗi khi lưu trạng thái phiên: {e}")
    
    def get_current_user(self):
        """Lấy thông tin người dùng hiện tại"""
        if not self.tracking_active or not self.current_session:
            return None
        
        return {
            'user_id': self.current_session.get('user_id'),
            'user_name': self.current_session.get('user_name')
        }
    
    def get_user_stats(self):
        """Lấy thống kê theo người dùng"""
        try:
            with self.db_lock:
                with sqlite3.connect(DB_PATH, timeout=10) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT 
                            COALESCE(user_name, 'Không xác định') as user,
                            SUM(duration) as total_duration,
                            COUNT(*) as session_count,
                            AVG(duration) as avg_duration
                        FROM sessions
                        GROUP BY user_id
                        ORDER BY total_duration DESC
                    ''')
                    result = cursor.fetchall()
                    logging.debug(f"User stats: {result}")
                    return result
        except Exception as e:
            logging.error(f"Lỗi khi lấy thống kê người dùng: {e}")
            return []
    
    def get_position_stats(self):
        """Lấy thống kê theo vị trí"""
        try:
            with self.db_lock:
                with sqlite3.connect(DB_PATH, timeout=10) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT 
                            position,
                            SUM(duration) as total_duration,
                            COUNT(*) as position_count
                        FROM positions
                        GROUP BY position
                        ORDER BY total_duration DESC
                    ''')
                    result = cursor.fetchall()
                    logging.debug(f"Position stats: {result}")
                    return result
        except Exception as e:
            logging.error(f"Lỗi khi lấy thống kê vị trí: {e}")
            return []
    
    def get_daily_stats(self, days=7):
        """Lấy thống kê theo ngày"""
        try:
            end_date = datetime.now()
            start_date = end_date - datetime.timedelta(days=days-1)
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            start_date_str = start_date.strftime("%Y-%m-%d")
            
            with self.db_lock:
                with sqlite3.connect(DB_PATH, timeout=10) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT 
                            date(start_time) as day,
                            SUM(duration) as total_duration
                        FROM sessions
                        WHERE date(start_time) >= ?
                        GROUP BY day
                        ORDER BY day
                    ''', (start_date_str,))
                    result = cursor.fetchall()
            
            days_data = {}
            for day, duration in result:
                days_data[day] = duration
            
            days_list = []
            durations_list = []
            
            for i in range(days):
                day = start_date + datetime.timedelta(days=i)
                day_str = day.strftime("%Y-%m-%d")
                days_list.append(day.strftime("%d/%m"))
                durations_list.append(days_data.get(day_str, 0) / 3600)
            
            logging.debug(f"Daily stats: days={days_list}, durations={durations_list}")
            return {
                'days': days_list,
                'durations': durations_list
            }
        except Exception as e:
            logging.error(f"Lỗi khi lấy thống kê hàng ngày: {e}")
            return {'days': [], 'durations': []}

# Tạo instance toàn cục để sử dụng
usage_tracker = UsageTracker()

# Test module nếu chạy trực tiếp
if __name__ == "__main__":
    logging.info("Kiểm tra module usage_tracker")
    
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    usage_tracker.start_tracking(user_name="User Test")
    
    logging.info("Đang theo dõi... (5 giây)")
    time.sleep(5)
    
    usage_tracker.update_position("sit")
    logging.info("Đã chuyển sang vị trí ngồi")
    time.sleep(3)
    
    usage_tracker.update_position("stand")
    logging.info("Đã chuyển sang vị trí đứng")
    time.sleep(3)
    
    usage_tracker.stop_tracking()
    
    user_stats = usage_tracker.get_user_stats()
    logging.info("\nThống kê người dùng:")
    for user, total, count, avg in user_stats:
        logging.info(f"{user}: {total:.1f}s ({count} phiên)")
    
    position_stats = usage_tracker.get_position_stats()
    logging.info("\nThống kê vị trí:")
    for position, total, count in position_stats:
        logging.info(f"{position}: {total:.1f}s ({count} lần)")
    
    daily_stats = usage_tracker.get_daily_stats(days=7)
    logging.info("\nThống kê theo ngày:")
    for i, day in enumerate(daily_stats['days']):
        logging.info(f"{day}: {daily_stats['durations'][i]:.2f} giờ")
    
    logging.info("\nKiểm tra hoàn tất")