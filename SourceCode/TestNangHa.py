#!/usr/bin/env python3
import time
import json
import threading
import tkinter as tk
from tkinter import ttk, font, messagebox, simpledialog
from gpiozero import DigitalOutputDevice, Button, DistanceSensor
import datetime
import os

# ===== CẤU HÌNH CHÂN GPIO =====
# Chân điều khiển động cơ
ENA_PIN = 23  # Chân ENA+ kết nối với GPIO 23
DIR_PIN = 24  # Chân DIR+ kết nối với GPIO 24
PUL_PIN = 25  # Chân PUL+ kết nối với GPIO 25

# Nút bấm vật lý (tùy chọn)
BTN_UP_PIN = 17      # Nút đi lên (GPIO17)
BTN_DOWN_PIN = 27    # Nút đi xuống (GPIO27)
MEM_BTN_1_PIN = 22   # Nút bộ nhớ 1 (GPIO22)
MEM_BTN_2_PIN = 5    # Nút bộ nhớ 2 (GPIO5)

# Cảm biến siêu âm HC-SR04 (tùy chọn)
TRIG_PIN = 16  # GPIO16
ECHO_PIN = 12  # GPIO12

# Công tắc giới hạn (tùy chọn)
LIMIT_TOP_PIN = 6     # GPIO6
LIMIT_BOTTOM_PIN = 13  # GPIO13

# ===== CÀI ĐẶT =====
PULSE_SPEED = 500      # Tốc độ xung (microseconds)
PULSE_SLOW = 1000      # Tốc độ xung chậm (microseconds) - khi gần đến vị trí mục tiêu
CONFIG_FILE = "table_heights.json"  # File lưu vị trí bộ nhớ

# ===== BIẾN TOÀN CỤC =====
running = True
motor_running = False
current_direction = True  # True = lên, False = xuống
memory_positions = {1: -1, 2: -1}  # Vị trí bộ nhớ (-1 = chưa đặt)
current_height = -1
moving_to_position = False
target_position = -1

# Import height_preferences
try:
    from height_preferences import height_prefs
    has_height_prefs = True
except ImportError:
    has_height_prefs = False
    print("Thiếu module height_preferences - các tính năng độ cao cá nhân hóa sẽ bị tắt")
    
# Import usage_tracker để lấy thông tin người dùng
try:
    from usage_tracker import usage_tracker
    has_usage_tracker = True
except ImportError:
    has_usage_tracker = False
    print("Thiếu module usage_tracker - các tính năng theo dõi người dùng sẽ bị tắt")

# ===== KHỞI TẠO PHẦN CỨNG =====
# Khởi tạo chân điều khiển động cơ
try:
    ena_pin = DigitalOutputDevice(ENA_PIN)
    dir_pin = DigitalOutputDevice(DIR_PIN)
    pul_pin = DigitalOutputDevice(PUL_PIN)
    
    # Kích hoạt driver (ENA active LOW)
    ena_pin.off()
    print("Đã khởi tạo chân điều khiển động cơ")
except Exception as e:
    print(f"Lỗi khởi tạo chân GPIO động cơ: {e}")
    exit(1)

# Khởi tạo nút bấm vật lý (nếu cần)
try:
    btn_up = Button(BTN_UP_PIN, pull_up=True)
    btn_down = Button(BTN_DOWN_PIN, pull_up=True)
    btn_mem1 = Button(MEM_BTN_1_PIN, pull_up=True)
    btn_mem2 = Button(MEM_BTN_2_PIN, pull_up=True)
    has_physical_buttons = True
    print("Đã khởi tạo nút bấm vật lý")
except Exception as e:
    has_physical_buttons = False
    print(f"Không tìm thấy nút bấm vật lý: {e}")

# Khởi tạo cảm biến khoảng cách (nếu có)
try:
    distance_sensor = DistanceSensor(echo=ECHO_PIN, trigger=TRIG_PIN, max_distance=4)
    has_distance_sensor = True
    print("Đã khởi tạo cảm biến khoảng cách")
except Exception as e:
    has_distance_sensor = False
    print(f"Không tìm thấy cảm biến khoảng cách: {e}")

# Khởi tạo công tắc giới hạn (nếu có)
try:
    limit_top = Button(LIMIT_TOP_PIN, pull_up=True)
    limit_bottom = Button(LIMIT_BOTTOM_PIN, pull_up=True)
    has_limit_switches = True
    print("Đã khởi tạo công tắc giới hạn")
