import cv2
import numpy as np
import os

class DRMManager:
    def __init__(self, config):
        self.config = config
        self.watermark_text = config.get("drm", {}).get("watermark_text", "COPYRIGHT")

    def apply_watermark(self, image: np.ndarray) -> np.ndarray:
        """
        Gắn watermark tên hệ thống vào ảnh để nhận diện trực quan.
        """
        output = image.copy()
        h, w = output.shape[:2]
        cv2.putText(output, self.watermark_text, (w - 200, h - 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        return output

    def embed_hidden_id(self, image: np.ndarray, owner_id: str) -> np.ndarray:
        """
        Mô phỏng cơ chế DRM ẩn (steganography đơn giản). 
        Thay đổi 1 pixel ở góc 0,0 để lưu dấu vết người sở hữu (giả lập).
        """
        output = image.copy()
        # Trong thực tế sẽ dùng các thuật toán phức tạp hơn để giấu tin
        # Ở đây ta chỉ làm marker đơn giản
        output[0, 0] = [255, 0, 0] # Red marker
        return output

    def check_drm_integrity(self, image: np.ndarray) -> bool:
        """
        Kiểm tra tính toàn vẹn của DRM metadata.
        Sử dụng tolerance để hỗ trợ ảnh JPEG bị nén nhẹ (màu sắc có thể lệch vài đơn vị).
        """
        if image is None or image.shape[0] < 1 or image.shape[1] < 1:
            return False
            
        # Lấy pixel đầu tiên
        pixel = image[0, 0] # Định dạng BGR trong OpenCV
        
        # Kiểm tra xem nó có "gần giống" màu đỏ [0, 0, 255] (BGR) không
        # Blue < 50, Green < 50, Red > 200
        is_red = pixel[2] > 200 and pixel[1] < 50 and pixel[0] < 50
        return is_red
