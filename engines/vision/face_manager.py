import os
import logging
import cv2
from deepface import DeepFace

logger = logging.getLogger("FaceManager")

class FaceManager:
    def __init__(self, faces_dir="models/vision/faces"):
        self.faces_dir = faces_dir
        self.model_name = "ArcFace" 
        self.detector_backend = "opencv" 
        self.threshold = 0.35 # Điều chỉnh ngưỡng khắt khe hơn cho ArcFace
        self.anti_spoofing = True # Kích hoạt Liveness Detection của DeepFace
        
        if not os.path.exists(self.faces_dir):
            os.makedirs(self.faces_dir)

    def register_face(self, name, image_path=None, frame=None):
        """
        Đăng ký một khuôn mặt mới bằng cách lưu ảnh vào thư mục faces/.
        DeepFace sẽ quét thư mục này để nhận diện.
        """
        try:
            # Làm sạch tên người dùng để tạo thư mục an toàn
            import unicodedata
            def remove_accents(input_str):
                nfkd_form = unicodedata.normalize('NFKD', input_str)
                return "".join([c for c in nfkd_form if not unicodedata.combining(c)])
            
            safe_name = remove_accents(name).replace(" ", "_")
            user_dir = os.path.join(self.faces_dir, safe_name)
            # --- BƯỚC MỚI: Kiểm tra trùng lặp khuôn mặt (LÀM TRƯỚC KHI LƯU) ---
            try:
                # Kiểm tra xem khuôn mặt trong frame (hoặc file tạm) đã có trong DB chưa
                check_input = frame if frame is not None else image_path
                existing_user = self.identify_face(check_input)
                
                if existing_user != "Unknown":
                    # Nếu khuôn mặt này đã thuộc về người khác -> Từ chối
                    if existing_user.lower() != safe_name.lower():
                        logger.warning(f"Từ chối đăng ký: {name} trùng khớp với {existing_user}")
                        return False, f"Khuôn mặt này đã được đăng ký dưới tên: {existing_user}"
                    else:
                        logger.info(f"Người dùng {name} đang bổ sung thêm mẫu khuôn mặt mới.")
            except Exception as e:
                logger.debug(f"Bỏ qua lỗi kiểm tra trùng lặp sơ bộ: {e}")
            # -------------------------------------------------------------

            if not os.path.exists(user_dir):
                os.makedirs(user_dir)
            
            # Lưu ảnh vào thư mục người dùng
            import time
            timestamp = int(time.time())
            filename = f"{safe_name}_{timestamp}.jpg"
            target_path = os.path.normpath(os.path.join(user_dir, filename))
            
            if image_path:
                import shutil
                shutil.copy(image_path, target_path)
            elif frame is not None:
                is_success, buffer = cv2.imencode(".jpg", frame)
                if is_success:
                    with open(target_path, "wb") as f:
                        f.write(buffer)
                else:
                    return False, "Không thể mã hóa hình ảnh."
            else:
                return False, "Không có dữ liệu hình ảnh."

            # Kiểm tra xem có khuôn mặt trong ảnh không, đồng thời chạy Liveness Check
            try:
                objs = DeepFace.extract_faces(img_path=target_path, detector_backend=self.detector_backend, enforce_detection=True, anti_spoofing=self.anti_spoofing)
                # Kiểm tra liveness (is_real) nếu anti_spoofing được bật
                if self.anti_spoofing:
                    all_real = all(obj.get("is_real", True) for obj in objs)
                    if not all_real:
                        if os.path.exists(target_path): os.remove(target_path)
                        return False, "Phát hiện khuôn mặt giả mạo (Spoofing)!"
                
                if len(objs) > 0:
                    logger.info(f"Đã đăng ký thành công khuôn mặt: {name} (Thư mục: {safe_name})")
                    return True, f"Đã đăng ký {name}"
                else:
                    if os.path.exists(target_path): os.remove(target_path)
                    return False, "Không tìm thấy khuôn mặt trong ảnh."
            except Exception as e:
                if os.path.exists(target_path): os.remove(target_path)
                return False, f"Không nhận diện được mặt: {e}"
                
        except Exception as e:
            return False, f"Lỗi hệ thống: {e}"

    def identify_face(self, frame):
        """Nhận diện khuôn mặt trong một frame hình ảnh sử dụng DeepFace.find."""
        try:
            results = DeepFace.find(img_path=frame, 
                                    db_path=self.faces_dir, 
                                    model_name=self.model_name, 
                                    detector_backend=self.detector_backend, 
                                    distance_metric='cosine',
                                    enforce_detection=False, # Không throw lỗi nếu detect mặt không rõ
                                    silent=True)
            
            if len(results) > 0 and not results[0].empty:
                best_match = results[0].iloc[0]
                
                # Tự tìm cột distance (tên cột thay đổi theo phiên bản DeepFace)
                dist_col = None
                for col in results[0].columns:
                    if 'cosine' in col.lower() or 'distance' in col.lower():
                        dist_col = col
                        break
                
                if dist_col is None:
                    logger.error(f"Không tìm thấy cột distance. Các cột hiện có: {list(results[0].columns)}")
                    return "Unknown"
                
                distance = best_match[dist_col]
                logger.info(f"Khoảng cách ArcFace tốt nhất: {distance:.4f} (ngưỡng: {self.threshold}, cột: {dist_col})")
                
                if distance < self.threshold:
                    best_match_path = best_match['identity']
                    user_name = os.path.basename(os.path.dirname(best_match_path))
                    logger.info(f"Nhận diện thành công: {user_name} (dist={distance:.4f})")
                    return user_name
                else:
                    logger.warning(f"Người lạ - khoảng cách {distance:.4f} > ngưỡng {self.threshold}")
                
            return "Unknown"
        except Exception as e:
            logger.error(f"Lỗi nhận diện: {e}") # Bật log để debug
            return "Unknown"
