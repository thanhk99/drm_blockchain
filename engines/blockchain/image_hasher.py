import hashlib
import cv2
import numpy as np

class ImageHasher:
    @staticmethod
    def get_sha256(image_path: str) -> str:
        """Tính toán SHA-256 hash của một file ảnh."""
        sha256_hash = hashlib.sha256()
        with open(image_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    @staticmethod
    def get_perceptual_hash(image: np.ndarray) -> str:
        """
        Tính toán mã băm cảm quan DHash (Difference Hash) - 256 bit.
        DHash mạnh mẽ hơn aHash trong việc nhận diện các thay đổi cấu trúc nhỏ.
        """
        # 1. Resize về 17x16 (17 ngang để so sánh cặp, 16 dọc)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (17, 16), interpolation=cv2.INTER_AREA)
        
        # 2. So sánh các pixel cạnh nhau theo chiều ngang
        # Nếu pixel trái > pixel phải -> 1, ngược lại -> 0
        diff = resized[:, :-1] > resized[:, 1:]
        
        # 3. Chuyển thành chuỗi hex 256-bit (64 ký tự hex)
        hash_binary = "".join(['1' if x else '0' for x in diff.flatten()])
        
        # Chuyển đổi chuỗi bit dài sang Hex
        hash_int = int(hash_binary, 2)
        hash_hex = hex(hash_int)[2:].zfill(64) # 256 bits = 64 hex chars
        return hash_hex
    @staticmethod
    def get_wavelet_hash(image: np.ndarray) -> str:
        """
        Tính toán Wavelet Hash (wHash), mạnh mẽ hơn pHash/dHash 
        trong việc chống lại thay đổi kích thước (scale) và nén JPEG.
        """
        import imagehash
        from PIL import Image
        img_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        return str(imagehash.whash(img_pil))

    @staticmethod
    def get_ssim_score(img1: np.ndarray, img2: np.ndarray) -> float:
        """Tính SSIM score giữa 2 ảnh (Yêu cầu ảnh gốc)"""
        try:
            from skimage.metrics import structural_similarity as ssim
            gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
            if gray1.shape != gray2.shape:
                gray2 = cv2.resize(gray2, (gray1.shape[1], gray1.shape[0]))
            score, _ = ssim(gray1, gray2, full=True)
            return score
        except Exception:
            return 0.0

    @staticmethod
    def hamming_distance(hash1: str, hash2: str) -> int:
        """Tính khoảng cách Hamming giữa 2 mã băm hex 256-bit."""
        try:
            h1 = int(hash1, 16)
            h2 = int(hash2, 16)
            return bin(h1 ^ h2).count('1')
        except:
            return 1000 # Lỗi định dạng mã băm

    @staticmethod
    def get_orb_features(image: np.ndarray):
        """
        Trích xuất đặc trưng ORB (Oriented FAST and Rotated BRIEF).
        Giúp nhận diện ảnh bất kể xoay, thu phóng hay biến dạng.
        """
        orb = cv2.ORB_create(nfeatures=500)
        keypoints, descriptors = orb.detectAndCompute(image, None)
        
        if descriptors is not None:
            # Chuyển đổi descriptors sang list để có thể lưu vào JSON
            return descriptors.tolist()
        return None

    @staticmethod
    def match_orb_features(desc1_list, desc2_list):
        """
        So khớp đặc trưng giữa 2 tập descriptors.
        Trả về tỉ lệ khớp (0.0 - 1.0).
        """
        if desc1_list is None or desc2_list is None:
            return 0.0
            
        desc1 = np.array(desc1_list, dtype=np.uint8)
        desc2 = np.array(desc2_list, dtype=np.uint8)
        
        # Khởi tạo Brute-Force Matcher với khoảng cách Hamming (dành cho ORB)
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(desc1, desc2)
        
        # Sắp xếp theo khoảng cách
        matches = sorted(matches, key=lambda x: x.distance)
        
        # Tính toán tỉ lệ khớp dựa trên số lượng matches tốt
        # Thông thường > 15% matches tốt là có sự tương đồng lớn
        good_matches = [m for m in matches if m.distance < 50]
        
        match_ratio = len(good_matches) / max(len(desc1), len(desc2))
        return match_ratio

    @staticmethod
    def get_content_hash(image: np.ndarray) -> str:
        """
        Tính toán hash dựa trên nội dung điểm ảnh (pixel data).
        """
        return hashlib.sha256(image.tobytes()).hexdigest()

    @staticmethod
    def compare_hashes(hash1: str, hash2: str) -> bool:
        return hash1 == hash2
