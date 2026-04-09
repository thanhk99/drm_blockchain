import logging
import time
import json
import os
import hashlib

logger = logging.getLogger("BlockchainManager")

class BlockchainManager:
    def __init__(self, config):
        """
        Khởi tạo Blockchain Manager. 
        Trong bản demo này, chúng ta sẽ mô phỏng một sổ cái (ledger) bằng file JSON cục bộ.
        """
        self.config = config
        self.ledger_path = "models/blockchain_ledger.json"
        self.wallet_path = "models/wallets.json"
        self._load_ledger()
        self._load_wallets()

    def _load_ledger(self):
        if os.path.exists(self.ledger_path):
            with open(self.ledger_path, "r", encoding="utf-8") as f:
                self.ledger = json.load(f)
            # Kiểm tra xem ledger có hợp lệ không, nếu có dữ liệu cũ không tương thích thì reset
            if self.ledger and ("hash" not in self.ledger[0] and self.ledger[0].get("index") != 0):
                logger.warning("Phát hiện dữ liệu blockchain cũ không tương thích. Đang khởi tạo lại...")
                self.ledger = []
                self._create_genesis_block()
        else:
            self.ledger = []
            self._create_genesis_block()

    def _create_genesis_block(self):
        """Khởi tạo khối đầu tiên của chuỗi."""
        genesis_block = {
            "index": 0,
            "timestamp": 1712644800.0, # Một mốc thời gian cố định cho Genesis
            "hashes": ["0"],
            "p_hash": "0",
            "w_hash": "0",
            "orb_features": None,
            "owner": "SYSTEM",
            "previous_hash": "0",
            "nonce": 0
        }
        genesis_block["hash"] = self.calculate_hash(genesis_block)
        self.ledger.append(genesis_block)
        self._save_ledger()
        logger.info("Đã khởi tạo Genesis Block.")

    def calculate_hash(self, block):
        """Tính toán mã băm SHA-256 cho một khối."""
        # Tạo một bản sao để không ảnh hưởng đến khối gốc và loại bỏ trường hash nếu có
        block_copy = {k: v for k, v in block.items() if k != "hash"}
        # Đảm bảo thứ tự các key là cố định để hash luôn giống nhau
        block_string = json.dumps(block_copy, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def proof_of_work(self, block, difficulty=2):
        """Cơ chế Proof of Work đơn giản: tìm nonce để hash có số lượng số 0 đầu tiên nhất định."""
        target = "0" * difficulty
        while True:
            hash_attempt = self.calculate_hash(block)
            if hash_attempt[:difficulty] == target:
                block["hash"] = hash_attempt
                return block
            block["nonce"] += 1

    def _save_ledger(self):
        # Đảm bảo thư mục tồn tại
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)
        with open(self.ledger_path, "w", encoding="utf-8") as f:
            json.dump(self.ledger, f, indent=4)

    def _load_wallets(self):
        """Tải dữ liệu ví từ file JSON."""
        if os.path.exists(self.wallet_path):
            with open(self.wallet_path, "r", encoding="utf-8") as f:
                self.wallets = json.load(f)
        else:
            self.wallets = {}
            self._save_wallets()

    def _save_wallets(self):
        """Lưu dữ liệu ví vào file JSON."""
        os.makedirs(os.path.dirname(self.wallet_path), exist_ok=True)
        with open(self.wallet_path, "w", encoding="utf-8") as f:
            json.dump(self.wallets, f, indent=4)

    def get_balance(self, username):
        """Lấy số dư của một người dùng."""
        return self.wallets.get(username, 0)

    def grant_reward(self, username, amount=10):
        """Tặng thưởng coin cho người dùng."""
        if username == "Unknown" or username == "Guest":
            return False
            
        current_balance = self.wallets.get(username, 0)
        self.wallets[username] = current_balance + amount
        self._save_wallets()
        logger.info(f"Đã tặng {amount} Coins cho {username}. Số dư mới: {self.wallets[username]}")
        return True

    def register_copyright(self, hash_list, p_hash, w_hash, orb_features, owner_name):
        """
        Ghi nhận bản quyền với Dual-Hash, pHash, wHash và ORB Features.
        """
        if isinstance(hash_list, str):
            hash_list = [hash_list]

        # Kiểm tra trùng lặp
        for entry in self.ledger:
            existing_hashes = entry.get("hashes", [])
            for h in hash_list:
                if h in existing_hashes:
                    return False, f"Ảnh này đã được đăng ký bởi {entry['owner']}"

        # Lấy hash của khối cuối cùng
        last_block = self.ledger[-1]
        
        new_block = {
            "index": len(self.ledger),
            "timestamp": time.time(),
            "hashes": hash_list,
            "p_hash": p_hash,
            "w_hash": w_hash,
            "orb_features": orb_features,
            "owner": owner_name,
            "previous_hash": last_block["hash"],
            "nonce": 0
        }
        
        # Thực hiện Proof of Work
        logger.info(f"Đang đào khối mới cho {owner_name}...")
        new_block = self.proof_of_work(new_block)
        
        self.ledger.append(new_block)
        self._save_ledger()
        
        # Tặng thưởng sau khi đào khối thành công
        reward_given = self.grant_reward(owner_name)
        reward_msg = f" (Nhận thêm 10 Coins thưởng!)" if reward_given else ""
        
        logger.info(f"Đã ghi nhận bản quyền trên blockchain với mã băm: {new_block['hash'][:10]}...")
        return True, f"Lưu thành công!{reward_msg} Mã băm khối: {new_block['hash'][:10]}..."

    def is_chain_valid(self):
        """Kiểm tra tính toàn vẹn của toàn bộ chuỗi blockchain."""
        for i in range(1, len(self.ledger)):
            current_block = self.ledger[i]
            previous_block = self.ledger[i-1]

            # 1. Kiểm tra mã băm hiện tại của khối
            if current_block["hash"] != self.calculate_hash(current_block):
                logger.error(f"Lỗi: Khối {i} bị thay đổi nội dung!")
                return False

            # 2. Kiểm tra liên kết với khối trước
            if current_block["previous_hash"] != previous_block["hash"]:
                logger.error(f"Lỗi: Khối {i} không liên kết đúng với khối {i-1}!")
                return False
                
            # 3. Kiểm tra Proof of Work (độ khó 2)
            if current_block["hash"][:2] != "00":
                logger.error(f"Lỗi: Khối {i} không thỏa mãn Proof of Work!")
                return False

        return True

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
