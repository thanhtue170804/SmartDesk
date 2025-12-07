#!/usr/bin/env python3
# module_ai.py - Module nhận diện người và khuôn mặt

import cv2
import numpy as np
import os
import time
import sys
import signal
import threading
import tkinter as tk
from tkinter import simpledialog
from datetime import datetime
import json
import logging

# Cấu hình logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Import các module phụ thuộc
try:
    from picamera2 import Picamera2
    has_picamera = True
except ImportError:
    has_picamera = False
    logging.warning("Không tìm thấy module picamera2 - sử dụng camera thông thường")

# Import audio_player
try:
    from audio_player import play_welcome_sound, play_personalized_greeting
    has_audio = True
except ImportError:
    has_audio = False
    logging.warning("Không tìm thấy module audio_player - tắt tính năng âm thanh")

# Import face_detector
try:
    from face_detector import (
        load_face_detector, detect_faces, create_face_recognizer, load_face_data,
        register_new_face, train_face_recognizer
    )
    has_face_detection = True
except ImportError:
    has_face_detection = False
    logging.warning("Không tìm thấy module face_detector - tắt tính năng nhận diện khuôn mặt")

# Import yolo_detector
try:
    from yolo_detector import load_yolo_model, detect_people
    has_yolo = True
except ImportError:
    has_yolo = False
    logging.warning("Không tìm thấy module yolo_detector - tắt tính năng nhận diện người")

# Import modules quản lý độ cao và theo dõi người dùng
try:
    from usage_tracker import usage_tracker
    from height_preferences import height_prefs
    has_height_features = True
except ImportError:
    has_height_features = False
    logging.warning("Không tìm thấy module height_preferences hoặc usage_tracker - tắt tính năng quản lý độ cao")

# Đường dẫn thư mục
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
DETECTED_USER_FILE = os.path.join(BASE_PATH, "data", "detected_user.json")

# Cấu hình mặc định
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
FRAME_RATE = 10  # FPS

# Thời gian chờ giữa các lần chào
FACE_GREETING_COOLDOWN = 60  # giây
WELCOME_COOLDOWN = 30  # giây

# Tần suất phát hiện
DETECTION_INTERVAL = 5  # Phát hiện người mỗi x khung hình
FACE_DETECTION_INTERVAL = 10  # Nhận diện khuôn mặt mỗi x khung hình

# Biến toàn cục
running = True
is_playing_sound = False
file_lock = threading.Lock()

def signal_handler(sig, frame):
    """Xử lý tín hiệu tắt chương trình"""
    global running
    logging.info("\nĐang tắt chương trình...")
    running = False

def save_detected_user(user):
    """Lưu thông tin người dùng được nhận diện vào detected_user.json"""
    try:
        with file_lock:
            with open(DETECTED_USER_FILE, 'w') as f:
                json.dump(user if user else {}, f)
            logging.debug(f"Đã lưu detected_user.json: {json.dumps(user)}")
    except Exception as e:
        logging.error(f"Lỗi khi lưu detected_user.json: {e}")

