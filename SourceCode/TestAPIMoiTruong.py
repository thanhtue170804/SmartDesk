import tkinter as tk
import requests
import threading
import time
from PIL import Image, ImageTk

class EnvironmentalInfoDisplay:
    def __init__(self, root):
        self.root = root
        self.root.title("Thông Tin Môi Trường TP. Hồ Chí Minh")
        self.root.geometry("800x600")  # Tăng kích thước để hiển thị nhiều thông tin hơn
        
        # Khung chính
        self.main_frame = tk.Frame(root, bg='white')
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Tiêu đề
        self.title_label = tk.Label(
            self.main_frame, 
            text="Thông Tin Môi Trường TP. Hồ Chí Minh", 
            font=("Arial", 18, "bold"), 
            bg='white', 
            fg='dark blue'
        )
        self.title_label.pack(pady=10)
        
        # Khung thông tin
        self.info_frame = tk.Frame(self.main_frame, bg='white')
        self.info_frame.pack(expand=True, fill=tk.BOTH, padx=20, pady=10)
        
        # Nhãn hiển thị các thông tin
        self.temp_label = tk.Label(
            self.info_frame, 
            text="Nhiệt độ: Đang tải...", 
            font=("Arial", 14), 
            bg='white'
        )
        self.temp_label.pack(anchor='w', pady=5)
        
        self.humidity_label = tk.Label(
            self.info_frame, 
            text="Độ ẩm: Đang tải...", 
            font=("Arial", 14), 
            bg='white'
        )
        self.humidity_label.pack(anchor='w', pady=5)
        
        self.aqi_label = tk.Label(
            self.info_frame, 
            text="Chỉ số chất lượng không khí: Đang tải...", 
            font=("Arial", 14), 
            bg='white'
        )
        self.aqi_label.pack(anchor='w', pady=5)
        
        # Thêm các nhãn thông tin mới
        self.wind_label = tk.Label(
            self.info_frame, 
            text="Tốc độ gió: Đang tải...", 
            font=("Arial", 14), 
            bg='white'
        )
        self.wind_label.pack(anchor='w', pady=5)
        
        self.pressure_label = tk.Label(
            self.info_frame, 
            text="Áp suất: Đang tải...", 
            font=("Arial", 14), 
            bg='white'
        )
        self.pressure_label.pack(anchor='w', pady=5)
        
        self.clouds_label = tk.Label(
            self.info_frame, 
            text="Mây che phủ: Đang tải...", 
            font=("Arial", 14), 
            bg='white'
        )
        self.clouds_label.pack(anchor='w', pady=5)
        
        self.uv_label = tk.Label(
            self.info_frame, 
            text="Chỉ số UV: Đang tải...", 
            font=("Arial", 14), 
            bg='white'
        )
        self.uv_label.pack(anchor='w', pady=5)
        self.back_button = tk.Button(
            self.main_frame, 
            text="Quay lại Menu Chính", 
            font=("Arial", 14, "bold"),
            bg='tomato', 
            fg='white',
            command=self.return_to_main
        )
        self.back_button.pack(pady=15)
        # Nhãn cập nhật
        self.update_label = tk.Label(
            self.main_frame, 
            text="Đang cập nhật...", 
            font=("Arial", 10), 
            bg='white', 
            fg='gray'
        )
        self.update_label.pack(pady=5)
        
        # Bắt đầu luồng cập nhật thông tin
        self.stop_thread = False
        self.update_thread = threading.Thread(target=self.update_environmental_info)
        self.update_thread.daemon = True
        self.update_thread.start()
        
        # Xử lý đóng cửa sổ
        root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def return_to_main(self):
        self.stop_thread = True
        self.root.destroy()
    def get_ho_chi_minh_weather(self):
        """Lấy thông tin thời tiết từ API OpenWeatherMap"""
        try:
            # Khóa API của bạn
            api_key = "56d1bc96c2b004e6bd34089b5154da42"  
            city = "Ho+Chi+Minh+City"
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric&lang=vi"
            
            # In ra URL để kiểm tra
            print(f"Weather API URL: {url}")
            
            response = requests.get(url)
            # In ra toàn bộ response để debug
            print(f"Weather API Response: {response.text}")
            
            data = response.json()
            
            # Kiểm tra lỗi từ API
            if 'cod' in data and data['cod'] != 200:
                print(f"Lỗi API: {data.get('message', 'Không rõ')}")
                return None
            
            # Kiểm tra cấu trúc dữ liệu
            if 'main' not in data:
                print("Dữ liệu thời tiết không đúng định dạng")
                return None
            
            # Trích xuất thêm thông tin
            return {
                'temperature': round(data['main']['temp'], 1),
                'humidity': data['main']['humidity'],
                'pressure': data['main']['pressure'],
                'wind_speed': round(data['wind']['speed'], 1),
                'clouds': data['clouds']['all'],
                'description': data['weather'][0]['description']
            }
        except Exception as e:
            print(f"Lỗi khi lấy thông tin thời tiết: {e}")
            return None
    
    def get_uv_index(self):
        """Lấy chỉ số UV"""
        try:
            lat, lon = 10.7758, 106.7018  # Tọa độ TP. Hồ Chí Minh
            api_key = "56d1bc96c2b004e6bd34089b5154da42"
            
            url = f"http://api.openweathermap.org/data/2.5/uvi?appid={api_key}&lat={lat}&lon={lon}"
            
            response = requests.get(url)
            data = response.json()
            
            # Phân loại chỉ số UV
            uv_value = data['value']
            if uv_value <= 2:
                uv_description = "Thấp"
            elif uv_value <= 5:
                uv_description = "Trung bình"
            elif uv_value <= 7:
                uv_description = "Cao"
            elif uv_value <= 10:
                uv_description = "Rất cao"
            else:
                uv_description = "Nguy hiểm"
            
            return f"{uv_value} ({uv_description})"
        except Exception as e:
            print(f"Lỗi khi lấy chỉ số UV: {e}")
            return "Không thể tải"
    
    def get_air_quality(self):
        """Lấy thông tin chất lượng không khí"""
        try:
            # Khóa API của bạn
            api_key = "56d1bc96c2b004e6bd34089b5154da42"
            lat, lon = 10.7758, 106.7018  # Tọa độ TP. Hồ Chí Minh
            url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={api_key}"
            
            response = requests.get(url)
            data = response.json()
            
            # Kiểm tra lỗi từ API
            if 'list' not in data or not data['list']:
                print("Dữ liệu chất lượng không khí không đúng định dạng")
                return "Không xác định"
            
            aqi = data['list'][0]['main']['aqi']
            aqi_descriptions = {
                1: "Rất tốt",
                2: "Tốt",
                3: "Trung bình",
                4: "Kém",
                5: "Rất kém"
            }
            
            return aqi_descriptions.get(aqi, "Không xác định")
        except Exception as e:
            print(f"Lỗi khi lấy thông tin chất lượng không khí: {e}")
            return "Không thể tải"
    
    def update_environmental_info(self):
        """Cập nhật thông tin môi trường định kỳ"""
        while not self.stop_thread:
            try:
                # Lấy thông tin thời tiết
                weather_info = self.get_ho_chi_minh_weather()
                
                if weather_info:
                    # Cập nhật nhãn nhiệt độ và độ ẩm
                    self.temp_label.config(text=f"Nhiệt độ: {weather_info['temperature']}°C")
                    self.humidity_label.config(text=f"Độ ẩm: {weather_info['humidity']}%")
                    
                    # Cập nhật thông tin gió
                    self.wind_label.config(text=f"Tốc độ gió: {weather_info['wind_speed']} m/s")
                    
                    # Cập nhật áp suất
                    self.pressure_label.config(text=f"Áp suất: {weather_info['pressure']} hPa")
                    
                    # Cập nhật mây che phủ
                    self.clouds_label.config(text=f"Mây che phủ: {weather_info['clouds']}%")
                else:
                    # Xử lý khi không lấy được dữ liệu
                    self.temp_label.config(text="Nhiệt độ: Không tải được")
                    self.humidity_label.config(text="Độ ẩm: Không tải được")
                    self.wind_label.config(text="Tốc độ gió: Không tải được")
                    self.pressure_label.config(text="Áp suất: Không tải được")
                    self.clouds_label.config(text="Mây che phủ: Không tải được")
                
                # Lấy thông tin chất lượng không khí
                air_quality = self.get_air_quality()
                self.aqi_label.config(text=f"Chỉ số chất lượng không khí: {air_quality}")
                
                # Lấy chỉ số UV
                uv_index = self.get_uv_index()
                self.uv_label.config(text=f"Chỉ số UV: {uv_index}")
                
                # Cập nhật thời gian
                current_time = time.strftime("%H:%M:%S %d/%m/%Y")
                self.update_label.config(text=f"Cập nhật lúc: {current_time}")
            
            except Exception as e:
                print(f"Lỗi cập nhật: {e}")
                self.update_label.config(text=f"Lỗi: {e}")
            
            # Chờ 15 phút trước khi cập nhật lại
            time.sleep(5)
    
    def on_closing(self):
        """Xử lý đóng cửa sổ"""
        self.stop_thread = True
        self.root.destroy()

def main():
    root = tk.Tk()
    
    # Toàn màn hình nếu muốn
    #root.attributes('-fullscreen', True)
    
    app = EnvironmentalInfoDisplay(root)
    root.mainloop()

if __name__ == "__main__":
    main()