# usage_stats.py - Giao diện thống kê thời gian sử dụng
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import datetime
import sqlite3
import os
from usage_tracker import usage_tracker, DB_PATH

class UsageStatsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Thống kê thời gian sử dụng")
        self.root.geometry("900x600")
        
        # Khởi tạo giao diện
        self.create_ui()
        
        # Tải dữ liệu thống kê
        self.load_stats()
    
    def create_ui(self):
        """Tạo giao diện người dùng"""
        # Notebook (Tab Control)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Tab 1: Tổng quan
        self.overview_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.overview_frame, text="Tổng quan")
        
        # Tab 2: Thống kê theo ngày
        self.daily_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.daily_frame, text="Theo ngày")
        
        # Tab 3: Thống kê theo người dùng
        self.user_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.user_frame, text="Theo người dùng")
        
        # Tab 4: Thống kê theo vị trí
        self.position_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.position_frame, text="Thời gian đứng/ngồi")
        
        # Tab 5: Độ cao theo người dùng
        self.height_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.height_frame, text="Độ cao")
        
        # Tạo nội dung cho từng tab
        self.setup_overview_tab()
        self.setup_daily_tab()
        self.setup_user_tab()
        self.setup_position_tab()
        self.setup_height_tab()
        
        # Nút quay lại
        self.back_button = tk.Button(
            self.root, 
            text="Quay lại", 
            font=("Arial", 14),
            bg="tomato", 
            fg="white",
            command=self.root.destroy,
            height=1
        )
        self.back_button.pack(pady=10)
    
    def setup_overview_tab(self):
        """Thiết lập tab tổng quan"""
        # Khung thống kê tổng quan
        stats_frame = ttk.LabelFrame(self.overview_frame, text="Tổng quan sử dụng")
        stats_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Các nhãn thống kê
        self.total_time_label = ttk.Label(stats_frame, text="Tổng thời gian: --", font=("Arial", 12))
        self.total_time_label.pack(anchor='w', padx=20, pady=5)
        
        self.total_sessions_label = ttk.Label(stats_frame, text="Tổng số phiên: --", font=("Arial", 12))
        self.total_sessions_label.pack(anchor='w', padx=20, pady=5)
        
        self.avg_session_label = ttk.Label(stats_frame, text="Thời gian trung bình: --", font=("Arial", 12))
        self.avg_session_label.pack(anchor='w', padx=20, pady=5)
        
        self.this_week_label = ttk.Label(stats_frame, text="Tuần này: --", font=("Arial", 12))
        self.this_week_label.pack(anchor='w', padx=20, pady=5)
        
        self.last_session_label = ttk.Label(stats_frame, text="Phiên gần nhất: --", font=("Arial", 12))
        self.last_session_label.pack(anchor='w', padx=20, pady=5)
        
        # Khung biểu đồ đơn giản
        chart_frame = ttk.LabelFrame(self.overview_frame, text="Xu hướng sử dụng")
        chart_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Giữ chỗ cho biểu đồ
        self.overview_chart_frame = ttk.Frame(chart_frame)
        self.overview_chart_frame.pack(fill='both', expand=True)
    
    def setup_daily_tab(self):
        """Thiết lập tab thống kê theo ngày"""
        # Khung điều khiển
        control_frame = ttk.Frame(self.daily_frame)
        control_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(control_frame, text="Số ngày:").pack(side=tk.LEFT, padx=5)
        
        self.days_var = tk.StringVar(value="7")
        days_combo = ttk.Combobox(control_frame, textvariable=self.days_var, values=["7", "14", "30", "90"], width=5)
        days_combo.pack(side=tk.LEFT, padx=5)
        
        refresh_button = ttk.Button(control_frame, text="Cập nhật", command=self.refresh_daily_stats)
        refresh_button.pack(side=tk.LEFT, padx=5)
        
        # Khung biểu đồ
        chart_frame = ttk.LabelFrame(self.daily_frame, text="Thời gian sử dụng theo ngày")
        chart_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Giữ chỗ cho biểu đồ
        self.daily_chart_frame = ttk.Frame(chart_frame)
        self.daily_chart_frame.pack(fill='both', expand=True)
    
    def setup_user_tab(self):
        """Thiết lập tab thống kê theo người dùng"""
        # Khung bảng dữ liệu
        table_frame = ttk.LabelFrame(self.user_frame, text="Thời gian sử dụng theo người dùng")
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Tạo bảng hiển thị
        columns = ("user", "total", "count", "average")
        self.user_table = ttk.Treeview(table_frame, columns=columns, show="headings")
        
        # Định nghĩa tiêu đề
        self.user_table.heading("user", text="Người dùng")
        self.user_table.heading("total", text="Tổng thời gian (giờ)")
        self.user_table.heading("count", text="Số phiên")
        self.user_table.heading("average", text="Trung bình (phút)")
        
        # Định nghĩa độ rộng cột
        self.user_table.column("user", width=150, anchor="w")
        self.user_table.column("total", width=120, anchor="center")
        self.user_table.column("count", width=80, anchor="center")
        self.user_table.column("average", width=120, anchor="center")
        
        # Thêm thanh cuộn
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.user_table.yview)
        self.user_table.configure(yscrollcommand=scrollbar.set)
        
        # Sắp xếp các widget
        self.user_table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Khung biểu đồ
        chart_frame = ttk.LabelFrame(self.user_frame, text="Biểu đồ thời gian sử dụng theo người dùng")
        chart_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Giữ chỗ cho biểu đồ
        self.user_chart_frame = ttk.Frame(chart_frame)
        self.user_chart_frame.pack(fill='both', expand=True)
    
    def setup_position_tab(self):
        """Thiết lập tab thống kê theo vị trí (đứng/ngồi)"""
        # Khung thông tin
        info_frame = ttk.LabelFrame(self.position_frame, text="Thời gian đứng/ngồi")
        info_frame.pack(fill='x', padx=10, pady=10)
        
        self.sit_time_label = ttk.Label(info_frame, text="Thời gian ngồi: --", font=("Arial", 12))
        self.sit_time_label.pack(anchor='w', padx=20, pady=5)
        
        self.stand_time_label = ttk.Label(info_frame, text="Thời gian đứng: --", font=("Arial", 12))
        self.stand_time_label.pack(anchor='w', padx=20, pady=5)
        
        self.sit_percent_label = ttk.Label(info_frame, text="Tỷ lệ ngồi: --", font=("Arial", 12))
        self.sit_percent_label.pack(anchor='w', padx=20, pady=5)
        
        self.stand_percent_label = ttk.Label(info_frame, text="Tỷ lệ đứng: --", font=("Arial", 12))
        self.stand_percent_label.pack(anchor='w', padx=20, pady=5)
        
        # Khung biểu đồ
        chart_frame = ttk.LabelFrame(self.position_frame, text="Biểu đồ thời gian đứng/ngồi")
        chart_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Giữ chỗ cho biểu đồ
        self.position_chart_frame = ttk.Frame(chart_frame)
        self.position_chart_frame.pack(fill='both', expand=True)
    
    def setup_height_tab(self):
        """Thiết lập tab thông tin độ cao"""
        # Import height_preferences nếu có
        try:
            from height_preferences import height_prefs
            has_height_prefs = True
        except ImportError:
            has_height_prefs = False
            
        if not has_height_prefs:
            # Hiển thị thông báo nếu không có module
            ttk.Label(
                self.height_frame, 
                text="Không tìm thấy module height_preferences",
                font=("Arial", 14)
            ).pack(pady=20)
            return
        
        # Khung thông tin độ cao
        table_frame = ttk.LabelFrame(self.height_frame, text="Độ cao theo người dùng")
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Tạo bảng hiển thị
        columns = ("user", "sitting", "standing", "updated")
        self.height_table = ttk.Treeview(table_frame, columns=columns, show="headings")
        
        # Định nghĩa tiêu đề
        self.height_table.heading("user", text="Người dùng")
        self.height_table.heading("sitting", text="Độ cao ngồi")
        self.height_table.heading("standing", text="Độ cao đứng")
        self.height_table.heading("updated", text="Cập nhật lần cuối")
        
        # Định nghĩa độ rộng cột
        self.height_table.column("user", width=150, anchor="w")
        self.height_table.column("sitting", width=100, anchor="center")
        self.height_table.column("standing", width=100, anchor="center")
        self.height_table.column("updated", width=150, anchor="center")
        
        # Thêm thanh cuộn
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.height_table.yview)
        self.height_table.configure(yscrollcommand=scrollbar.set)
        
        # Sắp xếp các widget
        self.height_table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Khung lịch sử
        history_frame = ttk.LabelFrame(self.height_frame, text="Lịch sử thay đổi độ cao")
        history_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Tạo bảng lịch sử
        columns = ("user", "position", "height", "timestamp")
        self.history_table = ttk.Treeview(history_frame, columns=columns, show="headings")
        
        # Định nghĩa tiêu đề
        self.history_table.heading("user", text="Người dùng")
        self.history_table.heading("position", text="Vị trí")
        self.history_table.heading("height", text="Độ cao")
        self.history_table.heading("timestamp", text="Thời gian")
        
        # Định nghĩa độ rộng cột
        self.history_table.column("user", width=150, anchor="w")
        self.history_table.column("position", width=80, anchor="center")
        self.history_table.column("height", width=80, anchor="center")
        self.history_table.column("timestamp", width=150, anchor="center")
        
        # Thêm thanh cuộn
        history_scrollbar = ttk.Scrollbar(history_frame, orient="vertical", command=self.history_table.yview)
        self.history_table.configure(yscrollcommand=history_scrollbar.set)
        
        # Sắp xếp các widget
        self.history_table.pack(side="left", fill="both", expand=True)
        history_scrollbar.pack(side="right", fill="y")
        
        # Nút làm mới
        refresh_button = ttk.Button(
            self.height_frame, 
            text="Làm mới dữ liệu", 
            command=self.refresh_height_stats
        )
        refresh_button.pack(pady=10)
    
    def load_stats(self):
        """Tải dữ liệu thống kê"""
        try:
            self.refresh_overview_stats()
            self.refresh_daily_stats()
            self.refresh_user_stats()
            self.refresh_position_stats()
            self.refresh_height_stats()
        except Exception as e:
            print(f"Lỗi khi tải dữ liệu thống kê: {e}")
    
    def refresh_overview_stats(self):
        """Cập nhật thống kê tổng quan"""
        # Kiểm tra xem database có tồn tại không
        if not os.path.exists(DB_PATH):
            print(f"Không tìm thấy cơ sở dữ liệu tại: {DB_PATH}")
            return
            
        # Truy vấn tổng thống kê từ database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Tổng thời gian và số phiên
        cursor.execute('''
            SELECT 
                SUM(duration) as total_time,
                COUNT(*) as total_sessions,
                AVG(duration) as avg_duration
            FROM sessions
        ''')
        result = cursor.fetchone()
        if result:
            total_time, total_sessions, avg_duration = result
        else:
            total_time, total_sessions, avg_duration = 0, 0, 0
        
        # Thời gian tuần này
        week_start = datetime.datetime.now() - datetime.timedelta(days=datetime.datetime.now().weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start_str = week_start.strftime("%Y-%m-%d %H:%M:%S.%f")
        
        cursor.execute('SELECT SUM(duration) FROM sessions WHERE start_time >= ?', (week_start_str,))
        week_time = cursor.fetchone()[0] or 0
        
        # Phiên gần nhất
        cursor.execute('''
            SELECT start_time, duration, user_name
            FROM sessions
            ORDER BY start_time DESC
            LIMIT 1
        ''')
        last_session = cursor.fetchone()
        
        conn.close()
        
        # Cập nhật UI
        if total_time:
            hours = total_time / 3600
            self.total_time_label.config(text=f"Tổng thời gian: {hours:.1f} giờ")
        else:
            self.total_time_label.config(text="Tổng thời gian: 0 giờ")
        
        self.total_sessions_label.config(text=f"Tổng số phiên: {total_sessions or 0}")
        
        if avg_duration:
            self.avg_session_label.config(text=f"Thời gian trung bình: {avg_duration/60:.1f} phút")
        else:
            self.avg_session_label.config(text="Thời gian trung bình: 0 phút")
        
        self.this_week_label.config(text=f"Tuần này: {week_time/3600:.1f} giờ")
        
        if last_session:
            start_time_str, duration, user_name = last_session
            try:
                start_time = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                # Thử với định dạng khác nếu lỗi
                try:
                    start_time = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
                except:
                    start_time = datetime.datetime.now()
                    
            self.last_session_label.config(
                text=f"Phiên gần nhất: {start_time.strftime('%d/%m/%Y %H:%M')}, {duration/60:.1f} phút, {user_name or 'Không xác định'}"
            )
        else:
            self.last_session_label.config(text="Phiên gần nhất: Chưa có")
        
        # Vẽ biểu đồ tổng quan
        self.draw_overview_chart()
    
    def refresh_daily_stats(self):
        """Cập nhật thống kê theo ngày"""
        try:
            days = int(self.days_var.get())
        except:
            days = 7
        
        # Vẽ biểu đồ
        self.draw_daily_chart(days)
    
    def refresh_user_stats(self):
        """Cập nhật thống kê theo người dùng"""
        # Lấy dữ liệu
        user_stats = self.get_user_stats()
        
        # Xóa dữ liệu cũ
        for item in self.user_table.get_children():
            self.user_table.delete(item)
        
        # Thêm dữ liệu mới
        for user, total_duration, session_count, avg_duration in user_stats:
            # Chuyển đổi thời gian
            total_hours = total_duration / 3600 if total_duration else 0
            avg_minutes = avg_duration / 60 if avg_duration else 0
            
            self.user_table.insert('', 'end', values=(
                user,
                f"{total_hours:.1f}",
                session_count,
                f"{avg_minutes:.1f}"
            ))
        
        # Vẽ biểu đồ
        self.draw_user_chart(user_stats)
    
    def refresh_position_stats(self):
        """Cập nhật thống kê theo vị trí"""
        # Lấy dữ liệu
        position_stats = self.get_position_stats()
        
        # Khởi tạo biến
        sit_time = 0
        stand_time = 0
        
        # Phân loại theo vị trí
        for position, duration, count in position_stats:
            position_lower = position.lower() if position else ""
            if position_lower == "sit" or position_lower == "ngoi":
                sit_time += duration
            elif position_lower == "stand" or position_lower == "dung":
                stand_time += duration
        
        # Tính tổng và tỷ lệ
        total_time = sit_time + stand_time
        sit_percent = (sit_time / total_time * 100) if total_time > 0 else 0
        stand_percent = (stand_time / total_time * 100) if total_time > 0 else 0
        
        # Cập nhật UI
        self.sit_time_label.config(text=f"Thời gian ngồi: {sit_time/3600:.1f} giờ")
        self.stand_time_label.config(text=f"Thời gian đứng: {stand_time/3600:.1f} giờ")
        self.sit_percent_label.config(text=f"Tỷ lệ ngồi: {sit_percent:.1f}%")
        self.stand_percent_label.config(text=f"Tỷ lệ đứng: {stand_percent:.1f}%")
        
        # Vẽ biểu đồ
        self.draw_position_chart(sit_time, stand_time)
    
    def refresh_height_stats(self):
        """Cập nhật thống kê độ cao"""
        try:
            from height_preferences import height_prefs
            
            # Xóa dữ liệu cũ
            for item in self.height_table.get_children():
                self.height_table.delete(item)
                
            for item in self.history_table.get_children():
                self.history_table.delete(item)
            
            # Lấy dữ liệu mới
            user_heights = height_prefs.get_all_user_heights()
            history = height_prefs.get_height_history(limit=20)
            
            # Cập nhật bảng độ cao
            for user_id, user_name, sitting_height, standing_height, updated_at in user_heights:
                try:
                    # Định dạng thời gian
                    updated_time = datetime.datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S.%f")
                    updated_str = updated_time.strftime("%d/%m/%Y %H:%M")
                except:
                    updated_str = updated_at
                    
                self.height_table.insert('', 'end', values=(
                    user_name or f"Người dùng {user_id}",
                    f"{sitting_height} cm" if sitting_height > 0 else "Chưa đặt",
                    f"{standing_height} cm" if standing_height > 0 else "Chưa đặt",
                    updated_str
                ))
            
            # Cập nhật bảng lịch sử
            for _, user_id, user_name, position, height, timestamp in history:
                try:
                    # Định dạng thời gian
                    time_obj = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
                    time_str = time_obj.strftime("%d/%m/%Y %H:%M")
                except:
                    time_str = timestamp
                    
                # Định dạng vị trí
                if position.lower() in ["sit", "ngoi"]:
                    position_str = "Ngồi"
                elif position.lower() in ["stand", "dung"]:
                    position_str = "Đứng"
                else:
                    position_str = position
                    
                self.history_table.insert('', 'end', values=(
                    user_name or f"Người dùng {user_id}",
                    position_str,
                    f"{height} cm",
                    time_str
                ))
        except Exception as e:
            print(f"Lỗi khi cập nhật thống kê độ cao: {e}")
    
    def get_user_stats(self):
        """Lấy thống kê người dùng từ database"""
        if not os.path.exists(DB_PATH):
            return []
            
        conn = sqlite3.connect(DB_PATH)
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
        conn.close()
        
        return result
    
    def get_position_stats(self):
        """Lấy thống kê vị trí từ database"""
        if not os.path.exists(DB_PATH):
            return []
            
        conn = sqlite3.connect(DB_PATH)
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
        conn.close()
        
        return result
    
    def draw_overview_chart(self):
        """Vẽ biểu đồ tổng quan"""
        # Xóa biểu đồ cũ nếu có
        for widget in self.overview_chart_frame.winfo_children():
            widget.destroy()
        
        # Lấy dữ liệu 7 ngày
        stats = self.get_daily_stats(days=7)
        
        if not stats['days']:
            label = ttk.Label(self.overview_chart_frame, text="Không có dữ liệu", font=("Arial", 14))
            label.pack(expand=True)
            return
        
        # Tạo figure và axes
        fig, ax = plt.subplots(figsize=(8, 3))
        fig.tight_layout(pad=3)
        
        # Vẽ biểu đồ cột
        ax.bar(stats['days'], stats['durations'], color='royalblue')
        
        # Tùy chỉnh trục
        ax.set_xlabel('Ngày')
        ax.set_ylabel('Giờ')
        ax.set_title('Thời gian sử dụng (7 ngày gần nhất)')
        ax.grid(axis='y', linestyle='--', alpha=0.7)
        plt.xticks(rotation=45)
        
        # Tạo canvas Tkinter
        canvas = FigureCanvasTkAgg(fig, master=self.overview_chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)
    
    def draw_daily_chart(self, days=7):
        """Vẽ biểu đồ theo ngày"""
        # Xóa biểu đồ cũ nếu có
        for widget in self.daily_chart_frame.winfo_children():
            widget.destroy()
        
        # Lấy dữ liệu
        stats = self.get_daily_stats(days=days)
        
        if not stats['days']:
            label = ttk.Label(self.daily_chart_frame, text="Không có dữ liệu", font=("Arial", 14))
            label.pack(expand=True)
            return
        
        # Tạo figure và axes
        fig, ax = plt.subplots(figsize=(8, 4))
        fig.tight_layout(pad=3)
        
        # Vẽ biểu đồ cột
        bars = ax.bar(stats['days'], stats['durations'], color='royalblue')
        
        # Thêm nhãn số liệu
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        f'{height:.1f}',
                        ha='center', va='bottom', rotation=0)
        
        # Tùy chỉnh trục
        ax.set_xlabel('Ngày')
        ax.set_ylabel('Giờ')
        ax.set_title(f'Thời gian sử dụng ({days} ngày gần nhất)')
        ax.grid(axis='y', linestyle='--', alpha=0.7)
        plt.xticks(rotation=45)
        
        # Tạo canvas Tkinter
        canvas = FigureCanvasTkAgg(fig, master=self.daily_chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)
    
    def get_daily_stats(self, days=7):
        """Lấy thống kê theo ngày từ database"""
        if not os.path.exists(DB_PATH):
            return {'days': [], 'durations': []}
            
        # Tính ngày bắt đầu
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=days-1)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Kết nối database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Tạo danh sách ngày
        date_list = []
        for i in range(days):
            day = start_date + datetime.timedelta(days=i)
            date_list.append(day.strftime("%Y-%m-%d"))
        
        # Lấy dữ liệu từ database
        durations = []
        for date_str in date_list:
            cursor.execute('''
                SELECT SUM(duration)
                FROM sessions
                WHERE date(start_time) = ?
            ''', (date_str,))
            
            total = cursor.fetchone()[0]
            if total:
                # Chuyển từ giây sang giờ
                durations.append(total / 3600)
            else:
                durations.append(0)
        
        conn.close()
        
        # Định dạng lại ngày để hiển thị
        formatted_dates = [datetime.datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m") for d in date_list]
        
        return {'days': formatted_dates, 'durations': durations}
    
    def draw_user_chart(self, user_stats):
        """Vẽ biểu đồ theo người dùng"""
        # Xóa biểu đồ cũ nếu có
        for widget in self.user_chart_frame.winfo_children():
            widget.destroy()
        
        if not user_stats:
            label = ttk.Label(self.user_chart_frame, text="Không có dữ liệu", font=("Arial", 14))
            label.pack(expand=True)
            return
        
        # Chuẩn bị dữ liệu
        users = []
        durations = []
        
        for user, total_duration, _, _ in user_stats:
            users.append(user)
            durations.append(total_duration / 3600 if total_duration else 0)  # Chuyển sang giờ
        
        # Tạo figure và axes
        fig, ax = plt.subplots(figsize=(8, 4))
        fig.tight_layout(pad=3)
        
        # Vẽ biểu đồ tròn
        wedges, texts, autotexts = ax.pie(
            durations, 
            labels=users, 
            autopct='%1.1f%%',
            startangle=90,
            wedgeprops={'edgecolor': 'w'}
        )
        
        # Tùy chỉnh font
        plt.setp(autotexts, size=9, weight='bold')
        plt.setp(texts, size=9)
        
        # Tiêu đề
        ax.set_title('Thời gian sử dụng theo người dùng')
        
        # Tạo canvas Tkinter
        canvas = FigureCanvasTkAgg(fig, master=self.user_chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)
    
    def draw_position_chart(self, sit_time, stand_time):
        """Vẽ biểu đồ theo vị trí"""
        # Xóa biểu đồ cũ nếu có
        for widget in self.position_chart_frame.winfo_children():
            widget.destroy()
        
        if sit_time == 0 and stand_time == 0:
            label = ttk.Label(self.position_chart_frame, text="Không có dữ liệu", font=("Arial", 14))
            label.pack(expand=True)
            return
        
        # Tạo figure và axes
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 4))
        fig.tight_layout(pad=3)
        
        # Vẽ biểu đồ tròn
        labels = ['Ngồi', 'Đứng']
        sizes = [sit_time, stand_time]
        explode = (0, 0.1)  # Tách phần "đứng" ra một chút
        
        wedges, texts, autotexts = ax1.pie(
            sizes, 
            explode=explode,
            labels=labels, 
            autopct='%1.1f%%',
            startangle=90,
            colors=['skyblue', 'lightgreen'],
            wedgeprops={'edgecolor': 'w'}
        )
        
        # Tùy chỉnh font
        plt.setp(autotexts, size=9, weight='bold')
        plt.setp(texts, size=9)
        
        # Tiêu đề
        ax1.set_title('Tỷ lệ thời gian đứng/ngồi')
        
        # Vẽ biểu đồ cột
        positions = ['Ngồi', 'Đứng']
        times = [sit_time / 3600, stand_time / 3600]  # Chuyển sang giờ
        
        bars = ax2.bar(positions, times, color=['skyblue', 'lightgreen'])
        
        # Thêm nhãn số liệu
        for bar in bars:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{height:.1f}h',
                    ha='center', va='bottom')
        
        # Tùy chỉnh trục
        ax2.set_ylabel('Giờ')
        ax2.set_title('Thời gian đứng/ngồi')
        ax2.grid(axis='y', linestyle='--', alpha=0.7)
        
        # Tạo canvas Tkinter
        canvas = FigureCanvasTkAgg(fig, master=self.position_chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)

def show_usage_stats():
    """Hiển thị thống kê sử dụng"""
    root = tk.Toplevel()
    app = UsageStatsApp(root)
    return app

# Thêm hàm test để kiểm tra module
if __name__ == "__main__":
    root = tk.Tk()
    app = UsageStatsApp(root)
    root.mainloop()