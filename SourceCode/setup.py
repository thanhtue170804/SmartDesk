# setup.py - Thiết lập ban đầu cho hệ thống

import os
import subprocess
import sys
from config import create_directories

def check_dependencies():
    """Kiểm tra các thư viện và công cụ cần thiết"""
    missing_packages = []
    
    # Kiểm tra các thư viện Python
    python_packages = {
        "opencv-python": "cv2",
        "numpy": "numpy",
        "picamera2": "picamera2"
    }
    
    for package, module in python_packages.items():
        try:
            __import__(module)
            print(f"✓ Đã cài đặt {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"✗ Chưa cài đặt {package}")
    
    # Kiểm tra các công cụ hệ thống
    system_tools = ["mpg123", "aplay", "mplayer", "espeak", "lame"]
    missing_tools = []
    
    for tool in system_tools:
        try:
            subprocess.run(["which", tool], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(f"✓ Đã cài đặt {tool}")
        except subprocess.SubprocessError:
            missing_tools.append(tool)
            print(f"✗ Chưa cài đặt {tool}")
    
    # Hiển thị thông tin về các gói còn thiếu
    if missing_packages or missing_tools:
        print("\nCác gói cần cài đặt:")
        
        if missing_packages:
            print("\nCài đặt các thư viện Python:")
            print("sudo apt-get update")
            print("sudo apt-get install -y python3-opencv python3-picamera2")
            print("hoặc sử dụng virtual environment:\n")
            print("python3 -m venv ~/myenv")
            print("source ~/myenv/bin/activate")
            print("pip install " + " ".join(missing_packages))
        
        if missing_tools:
            print("\nCài đặt các công cụ hệ thống:")
            print("sudo apt-get update")
            print("sudo apt-get install -y " + " ".join(missing_tools))
        
        return False
    
    return True

def setup_system():
    """Thiết lập ban đầu cho hệ thống"""
    print("Đang thiết lập hệ thống nhận diện người và khuôn mặt...")
    
    # Tạo các thư mục cần thiết
    create_directories()
    print("✓ Đã tạo các thư mục cần thiết")
    
    # Tạo các file âm thanh
    try:
        from audio_player import create_sound_files
        create_sound_files()
        print("✓ Đã tạo các file âm thanh")
    except Exception as e:
        print(f"✗ Lỗi khi tạo file âm thanh: {e}")
    
    # Kiểm tra và tải mô hình YOLO nếu cần
    try:
        from yolo_detector import download_yolo_model
        download_yolo_model()
        print("✓ Đã tải mô hình YOLO")
    except Exception as e:
        print(f"✗ Lỗi khi tải mô hình YOLO: {e}")
    
    print("\nQuá trình thiết lập đã hoàn tất. Chạy chương trình chính với lệnh:")
    print("python3 main.py")

if __name__ == "__main__":
    if check_dependencies():
        setup_system()
    else:
        print("\nVui lòng cài đặt các gói còn thiếu trước khi tiếp tục.")