# config.py - Cài đặt và cấu hình chung

import os

# Đường dẫn gốc
BASE_PATH = os.path.dirname(os.path.abspath(__file__))

# Cấu hình thư mục dữ liệu
FACES_DIR = os.path.join(BASE_PATH, "faces")
SAMPLES_DIR = os.path.join(FACES_DIR, "samples")
SOUNDS_DIR = os.path.join(BASE_PATH, "sounds")
MODELS_DIR = os.path.join(BASE_PATH, "models")

# Cấu hình nhận diện
FACE_MODEL_PATH = os.path.join(MODELS_DIR, "face_model.yml")
FACE_MAPPING_PATH = os.path.join(FACES_DIR, "face_mapping.pkl")
FACE_CONFIDENCE_THRESHOLD = 70  # Ngưỡng tin cậy cho nhận diện khuôn mặt

# Cấu hình YOLO
YOLO_CONFIG = os.path.join(BASE_PATH, 'yolov4-tiny.cfg')
YOLO_WEIGHTS = os.path.join(BASE_PATH, 'yolov4-tiny.weights')
YOLO_CLASSES = os.path.join(BASE_PATH, 'coco.names')

# Cấu hình camera
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

# Cấu hình thời gian
FACE_GREETING_COOLDOWN = 60  # Thời gian chờ giữa các lần chào (giây)
WELCOME_COOLDOWN = 30  # Thời gian chờ giữa các lần chào chung (giây)

# Cấu hình phát hiện
DETECTION_INTERVAL = 5  # Phát hiện người mỗi x khung hình
FACE_DETECTION_INTERVAL = 10  # Nhận diện khuôn mặt mỗi x khung hình

# Tạo các thư mục cần thiết
def create_directories():
    """Tạo các thư mục cần thiết nếu chưa tồn tại"""
    dirs = [FACES_DIR, SAMPLES_DIR, SOUNDS_DIR, MODELS_DIR]
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)