from flask import Flask, render_template, request, jsonify
import threading
import time
from datetime import datetime, timedelta
import sqlite3
import logging
from gpiozero import DigitalOutputDevice, Button, DistanceSensor, Device
import json
import warnings
from gpiozero.exc import DistanceSensorNoEcho
import concurrent.futures
import os
import sys
import requests
import subprocess

# Cấu hình logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Import các module bổ sung
try:
    from usage_tracker import usage_tracker
    has_usage_tracker = True
except ImportError:
    has_usage_tracker = False
    logging.error("Thư viện usage_tracker không khả dụng - chức năng quản lý người dùng sẽ bị tắt")

try:
    from height_preferences import height_prefs
    has_height_prefs = True
except ImportError:
    has_height_prefs = False
    logging.error("Thư viện height_preferences không khả dụng - chức năng quản lý độ cao sẽ bị tắt")

app = Flask(__name__)

# Đường dẫn cơ bản và DB_PATH
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_PATH, "data", "usage_stats.db")
DETECTED_USER_FILE = os.path.join(BASE_PATH, "data", "detected_user.json")

# Kiểm tra quyền truy cập file cơ sở dữ liệu
def check_db_permissions():
    try:
        if not os.path.exists(DB_PATH):
            logging.info(f"Tạo file cơ sở dữ liệu mới tại: {DB_PATH}")
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            open(DB_PATH, 'a').close()
        if not os.access(DB_PATH, os.W_OK):
            logging.error(f"Không có quyền ghi vào {DB_PATH}")
            raise PermissionError(f"Không có quyền ghi vào {DB_PATH}")
        logging.info(f"Quyền truy cập {DB_PATH} đã được xác nhận")
    except Exception as e:
        logging.error(f"Lỗi kiểm tra quyền cơ sở dữ liệu: {e}")
        raise

check_db_permissions()

# Cấu hình
try:
    from config import *
except ImportError:
    logging.info("Không thể import config.py - sử dụng cấu hình mặc định")
    FACES_DIR = os.path.join(BASE_PATH, "faces")
    SAMPLES_DIR = os.path.join(FACES_DIR, "samples")
    SOUNDS_DIR = os.path.join(BASE_PATH, "sounds")
    MODELS_DIR = os.path.join(BASE_PATH, "models")
    FACE_MODEL_PATH = os.path.join(MODELS_DIR, "face_model.yml")
    FACE_MAPPING_PATH = os.path.join(FACES_DIR, "face_mapping.pkl")
    FACE_CONFIDENCE_THRESHOLD = 70
    CAMERA_WIDTH = 640
    CAMERA_HEIGHT = 480
    FACE_GREETING_COOLDOWN = 60
    WELCOME_COOLDOWN = 30
    DETECTION_INTERVAL = 5
    FACE_DETECTION_INTERVAL = 10

# Tạo các thư mục nếu chưa tồn tại
def create_directories():
    dirs = [FACES_DIR, SAMPLES_DIR, SOUNDS_DIR, MODELS_DIR, os.path.join(BASE_PATH, "data")]
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)

create_directories()

# Khóa để đồng bộ hóa truy cập cơ sở dữ liệu và file
db_lock = threading.Lock()
file_lock = threading.Lock()

# Khởi tạo cơ sở dữ liệu
def init_db():
    try:
        with db_lock:
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
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
                logging.info("Khởi tạo cơ sở dữ liệu thành công")
    except Exception as e:
        logging.error(f"Lỗi khởi tạo cơ sở dữ liệu: {e}")
        raise

init_db()

# Cấu hình chân GPIO
ENA_PIN = 23  # Motor enable
DIR_PIN = 24  # Motor direction
PUL_PIN = 25  # Motor pulse
BTN_UP_PIN = 17
BTN_DOWN_PIN = 27
MEM_BTN_1_PIN = 22
MEM_BTN_2_PIN = 5
LIMIT_TOP_PIN = 6
LIMIT_BOTTOM_PIN = 13
TRIG_PIN = 16  # Cảm biến khoảng cách trigger
ECHO_PIN = 12  # Cảm biến khoảng cách echo
LIGHT_PIN = 26  # Chân LED

# Cài đặt điều khiển động cơ
PULSE_SPEED = 500  # Microseconds
PULSE_SLOW = 1000  # Microseconds (chậm hơn khi gần mục tiêu)
CONFIG_FILE = os.path.join(BASE_PATH, "table_heights.json")