except Exception as e:
    has_limit_switches = False
    print(f"Không tìm thấy công tắc giới hạn: {e}")

# ===== QUẢN LÝ LƯU TRỮ VỊ TRÍ =====
def load_positions():
    """Tải vị trí bộ nhớ từ file"""
    global memory_positions
    
    try:
        with open(CONFIG_FILE, 'r') as file:
            loaded_data = json.load(file)
            memory_positions = {1: loaded_data.get('position1', -1), 
                               2: loaded_data.get('position2', -1)}
        print(f"Đã tải vị trí bộ nhớ: 1={memory_positions[1]}cm, 2={memory_positions[2]}cm")
    except (FileNotFoundError, json.JSONDecodeError):
        memory_positions = {1: -1, 2: -1}
        save_positions()
        print("Đã tạo file cấu hình vị trí mới")

def save_positions():
    """Lưu vị trí bộ nhớ vào file"""
    try:
        data = {'position1': memory_positions[1], 'position2': memory_positions[2]}
        with open(CONFIG_FILE, 'w') as file:
            json.dump(data, file)
        print(f"Đã lưu vị trí: 1={memory_positions[1]}cm, 2={memory_positions[2]}cm")
    except Exception as e:
        print(f"Lỗi khi lưu vị trí: {e}")

# ===== ĐO KHOẢNG CÁCH =====
def get_current_height():
    """Đọc chiều cao hiện tại từ cảm biến"""
    if not has_distance_sensor:
        return -1
        
    try:
        # Lấy khoảng cách tính bằng mét và chuyển sang cm
        distance_m = distance_sensor.distance
        distance_cm = distance_m * 100
        
        # Kiểm tra phạm vi hợp lệ (2-400cm)
        if 2 <= distance_cm <= 400:
            return round(distance_cm)
        return -1
    except:
        return -1

# ===== ĐIỂU KHIỂN ĐỘNG CƠ =====
def check_limits(direction):
    """Kiểm tra công tắc giới hạn"""
    if not has_limit_switches:
        return False
        
    if direction and limit_top.is_pressed:
        print("Đạt giới hạn trên!")
        return True
    if not direction and limit_bottom.is_pressed:
        print("Đạt giới hạn dưới!")
        return True
    
    return False

def stop_motor():
    """Dừng động cơ"""
    global motor_running, moving_to_position
    
    motor_running = False
    moving_to_position = False
    pul_pin.off()

def start_motor_up(from_gui=False):
    """Bắt đầu quay động cơ lên"""
    global motor_running, current_direction, moving_to_position
    
    if check_limits(True):
        print("Không thể đi lên - đã đạt giới hạn trên")
        return
        
    print("Di chuyển LÊN")
    dir_pin.on()  # Đặt hướng lên
    current_direction = True
    moving_to_position = False
    motor_running = True

def start_motor_down(from_gui=False):
    """Bắt đầu quay động cơ xuống"""
    global motor_running, current_direction, moving_to_position
    
    if check_limits(False):
        print("Không thể đi xuống - đã đạt giới hạn dưới")
        return
        
    print("Di chuyển XUỐNG")
    dir_pin.off()  # Đặt hướng xuống
    current_direction = False
    moving_to_position = False
    motor_running = True

