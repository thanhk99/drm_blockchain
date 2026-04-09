import cv2
import logging
import os
import sys
import time
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog
from PIL import Image, ImageTk

# Thêm đường dẫn để import các module local
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config_loader import load_config
from engines.vision.security_engine import SecurityEngine
from engines.blockchain.blockchain_manager import BlockchainManager
from engines.blockchain.image_hasher import ImageHasher
from engines.drm.drm_manager import DRMManager

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("DRM_App")

class CameraDialog(tk.Toplevel):
    """Cửa sổ hiển thị Camera Live View."""
    def __init__(self, parent, title="Camera View", mode="verify"):
        super().__init__(parent)
        self.title(title)
        self.geometry("660x540")
        self.configure(bg="#2c3e50")
        self.resizable(False, False)
        
        self.mode = mode # "verify" hoặc "register"
        self.captured_frame = None
        self.current_frame = None
        self.is_running = True
        
        self.label = tk.Label(self)
        self.label.pack(pady=10)
        
        btn_frame = tk.Frame(self, bg="#2c3e50")
        btn_frame.pack(fill=tk.X, pady=10)
        
        btn_text = "Chụp ảnh" if mode=="register" else "Xác nhận"
        self.action_btn = tk.Button(btn_frame, text=btn_text, 
                                   command=self.capture, bg="#2ecc71", fg="white", font=("Helvetica", 12), width=15)
        self.action_btn.pack(side=tk.LEFT, padx=100)
        
        tk.Button(btn_frame, text="Hủy", command=self.cancel, 
                  bg="#e74c3c", fg="white", font=("Helvetica", 12), width=15).pack(side=tk.RIGHT, padx=100)
        
        self.protocol("WM_DELETE_WINDOW", self.cancel)

    def update_frame(self, cap):
        if self.is_running:
            ret, frame = cap.read()
            if ret:
                self.current_frame = frame
                # Chuyển đổi để hiển thị trong Tkinter
                cv2_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(cv2_img)
                imgtk = ImageTk.PhotoImage(image=img)
                self.label.imgtk = imgtk # type: ignore
                self.label.configure(image=imgtk)
            
            self.after(20, lambda: self.update_frame(cap))

    def capture(self):
        if self.current_frame is not None:
            self.captured_frame = self.current_frame.copy()
        self.is_running = False
        self.destroy()

    def cancel(self):
        self.captured_frame = None
        self.is_running = False
        self.destroy()

class DRMAppGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Hệ thống Bản quyền Số - Blockchain & FaceID")
        self.root.geometry("800x650") # Tăng chiều cao một chút
        self.root.configure(bg="#2c3e50")

        # Khởi tạo backend
        self.config = load_config("config.yaml")
        self.security = SecurityEngine()
        self.blockchain = BlockchainManager(self.config)
        self.drm = DRMManager(self.config)
        self.hasher = ImageHasher()
        self.output_dir = "protected_images"
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.log_area = None
        self._setup_ui()
        
        # Kiểm tra tính toàn vẹn blockchain ngay khi khởi động
        self._check_blockchain_integrity()

    def _check_blockchain_integrity(self):
        """Kiểm tra và thông báo trạng thái blockchain."""
        self.log("Đang kiểm tra tính toàn vẹn của hệ thống Blockchain...")
        if self.blockchain.is_chain_valid():
            self.log("TRẠNG THÁI: [SECURE] Blockchain hợp lệ và an toàn.")
        else:
            self.log("CẢNH BÁO: [TAMPERED] Phát hiện dấu hiệu chỉnh sửa dữ liệu trái phép!")
            messagebox.showwarning("Cảnh báo Bảo mật", "Hệ thống Blockchain phát hiện dữ liệu có dấu hiệu bị can thiệp trái phép!")

    def _setup_ui(self):
        # Title
        title_label = tk.Label(self.root, text="HỆ THỐNG BẢO VỆ BẢN QUYỀN SỐ", 
                               font=("Helvetica", 18, "bold"), fg="#ecf0f1", bg="#2c3e50", pady=20)
        title_label.pack()

        # Main Frame
        main_frame = tk.Frame(self.root, bg="#2c3e50")
        main_frame.pack(pady=10, fill=tk.BOTH, expand=True)

        # Button Frame
        btn_frame = tk.Frame(main_frame, bg="#2c3e50")
        btn_frame.pack(side=tk.LEFT, padx=20, fill=tk.Y)

        tk.Button(btn_frame, text="0. Đăng ký từ Camera", command=self.on_register_face, 
                  font=("Helvetica", 12, "bold"), width=20, pady=10, bg="#27ae60", fg="white", activebackground="#219150").pack(pady=5)
        
        tk.Button(btn_frame, text="0b. Đăng ký từ Ảnh File", command=self.on_register_face_from_file, 
                  font=("Helvetica", 11), width=20, pady=8, bg="#1e8449", fg="white", activebackground="#196f3d").pack(pady=5)
        
        tk.Button(btn_frame, text="1. Đăng ký Bản quyền", command=self.on_register, 
                  font=("Helvetica", 12), width=20, pady=10, bg="#3498db", fg="white", activebackground="#2980b9").pack(pady=10)
        tk.Button(btn_frame, text="2. Xác thực Bản quyền", command=self.on_verify_image, 
                  font=("Helvetica", 12), width=20, pady=10, bg="#3498db", fg="white", activebackground="#2980b9").pack(pady=10)
        tk.Button(btn_frame, text="3. Quét Khuôn mặt", command=self.on_face_id, 
                  font=("Helvetica", 12), width=20, pady=10, bg="#3498db", fg="white", activebackground="#2980b9").pack(pady=10)
        
        tk.Label(btn_frame, text="---", bg="#2c3e50", fg="#7f8c8d").pack(pady=5)
        tk.Button(btn_frame, text="4. Kiểm tra Blockchain", command=self._check_blockchain_integrity, 
                  font=("Helvetica", 10), width=20, pady=5, bg="#95a5a6", fg="white", activebackground="#7f8c8d").pack(pady=5)
        
        tk.Button(btn_frame, text="Thoát", command=self.root.quit, bg="#e74c3c", fg="white", width=20).pack(pady=10)

        # Log Frame
        log_frame = tk.Frame(main_frame, bg="#2c3e50")
        log_frame.pack(side=tk.RIGHT, padx=20, fill=tk.BOTH, expand=True)

        tk.Label(log_frame, text="Nhật ký hệ thống:", bg="#2c3e50", fg="#bdc3c7").pack(anchor=tk.W)
        self.log_area = scrolledtext.ScrolledText(log_frame, bg="#000", fg="#0f0", font=("Consolas", 10))
        self.log_area.pack(fill=tk.BOTH, expand=True)

    def log(self, message):
        if self.log_area:
            timestamp = time.strftime("[%H:%M:%S] ")
            self.log_area.insert(tk.END, timestamp + message + "\n")
            self.log_area.see(tk.END)
        logger.info(message)

    def _open_camera(self, cam_id):
        """Hàm helper để mở camera với nhiều backend trên Windows."""
        if cam_id is None: return None
        
        # Thử các backend khác nhau trên Windows
        backends = [cv2.CAP_DSHOW, None, cv2.CAP_MSMF]
        
        for backend in backends:
            name = "Mặc định" if backend is None else ("DSHOW" if backend == cv2.CAP_DSHOW else "MSMF")
            try:
                self.log(f"Đang thử mở Camera {cam_id} với driver: {name}...")
                cap = cv2.VideoCapture(cam_id + (backend if backend else 0))
                
                if cap.isOpened():
                    # Đọc thử vài frame để kiểm tra hối đáp (tránh màn hình xanh/đen)
                    for _ in range(5):
                        ret, frame = cap.read()
                        if ret:
                            self.log(f"Thành công! Đã mở camera {cam_id} bằng {name}")
                            return cap
                    cap.release()
            except Exception as e:
                logger.error(f"Lỗi khi thử driver {name}: {e}")
                
        return None

    def _get_frame_from_camera(self, title="Camera View", mode="verify"):
        """Hiển thị cửa sổ Live View và trả về frame người dùng chụp."""
        cam_id = self.config.get("vision", {}).get("camera_id", 0)
        cap = self._open_camera(cam_id)
        if not cap:
            messagebox.showerror("Lỗi", "Không thể mở camera.")
            return None
        
        dialog = CameraDialog(self.root, title=title, mode=mode)
        dialog.update_frame(cap)
        self.root.wait_window(dialog)
        
        captured_frame = dialog.captured_frame
        cap.release()
        return captured_frame

    def imread_unicode(self, path):
        """Đọc ảnh từ đường dẫn Unicode trên Windows."""
        import numpy as np
        try:
            return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        except Exception as e:
            self.log(f"Lỗi khi đọc file Unicode: {e}")
            return None

    def on_register_face_from_file(self):
        """Đăng ký khuôn mặt từ file ảnh tự chụp."""
        from tkinter import simpledialog
        name = simpledialog.askstring("Đăng ký", "Nhập tên người dùng:")
        if not name:
            return

        file_path = filedialog.askopenfilename(
            title=f"Chọn ảnh khuôn mặt cho: {name}",
            filetypes=[("Image files", "*.jpg *.jpeg *.png")]
        )
        if not file_path:
            return

        def task():
            self.log(f"Đang đăng ký khuôn mặt từ file: {os.path.basename(file_path)}")
            img_data = self.imread_unicode(file_path)
            if img_data is None:
                self.log("Lỗi: Không thể đọc file ảnh.")
                messagebox.showerror("Lỗi", "Không thể đọc file ảnh. Vui lòng thử lại.")
                return

            success, msg = self.security.face_manager.register_face(name, frame=img_data)
            if success:
                self.log(f"Thành công: {msg}")
                messagebox.showinfo("Thành công", f"Đã đăng ký khuôn mặt cho {name} từ file ảnh!")
            else:
                self.log(f"Thất bại: {msg}")
                messagebox.showerror("Lỗi", msg)

        threading.Thread(target=task, daemon=True).start()

    def on_register_face(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("Đăng ký", "Nhập tên người dùng mới:")
        if not name:
            return

        def task():
            self.log(f"Bắt đầu đăng ký khuôn mặt cho: {name}")
            frame = self._get_frame_from_camera(f"Đăng ký khuôn mặt: {name}", mode="register")
            
            if frame is not None:
                success, msg = self.security.face_manager.register_face(name, frame=frame)
                if success:
                    self.log(f"Thành công: {msg}")
                    messagebox.showinfo("Thành công", f"Đã đăng ký khuôn mặt cho {name}")
                else:
                    self.log(f"Thất bại: {msg}")
                    messagebox.showerror("Lỗi", msg)
            else:
                self.log("Đã hủy đăng ký khuôn mặt.")

        threading.Thread(target=task, daemon=True).start()

    def on_face_id(self):
        def task():
            self.log("Đang mở camera để quét khuôn mặt...")
            frame = self._get_frame_from_camera("Xác thực khuôn mặt")
            
            if frame is None:
                self.log("Đã hủy quét khuôn mặt.")
                return

            user = self.security.authenticate(frame)
            if user != "Unknown" and user != "Guest":
                balance = self.blockchain.get_balance(user)
                self.log(f"Xác thực thành công: CHÀO {user.upper()}")
                self.log(f"Số dư Ví: {balance} DRM Coins")
                messagebox.showinfo("FaceID", f"Xin chào {user}!\nSố dư hiện tại: {balance} DRM Coins")
            else:
                self.log("Cảnh báo: Không nhận diện được người dùng.")
                messagebox.showwarning("FaceID", "Không nhận diện được khuôn mặt.")

        threading.Thread(target=task, daemon=True).start()

    def on_register(self):
        file_path = filedialog.askopenfilename(title="Chọn ảnh để đăng ký bản quyền", 
                                              filetypes=[("Image files", "*.jpg *.jpeg *.png")])
        if not file_path:
            return

        def task():
            self.log(f"Bắt đầu đăng ký cho: {os.path.basename(file_path)}")
            
            # Bước 1: FaceID
            self.log("Bước 1: Quét khuôn mặt xác nhận chủ sở hữu...")
            frame = self._get_frame_from_camera("Xác thực chủ sở hữu")
            
            if frame is None:
                self.log("Đã hủy quy trình đăng ký.")
                return

            user = self.security.authenticate(frame)
            if user == "Unknown" or user == "Guest":
                self.log("Thất bại: Bạn không có quyền đăng ký bản quyền.")
                messagebox.showerror("Lỗi", "Vui lòng xác thực khuôn mặt chủ sở hữu đã đăng ký.")
                return

            balance = self.blockchain.get_balance(user)
            self.log(f"Đã xác thực: {user} (Số dư hiện tại: {balance} Coins)")

            # Bước 2: Xử lý DRM - Tạo ảnh bảo vệ trước
            self.log("Bước 2: Đang thực hiện gắn dấu bảo vệ DRM...")
            img_data = self.imread_unicode(file_path)
            if img_data is None:
                self.log("Lỗi: Không thể đọc dữ liệu ảnh.")
                messagebox.showerror("Lỗi", "Không thể đọc file ảnh. Vui lòng kiểm tra lại đường dẫn.")
                return

            # Tạo phiên ảnh bảo vệ (có watermark và marker)
            protected_img = self.drm.apply_watermark(img_data)
            protected_img = self.drm.embed_hidden_id(protected_img, user)
            
            # Bước 3: Đăng ký đa tầng (Dual-Hash + pHash + ORB) lên Blockchain
            self.log(f"Bước 3: Ghi nhận bản quyền nâng cao cho chủ sở hữu: {user}")
            
            # Tính hash của ảnh gốc và ảnh đã bảo vệ
            hash_original = self.hasher.get_content_hash(img_data)
            hash_protected = self.hasher.get_content_hash(protected_img)
            
            # Tính pHash (Mã băm cảm quan - 256bit)
            p_hash = self.hasher.get_perceptual_hash(img_data)
            
            # Tính Wavelet Hash (kháng scale & JPEG compress)
            w_hash = self.hasher.get_wavelet_hash(img_data)
            
            # Trích xuất đặc trưng hình học ORB (Kháng xoay/thu phóng)
            orb_features = self.hasher.get_orb_features(img_data)
            
            # Đăng ký lên Blockchain (thêm w_hash)
            success, msg = self.blockchain.register_copyright([hash_original, hash_protected], p_hash, w_hash, orb_features, user)
            if not success:
                self.log(f"Lỗi: {msg}")
                messagebox.showwarning("Thông báo", msg)
                return

            # Bước 4: DRM Export
            self.log("Bước 4: Xuất file ảnh bản quyền...")
            output_path = os.path.join(self.output_dir, f"DRM_{os.path.basename(file_path)}")
            
            # Ghi file an toàn với Unicode
            is_success, buffer = cv2.imencode(".jpg", protected_img)
            if is_success:
                with open(output_path, "wb") as f:
                    f.write(buffer)
                self.log(f"HOÀN TẤT! File bảo vệ: {output_path}")
                messagebox.showinfo("Thành công", f"Đã đăng ký bản quyền!\n\nLưu tại: {output_path}\nĐã kích hoạt bảo vệ mức Cao (Kháng xoay/thu phóng).")
            else:
                self.log("Lỗi: Không thể xuất file ảnh bảo vệ.")

        threading.Thread(target=task, daemon=True).start()

    def on_verify_image(self):
        file_path = filedialog.askopenfilename(title="Chọn ảnh để kiểm tra bản quyền")
        if not file_path:
            return

        def task():
            self.log(f"Đang kiểm tra: {os.path.basename(file_path)}")
            img_data = self.imread_unicode(file_path)
            if img_data is None:
                self.log("Lỗi: Không thể đọc dữ liệu ảnh.")
                return

            # Tính toán các mã băm
            content_hash = self.hasher.get_content_hash(img_data)
            current_p_hash = self.hasher.get_perceptual_hash(img_data)
            current_w_hash = self.hasher.get_wavelet_hash(img_data)
            
            # Xác thực đa tầng
            found, record, match_type = self.blockchain.verify_copyright(content_hash, current_p_hash, current_w_hash, img_data)
            
            if found:
                self.log(f">>> KẾT QUẢ: XÁC THỰC THÀNH CÔNG! ({match_type})")
                self.log(f"Chủ sở hữu: {record['owner']}")
                
                # Logic hiển thị thông báo
                if "GEOMETRIC" in match_type:
                    self.log("Phát hiện: Ảnh đã bị xoay, thu phóng hoặc biến dạng hình học.")
                    status_msg = f"Chủ sở hữu: {record['owner']}\nKết quả: Khớp đặc trưng hình học\nTrạng thái: Hợp lệ (Bất kể xoay/thu phóng)"
                elif "WAVELET" in match_type:
                    self.log("Phát hiện: Ảnh đã bị thay đổi kích thước hoặc nén mạnh.")
                    status_msg = f"Chủ sở hữu: {record['owner']}\nKết quả: Khớp Wavelet\nTrạng thái: Hợp lệ (Đã scale/nén)"
                elif "FUZZY" in match_type:
                    self.log("Phát hiện: Ảnh đã bị chỉnh sửa nhẹ hoặc nén lại.")
                    status_msg = f"Chủ sở hữu: {record['owner']}\nKết quả: Khớp nội dung cảm quan\nTrạng thái: Hợp lệ (Đã chỉnh sửa nhẹ)"
                else:
                    status_msg = f"Chủ sở hữu: {record['owner']}\nTrạng thái: Nguyên bản (Khớp 100%)"
                
                messagebox.showinfo("Xác thực bản quyền", status_msg)
            else:
                self.log(">>> KẾT QUẢ: KHÔNG TÌM THẤY BẢN QUYỀN.")
                messagebox.showerror("Kết quả", "Hệ thống không tìm thấy bản quyền cho ảnh này (Ngay cả khi đã quét đặc trưng hình học).")

        threading.Thread(target=task, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = DRMAppGUI(root)
    root.mainloop()