# Biến toàn cục
processes = {}
ai_detection_active = True  # AI luôn chạy khi khởi động
motor_running = False
current_direction = None  # True = lên, False = xuống
memory_positions = {1: -1, 2: -1}  # Vị trí 1 (ngồi), 2 (đứng)
current_height = -1
moving_to_position = False
target_position = -1
running = True
auto_light_enabled = False  # Trạng thái Auto-light
manual_light_state = None  # None = tự động, True = bật, False = tắt
# Khởi tạo phần cứng
try:
    ena_pin = DigitalOutputDevice(ENA_PIN)
    dir_pin = DigitalOutputDevice(DIR_PIN)
    pul_pin = DigitalOutputDevice(PUL_PIN)
    ena_pin.off()  # Kích hoạt driver động cơ (active LOW)
    logging.info("Đã khởi tạo chân điều khiển động cơ: ENA=%s, DIR=%s, PUL=%s", ena_pin.value, dir_pin.value, pul_pin.value)
except Exception as e:
    logging.error(f"Lỗi khởi tạo chân GPIO động cơ: {e}")
    ena_pin = dir_pin = pul_pin = None

try:
    btn_up = Button(BTN_UP_PIN, pull_up=True)
    btn_down = Button(BTN_DOWN_PIN, pull_up=True)
    btn_mem1 = Button(MEM_BTN_1_PIN, pull_up=True)
    btn_mem2 = Button(MEM_BTN_2_PIN, pull_up=True)
    has_physical_buttons = True
    logging.info("Đã khởi tạo nút bấm vật lý")
except Exception as e:
    has_physical_buttons = False
    logging.warning(f"Không tìm thấy nút bấm vật lý: {e}")

try:
    limit_top = Button(LIMIT_TOP_PIN, pull_up=True)
    limit_bottom = Button(LIMIT_BOTTOM_PIN, pull_up=True)
    has_limit_switches = True
    logging.info("Đã khởi tạo công tắc giới hạn")
except Exception as e:
    has_limit_switches = False
    logging.warning(f"Không tìm thấy công tắc giới hạn: {e}")

try:
    distance_sensor = DistanceSensor(echo=ECHO_PIN, trigger=TRIG_PIN, max_distance=4)
    has_distance_sensor = True
    logging.info("Đã khởi tạo cảm biến khoảng cách")
except Exception as e:
    has_distance_sensor = False
    logging.warning(f"Không tìm thấy cảm biến khoảng cách: {e}")

try:
    light = DigitalOutputDevice(LIGHT_PIN, initial_value= False)
    has_light = True
    logging.info("Đã khởi tạo đèn")
except Exception as e:
    has_light = False   
    logging.error(f"Không thể khởi tạo đèn: {e}")

# Tải vị trí bộ nhớ
def load_positions():
    global memory_positions
    try:
        with open(CONFIG_FILE, 'r') as file:
            loaded_data = json.load(file)
            memory_positions = {1: loaded_data.get('position1', -1), 2: loaded_data.get('position2', -1)}
        logging.info(f"Đã tải vị trí bộ nhớ: 1={memory_positions[1]}cm, 2={memory_positions[2]}cm")
    except (FileNotFoundError, json.JSONDecodeError):
        memory_positions = {1: -1, 2: -1}
        save_positions()
        logging.info("Đã tạo file cấu hình vị trí mới")

def save_positions():
    try:
        data = {'position1': memory_positions[1], 'position2': memory_positions[2]}
        with open(CONFIG_FILE, 'w') as file:
            json.dump(data, file)
        logging.info(f"Đã lưu vị trí: 1={memory_positions[1]}cm, 2={memory_positions[2]}cm")
    except Exception as e:
        logging.error(f"Lỗi khi lưu vị trí: {e}")

# Đo chiều cao với timeout
def get_current_height(timeout=2):
    if not has_distance_sensor:
        logging.warning("Không có cảm biến khoảng cách, trả về -1")
        return -1
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: distance_sensor.distance)
                try:
                    distance_m = future.result(timeout=timeout)
                except concurrent.futures.TimeoutError:
                    logging.error("Timeout khi đo khoảng cách - cảm biến có thể không phản hồi")
                    return -1
            for warning in w:
                if isinstance(warning.message, DistanceSensorNoEcho):
                    logging.error(f"Lỗi cảm biến khoảng cách: {warning.message}")
                    return -1
            distance_cm = distance_m * 100
            if 2 <= distance_cm <= 400:
                return round(distance_cm)
            logging.warning(f"Chiều cao ngoài phạm vi: {distance_cm} cm")
            return -1
    except Exception as e:
        logging.error(f"Lỗi nghiêm trọng khi đo chiều cao: {e}")
        return -1

# Các hàm điều khiển động cơ
def check_limits(direction):
    if not has_limit_switches:
        return False
    if direction and limit_top.is_pressed:
        logging.info("Đạt giới hạn trên!")
        return True
    if not direction and limit_bottom.is_pressed:
        logging.info("Đạt giới hạn dưới!")
        return True
    return False