def handle_memory_button(position_num):
    """Xử lý khi nhấn nút bộ nhớ"""
    global memory_positions, current_height, moving_to_position, target_position, motor_running
    
    if not has_distance_sensor:
        print("Không thể sử dụng chức năng bộ nhớ - không có cảm biến khoảng cách")
        return
    
    # Lấy vị trí hiện tại
    current_height = get_current_height()
    
    # Kiểm tra độ cao cá nhân nếu có module height_prefs
    user_height = None
    if has_height_prefs and has_usage_tracker:
        current_user = usage_tracker.get_current_user()
        if current_user and current_user.get('user_id'):
            heights = height_prefs.get_heights(current_user.get('user_id'))
            if position_num == 1 and heights['sitting'] > 0:  # Vị trí ngồi
                user_height = heights['sitting']
                print(f"Sử dụng độ cao ngồi cá nhân: {user_height}cm")
            elif position_num == 2 and heights['standing'] > 0:  # Vị trí đứng
                user_height = heights['standing']
                print(f"Sử dụng độ cao đứng cá nhân: {user_height}cm")
    
    # Nếu có độ cao cá nhân, sử dụng nó
    if user_height:
        print(f"Di chuyển đến vị trí cá nhân {position_num}: {user_height}cm")
        target_position = user_height
        moving_to_position = True
        motor_running = True
        return
    
    # Nếu không có độ cao cá nhân, sử dụng logic cũ
    if memory_positions[position_num] == -1 and current_height > 0:
        memory_positions[position_num] = current_height
        save_positions()
        print(f"Đã lưu vị trí {position_num}: {current_height}cm")
    
    # Nếu vị trí đã được đặt, di chuyển đến vị trí đó
    elif memory_positions[position_num] > 0:
        if current_height > 0:
            print(f"Di chuyển đến vị trí {position_num}: {memory_positions[position_num]}cm")
            target_position = memory_positions[position_num]
            moving_to_position = True
            motor_running = True
        else:
            print("Không thể di chuyển - cảm biến khoảng cách không hoạt động")

def clear_memory_position(position_num):
    """Xóa vị trí bộ nhớ"""
    global memory_positions
    
    memory_positions[position_num] = -1
    save_positions()
    print(f"Đã xóa vị trí bộ nhớ {position_num}")

# ===== CÁC LUỒNG HOẠT ĐỘNG =====
def motor_control_thread():
    """Luồng điều khiển động cơ"""
    global running, motor_running, current_direction, moving_to_position, target_position, current_height
    
    while running:
        if motor_running:
            # Nếu đang di chuyển đến vị trí cụ thể
            if moving_to_position and has_distance_sensor:
                current_height = get_current_height()
                
                if current_height > 0 and target_position > 0:
                    # Tính khoảng cách đến mục tiêu
                    distance_to_target = abs(current_height - target_position)
                    
                    # Đã đến vị trí mục tiêu
                    if distance_to_target <= 2:  # Dung sai 2cm
                        print(f"Đã đến vị trí mục tiêu: {current_height}cm")
                        stop_motor()
                        continue
                    
                    # Xác định hướng di chuyển
                    new_direction = current_height < target_position
                    if new_direction != current_direction:
                        current_direction = new_direction
                        dir_pin.on() if current_direction else dir_pin.off()
                    
                    # Chọn tốc độ phù hợp
                    pulse_time = PULSE_SLOW if distance_to_target < 10 else PULSE_SPEED
                else:
                    # Nếu không đọc được khoảng cách, dừng lại
                    stop_motor()
                    continue
            else:
                pulse_time = PULSE_SPEED
                
            # Kiểm tra giới hạn
            if check_limits(current_direction):
                stop_motor()
                continue
                
            # Tạo xung
            pul_pin.on()
            time.sleep(pulse_time / 2000000)  # Chuyển microseconds sang giây
            pul_pin.off()
            time.sleep(pulse_time / 2000000)
        else:
            # Chờ một chút để giảm tải CPU
            time.sleep(0.01)

def height_monitor_thread():
    """Luồng theo dõi chiều cao"""
    global running, current_height
    
    while running and has_distance_sensor:
        current_height = get_current_height()
        time.sleep(0.2)

