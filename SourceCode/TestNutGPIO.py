import tkinter as tk
from gpiozero import Button, InputDevice

# Định nghĩa chân kết nối
BUTTON_PINS = [17, 27, 22, 5]     # Các nút nhấn
LIMIT_SWITCH_PINS = [6, 13]        # Các switch giới hạn

def main():
    # Khởi tạo giao diện
    root = tk.Tk()
    root.title("Test Nút Nhấn & Switch")
    root.attributes('-fullscreen', True)

    # Tạo frame chính
    main_frame = tk.Frame(root)
    main_frame.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)

    # Tiêu đề
    title_label = tk.Label(main_frame, text="KIỂM TRA NÚT NHẤN & SWITCH", 
                           font=("Arial", 24, "bold"))
    title_label.pack(pady=20)

    # Frame cho nút nhấn
    buttons_frame = tk.Frame(main_frame)
    buttons_frame.pack(pady=10)
    tk.Label(buttons_frame, text="CÁC NÚT NHẤN", font=("Arial", 18, "bold")).pack()

    # Nhãn và đối tượng cho các nút nhấn
    button_labels = []
    button_devices = []
    for pin in BUTTON_PINS:
        label = tk.Label(buttons_frame, 
                         text=f"Nút GPIO {pin}: KHÔNG NHẤN", 
                         font=("Arial", 16), fg="green")
        label.pack(pady=5)
        button_labels.append(label)
        
        # Tạo đối tượng nút với pull_up=True
        button = Button(pin, pull_up=True)
        button_devices.append(button)

    # Frame cho switch giới hạn
    limit_frame = tk.Frame(main_frame)
    limit_frame.pack(pady=10)
    tk.Label(limit_frame, text="SWITCH GIỚI HẠN", font=("Arial", 18, "bold")).pack()

    # Nhãn và đối tượng cho các switch giới hạn
    limit_labels = []
    limit_devices = []
    for pin in LIMIT_SWITCH_PINS:
        label = tk.Label(limit_frame, 
                         text=f"Switch GPIO {pin}: MỞ", 
                         font=("Arial", 16), fg="green")
        label.pack(pady=5)
        limit_labels.append(label)
        
        # Tạo đối tượng input device với pull_up=True
        limit_switch = InputDevice(pin, pull_up=True)
        limit_devices.append(limit_switch)

    # Nút thoát
    exit_button = tk.Button(main_frame, text="THOÁT", 
                            command=root.quit, 
                            font=("Arial", 16))
    exit_button.pack(pady=20)

    # Hàm cập nhật trạng thái
    def update_input_state():
        try:
            # Cập nhật trạng thái nút nhấn
            for i, button in enumerate(button_devices):
                label = button_labels[i]
                
                if button.is_pressed:
                    label.config(text=f"Nút GPIO {BUTTON_PINS[i]}: NHẤN", fg="red")
                else:
                    label.config(text=f"Nút GPIO {BUTTON_PINS[i]}: KHÔNG NHẤN", fg="green")

            # Cập nhật trạng thái switch giới hạn
            for i, switch in enumerate(limit_devices):
                label = limit_labels[i]
                
                if switch.is_active:
                    label.config(text=f"Switch GPIO {LIMIT_SWITCH_PINS[i]}: ĐÓNG", fg="red")
                else:
                    label.config(text=f"Switch GPIO {LIMIT_SWITCH_PINS[i]}: MỞ", fg="green")

            # Lập lịch cập nhật lại
            root.after(100, update_input_state)
        except Exception as e:
            print(f"Lỗi: {e}")

    # Bắt đầu cập nhật
    update_input_state()

    # Chạy ứng dụng
    root.mainloop()

if __name__ == "__main__":
    main()