def stop_motor():
    global motor_running, moving_to_position
    motor_running = False
    moving_to_position = False
    if pul_pin:
        pul_pin.off()
    logging.info("Động cơ đã dừng, DIR=%s", dir_pin.value if dir_pin else "N/A")

# Thay thế hàm start_motor_up()
def start_motor_up():
    global motor_running, current_direction, moving_to_position
    if not ena_pin or not dir_pin or not pul_pin:
        logging.error("Motor pins not initialized")
        return
    if check_limits(True):
        logging.info("Không thể đi lên - đã đạt giới hạn trên")
        return
    if motor_running and not current_direction:  # Nếu đang chạy hướng ngược, dừng trước
        stop_motor()
        time.sleep(0.1)  # Đợi để đảm bảo động cơ dừng
    logging.info("Di chuyển LÊN, Đặt DIR=OFF")
    dir_pin.off()  # Đổi từ on() thành off() để khớp với hướng lên thực tế
    current_direction = True
    moving_to_position = False
    motor_running = True

# Thay thế hàm start_motor_down()
def start_motor_down():
    global motor_running, current_direction, moving_to_position
    if not ena_pin or not dir_pin or not pul_pin:
        logging.error("Motor pins not initialized")
        return
    if check_limits(False):
        logging.info("Không thể đi xuống - đã đạt giới hạn dưới")
        return
    if motor_running and current_direction:  # Nếu đang chạy hướng ngược, dừng trước
        stop_motor()
        time.sleep(0.1)  # Đợi để đảm bảo động cơ dừng
    logging.info("Di chuyển XUỐNG, Đặt DIR=ON")
    dir_pin.on()  # Đổi từ off() thành on() để khớp với hướng xuống thực tế
    current_direction = False
    moving_to_position = False
    motor_running = True

def move_to_position(position_num):
    global memory_positions, current_height, moving_to_position, target_position, motor_running
    if not has_distance_sensor:
        logging.error("Không thể sử dụng chức năng bộ nhớ - không có cảm biến khoảng cách")
        return
    current_height = get_current_height()
    user_height = None
    if has_height_prefs and has_usage_tracker:
        current_user = usage_tracker.get_current_user()
        if current_user and current_user.get('user_id'):
            heights = height_prefs.get_heights(current_user.get('user_id'))
            if position_num == 1 and heights['sitting'] > 0:
                user_height = heights['sitting']
                logging.info(f"Sử dụng độ cao ngồi cá nhân: {user_height}cm")
            elif position_num == 2 and heights['standing'] > 0:
                user_height = heights['standing']
                logging.info(f"Sử dụng độ cao đứng cá nhân: {user_height}cm")
    if user_height:
        logging.info(f"Di chuyển đến vị trí cá nhân {position_num}: {user_height}cm")
        target_position = user_height
        moving_to_position = True
        motor_running = True
        if has_usage_tracker and current_user:
            try:
                usage_tracker.update_position('sitting' if position_num == 1 else 'standing')
                logging.info(f"Đã ghi trạng thái: {'sitting' if position_num == 1 else 'standing'} cho user_id={current_user.get('user_id')}")
            except Exception as e:
                logging.error(f"Lỗi ghi trạng thái vào positions: {e}")
        return
    if memory_positions[position_num] == -1 and current_height > 0:
        memory_positions[position_num] = current_height
        save_positions()
        logging.info(f"Đã lưu vị trí {position_num}: {current_height}cm")
    elif memory_positions[position_num] > 0:
        if current_height > 0:
            logging.info(f"Di chuyển đến vị trí {position_num}: {memory_positions[position_num]}cm")
            target_position = memory_positions[position_num]
            moving_to_position = True
            motor_running = True
            if has_usage_tracker and current_user:
                try:
                    usage_tracker.update_position('sitting' if position_num == 1 else 'standing')
                    logging.info(f"Đã ghi trạng thái: {'sitting' if position_num == 1 else 'standing'} cho user_id={current_user.get('user_id')}")
                except Exception as e:
                    logging.error(f"Lỗi ghi trạng thái vào positions: {e}")
        else:
            logging.error("Không thể di chuyển - cảm biến khoảng cách không hoạt động")