class AIDetector:
    def __init__(self):
        """Khởi tạo bộ nhận diện AI"""
        self.camera = None
        
        # Khởi tạo người dùng đã phát hiện
        self.recognized_faces = {}  # {face_id: last_time}
        self.person_detected = False
        self.last_person_time = 0
        
        # Khởi tạo các thành phần nhận diện
        self.init_detectors()
    
    def init_detectors(self):
        """Khởi tạo các bộ nhận diện"""
        # Khởi tạo bộ nhận diện khuôn mặt
        self.face_detector = None
        self.face_recognizer = None
        self.face_info = {}
        
        if has_face_detection:
            logging.info("Đang khởi tạo bộ phát hiện khuôn mặt...")
            self.face_detector = load_face_detector()
            if self.face_detector is not None:
                self.face_recognizer = create_face_recognizer()
                has_face_model, self.face_info = load_face_data(self.face_recognizer)
                if has_face_model:
                    logging.info(f"Đã tải thông tin cho {len(self.face_info)} khuôn mặt")
        
        # Khởi tạo bộ nhận diện người (YOLO)
        self.yolo_net = None
        self.output_layers = None
        self.person_class_id = None
        
        if has_yolo:
            logging.info("Đang khởi tạo bộ phát hiện người...")
            self.yolo_net, self.output_layers, self.person_class_id = load_yolo_model()
            if self.yolo_net is None:
                logging.error("Không thể tải mô hình YOLO")
    
    def init_camera(self):
        """Khởi tạo camera"""
        try:
            logging.info("Đang khởi động camera...")
            
            if has_picamera:
                # Sử dụng Picamera2 trên Raspberry Pi
                self.camera = Picamera2()
                config = self.camera.create_preview_configuration(main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT)})
                self.camera.configure(config)
                self.camera.start()
            else:
                # Sử dụng OpenCV camera trên các hệ thống khác
                self.camera = cv2.VideoCapture(0)
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            
            logging.info("Đã khởi động camera thành công!")
            return True
        except Exception as e:
            logging.error(f"Lỗi khi khởi tạo camera: {e}")
            return False
    
    def get_frame(self):
        """Lấy khung hình từ camera"""
        if self.camera is None:
            return None
        
        if has_picamera:
            # Picamera2
            frame = self.camera.capture_array()
            if frame.shape[2] == 4:  # Nếu là RGBA
                frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
        else:
            # OpenCV camera
            ret, frame = self.camera.read()
            if not ret:
                return None
        
        return frame
    
    def detect_people_in_frame(self, frame):
        """Nhận diện người trong khung hình"""
        if self.yolo_net is None or not has_yolo:
            return [], []
        
        return detect_people(frame, self.yolo_net, self.output_layers, self.person_class_id)
    
    def detect_faces_in_frame(self, frame):
        """Nhận diện khuôn mặt trong khung hình"""
        if self.face_detector is None or not has_face_detection:
            return []
        
        return detect_faces(frame, self.face_detector)
    
    def handle_recognized_face(self, face_id, confidence, current_time):
        """Xử lý khi nhận diện được khuôn mặt"""
        global is_playing_sound
        
        if face_id in self.face_info:
            person_name = self.face_info[face_id]["name"]
            logging.info(f"Nhận diện: {person_name} (ID: {face_id}, Độ tin cậy: {confidence:.1f}%)")
            
            # Lưu thông tin người dùng vào detected_user.json
            user_data = {"user_id": str(face_id), "user_name": person_name}
            save_detected_user(user_data)
            
            # Bắt đầu theo dõi thời gian sử dụng cho người dùng này
            if has_height_features:
                # Kiểm tra xem đã có phiên đang theo dõi chưa
                current_user = usage_tracker.get_current_user()
                if not current_user or current_user.get('user_id') != str(face_id):
                    # Bắt đầu theo dõi người dùng mới
                    usage_tracker.start_tracking(user_id=str(face_id), user_name=person_name)
                    logging.info(f"Bắt đầu theo dõi thời gian sử dụng cho {person_name}")
            
            # Phát âm thanh chào nếu là người mới xuất hiện
            if face_id not in self.recognized_faces or current_time - self.recognized_faces.get(face_id, 0) > FACE_GREETING_COOLDOWN:
                if not is_playing_sound and has_audio:
                    is_playing_sound = True
                    
                    # Tạo thread riêng để phát âm thanh
                    def play_sound_thread():
                        global is_playing_sound
                        play_personalized_greeting(person_name, face_id)
                        is_playing_sound = False
                    
                    sound_thread = threading.Thread(target=play_sound_thread)
                    sound_thread.daemon = True
                    sound_thread.start()
                    
                    # Cập nhật thời gian cuối cùng phát hiện
                    self.recognized_faces[face_id] = current_time
    
    def register_new_user(self):
        """Đăng ký người dùng mới nếu chưa có trong database"""
        if not has_face_detection:
            logging.error("Không thể đăng ký người dùng mới - không có module face_detector")
            return False
            
        # Lấy khung hình hiện tại
        frame = self.get_frame()
        if frame is None:
            logging.error("Không thể lấy khung hình từ camera")
            return False
        
        # Tạo cửa sổ dialog để nhập tên
        root = tk.Tk()
        root.withdraw()  # Ẩn cửa sổ chính
        
        # Hiển thị dialog yêu cầu nhập tên
        user_name = simpledialog.askstring("Đăng ký người dùng", "Nhập tên của bạn:")
        root.destroy()
        
        if not user_name:
            logging.info("Người dùng đã hủy đăng ký")
            return False
        
        # Gọi hàm đăng ký khuôn mặt
        success, message = register_new_face(frame, self.face_detector, user_name)
        
        if success:
            logging.info(message)
            
            # Huấn luyện lại mô hình
            train_success, train_message = train_face_recognizer(self.face_recognizer)
            logging.info(train_message)
            
            if train_success:
                # Tải lại dữ liệu khuôn mặt
                has_face_model, self.face_info = load_face_data(self.face_recognizer)
                logging.info("Đã tải lại dữ liệu khuôn mặt")
                return True
        else:
            logging.error(f"Lỗi khi đăng ký người dùng mới: {message}")
        
        return False
    
    def release(self):
        """Giải phóng tài nguyên"""
        if self.camera is not None:
            if has_picamera:
                self.camera.stop()
            else:
                self.camera.release()
            
            logging.info("Đã đóng camera")
        
        # Dừng theo dõi người dùng nếu đang hoạt động
        if has_height_features and hasattr(usage_tracker, 'tracking_active') and usage_tracker.tracking_active:
            usage_tracker.stop_tracking()
            logging.info("Đã dừng theo dõi thời gian sử dụng")

