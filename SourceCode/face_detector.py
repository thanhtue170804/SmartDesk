# face_detector.py - Các hàm phát hiện khuôn mặt

import cv2
import os
import numpy as np
from datetime import datetime
import pickle
import time
from config import *

def load_face_detector():
    """Tải bộ phát hiện khuôn mặt sử dụng Haar Cascade"""
    # Các đường dẫn thông thường cho file Haar Cascade
    common_paths = [
        "/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml",
        "/usr/local/share/opencv4/haarcascades/haarcascade_frontalface_default.xml",
        "/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml",
        "/usr/local/share/opencv/haarcascades/haarcascade_frontalface_default.xml"
    ]
    
    # Kiểm tra các đường dẫn
    detector_path = None
    for path in common_paths:
        if os.path.exists(path):
            detector_path = path
            break
    
    # Nếu không tìm thấy, tải xuống
    if detector_path is None:
        print("Không tìm thấy file haar cascade. Đang tải xuống...")
        import urllib.request
        
        # Tạo thư mục models nếu chưa tồn tại
        models_dir = os.path.join(BASE_PATH, "models")
        os.makedirs(models_dir, exist_ok=True)
        
        # Tải file cascade từ GitHub
        detector_path = os.path.join(models_dir, "haarcascade_frontalface_default.xml")
        url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
        
        try:
            urllib.request.urlretrieve(url, detector_path)
            print(f"Đã tải file haar cascade: {detector_path}")
        except Exception as e:
            print(f"Lỗi khi tải file haar cascade: {e}")
            return None
    
    # Tải detector
    face_detector = cv2.CascadeClassifier(detector_path)
    if face_detector.empty():
        print(f"Không thể tải file cascade từ: {detector_path}")
        return None
        
    print(f"Đã tải bộ phát hiện khuôn mặt từ: {detector_path}")
    return face_detector

def detect_faces(frame, face_detector):
    """Phát hiện khuôn mặt trong khung hình"""
    # Chuyển sang ảnh xám để xử lý nhanh hơn
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Phát hiện khuôn mặt trong ảnh xám
    faces = face_detector.detectMultiScale(
        gray, 
        scaleFactor=1.1,        # Hệ số tỷ lệ khi thay đổi kích thước ảnh
        minNeighbors=5,         # Số lượng hàng xóm tối thiểu
        minSize=(30, 30),       # Kích thước tối thiểu của khuôn mặt
        flags=cv2.CASCADE_SCALE_IMAGE
    )
    
    # Trả về danh sách các khuôn mặt (x, y, w, h)
    return faces

def create_face_recognizer():
    """Tạo và tải bộ nhận diện khuôn mặt"""
    # Sử dụng LBPH (Local Binary Patterns Histograms) - nhẹ và hiệu quả cho Raspberry Pi
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    return recognizer