def motor_control_thread():
    global running, motor_running, current_direction, moving_to_position, target_position, current_height
    logging.info("Motor control thread started")
    while running:
        try:
            if motor_running and pul_pin:
                if moving_to_position and has_distance_sensor:
                    current_height = get_current_height()
                    if current_height > 0 and target_position > 0:
                        distance_to_target = abs(current_height - target_position)
                        if distance_to_target <= 2:
                            logging.info(f"Đã đến vị trí mục tiêu: {current_height}cm")
                            stop_motor()
                            continue
                        new_direction = current_height < target_position
                        if new_direction != current_direction:
                            logging.info(f"Đổi hướng từ {current_direction} sang {new_direction}")
                            stop_motor()  # Dừng trước khi đổi hướng
                            time.sleep(0.1)  # Đợi để đảm bảo dừng
                            current_direction = new_direction
                            dir_pin.on() if current_direction else dir_pin.off()
                            logging.info(f"Đã đặt DIR={dir_pin.value if dir_pin else 'N/A'}")
                        pulse_time = PULSE_SLOW if distance_to_target < 10 else PULSE_SPEED
                    else:
                        stop_motor()
                        continue
                else:
                    pulse_time = PULSE_SPEED
                if check_limits(current_direction):
                    stop_motor()
                    continue
                pul_pin.on()
                time.sleep(pulse_time / 1000000)  # Chuyển từ micro giây sang giây
                pul_pin.off()
                time.sleep(pulse_time / 1000000)
            else:
                time.sleep(0.01)
        except Exception as e:
            logging.error(f"Error in motor control thread: {e}")
            time.sleep(1)

# Cập nhật auto_light_thread
def auto_light_thread():
    global running, auto_light_enabled, light, manual_light_state
    logging.info("Auto-light thread started")
    while running:
        if auto_light_enabled and has_light and light:
            lux = read_light_level()
            logging.debug(f"Auto-light: lux = {lux}, light.value = {light.value}, manual_light_state = {manual_light_state}")
            if manual_light_state is not None:
                manual_light_state = None
                logging.info("Auto-light: Đã reset trạng thái thủ công")
            if lux < 50:
                if not light.value:
                    light.on()
                    logging.info("Auto-light: Bật đèn do mức ánh sáng thấp")
            elif lux >= 50:
                if light.value:
                    light.off()
                    logging.info("Auto-light: Tắt đèn do mức ánh sáng cao")
                else:
                    # Buộc tắt nếu phần cứng không phản hồi
                    light.off()
                    logging.warning("Auto-light: Trạng thái không khớp, buộc tắt đèn")
        time.sleep(1)  # Giảm thời gian sleep để phản hồi nhanh hơn
def height_monitor_thread():
    global running, current_height
    while running and has_distance_sensor:
        current_height = get_current_height()
        time.sleep(0.2)

def get_detected_user():
    try:
        for _ in range(3):  # Thử 3 lần
            with file_lock:
                if os.path.exists(DETECTED_USER_FILE):
                    with open(DETECTED_USER_FILE, 'r') as f:
                        user_data = json.load(f)
                    return user_data if user_data.get('user_id') and user_data.get('user_name') else None
            time.sleep(0.1)  # Chờ 100ms trước khi thử lại
        logging.warning("Không thể đọc detected_user.json sau 3 lần thử")
        return None
    except Exception as e:
        logging.error(f"Lỗi khi đọc detected_user.json: {e}")
        return None

def user_detection_thread():
    global running, has_usage_tracker
    logging.info("User detection thread started")
    last_user_id = None
    while running and has_usage_tracker:
        try:
            detected_user = get_detected_user()
            if detected_user:
                current_user = usage_tracker.get_current_user()
                current_user_id = current_user.get('user_id') if current_user else None
                if detected_user.get('user_id') != current_user_id:
                    with db_lock:
                        if current_user_id and usage_tracker.tracking_active:
                            usage_tracker.stop_tracking()
                            logging.info(f"Kết thúc phiên cho user_id={current_user_id}")
                        user_data = usage_tracker.start_tracking(user_name=detected_user.get('user_name'), user_id=detected_user.get('user_id'))
                        logging.info(f"Tự động chuyển sang phiên user: {user_data.get('user_name')}, user_id={user_data.get('user_id')}")
                last_user_id = detected_user.get('user_id')
            time.sleep(2)  # Kiểm tra mỗi 2 giây
        except Exception as e:
            logging.error(f"Lỗi trong user_detection_thread: {e}")
            time.sleep(5)

# Cài đặt nút bấm vật lý
if has_physical_buttons:
    btn_up.when_pressed = start_motor_up
    btn_up.when_released = stop_motor
    btn_down.when_pressed = start_motor_down
    btn_down.when_released = stop_motor
    btn_mem1.when_pressed = lambda: move_to_position(1)
    btn_mem2.when_pressed = lambda: move_to_position(2)

# Khởi động các luồng
motor_thread = threading.Thread(target=motor_control_thread)
motor_thread.daemon = True
motor_thread.start()