def main():
    """Hàm chính của chương trình"""
    global running, is_playing_sound
    
    # Đăng ký xử lý tín hiệu tắt chương trình
    signal.signal(signal.SIGINT, signal_handler)
    
    logging.info("\n=== MODULE NHẬN DIỆN AI ===")
    
    # Khởi tạo bộ nhận diện
    detector = AIDetector()
    
    # Khởi tạo camera
    if not detector.init_camera():
        logging.error("Không thể khởi tạo camera. Thoát chương trình.")
        return
    
    frame_count = 0
    detected_boxes = []
    detected_confidences = []
    
    logging.info("\nĐang chạy... Nhấn Ctrl+C hoặc 'q' để thoát.")
    logging.info("Nhấn 'r' để đăng ký người dùng mới.")
    
    try:
        while running:
            start_time = time.time()
            
            # Lấy khung hình
            frame = detector.get_frame()
            if frame is None:
                logging.warning("Không thể lấy khung hình. Thử lại...")
                time.sleep(0.1)
                continue
            
            # Tạo bản sao để hiển thị
            display_frame = frame.copy()
            height, width = frame.shape[:2]
            
            # Tăng frame count
            frame_count += 1
            
            # Phát hiện người bằng YOLO mỗi vài khung hình
            if frame_count % DETECTION_INTERVAL == 0 and has_yolo:
                detected_boxes, detected_confidences = detector.detect_people_in_frame(frame)
            
            # Nhận diện khuôn mặt mỗi vài khung hình
            if has_face_detection and frame_count % FACE_DETECTION_INTERVAL == 0:
                # Phát hiện khuôn mặt
                faces = detector.detect_faces_in_frame(frame)
                
                current_time = time.time()
                
                # Xử lý từng khuôn mặt phát hiện được
                for (x, y, w, h) in faces:
                    # Vẽ hình chữ nhật xung quanh khuôn mặt
                    cv2.rectangle(display_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    
                    # Cắt vùng khuôn mặt
                    face_roi = frame[y:y+h, x:x+w]
                    
                    # Chuyển sang ảnh xám để nhận diện
                    face_gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
                    
                    # Nhận diện khuôn mặt
                    try:
                        face_id, confidence = detector.face_recognizer.predict(face_gray)
                        confidence_value = 100.0 - confidence  # Chuyển ngược lại thành % tin cậy
                        
                        # Kiểm tra độ tin cậy (số nhỏ hơn = tin cậy hơn cho LBPH)
                        if confidence < 70:  # Ngưỡng tin cậy
                            # Vẽ tên và độ tin cậy
                            if face_id in detector.face_info:
                                person_name = detector.face_info[face_id]["name"]
                                cv2.putText(display_frame, person_name, (x, y-10), 
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                                cv2.putText(display_frame, f"{confidence_value:.1f}%", (x+w-70, y-10), 
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                                
                                # Xử lý khuôn mặt đã nhận diện
                                detector.handle_recognized_face(face_id, confidence_value, current_time)
                            else:
                                cv2.putText(display_frame, f"ID: {face_id}", (x, y-10), 
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        else:
                            # Khuôn mặt không xác định
                            cv2.putText(display_frame, "Khong xac dinh", (x, y-10), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                            # Xóa detected_user.json nếu không nhận diện được
                            save_detected_user(None)
                    except Exception as e:
                        logging.error(f"Lỗi khi nhận diện khuôn mặt: {e}")
            
            # Vẽ bounding boxes từ YOLO
            count = 0
            for i, (x, y, w, h) in enumerate(detected_boxes):
                confidence = detected_confidences[i]
                
                # Vẽ rectangle và text
                cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                cv2.putText(display_frame, f"Nguoi: {confidence:.2f}", (x, y - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                count += 1
            
            # Xử lý logic phát hiện người và phát âm thanh
            current_time = time.time()
            person_present_now = count > 0
            
            # Nếu phát hiện người và trước đó không có người
            if person_present_now and not detector.person_detected:
                detector.person_detected = True
                
                # Kiểm tra thời gian kể từ lần cuối phát âm thanh
                if current_time - detector.last_person_time > WELCOME_COOLDOWN and not is_playing_sound and has_audio:
                    # Đánh dấu đang phát âm thanh
                    is_playing_sound = True
                    
                    # Tạo thread riêng để phát âm thanh
                    def play_sound_thread():
                        global is_playing_sound
                        play_welcome_sound()
                        is_playing_sound = False
                    
                    sound_thread = threading.Thread(target=play_sound_thread)
                    sound_thread.daemon = True
                    sound_thread.start()
                    
                    # Cập nhật thời gian cuối cùng phát âm thanh
                    detector.last_person_time = current_time
                    
                    # Hiển thị thông báo
                    cv2.putText(display_frame, "Xin chao ban!", (width - 200, 60), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            # Nếu không còn phát hiện người
            elif not person_present_now:
                detector.person_detected = False
                # Xóa detected_user.json nếu không có người
                save_detected_user(None)
            
            # Tính FPS
            fps = 1.0 / (time.time() - start_time)
            
            # Hiển thị thông tin
            cv2.putText(display_frame, f"FPS: {fps:.1f}", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.putText(display_frame, f"So nguoi: {count}", (10, 60), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.putText(display_frame, time.strftime("%H:%M:%S"), (width - 150, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            
            # Hiển thị trạng thái
            status_text = "Trang thai: co nguoi" if detector.person_detected else "Trang thai: khong co nguoi"
            cv2.putText(display_frame, status_text, (10, 90), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
            
            # Hiển thị tên người dùng đang theo dõi nếu có
            if has_height_features and hasattr(usage_tracker, 'tracking_active') and usage_tracker.tracking_active:
                current_user = usage_tracker.get_current_user()
                if current_user:
                    user_text = f"Nguoi dung: {current_user.get('user_name', 'Khong xac dinh')}"
                    cv2.putText(display_frame, user_text, (10, 120), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Hiển thị hướng dẫn đăng ký
            cv2.putText(display_frame, "Nhan 'r' de dang ky nguoi dung moi", 
                        (10, height - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Hiển thị khung hình
            cv2.imshow("AI Recognition", display_frame)
            
            # Kiểm tra phím bấm
            key = cv2.waitKey(1) & 0xFF
            
            # Nhấn 'q' để thoát
            if key == ord('q'):
                running = False
            
            # Nhấn 'r' để đăng ký người dùng mới
            elif key == ord('r'):
                logging.info("Đang bắt đầu đăng ký người dùng mới...")
                detector.register_new_user()
            
            # Điều chỉnh tốc độ frame
            if FRAME_RATE > 0:
                time_to_sleep = 1.0 / FRAME_RATE - (time.time() - start_time)
                if time_to_sleep > 0:
                    time.sleep(time_to_sleep)
    
    except Exception as e:
        logging.error(f"Lỗi: {e}")
    
    finally:
        # Giải phóng tài nguyên
        detector.release()
        cv2.destroyAllWindows()
        logging.info("Chương trình đã kết thúc")

if __name__ == "__main__":
    main()