def register_new_face(frame, face_detector, name=None):
    """Đăng ký khuôn mặt mới từ khung hình"""
    # Phát hiện khuôn mặt
    faces = detect_faces(frame, face_detector)
    
    if len(faces) == 0:
        return False, "Không tìm thấy khuôn mặt trong khung hình"
    
    # Nếu phát hiện nhiều khuôn mặt, lấy khuôn mặt lớn nhất
    if len(faces) > 1:
        print(f"Phát hiện {len(faces)} khuôn mặt, đang chọn khuôn mặt lớn nhất")
        # Tính diện tích của mỗi khuôn mặt
        face_areas = [w*h for (x, y, w, h) in faces]
        # Chọn khuôn mặt có diện tích lớn nhất
        largest_face_idx = np.argmax(face_areas)
        x, y, w, h = faces[largest_face_idx]
    else:
        x, y, w, h = faces[0]
    
    # Đảm bảo thư mục tồn tại
    os.makedirs(SAMPLES_DIR, exist_ok=True)
    
    # Đọc file mapping hiện tại hoặc tạo mới
    face_info = {}
    next_id = 1
    
    if os.path.exists(FACE_MAPPING_PATH):
        with open(FACE_MAPPING_PATH, 'rb') as f:
            face_info = pickle.load(f)
            # Tìm ID tiếp theo
            if face_info:
                next_id = max(face_info.keys()) + 1
    
    # Tạo ID mới cho khuôn mặt
    face_id = next_id
    
    # Nếu không có tên, tạo tên mặc định
    if not name or name.strip() == "":
        name = f"Người dùng {face_id}"
    
    # Cắt khuôn mặt
    face_roi = frame[y:y+h, x:x+w]
    
    # Chuyển sang ảnh xám
    face_gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
    
    # Lưu ảnh khuôn mặt (lưu 5 mẫu để tăng độ chính xác)
    for i in range(1, 6):
        filename = f"face_{face_id}_sample_{i}.jpg"
        filepath = os.path.join(SAMPLES_DIR, filename)
        cv2.imwrite(filepath, face_gray)
        print(f"Đã lưu mẫu {i} cho khuôn mặt {face_id}")
    
    # Cập nhật mapping
    face_info[face_id] = {
        "name": name,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "samples": 5
    }
    
    # Lưu mapping
    with open(FACE_MAPPING_PATH, 'wb') as f:
        pickle.dump(face_info, f)
    
    # Tạo file âm thanh cá nhân cho người dùng mới
    try:
        print(f"Đang tạo âm thanh cá nhân cho {name}...")
        
        # Import module tạo âm thanh
        from tts_generator import create_time_based_greetings
        create_time_based_greetings(face_id, name)
        
        print(f"Đã tạo âm thanh cá nhân cho người dùng {name}")
    except Exception as e:
        print(f"Lỗi khi tạo âm thanh cá nhân: {e}")
    
    return True, f"Đã đăng ký khuôn mặt mới: {name} (ID: {face_id})"

def train_face_recognizer(face_recognizer):
    """Huấn luyện bộ nhận diện khuôn mặt với dữ liệu đã lưu"""
    # Danh sách ảnh và nhãn
    face_samples = []
    face_ids = []
    
    # Nếu thư mục samples không tồn tại thì tạo mới
    if not os.path.exists(SAMPLES_DIR):
        os.makedirs(SAMPLES_DIR)
        return False, "Chưa có dữ liệu khuôn mặt để huấn luyện"
    
    # Đọc file mapping nếu có
    face_info = {}
    if os.path.exists(FACE_MAPPING_PATH):
        with open(FACE_MAPPING_PATH, 'rb') as f:
            face_info = pickle.load(f)
    
    # Duyệt qua tất cả các file ảnh trong thư mục samples
    for filename in os.listdir(SAMPLES_DIR):
        if filename.endswith('.jpg') or filename.endswith('.png'):
            # Lấy face_id từ tên file (ví dụ: face_1_sample_1.jpg -> face_id = 1)
            face_id = int(filename.split('_')[1])
            
            # Đọc ảnh
            img_path = os.path.join(SAMPLES_DIR, filename)
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)  # Đọc dưới dạng ảnh xám
            
            # Thêm vào danh sách
            face_samples.append(img)
            face_ids.append(face_id)
    
    # Kiểm tra xem có đủ dữ liệu không
    if len(face_samples) == 0:
        return False, "Không có ảnh khuôn mặt trong thư mục samples"
    
    # Huấn luyện recognizer
    print(f"Đang huấn luyện với {len(face_samples)} ảnh khuôn mặt...")
    face_recognizer.train(face_samples, np.array(face_ids))
    
    # Lưu mô hình đã huấn luyện
    os.makedirs(os.path.dirname(FACE_MODEL_PATH), exist_ok=True)
    face_recognizer.save(FACE_MODEL_PATH)
    
    return True, f"Đã huấn luyện xong với {len(face_samples)} ảnh khuôn mặt"

def load_face_data(face_recognizer):
    """Tải dữ liệu khuôn mặt và mô hình nhận diện"""
    face_info = {}
    
    # Kiểm tra và tải mapping
    if os.path.exists(FACE_MAPPING_PATH):
        with open(FACE_MAPPING_PATH, 'rb') as f:
            face_info = pickle.load(f)
    
    # Kiểm tra và tải mô hình
    if os.path.exists(FACE_MODEL_PATH):
        face_recognizer.read(FACE_MODEL_PATH)
        print("Đã tải mô hình nhận diện khuôn mặt")
        return True, face_info
    else:
        print("Không tìm thấy mô hình nhận diện khuôn mặt")
        return False, face_info