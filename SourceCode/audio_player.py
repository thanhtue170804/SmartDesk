# audio_player.py - Các hàm phát âm thanh

import os
import subprocess
from datetime import datetime
from config import *

def play_welcome_sound():
    """Hàm phát âm thanh chào mừng sử dụng các công cụ có sẵn trên hệ thống"""
    try:
        # Kiểm tra thời gian để phát âm thanh phù hợp
        current_hour = datetime.now().hour
        
        # Chọn file âm thanh phù hợp theo thời gian
        if 5 <= current_hour < 12:
            sound_file = "chao_buoi_sang.mp3"  # Âm thanh buổi sáng
        elif 12 <= current_hour < 18:
            sound_file = "chao_buoi_chieu.mp3"  # Âm thanh buổi chiều
        else:
            sound_file = "chao_buoi_toi.mp3"  # Âm thanh buổi tối
            
        # Đường dẫn đến file âm thanh
        sound_path = os.path.join(SOUNDS_DIR, sound_file)
        
        # Nếu không tìm thấy file âm thanh cụ thể, sử dụng file mặc định
        if not os.path.exists(sound_path):
            default_sound = os.path.join(SOUNDS_DIR, "welcome.mp3")
            if os.path.exists(default_sound):
                sound_path = default_sound
            else:
                print(f"Không tìm thấy file âm thanh. Vui lòng tạo thư mục 'sounds' và thêm file 'welcome.mp3'")
                return False
        
        # Phát âm thanh
        return play_sound(sound_path)
        
    except Exception as e:
        print(f"Lỗi khi phát âm thanh: {e}")
        return False

def play_personalized_greeting(person_name, face_id):
    """Phát âm thanh chào với tên người dùng sử dụng âm thanh mặc định theo buổi"""
    try:
        # Lấy thời gian hiện tại
        current_hour = datetime.now().hour
        
        # Chọn file âm thanh phù hợp theo thời gian - chỉ dùng âm thanh mặc định
        if 5 <= current_hour < 12:
            sound_file = "chao_buoi_sang.mp3"  # Buổi sáng
        elif 12 <= current_hour < 18:
            sound_file = "chao_buoi_chieu.mp3"  # Buổi chiều
        else:
            sound_file = "chao_buoi_toi.mp3"  # Buổi tối
        
        # Đường dẫn đến file âm thanh mặc định
        default_sound = os.path.join(SOUNDS_DIR, sound_file)
        welcome_sound = os.path.join(SOUNDS_DIR, "welcome.mp3")
        
        # Ưu tiên sử dụng âm thanh theo thời gian
        if os.path.exists(default_sound):
            sound_path = default_sound
            print(f"Phát âm thanh theo thời gian cho {person_name}")
        elif os.path.exists(welcome_sound):
            sound_path = welcome_sound
            print(f"Phát âm thanh chào mặc định cho {person_name}")
        else:
            print("Không tìm thấy file âm thanh")
            return False
        
        # Phát âm thanh
        return play_sound(sound_path)
    
    except Exception as e:
        print(f"Lỗi khi phát âm thanh cá nhân hóa: {e}")
        return False

def play_sound(sound_path):
    """Phát file âm thanh sử dụng các trình phát có sẵn"""
    players = [
        ["mpg123", "-q"],
        ["aplay", "-q"],
        ["mplayer", "-really-quiet"]
    ]
    
    for player_cmd in players:
        try:
            # Kiểm tra xem command có tồn tại không
            subprocess.run(["which", player_cmd[0]], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Chạy lệnh phát nhạc
            cmd = player_cmd + [sound_path]
            subprocess.run(cmd, check=True)
            
            # Nếu thành công, dừng vòng lặp
            print(f"Đã phát âm thanh bằng {player_cmd[0]}")
            return True
        except subprocess.SubprocessError:
            continue
    
    print("Không tìm thấy trình phát âm thanh nào")
    return False

def check_sound_files():
    """Kiểm tra xem các file âm thanh có tồn tại không"""
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    
    required_files = [
        "welcome.mp3",
        "chao_buoi_sang.mp3",
        "chao_buoi_chieu.mp3",
        "chao_buoi_toi.mp3"
    ]
    
    missing_files = []
    for filename in required_files:
        file_path = os.path.join(SOUNDS_DIR, filename)
        if not os.path.exists(file_path):
            missing_files.append(filename)
    
    if missing_files:
        print("Cảnh báo: Các file âm thanh sau không tồn tại:")
        for file in missing_files:
            print(f"  - {file}")
        print("Hãy sao chép các file âm thanh này vào thư mục 'sounds/'")
        
        # Kiểm tra xem file welcome.mp3 có tồn tại không
        if "welcome.mp3" in missing_files:
            print("Ít nhất file 'welcome.mp3' là cần thiết để phát âm thanh chào")
    
    return len(missing_files) == 0