# ===== GIAO DIỆN ĐỒ HỌA =====
class TableControlGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Điều khiển bàn nâng")
        self.root.geometry("800x480")  # Kích thước phù hợp với màn hình 7" Raspberry Pi
        
        # Tùy chọn toàn màn hình (bỏ comment nếu muốn sử dụng)
        # self.root.attributes('-fullscreen', True)
        
        # Khởi tạo font
        self.title_font = font.Font(family="Arial", size=24, weight="bold")
        self.normal_font = font.Font(family="Arial", size=18)
        self.button_font = font.Font(family="Arial", size=20, weight="bold")
        self.status_font = font.Font(family="Arial", size=16)
        
        # Tạo giao diện
        self.create_ui()
        
        # Bắt đầu cập nhật hiển thị
        self.update_display()
        
        # Biến theo dõi trạng thái nút
        self.up_pressed = False
        self.down_pressed = False
        
    def create_ui(self):
        """Tạo giao diện người dùng"""
        # Khung chính
        self.main_frame = ttk.Frame(self.root, padding=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Tiêu đề
        ttk.Label(self.main_frame, text="Điều khiển bàn nâng", font=self.title_font).pack(pady=10)
        
        # Khu vực hiển thị thông tin
        info_frame = ttk.Frame(self.main_frame)
        info_frame.pack(fill=tk.X, pady=10)
        
        # Hiển thị chiều cao
        height_frame = ttk.Frame(info_frame)
        height_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(height_frame, text="Chiều cao hiện tại:", font=self.normal_font).pack(anchor=tk.W)
        self.height_value = ttk.Label(height_frame, text="--", font=self.normal_font)
        self.height_value.pack(anchor=tk.W)
        
        # Hiển thị trạng thái
        status_frame = ttk.Frame(info_frame)
        status_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        ttk.Label(status_frame, text="Trạng thái:", font=self.normal_font).pack(anchor=tk.W)
        self.status_value = ttk.Label(status_frame, text="Sẵn sàng", font=self.status_font)
        self.status_value.pack(anchor=tk.W)
        
        # Khu vực hiển thị vị trí đã lưu
        memory_frame = ttk.Frame(self.main_frame)
        memory_frame.pack(fill=tk.X, pady=10)
        
        # Vị trí 1
        mem1_frame = ttk.Frame(memory_frame)
        mem1_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(mem1_frame, text="Vị trí 1:", font=self.normal_font).pack(anchor=tk.W)
        self.mem1_value = ttk.Label(mem1_frame, text="Chưa đặt", font=self.normal_font)
        self.mem1_value.pack(anchor=tk.W)
        
        # Vị trí 2
        mem2_frame = ttk.Frame(memory_frame)
        mem2_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        ttk.Label(mem2_frame, text="Vị trí 2:", font=self.normal_font).pack(anchor=tk.W)
        self.mem2_value = ttk.Label(mem2_frame, text="Chưa đặt", font=self.normal_font)
        self.mem2_value.pack(anchor=tk.W)
        
        # Khu vực nút điều khiển lên/xuống
        control_frame = ttk.Frame(self.main_frame)
        control_frame.pack(fill=tk.X, pady=20)
        
        # Nút lên
        self.up_button = tk.Button(
            control_frame, 
            text="▲ LÊN", 
            font=self.button_font,
            bg="lightblue", 
            activebackground="deepskyblue",
            height=2
        )
        self.up_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        
        # Xử lý sự kiện nút lên (nhấn và giữ)
        self.up_button.bind("<ButtonPress-1>", self.on_up_press)
        self.up_button.bind("<ButtonRelease-1>", self.on_up_release)
        
        # Nút xuống
        self.down_button = tk.Button(
            control_frame, 
            text="▼ XUỐNG", 
            font=self.button_font,
            bg="lightblue", 
            activebackground="deepskyblue",
            height=2
        )
        self.down_button.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=5)
        
        # Xử lý sự kiện nút xuống (nhấn và giữ)
        self.down_button.bind("<ButtonPress-1>", self.on_down_press)
        self.down_button.bind("<ButtonRelease-1>", self.on_down_release)
        
        # Khu vực nút bộ nhớ
        memory_buttons_frame = ttk.Frame(self.main_frame)
        memory_buttons_frame.pack(fill=tk.X, pady=10)
        
        # Nút bộ nhớ 1
        self.mem1_button = tk.Button(
            memory_buttons_frame, 
            text="Vị trí 1", 
            font=self.button_font,
            bg="lightgreen", 
            activebackground="limegreen",
            command=lambda: handle_memory_button(1),
            height=2
        )
        self.mem1_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        
        # Nút bộ nhớ 2
        self.mem2_button = tk.Button(
            memory_buttons_frame, 
            text="Vị trí 2", 
            font=self.button_font,
            bg="lightgreen", 
            activebackground="limegreen",
            command=lambda: handle_memory_button(2),
            height=2
        )
        self.mem2_button.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=5)
        
        # Nút dừng khẩn cấp
        self.stop_button = tk.Button(
            self.main_frame, 
            text="DỪNG", 
            font=self.button_font,
            bg="red", 
            activebackground="darkred",
            fg="white",
            command=stop_motor,
            height=2
        )
        self.stop_button.pack(fill=tk.X, pady=10)
        
        # Khu vực nút cài đặt/thoát
        bottom_frame = ttk.Frame(self.main_frame)
        bottom_frame.pack(fill=tk.X, pady=5)
        
        # Nút cài đặt
        self.settings_button = tk.Button(
            bottom_frame, 
            text="Cài đặt", 
            font=self.normal_font,
            bg="orange", 
            activebackground="darkorange",
            command=self.open_settings,
            height=1
        )
        self.settings_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Nút thoát
        self.exit_button = tk.Button(
            bottom_frame, 
            text="Quay lại Menu chính", 
            font=self.normal_font,
            bg="tomato", 
            activebackground="red",
            command=self.return_to_main,
            height=1
        )
        self.exit_button.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)
    
    def update_display(self):
        """Cập nhật hiển thị thông tin"""
        # Cập nhật chiều cao hiện tại
        if has_distance_sensor:
            if current_height > 0:
                self.height_value.config(text=f"{current_height} cm")
            else:
                self.height_value.config(text="Ngoài phạm vi")
        else:
            self.height_value.config(text="Không có cảm biến")
        
        # Cập nhật vị trí đã lưu
        if memory_positions[1] > 0:
            self.mem1_value.config(text=f"{memory_positions[1]} cm")
        else:
            self.mem1_value.config(text="Chưa đặt")
            
        if memory_positions[2] > 0:
            self.mem2_value.config(text=f"{memory_positions[2]} cm")
        else:
            self.mem2_value.config(text="Chưa đặt")
        
        # Cập nhật trạng thái
        if moving_to_position:
            self.status_value.config(text=f"Di chuyển đến vị trí {target_position}cm")
        elif motor_running:
            if current_direction:
                self.status_value.config(text="Đang đi lên")
            else:
                self.status_value.config(text="Đang đi xuống")
        else:
            self.status_value.config(text="Sẵn sàng")
        
        # Cập nhật màu nút dừng
        if motor_running:
            self.stop_button.config(bg="purple", activebackground="darkmagenta")
        else:
            self.stop_button.config(bg="red", activebackground="darkred")
        
        # Lập lịch cập nhật tiếp theo
        self.root.after(200, self.update_display)
    
    def on_up_press(self, event):
        """Xử lý khi nhấn nút lên"""
        self.up_pressed = True
        start_motor_up(from_gui=True)
    
    def on_up_release(self, event):
        """Xử lý khi thả nút lên"""
        self.up_pressed = False
        stop_motor()
    
    def on_down_press(self, event):
        """Xử lý khi nhấn nút xuống"""
        self.down_pressed = True
        start_motor_down(from_gui=True)
    
    def on_down_release(self, event):
        """Xử lý khi thả nút xuống"""
        self.down_pressed = False
        stop_motor()
    
    def open_settings(self):
        """Mở cửa sổ cài đặt"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Cài đặt")
        settings_window.geometry("400x400")  # Tăng kích thước
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        settings_frame = ttk.Frame(settings_window, padding=20)
        settings_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(settings_frame, text="Cài đặt", font=self.title_font).pack(pady=10)
        
        # Khung cài đặt vị trí
        position_frame = ttk.LabelFrame(settings_frame, text="Vị trí bộ nhớ")
        position_frame.pack(fill=tk.X, pady=10)
        
        # Nút xóa vị trí 1
        clear_mem1_button = tk.Button(
            position_frame, 
            text="Xóa vị trí 1", 
            font=self.normal_font,
            bg="yellow", 
            activebackground="gold",
            command=lambda: [clear_memory_position(1), settings_window.destroy()],
            height=1
        )
        clear_mem1_button.pack(fill=tk.X, pady=5)
        
        # Nút xóa vị trí 2
        clear_mem2_button = tk.Button(
            position_frame, 
            text="Xóa vị trí 2", 
            font=self.normal_font,
            bg="yellow", 
            activebackground="gold",
            command=lambda: [clear_memory_position(2), settings_window.destroy()],
            height=1
        )
        clear_mem2_button.pack(fill=tk.X, pady=5)
        
        # Khung cài đặt độ cao người dùng (nếu có module height_prefs)
        if has_height_prefs:
            height_frame = ttk.LabelFrame(settings_frame, text="Độ cao cá nhân")
            height_frame.pack(fill=tk.X, pady=10)
            
            # Nút lưu độ cao ngồi
            save_sit_button = tk.Button(
                height_frame, 
                text="Lưu vị trí ngồi hiện tại", 
                font=self.normal_font,
                bg="lightblue", 
                activebackground="skyblue",
                command=lambda: self.register_current_heights(1),
                height=1
            )
            save_sit_button.pack(fill=tk.X, pady=5)
            
            # Nút lưu độ cao đứng
            save_stand_button = tk.Button(
                height_frame, 
                text="Lưu vị trí đứng hiện tại", 
                font=self.normal_font,
                bg="lightblue", 
                activebackground="skyblue",
                command=lambda: self.register_current_heights(2),
                height=1
            )
            save_stand_button.pack(fill=tk.X, pady=5)
            
            # Nút xem thông tin độ cao
            view_heights_button = tk.Button(
                height_frame, 
                text="Xem độ cao đã lưu", 
                font=self.normal_font,
                bg="lightgreen", 
                activebackground="limegreen",
                command=self.show_height_info,
                height=1
            )
            view_heights_button.pack(fill=tk.X, pady=5)
        
        # Nút đóng
        close_button = tk.Button(
            settings_frame, 
            text="Đóng", 
            font=self.normal_font,
            bg="gray", 
            activebackground="darkgray",
            command=settings_window.destroy,
            height=1
        )
        close_button.pack(fill=tk.X, pady=10)
    
    def register_current_heights(self, position_num=None):
        """Đăng ký độ cao hiện tại cho người dùng"""
        if not has_height_prefs or not has_usage_tracker:
            messagebox.showinfo("Thông báo", "Tính năng đăng ký độ cao theo người dùng không khả dụng")
            return
        
        # Lấy người dùng hiện tại
        current_user = usage_tracker.get_current_user()
        if not current_user or not current_user.get('user_id'):
            # Yêu cầu nhập tên nếu chưa có
            user_name = simpledialog.askstring("Nhập tên", "Vui lòng nhập tên của bạn:")
            if not user_name:
                return
            
            # Tạo người dùng mới
            usage_tracker.start_tracking(user_name=user_name)
            current_user = usage_tracker.get_current_user()
        
        user_id = current_user.get('user_id')
        user_name = current_user.get('user_name', 'Không xác định')
        
        # Lấy chiều cao hiện tại
        current_height = get_current_height()
        
        if current_height <= 0:
            messagebox.showwarning("Lỗi", "Không thể đọc được chiều cao hiện tại từ cảm biến")
            return
        
        # Xác định vị trí ngồi hay đứng
        if position_num is None:
            # Hỏi người dùng
            position = simpledialog.askstring(
                "Vị trí", 
                "Đây là vị trí đứng hay ngồi? (nhập 'đứng' hoặc 'ngồi')"
            )
            
            if not position:
                return
                
            if position.lower() in ["đứng", "dung", "stand"]:
                height_prefs.save_height(user_id, standing_height=current_height)
                messagebox.showinfo("Thành công", f"Đã lưu chiều cao đứng {current_height}cm cho {user_name}")
            elif position.lower() in ["ngồi", "ngoi", "sit"]:
                height_prefs.save_height(user_id, sitting_height=current_height)
                messagebox.showinfo("Thành công", f"Đã lưu chiều cao ngồi {current_height}cm cho {user_name}")
            else:
                messagebox.showwarning("Lỗi", "Vị trí không hợp lệ. Vui lòng nhập 'đứng' hoặc 'ngồi'")
        else:
            # Sử dụng vị trí được chỉ định
            if position_num == 1:  # Vị trí ngồi
                height_prefs.save_height(user_id, sitting_height=current_height)
                messagebox.showinfo("Thành công", f"Đã lưu chiều cao ngồi {current_height}cm cho {user_name}")
            elif position_num == 2:  # Vị trí đứng
                height_prefs.save_height(user_id, standing_height=current_height)
                messagebox.showinfo("Thành công", f"Đã lưu chiều cao đứng {current_height}cm cho {user_name}")
    
    def show_height_info(self):
        """Hiển thị thông tin độ cao theo người dùng"""
        if not has_height_prefs:
            messagebox.showinfo("Thông báo", "Tính năng quản lý độ cao không khả dụng")
            return
        
        # Lấy người dùng hiện tại
        current_user = None
        if has_usage_tracker:
            current_user = usage_tracker.get_current_user()
        
        # Tạo cửa sổ hiển thị
        info_window = tk.Toplevel(self.root)
        info_window.title("Thông tin độ cao")
        info_window.geometry("500x400")
        info_window.transient(self.root)
        
        # Khung chính
        main_frame = ttk.Frame(info_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Tiêu đề
        ttk.Label(main_frame, text="Thông tin độ cao theo người dùng", font=self.title_font).pack(pady=10)
        
        # Lấy tất cả thông tin độ cao
        user_heights = height_prefs.get_all_user_heights()
        
        if not user_heights:
            ttk.Label(main_frame, text="Chưa có thông tin độ cao nào được lưu", font=self.normal_font).pack(pady=20)
        else:
            # Tạo bảng hiển thị
            columns = ("user", "sitting", "standing", "updated")
            height_table = ttk.Treeview(main_frame, columns=columns, show="headings")
            
            # Định nghĩa tiêu đề
            height_table.heading("user", text="Người dùng")
            height_table.heading("sitting", text="Độ cao ngồi")
            height_table.heading("standing", text="Độ cao đứng")
            height_table.heading("updated", text="Cập nhật lần cuối")
            
            # Định nghĩa độ rộng cột
            height_table.column("user", width=120, anchor="w")
            height_table.column("sitting", width=100, anchor="center")
            height_table.column("standing", width=100, anchor="center")
            height_table.column("updated", width=150, anchor="center")
            
            # Thêm dữ liệu
            for user_id, user_name, sitting_height, standing_height, updated_at in user_heights:
                # Định dạng thời gian
                try:
                    updated_time = datetime.datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S.%f")
                    updated_str = updated_time.strftime("%d/%m/%Y %H:%M")
                except:
                    updated_str = updated_at
                    
                # Đánh dấu người dùng hiện tại
                display_name = user_name or f"Người dùng {user_id}"
                if current_user and current_user.get('user_id') == user_id:
                    display_name += " (bạn)"
                    
                height_table.insert('', 'end', values=(
                    display_name,
                    f"{sitting_height} cm" if sitting_height > 0 else "Chưa đặt",
                    f"{standing_height} cm" if standing_height > 0 else "Chưa đặt",
                    updated_str
                ))
            
            # Thêm thanh cuộn
            scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=height_table.yview)
            height_table.configure(yscrollcommand=scrollbar.set)
            
            # Sắp xếp các widget
            height_table.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
        
        # Nút đóng
        close_button = tk.Button(
            info_window, 
            text="Đóng", 
            font=self.normal_font,
            bg="gray", 
            activebackground="darkgray",
            command=info_window.destroy,
            height=1
        )
        close_button.pack(pady=10)
    
    def return_to_main(self):
        """Thoát chương trình"""
        global running
        
        if messagebox.askyesno("Xác nhận thoát", "Bạn có chắc muốn thoát?"):
            running = False
            stop_motor()
            self.root.destroy()

# ===== CHƯƠNG TRÌNH CHÍNH =====
def main():
    global running
    
    print("\n=== CHƯƠNG TRÌNH ĐIỀU KHIỂN BÀN NÂNG ===")
    
    # Tải vị trí đã lưu
    load_positions()
    
    # Thiết lập nút bấm vật lý (nếu có)
    if has_physical_buttons:
        btn_up.when_pressed = start_motor_up
        btn_up.when_released = stop_motor
        btn_down.when_pressed = start_motor_down
        btn_down.when_released = stop_motor
        btn_mem1.when_pressed = lambda: handle_memory_button(1)
        btn_mem2.when_pressed = lambda: handle_memory_button(2)
    
    # Khởi động luồng điều khiển động cơ
    motor_thread = threading.Thread(target=motor_control_thread)
    motor_thread.daemon = True
    motor_thread.start()
    
    # Khởi động luồng theo dõi chiều cao (nếu có cảm biến)
    if has_distance_sensor:
        height_thread = threading.Thread(target=height_monitor_thread)
        height_thread.daemon = True
        height_thread.start()
    
    # Khởi động giao diện đồ họa
    root = tk.Tk()
    app = TableControlGUI(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\n\nĐang thoát chương trình...")
    finally:
        # Dọn dẹp
        running = False
        stop_motor()
        time.sleep(0.5)
        ena_pin.on()  # Vô hiệu hóa driver (ENA HIGH)
        print("Chương trình đã kết thúc.")

if __name__ == "__main__":
    main()