if has_distance_sensor:
    height_thread = threading.Thread(target=height_monitor_thread)
    height_thread.daemon = True
    height_thread.start()

if has_light:
    auto_light_thread = threading.Thread(target=auto_light_thread)
    auto_light_thread.daemon = True
    auto_light_thread.start()

if has_usage_tracker:
    user_detection_thread = threading.Thread(target=user_detection_thread)
    user_detection_thread.daemon = True
    user_detection_thread.start()

def run_script(script_name):
    script_path = os.path.join(BASE_PATH, script_name)
    if not os.path.exists(script_path):
        logging.error(f"Không tìm thấy file {script_path}")
        return False, f"Không tìm thấy file {script_path}"
    try:
        if sys.platform.startswith('linux'):
            subprocess.run(["pkill", "-f", "python.*module_ai.py"], check=False)
            time.sleep(1)
        process = subprocess.Popen([sys.executable, script_path])
        processes[script_name] = process
        logging.info(f"Đã chạy {script_name}")
        return True, f"Đã chạy {script_name}"
    except Exception as e:
        logging.error(f"Lỗi khi chạy {script_name}: {e}")
        return False, f"Lỗi khi chạy {script_name}: {str(e)}"

# Khởi động AI detection
def start_ai_detection():
    global ai_detection_active
    success, message = run_script('module_ai.py')
    if success:
        ai_detection_active = True
        logging.info("AI detection started automatically")
    else:
        logging.error(f"Failed to start AI detection: {message}")
        ai_detection_active = False

start_ai_detection()
load_positions()

# Các route Flask
@app.route('/')
def index():
    stats = get_usage_stats()
    current_user = usage_tracker.get_current_user() if has_usage_tracker else None
    logging.debug(f"Current user in index: {current_user}")
    if current_user:
        logging.info(f"Rendering index with current_user: {current_user}")
    else:
        logging.info("Rendering index with no current_user")
    return render_template('index.html', stats=stats, current_user=current_user)

@app.route('/set_user', methods=['POST'])
def set_user():
    logging.debug(f"Yêu cầu set_user: user_name={request.form.get('user_name')}")
    if not has_usage_tracker:
        logging.warning("Tính năng quản lý người dùng không khả dụng")
        return jsonify({'success': False, 'message': 'Tính năng quản lý người dùng không khả dụng'})
    user_name = request.form.get('user_name')
    if not user_name:
        logging.warning("Tên người dùng không hợp lệ")
        return jsonify({'success': False, 'message': 'Tên người dùng không hợp lệ'})
    try:
        with db_lock:
            user_data = usage_tracker.start_tracking(user_name=user_name)
        logging.info(f"Started tracking for user: {user_name}, user_data={user_data}")
        return jsonify({
            'success': True,
            'message': f'Đã thiết lập người dùng: {user_name}',
            'user_id': user_data.get('user_id') if user_data else None
        })
    except Exception as e:
        logging.error(f"Error starting tracking for user {user_name}: {e}")
        return jsonify({'success': False, 'message': f'Lỗi khi thiết lập người dùng: {str(e)}'})

@app.route('/end_session', methods=['POST'])
def end_session():
    logging.debug("Yêu cầu end_session")
    if not has_usage_tracker:
        logging.warning("Tính năng quản lý người dùng không khả dụng")
        return jsonify({'success': False, 'message': 'Tính năng quản lý người dùng không khả dụng'})
    try:
        if not hasattr(usage_tracker, 'tracking_active') or not usage_tracker.tracking_active:
            logging.warning("No active session to end")
            return jsonify({'success': False, 'message': 'Không có phiên đang hoạt động'})
        with db_lock:
            session_data = usage_tracker.stop_tracking()
        logging.info(f"Session ended, session_data={session_data}")
        return jsonify({'success': True, 'message': 'Đã kết thúc phiên'})
    except Exception as e:
        logging.error(f"Error ending session: {e}")
        return jsonify({'success': False, 'message': f'Lỗi khi kết thúc phiên: {str(e)}'})

@app.route('/environment')
def environment():
    info = get_environment_info()
    current_user = usage_tracker.get_current_user() if has_usage_tracker else None
    if info:
        return render_template('environment.html', info=info, current_user=current_user)
    return render_template('environment.html', info=None, current_user=current_user)

@app.route('/light_control')
def light_control():
    lux = read_light_level()
    light_state = "Bật" if has_light and light and light.value else "Tắt"
    current_user = usage_tracker.get_current_user() if has_usage_tracker else None
    return render_template('light_control.html', lux=lux, light_state=light_state, current_user=current_user, auto_light_enabled=auto_light_enabled)

