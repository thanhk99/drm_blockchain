import logging
import time
import json
import os

logger = logging.getLogger("BlockchainManager")

class BlockchainManager:
    def __init__(self, config):
        """
        Khởi tạo Blockchain Manager. 
        Trong bản demo này, chúng ta sẽ mô phỏng một sổ cái (ledger) bằng file JSON cục bộ.
        """
        self.config = config
        self.ledger_path = "models/blockchain_ledger.json"
        self._load_ledger()

    def _load_ledger(self):
        if os.path.exists(self.ledger_path):
            with open(self.ledger_path, "r", encoding="utf-8") as f:
                self.ledger = json.load(f)
        else:
            self.ledger = []
            self._save_ledger()

    def _save_ledger(self):
        # Đảm bảo thư mục tồn tại
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)
        with open(self.ledger_path, "w", encoding="utf-8") as f:
            json.dump(self.ledger, f, indent=4)

    def register_copyright(self, hash_list, p_hash, w_hash, orb_features, owner_name):
        """
        Ghi nhận bản quyền với Dual-Hash, pHash, wHash và ORB Features.
        """
        if isinstance(hash_list, str):
            hash_list = [hash_list]

        # Kiểm tra trùng lặp tuyệt đối
        for entry in self.ledger:
            existing_hashes = entry.get("hashes", [entry.get("hash")])
            for h in hash_list:
                if h in existing_hashes:
                    return False, f"Ảnh này đã được đăng ký bởi {entry['owner']}"

        new_block = {
            "index": len(self.ledger) + 1,
            "timestamp": time.time(),
            "hashes": hash_list,
            "p_hash": p_hash,
            "w_hash": w_hash,
            "orb_features": orb_features, # Lưu đặc trưng hình học
            "owner": owner_name,
            "previous_hash": self.ledger[-1].get("hashes", [self.ledger[-1].get("hash", "0")])[0] if self.ledger else "0"
        }
        
        self.ledger.append(new_block)
        self._save_ledger()
        logger.info(f"Đã ghi nhận bản quyền ORB cho {owner_name}")
        return True, "Đã lưu lên Blockchain thành công (ORB)."

    def verify_copyright(self, image_hash, current_p_hash=None, current_w_hash=None, current_image=None):
        """
        Xác thực bản quyền đa tầng:
        1. Exact Hash (SHA256)
        2. Perceptual Hash (DHash) & Wavelet Hash (wHash)
        3. Feature Matching (ORB) - Kháng xoay/thu phóng
        """
        from engines.blockchain.image_hasher import ImageHasher

        # Tầng 1: Khớp tuyệt đối
        for entry in self.ledger:
            existing_hashes = entry.get("hashes", [entry.get("hash")])
            if image_hash in existing_hashes:
                return True, entry, "EXACT"

        # Tầng 2: Khớp cảm quan (pHash & wHash)
        if current_p_hash or current_w_hash:
            for entry in self.ledger:
                # Kiểm tra Wavelet Hash trước vì nó chính xác hơn cho scale/nén
                if current_w_hash and entry.get("w_hash"):
                    try:
                        import imagehash
                        h1 = imagehash.hex_to_hash(current_w_hash)
                        h2 = imagehash.hex_to_hash(entry.get("w_hash"))
                        distance = h1 - h2
                        if distance <= 12: # Ngưỡng Hamming cho wHash
                            similarity = ((64 - distance) / 64) * 100
                            return True, entry, f"WAVELET (Sự tương đồng wHash: {similarity:.1f}%)"
                    except Exception:
                        pass
                
                # Fallback pHash
                target_p_hash = entry.get("p_hash")
                if current_p_hash and target_p_hash:
                    distance = ImageHasher.hamming_distance(current_p_hash, target_p_hash)
                    if distance <= 32:
                        similarity = ((256 - distance) / 256) * 100
                        return True, entry, f"FUZZY (Sự tương đồng pHash: {similarity:.1f}%)"

        # Tầng 3: Khớp đặc trưng (ORB) - Cuối cùng, mạnh nhất nhưng chậm nhất
        if current_image is not None:
            current_orb = ImageHasher.get_orb_features(current_image)
            if current_orb:
                for entry in self.ledger:
                    target_orb = entry.get("orb_features")
                    if target_orb:
                        match_ratio = ImageHasher.match_orb_features(current_orb, target_orb)
                        # Ngưỡng 0.15 (15%) là đủ để xác nhận ảnh bị xoay/cắt
                        if match_ratio > 0.15:
                            return True, entry, f"GEOMETRIC (Khớp đặc trưng hình học: {match_ratio*100:.1f}%)"
                        
        return False, None, "NONE"
