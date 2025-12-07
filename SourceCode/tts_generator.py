# tts_generator.py - Tạo âm thanh cá nhân bằng Text-to-Speech API

import os
import pickle
import requests
import json
from config import *

def generate_personal_greetings():
    """Tạo âm thanh chào cá nhân cho tất cả người dùng đã đăng ký"""
    # Kiểm tra file mapping
    if not os.path.exists(FACE_MAPPING_PATH):
        print("Chưa có người dùng nào được đăng ký.")
        return False
    
    # Đọc dữ liệu người dùng
    with open(FACE_MAPPING_PATH, 'rb') as f:
        face_info = pickle.load(f)
    
    # Hiển thị danh sách người dùng
    print("\nĐang tạo âm thanh chào cho người dùng:")
    print("-" * 40)
    
    for face_id, info in face_info.items():
        person_name = info["name"]
        print(f"ID: {face_id} | Tên: {person_name}")
        
        # Tạo 3 loại lời chào theo thời gian
        create_time_based_greetings(face_id, person_name)
    
    print("-" * 40)
    print("Đã hoàn thành việc tạo âm thanh!")
    return True

def create_time_based_greetings(face_id, person_name):
    """Tạo các file âm thanh theo thời gian cho một người dùng"""
    greetings = {
        "morning": f"Chào buổi sáng {person_name}, chúc bạn một ngày tốt lành",
        "afternoon": f"Chào buổi chiều {person_name}, chúc bạn có buổi chiều vui vẻ",
        "evening": f"Chào buổi tối {person_name}, chúc bạn một buổi tối an lành"
    }
    
    for time_key, text in greetings.items():
        output_path = os.path.join(FACES_DIR, f"face_{face_id}_{time_key}.mp3")
        
        # Tạo file âm thanh
        success = generate_tts(text, output_path)
        if success:
            print(f"  ✓ Đã tạo âm thanh {time_key} cho {person_name}")
        else:
            print(f"  ✗ Lỗi khi tạo âm thanh {time_key} cho {person_name}")

def generate_tts(text, output_path):
    """Tạo file âm thanh từ văn bản sử dụng API"""
    try:
        # Sử dụng API miễn phí VoiceRSS (đăng ký tại https://www.voicerss.org/)
        # Thay API_KEY bằng khóa API của bạn sau khi đăng ký
        API_KEY = "YOUR_API_KEY"  # Thay thế bằng API key của bạn
        
        # Chuẩn bị tham số
        params = {
            'key': API_KEY,
            'src': text,
            'hl': 'vi-vn',  # Tiếng Việt
            'r': '0',  # Tốc độ đọc bình thường
            'c': 'mp3',  # Định dạng MP3
            'f': '44khz_64bit_stereo'  # Chất lượng âm thanh
        }
        
        # Gọi API
        response = requests.get('https://api.voicerss.org/', params=params)
        
        # Kiểm tra kết quả
        if response.status_code == 200 and not response.text.startswith('ERROR'):
            # Lưu file
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return True
        else:
            print(f"Lỗi API: {response.text}")
            # Sử dụng phương án dự phòng
            return generate_tts_fallback(text, output_path)
    
    except Exception as e:
        print(f"Lỗi khi tạo TTS: {e}")
        # Sử dụng phương án dự phòng
        return generate_tts_fallback(text, output_path)

def generate_tts_fallback(text, output_path):
    """Phương án dự phòng sử dụng espeak và lame"""
    try:
        import subprocess
        
        # Tạo thư mục nếu chưa tồn tại
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Tạo file WAV tạm thời
        temp_wav = os.path.join(os.path.dirname(output_path), "temp.wav")
        
        # Sử dụng espeak để tạo file WAV
        espeak_cmd = f'espeak -v vi -s 130 -p 50 "{text}" -w {temp_wav}'
        subprocess.run(espeak_cmd, shell=True, check=True)
        
        # Chuyển WAV sang MP3
        lame_cmd = f"lame {temp_wav} {output_path}"
        subprocess.run(lame_cmd, shell=True, check=True)
        
        # Dọn dẹp
        if os.path.exists(temp_wav):
            os.remove(temp_wav)
        
        return True
    
    except Exception as e:
        print(f"Lỗi khi tạo TTS dự phòng: {e}")
        return False

if __name__ == "__main__":
    # Tạo thư mục cần thiết
    create_directories()
    
    # Tạo âm thanh cho tất cả người dùng
    generate_personal_greetings()
    