# Cập nhật toggle_light
@app.route('/light_control/toggle', methods=['POST'])
def toggle_light():
    global auto_light_enabled, manual_light_state
    logging.debug("Yêu cầu toggle_light")
    try:
        if light is None:
            logging.error("Đèn không khả dụng")
            return jsonify({'status': 'error', 'message': 'Đèn không khả dụng'}), 500
        if auto_light_enabled:
            logging.warning("Auto-light đang bật, không thể điều khiển thủ công")
            return jsonify({'status': 'error', 'message': 'Auto-light đang bật'}), 400
        # Đặt trạng thái thủ công và áp dụng
        manual_light_state = not light.value if manual_light_state is None else not manual_light_state
        light.value = manual_light_state
        new_state = "Bật" if light.value else "Tắt"
        lux = read_light_level()
        # Kiểm tra nếu trạng thái không thay đổi (lỗi phần cứng)
        if light.value != manual_light_state:
            logging.error("Phần cứng không phản hồi lệnh điều khiển đèn")
            return jsonify({'status': 'error', 'message': 'Phần cứng không phản hồi'}), 500
        logging.info(f"Đèn chuyển sang trạng thái thủ công: {new_state}, lux: {lux}")
        return jsonify({
            'status': 'success',
            'light_state': new_state,
            'lux': lux
        })
    except Exception as e:
        logging.error(f"Lỗi khi bật/tắt đèn: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/light_control/toggle_auto', methods=['POST'])
def toggle_auto_light():
    global auto_light_enabled
    logging.debug("Yêu cầu toggle_auto_light")
    try:
        auto_light_enabled = not auto_light_enabled
        logging.info(f"Auto-light: {'Bật' if auto_light_enabled else 'Tắt'}")
        return jsonify({
            'status': 'success',
            'auto_light_enabled': auto_light_enabled
        })
    except Exception as e:
        logging.error(f"Lỗi khi bật/tắt Auto-light: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/table_control')
def table_control():
    logging.debug("Yêu cầu table_control")
    global current_height
    try:
        logging.debug("Bắt đầu xử lý table_control")
        current_height = get_current_height(timeout=2)
        status = "Đang di chuyển" if motor_running else "Dừng"
        current_user = None
        if has_usage_tracker:
            logging.debug("Gọi usage_tracker.get_current_user")
            current_user = usage_tracker.get_current_user()
            logging.debug(f"Người dùng hiện tại: {current_user}")

        preferred_heights = {'sitting': -1, 'standing': -1}
        sensor_error = False

        if current_height == -1:
            logging.warning("Không thể đọc chiều cao, sử dụng giá trị mặc định")
            sensor_error = True

        if has_height_prefs and has_usage_tracker and current_user and current_user.get('user_id'):
            logging.debug(f"Lấy preferred_heights cho user_id={current_user['user_id']}")
            try:
                preferred_heights = height_prefs.get_heights(current_user['user_id'])
                logging.debug(f"preferred_heights: {preferred_heights}")
            except Exception as e:
                logging.error(f"Lỗi khi lấy preferred_heights: {e}")
                preferred_heights = {'sitting': -1, 'standing': -1}

        logging.info(f"Render table_control.html với height={current_height}, status={status}, "
                     f"current_user={current_user}, preferred_heights={preferred_heights}, "
                     f"memory_positions={memory_positions}, sensor_error={sensor_error}")
        return render_template('table_control.html', height=current_height, status=status,
                              memory_positions=memory_positions, current_user=current_user,
                              preferred_heights=preferred_heights, sensor_error=sensor_error)
    except Exception as e:
        logging.error(f"Lỗi nghiêm trọng trong route /table_control: {e}", exc_info=True)
        return render_template('table_control.html', height=-1, status="Lỗi",
                              memory_positions=memory_positions, current_user=None,
                              preferred_heights={'sitting': -1, 'standing': -1}, sensor_error=True)

@app.route('/table_control/move', methods=['POST'])
def move_table():
    logging.debug(f"Yêu cầu move_table: action={request.form.get('action')}")
    action = request.form.get('action')
    if action == 'up':
        start_motor_up()
    elif action == 'down':
        start_motor_down()
    elif action == 'stop':
        stop_motor()
    elif action == 'pos1':
        move_to_position(1)
    elif action == 'pos2':
        move_to_position(2)
    current_height = get_current_height()
    status = "Đang di chuyển" if motor_running else "Dừng"
    return jsonify({'status': 'success', 'height': current_height, 'status_text': status})

@app.route('/set_height/<position>', methods=['POST'])
def set_height():
    logging.debug(f"Yêu cầu set_height: position={position}")
    if not has_height_prefs:
        logging.warning("Tính năng quản lý độ cao không khả dụng")
        return jsonify({'success': False, 'message': 'Tính năng quản lý độ cao không khả dụng'})
    if position not in ['sitting', 'standing']:
        logging.warning(f"Vị trí không hợp lệ: {position}")
        return jsonify({'success': False, 'message': 'Vị trí không hợp lệ'})
    current_user = usage_tracker.get_current_user() if has_usage_tracker else None
    if not current_user or not current_user.get('user_id'):
        logging.warning("Không có người dùng hiện tại")
        return jsonify({'success': False, 'message': 'Không có người dùng hiện tại'})
    current_height = get_current_height()
    if current_height <= 0:
        logging.error("Không thể đọc chiều cao hiện tại")
        return jsonify({'success': False, 'message': 'Không thể đọc chiều cao hiện tại'})
    try:
        with db_lock:
            if position == 'sitting':
                height_prefs.save_height(current_user['user_id'], sitting_height=current_height)
            else:
                height_prefs.save_height(current_user['user_id'], standing_height=current_height)
        logging.info(f"Đã thiết lập độ cao {position}: {current_height} cm cho user_id={current_user['user_id']}")
        return jsonify({'success': True, 'message': f'Đã thiết lập độ cao {position}: {current_height} cm'})
    except Exception as e:
        logging.error(f"Lỗi khi lưu độ cao {position}: {e}")
        return jsonify({'success': False, 'message': f'Lỗi khi lưu độ cao: {str(e)}'})

@app.route('/run_script/<script_name>', methods=['POST'])
def run_script_route(script_name):
    logging.debug(f"Yêu cầu run_script: script_name={script_name}")
    success, message = run_script(script_name)
    return jsonify({'success': success, 'message': message})

@app.route('/usage_stats_detail', methods=['GET'])
def usage_stats():
    stats = get_usage_stats()
    current_user = usage_tracker.get_current_user() if has_usage_tracker else None
    if stats:
        return render_template('usage_stats_detail.html', stats=stats, current_user=current_user)
    return jsonify({'error': 'Không thể lấy thống kê'}), 500

@app.route('/get_current_user')
def get_current_user():
    current_user = usage_tracker.get_current_user() if has_usage_tracker else None
    return jsonify({'user_name': current_user.get('user_name') if current_user else None})

# Hằng số cho cảm biến BH1750
DEVICE = 0x23  # Địa chỉ I2C của BH1750
POWER_DOWN = 0x00
POWER_ON = 0x01
RESET = 0x07
CONTINUOUS_HIGH_RES_MODE = 0x10

# Khởi tạo I2C bus toàn cục
try:
    import smbus2
    bus = smbus2.SMBus(1)  # Bus 1 trên Raspberry Pi
    logging.info("Khởi tạo I2C bus thành công")
except Exception as e:
    bus = None
    logging.error(f"Lỗi khởi tạo I2C bus: {e}")

def read_light_level():
    logging.debug("Gọi read_light_level")
    if bus is None:
        logging.error("I2C bus không khả dụng")
        return 0.0
    try:
        bus.write_byte(DEVICE, CONTINUOUS_HIGH_RES_MODE)
        time.sleep(0.2)
        data = bus.read_i2c_block_data(DEVICE, CONTINUOUS_HIGH_RES_MODE, 2)
        lux = (data[1] + (256 * data[0])) / 1.2
        lux = round(lux, 2)
        return lux
    except Exception as e:
        logging.error(f"Lỗi khi đọc cảm biến BH1750: {e}")
        return 0.0

def get_environment_info():
    logging.debug("Gọi get_environment_info")
    try:
        api_key = "56d1bc96c2b004e6bd34089b5154da42"
        city = "Ho+Chi+Minh+City"
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric&lang=vi"
        logging.debug(f"OpenWeatherMap API URL: {url}")
        response = requests.get(url, timeout=5)
        data = response.json()
        logging.debug(f"OpenWeatherMap API Response: {data}")
        if 'cod' in data and data['cod'] != 200:
            logging.error(f"Lỗi API OpenWeatherMap: {data.get('message', 'Không rõ')}")
            return None
        if 'main' not in data or 'weather' not in data or 'wind' not in data or 'clouds' not in data:
            logging.error("Dữ liệu thời tiết không đúng định dạng")
            return None
        info = {
            'temperature': round(data['main']['temp'], 1),
            'humidity': int(data['main']['humidity']),
            'description': data['weather'][0]['description'].capitalize(),
            'wind_speed': round(data['wind']['speed'], 1),
            'pressure': int(data['main']['pressure']),
            'clouds': int(data['clouds']['all'])
        }
        logging.info(f"Thông tin môi trường: {info}")
        return info
    except requests.exceptions.RequestException as e:
        logging.error(f"Lỗi khi gọi API OpenWeatherMap: {e}")
        return None
    except Exception as e:
        logging.error(f"Lỗi không xác định trong get_environment_info: {e}")
        return None

def stop_process(process_name):
    if process_name in processes:
        process = processes[process_name]
        try:
            process.terminate()
            process.wait(timeout=2)
            logging.info(f"Đã dừng process {process_name}")
        except subprocess.TimeoutExpired:
            process.kill()
            logging.warning(f"Đã buộc dừng process {process_name}")
        del processes[process_name]

def get_usage_stats():
    if not os.path.exists(DB_PATH):
        logging.warning(f"Database file {DB_PATH} does not exist")
        init_db()
        return {
            'total_time': 0,
            'today_time': 0,
            'week_time': 0,
            'avg_time': 0,
            'sit_time': 0,
            'stand_time': 0,
            'sit_percent': 0,
            'stand_percent': 0,
            'users': []
        }
    try:
        with db_lock:
            with sqlite3.connect(DB_PATH, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT SUM(duration) FROM sessions")
                total_time = cursor.fetchone()[0] or 0
                today = datetime.now().strftime("%Y-%m-%d")
                cursor.execute("SELECT SUM(duration) FROM sessions WHERE date(start_time) = ?", (today,))
                today_time = cursor.fetchone()[0] or 0
                week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
                cursor.execute("SELECT SUM(duration) FROM sessions WHERE date(start_time) >= ?", (week_start,))
                week_time = cursor.fetchone()[0] or 0
                cursor.execute("SELECT COUNT(DISTINCT date(start_time)) FROM sessions")
                days_count = cursor.fetchone()[0] or 1
                avg_time = total_time / days_count
                cursor.execute("SELECT position, SUM(duration) FROM positions GROUP BY position")
                position_results = cursor.fetchall()
                sit_time = stand_time = 0
                for position, duration in position_results:
                    position = position.lower() if position else ""
                    if position in ("sit", "ngoi"):
                        sit_time += duration
                    elif position in ("stand", "dung"):
                        stand_time += duration
                total_position_time = sit_time + stand_time
                sit_percent = (sit_time / total_position_time * 100) if total_position_time > 0 else 0
                stand_percent = (stand_time / total_position_time * 100) if total_position_time > 0 else 0
                cursor.execute('''
                    SELECT COALESCE(user_name, 'Không xác định') as user,
                           SUM(duration) as total_duration,
                           COUNT(*) as session_count,
                           AVG(duration) as avg_duration
                    FROM sessions
                    GROUP BY user_id
                    ORDER BY total_duration DESC
                    LIMIT 5
                ''')
                user_results = cursor.fetchall()
                users = [
                    {
                        'user': user,
                        'total': total_duration / 3600 if total_duration else 0,
                        'count': session_count,
                        'average': avg_duration / 60 if avg_duration else 0
                    }
                    for user, total_duration, session_count, avg_duration in user_results
                ]
                logging.debug(f"Usage stats: total_time={total_time/3600}, today_time={today_time/3600}, users={users}")
                return {
                    'total_time': total_time / 3600,
                    'today_time': today_time / 3600,
                    'week_time': week_time / 3600,
                    'avg_time': avg_time / 3600,
                    'sit_time': sit_time / 3600,
                    'stand_time': stand_time / 3600,
                    'sit_percent': sit_percent,
                    'stand_percent': stand_percent,
                    'users': users
                }
    except Exception as e:
        logging.error(f"Lỗi khi lấy thống kê: {e}")
        return {
            'total_time': 0,
            'today_time': 0,
            'week_time': 0,
            'avg_time': 0,
            'sit_time': 0,
            'stand_time': 0,
            'sit_percent': 0,
            'stand_percent': 0,
            'users': []
        }

def cleanup_gpio():
    global running
    running = False
    stop_motor()
    if ena_pin:
        ena_pin.on()  # Tắt driver động cơ
    pins = [LIGHT_PIN, ENA_PIN, DIR_PIN, PUL_PIN, BTN_UP_PIN, BTN_DOWN_PIN,
            MEM_BTN_1_PIN, MEM_BTN_2_PIN, LIMIT_TOP_PIN, LIMIT_BOTTOM_PIN, TRIG_PIN, ECHO_PIN]
    for pin in pins:
        try:
            device = Device.pin(pin)
            if device:
                device.close()
                logging.info(f"Đã giải phóng GPIO {pin}")
        except:
            pass
    if has_light and light:
        light.close()
        logging.info("Đã giải phóng GPIO cho đèn")

def cleanup():
    stop_process('module_ai.py')
    for script_name in list(processes.keys()):
        stop_process(script_name)
    cleanup_gpio()

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    finally:
        cleanup()