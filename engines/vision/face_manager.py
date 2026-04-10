import os
import logging
import cv2
import hashlib
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
            
        self.node_base_dir = "nodes"

    def _get_file_hash(self, filepath):
        """Tính toán mã băm SHA-256 của một file."""
        sha256_hash = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception:
            return None

    def check_identity_integrity(self, user_name):
        """
        Kiểm tra tính toàn vẹn của dữ liệu khuôn mặt giữa 2 vị trí lưu trữ.
        Trả về (True, "") nếu hợp lệ, hoặc (False, message) nếu bị can thiệp.
        """
        central_dir = os.path.join(self.faces_dir, user_name)
        node_dir = os.path.join(self.node_base_dir, user_name, "face_samples")
        
        if not os.path.exists(node_dir):
            return False, f"Thư mục định danh trong Node {user_name} bị thiếu!"
        if not os.path.exists(central_dir):
            return False, f"Thư mục định danh trung tâm của {user_name} bị thiếu!"
            
        central_files = [f for f in os.listdir(central_dir) if f.endswith(".jpg")]
        node_files = [f for f in os.listdir(node_dir) if f.endswith(".jpg")]
        
        if not central_files or not node_files:
            return False, f"Không tìm thấy mẫu khuôn mặt cho {user_name}."
            
        # So sánh hash của các file tương ứng (giả định tên file giống nhau)
        for filename in central_files:
            if filename in node_files:
                h1 = self._get_file_hash(os.path.join(central_dir, filename))
                h2 = self._get_file_hash(os.path.join(node_dir, filename))
                if h1 != h2:
                    logger.error(f"CANH BAO: {filename} cua {user_name} bi sai lech Hash!")
                    return False, f"Dữ liệu nhận diện của {user_name} đã bị chỉnh sửa trái phép!"
                    
        return True, ""

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
            user_dir_central = os.path.join(self.faces_dir, safe_name)
            user_dir_node = os.path.join(self.node_base_dir, safe_name, "face_samples")
            
            # Đảm bảo thư mục Node tồn tại (Bao gồm cả keys và ledger nếu là đăng ký mới)
            try:
                from engines.blockchain.blockchain_manager import BlockchainManager
                from core.config_loader import load_config
                config = load_config("config.yaml")
                BlockchainManager(config, node_name=safe_name)
            except Exception as e:
                logger.error(f"Loi khoi tao Node khi dang ky mat: {e}")

            # --- BƯỚC MỚI: Kiểm tra trùng lặp khuôn mặt (LÀM TRƯỚC KHI LƯU) ---
            try:
                check_input = frame if frame is not None else image_path
                existing_user = self.identify_face(check_input, skip_integrity=True)
                
                if existing_user != "Unknown":
                    if existing_user.lower() != safe_name.lower():
                        logger.warning(f"Từ chối đăng ký: {name} trùng khớp với {existing_user}")
                        return False, f"Khuôn mặt này đã được đăng ký dưới tên: {existing_user}"
            except Exception:
                pass

            if not os.path.exists(user_dir_central): os.makedirs(user_dir_central)
            if not os.path.exists(user_dir_node): os.makedirs(user_dir_node)
            
            # Lưu ảnh vào CẢ 2 thư mục
            import time
            timestamp = int(time.time())
            filename = f"{safe_name}_{timestamp}.jpg"
            target_path_central = os.path.join(user_dir_central, filename)
            target_path_node = os.path.join(user_dir_node, filename)
            
            def save_to_paths(data_or_path):
                if isinstance(data_or_path, str): # image_path
                    import shutil
                    shutil.copy(data_or_path, target_path_central)
                    shutil.copy(data_or_path, target_path_node)
                else: # frame
                    is_success, buffer = cv2.imencode(".jpg", data_or_path)
                    if is_success:
                        with open(target_path_central, "wb") as f: f.write(buffer)
                        with open(target_path_node, "wb") as f: f.write(buffer)
                        return True
                    return False

            if image_path:
                save_to_paths(image_path)
            elif frame is not None:
                if not save_to_paths(frame):
                    return False, "Không thể mã hóa hình ảnh."
            else:
                return False, "Không có dữ liệu hình ảnh."

            # Kiểm tra xem có khuôn mặt trong ảnh không (Dùng bản central để quét)
            try:
                objs = DeepFace.extract_faces(img_path=target_path_central, detector_backend=self.detector_backend, enforce_detection=True, anti_spoofing=self.anti_spoofing)
                # Kiểm tra liveness (is_real) nếu anti_spoofing được bật
                if self.anti_spoofing:
                    all_real = all(obj.get("is_real", True) for obj in objs)
                    if not all_real:
                        if os.path.exists(target_path): os.remove(target_path)
                        return False, "Phát hiện khuôn mặt giả mạo (Spoofing)!"
                
                if len(objs) > 0:
                    logger.info(f"Đã đăng ký thành công khuôn mặt: {name} (Lưu kép tại Central & Node {safe_name})")
                    return True, f"Đã đăng ký {name}"
                else:
                    if os.path.exists(target_path_central): os.remove(target_path_central)
                    if os.path.exists(target_path_node): os.remove(target_path_node)
                    return False, "Không tìm thấy khuôn mặt trong ảnh."
            except Exception as e:
                if os.path.exists(target_path_central): os.remove(target_path_central)
                if os.path.exists(target_path_node): os.remove(target_path_node)
                return False, f"Không nhận diện được mặt: {e}"
                
        except Exception as e:
            return False, f"Lỗi hệ thống: {e}"

    def identify_face(self, frame, skip_integrity=False):
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
                    
                    # --- BƯỚC MỚI: Kiểm tra tính toàn vẹn (Integrity Check) ---
                    if not skip_integrity:
                        is_ok, err_msg = self.check_identity_integrity(user_name)
                        if not is_ok:
                            logger.error(f"Xac thuc bi chan dung do {err_msg}")
                            return "Unknown" # Hoặc có thể trả về một code lỗi riêng
                    # ---------------------------------------------------------

                    logger.info(f"Nhận diện thành công: {user_name} (dist={distance:.4f})")
                    return user_name
                else:
                    logger.warning(f"Người lạ - khoảng cách {distance:.4f} > ngưỡng {self.threshold}")
                
            return "Unknown"
        except Exception as e:
            logger.error(f"Lỗi nhận diện: {e}") # Bật log để debug
            return "Unknown"
