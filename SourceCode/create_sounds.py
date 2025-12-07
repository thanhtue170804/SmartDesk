# create_sounds.py - Script tạo file âm thanh

import subprocess
import os
from config import *

def main():
    """Tạo các file âm thanh cần thiết"""
    print("Bắt đầu tạo file âm thanh...")
    
    # Tạo thư mục sounds nếu chưa tồn tại
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    
    # Kiểm tra xem có các công cụ cần thiết không
    try:
        subprocess.run(["which", "espeak"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except:
        print("Không tìm thấy espeak. Cài đặt bằng lệnh: sudo apt-get install espeak")
        return
    
    try:
        subprocess.run(["which", "lame"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except:
        print("Không tìm thấy lame. Cài đặt bằng lệnh: sudo apt-get install lame")
        return
    
    # Danh sách các lời chào
    greetings = {
        "welcome.mp3": "Xin chào, rất vui được gặp bạn",
        "chao_buoi_sang.mp3": "Xin chào, chúc bạn một buổi sáng tốt lành",
        "chao_buoi_chieu.mp3": "Xin chào, chúc bạn một buổi chiều vui vẻ",
        "chao_buoi_toi.mp3": "Xin chào, chúc bạn một buổi tối an lành"
    }
    
    # Tạo file âm thanh
    for filename, text in greetings.items():
        output_path = os.path.join(SOUNDS_DIR, filename)
        
        if os.path.exists(output_path):
            print(f"File {filename} đã tồn tại, bỏ qua")
            continue
        
        print(f"Đang tạo file {filename}...")
        
        # Tạo file WAV tạm thời
        temp_wav = os.path.join(SOUNDS_DIR, "temp.wav")
        
        try:
            # Sử dụng espeak để tạo file WAV
            espeak_cmd = f'espeak -v vi -s 130 -p 50 "{text}" -w {temp_wav}'
            subprocess.run(espeak_cmd, shell=True, check=True)
            
            # Chuyển WAV sang MP3
            lame_cmd = f"lame {temp_wav} {output_path}"
            subprocess.run(lame_cmd, shell=True, check=True)
            
            print(f"Đã tạo file {filename} thành công")
        except Exception as e:
            print(f"Lỗi khi tạo file {filename}: {e}")
        finally:
            # Dọn dẹp file tạm
            if os.path.exists(temp_wav):
                os.remove(temp_wav)
    
    print("Đã hoàn thành việc tạo file âm thanh")

if __name__ == "__main__":
    # Tạo thư mục cần thiết
    create_directories()
    
    # Tạo file âm thanh
    main()