# yolo_detector.py - Phát hiện người với YOLO

import cv2
import numpy as np
import os
from config import *

def load_yolo_model():
    """Tải mô hình YOLO"""
    try:
        # Kiểm tra nếu các file mô hình tồn tại
        if not (os.path.exists(YOLO_CONFIG) and os.path.exists(YOLO_WEIGHTS) and os.path.exists(YOLO_CLASSES)):
            download_yolo_model()
            
            # Kiểm tra lại sau khi tải
            if not (os.path.exists(YOLO_CONFIG) and os.path.exists(YOLO_WEIGHTS) and os.path.exists(YOLO_CLASSES)):
                print("Không thể tải mô hình. Vui lòng tạo thủ công các file hoặc kiểm tra lại kết nối Internet.")
                return None, None, None
        
        # Đọc danh sách các lớp
        with open(YOLO_CLASSES, 'r') as f:
            classes = [line.strip() for line in f.readlines()]
        
        # Chỉ quan tâm đến lớp 'person' (thường là index 0 trong coco.names)
        person_class_id = classes.index('person') if 'person' in classes else 0
        
        # Tải mô hình YOLO
        net = cv2.dnn.readNetFromDarknet(YOLO_CONFIG, YOLO_WEIGHTS)
        
        # Sử dụng CPU
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        
        # Lấy tên các layer output
        layer_names = net.getLayerNames()
        output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]
        
        return net, output_layers, person_class_id
    
    except Exception as e:
        print(f"Lỗi khi tải mô hình YOLO: {e}")
        return None, None, None

def download_yolo_model():
    """Tải các file mô hình YOLO nếu chưa có"""
    print("Cần tải file mô hình YOLOv4-tiny. Đang tải...")
    
    # Tạo thư mục nếu chưa tồn tại
    os.makedirs(os.path.dirname(YOLO_CONFIG), exist_ok=True)
    
    # Tải file cấu hình YOLOv4-tiny
    print("Đang tải file cấu hình...")
    os.system(f"wget -O {YOLO_CONFIG} https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4-tiny.cfg")
    
    # Tải file weights YOLOv4-tiny
    print("Đang tải file weights...")
    os.system(f"wget -O {YOLO_WEIGHTS} https://github.com/AlexeyAB/darknet/releases/download/darknet_yolo_v4_pre/yolov4-tiny.weights")
    
    # Tải file tên lớp
    print("Đang tải file classes...")
    os.system(f"wget -O {YOLO_CLASSES} https://raw.githubusercontent.com/AlexeyAB/darknet/master/data/coco.names")

def detect_people(frame, net, output_layers, person_class_id):
    """Phát hiện người trong khung hình sử dụng YOLO"""
    height, width = frame.shape[:2]
    
    # Chuẩn bị blob cho YOLO
    blob = cv2.dnn.blobFromImage(frame, 1/255.0, (416, 416), swapRB=True, crop=False)
    net.setInput(blob)
    
    # Chạy mô hình
    outputs = net.forward(output_layers)
    
    # Xử lý kết quả
    boxes = []
    confidences = []
    class_ids = []
    
    for output in outputs:
        for detection in output:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            
            # Chỉ quan tâm đến người và confidence > 0.5
            if class_id == person_class_id and confidence > 0.5:
                # Tọa độ hình chữ nhật
                center_x = int(detection[0] * width)
                center_y = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)
                
                # Điểm trên cùng bên trái
                x = int(center_x - w / 2)
                y = int(center_y - h / 2)
                
                boxes.append([x, y, w, h])
                confidences.append(float(confidence))
                class_ids.append(class_id)
    
    # Non-maximum suppression để loại bỏ các bounding box chồng chéo
    indices = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)
    
    result_boxes = []
    result_confidences = []
    
    if len(boxes) > 0:
        if isinstance(indices, np.ndarray):
            indices = indices.flatten()
        else:
            indices = indices.flatten() if len(indices) > 0 else []
        
        for i in indices:
            result_boxes.append(boxes[i])
            result_confidences.append(confidences[i])
    
    return result_boxes, result_confidences