"""
SmartLight Controller - Raspberry Pi Version
Sử dụng cảm biến BH1750 để đo ánh sáng và điều khiển đèn tự động
"""

import time
import smbus
import os
from gpiozero import DigitalOutputDevice, Device

# Định nghĩa các hằng số cho cảm biến BH1750
DEVICE = 0x23  # Địa chỉ I2C của BH1750 (mặc định)
POWER_DOWN = 0x00
POWER_ON = 0x01
RESET = 0x07
CONTINUOUS_HIGH_RES_MODE = 0x10

# Xác định các chân SDA và SCL
SDA_PIN = 2  # GPIO 2 cho SDA
SCL_PIN = 3  # GPIO 3 cho SCL

# Cấu hình I2C trên Raspberry Pi
# Đảm bảo I2C được kích hoạt 
os.system('dtparam i2c_arm=on')
# Có thể cần thiết lập tốc độ I2C nếu cần
# os.system('i2cdetect -y 1')  # Kiểm tra các thiết bị I2C đã kết nối

# Khởi tạo bus I2C
bus = smbus.SMBus(1)  # Trên Raspberry Pi 5, sử dụng bus 1

# Định nghĩa chân GPIO để điều khiển transistor
transistor_pin = 26  # GPIO 26

def cleanup_gpio_26():
    """Giải phóng chân GPIO 26"""
    try:
        # Tạo một thiết bị tại chân 26 và đặt về trạng thái ban đầu
        device = Device.pin(26)
        
        # Đảm bảo thiết bị được đóng
        device.close()
        
        print(f"Đã giải phóng chân GPIO 26 thành công.")
    except Exception as e:
        print(f"Có lỗi xảy ra khi giải phóng GPIO 26: {e}")

def read_light_level():
    """Đọc giá trị ánh sáng từ cảm biến BH1750"""
    try:
        # Kiểm tra xem cảm biến có tồn tại trên bus I2C không
        try:
            bus.write_quick(DEVICE)
        except OSError:
            print(f"Không tìm thấy cảm biến tại địa chỉ 0x{DEVICE:02x}. Kiểm tra kết nối SDA (GPIO {SDA_PIN}) và SCL (GPIO {SCL_PIN}).")
            return 0
            
        # Gửi lệnh đọc đến cảm biến
        bus.write_byte(DEVICE, CONTINUOUS_HIGH_RES_MODE)
        time.sleep(0.2)  # Chờ một chút để cảm biến xử lý
        
        # Đọc dữ liệu từ cảm biến
        data = bus.read_i2c_block_data(DEVICE, CONTINUOUS_HIGH_RES_MODE, 2)
        
        # Chuyển đổi dữ liệu sang giá trị lux
        result = (data[1] + (256 * data[0])) / 1.2
        return result
    except Exception as e:
        print(f"Lỗi khi đọc cảm biến: {e}")
        return 0

def main():
    """Chương trình chính"""
    # Giải phóng chân GPIO 26 trước khi sử dụng
    cleanup_gpio_26()
    
    print("Hệ thống SmartLight đang khởi động...")
    
    # Kiểm tra xem I2C đã được kích hoạt chưa
    try:
        # Sử dụng phương pháp xác thực I2C phổ biến hơn
        if os.path.exists('/dev/i2c-1'):
            print("I2C đã được kích hoạt (Bus 1).")
        else:
            print("CẢNH BÁO: I2C có thể chưa được kích hoạt. Hãy chạy 'sudo raspi-config' để kích hoạt I2C.")
            print("Chương trình vẫn sẽ tiếp tục nhưng có thể gặp lỗi.")
    except Exception as e:
        print(f"Không thể kiểm tra trạng thái I2C: {e}")
    
    print(f"Cấu hình: SDA trên GPIO {SDA_PIN}, SCL trên GPIO {SCL_PIN}, Transistor trên GPIO {transistor_pin}")
    
    # Khởi tạo đèn sau khi giải phóng chân GPIO
    light = DigitalOutputDevice(transistor_pin, initial_value=False)  # Đèn tắt khi bắt đầu
    
    print("Hệ thống SmartLight đã sẵn sàng.")
    
    try:
        # Kiểm tra xem cảm biến có hoạt động không
        lux = read_light_level()
        if lux == 0:
            print("Cảnh báo: Không thể đọc được giá trị ánh sáng từ cảm biến!")
        else:
            print(f"Cảm biến BH1750 đã sẵn sàng. Giá trị ban đầu: {lux} lux")
        
        # Vòng lặp chính
        while True:
            # Đọc giá trị ánh sáng
            lux = read_light_level()
            
            # In giá trị ánh sáng
            print(f"Độ sáng: {lux:.2f} lux")
            
            # Đặt ngưỡng ánh sáng để bật/tắt đèn (ví dụ: ngưỡng là 100 lux)
            if lux < 100:
                # Nếu ánh sáng thấp (tối), bật đèn
                light.on()
                print("Đèn bật")
            else:
                # Nếu ánh sáng cao (sáng), tắt đèn
                light.off()
                print("Đèn tắt")
            
            # Đợi 1 giây trước khi đọc lại
            time.sleep(1)
            
    except KeyboardInterrupt:
        # Xử lý khi người dùng nhấn Ctrl+C
        print("\nĐang thoát chương trình...")
        light.off()  # Đảm bảo tắt đèn trước khi thoát
    except Exception as e:
        # Xử lý các ngoại lệ khác
        print(f"Lỗi: {e}")
        light.off()  # Đảm bảo tắt đèn khi có lỗi
    finally:
        # Đảm bảo tắt đèn và giải phóng tài nguyên khi thoát
        light.close()
        print("Đã tắt hệ thống.")

if __name__ == "__main__":
    main()