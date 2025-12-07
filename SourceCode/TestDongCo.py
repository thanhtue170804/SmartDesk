import time
from gpiozero import DigitalOutputDevice

# Định nghĩa các chân kết nối
ENA_PIN = 23  # Chân ENA+ kết nối với GPIO 23
DIR_PIN = 24  # Chân DIR+ kết nối với GPIO 19
PUL_PIN = 25  # Chân PUL+ kết nối với GPIO 18

def setup_stepper():
    """Thiết lập các chân điều khiển động cơ"""
    # Tạo các đối tượng digital output
    ena = DigitalOutputDevice(ENA_PIN)
    dir_pin = DigitalOutputDevice(DIR_PIN)
    pul_pin = DigitalOutputDevice(PUL_PIN)
    
    # Kích hoạt driver (ENA active LOW)
    ena.off()  # Kích hoạt TB6600
    
    return dir_pin, pul_pin

def rotate_motor(dir_pin, pul_pin, direction=True, duration=10, speed=1000):
    """
    Điều khiển động cơ bước
    :param dir_pin: Chân điều hướng
    :param pul_pin: Chân xung
    :param direction: True (một chiều), False (chiều ngược)
    :param duration: Thời gian quay (giây)
    :param speed: Tốc độ (microseconds between pulses)
    """
    # Đặt hướng quay
    dir_pin.on() if direction else dir_pin.off()
    
    # Thời gian bắt đầu
    start_time = time.time()
    
    # Quay động cơ
    try:
        while time.time() - start_time < duration:
            pul_pin.on()
            time.sleep(speed / 2000000)  # Chuyển microseconds sang giây
            pul_pin.off()
            time.sleep(speed / 2000000)
    except KeyboardInterrupt:
        print("\nDừng quay động cơ.")

def main():
    try:
        # Thiết lập các chân
        dir_pin, pul_pin = setup_stepper()
        
        print("Bắt đầu quay động cơ NEMA17...")
        
        # Quay một chiều
        print("Quay một chiều trong 5 giây...")
        rotate_motor(dir_pin, pul_pin, direction=True, duration=5, speed=500)
        
        # Dừng lại giữa các lượt quay
        time.sleep(1)
        
        # Quay chiều ngược lại
        print("Quay chiều ngược trong 5 giây...")
        rotate_motor(dir_pin, pul_pin, direction=False, duration=5, speed=500)
    
    except Exception as e:
        print(f"Lỗi: {e}")
    from gpiozero import DigitalOutputDevice

    def test():
        dir_pin, = setup_stepper()
        
        print("test chan")
        for i in range (10):
            print(f"DIR = high")
            dir_pin.on()
            time.sleep(1)
            print(f"DIR = LOW")
            dir_pin.off()
            timne.sleep(1)

if __name__ == "__main__":
    main()