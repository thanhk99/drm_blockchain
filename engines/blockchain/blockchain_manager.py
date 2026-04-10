import logging
import time
import json
import os
import hashlib
import hmac
import secrets
import base64
from cryptography.fernet import Fernet

logger = logging.getLogger("BlockchainManager")

class BlockchainManager:
    def __init__(self, config):
        """
        Khởi tạo Blockchain Manager.
        Sổ cái được mô phỏng bằng JSON cục bộ + bảo vệ bằng HMAC.
        """
        self.config = config
        self.ledger_path = "models/blockchain_ledger.json"
        self.wallet_path = "models/wallets.json"
        self.secret_path = "models/.ledger_secret"
        self.sig_path = "models/ledger.sig"
        # Đọc difficulty từ config, mặc định 4
        self.difficulty = self.config.get("blockchain", {}).get("pow_difficulty", 4)
        self._secret_key = self._get_or_create_secret_key()
        self._cipher = Fernet(base64.urlsafe_b64encode(self._secret_key[:32]))
        self._load_ledger()
        self._load_wallets()

    def _get_or_create_secret_key(self) -> bytes:
        """Đọc từ biến môi trường hoặc file, hoặc tạo mới secret key."""
        # Ưu tiên biến môi trường (Bảo mật cao nhất)
        env_key = os.getenv("DRM_LEDGER_SECRET")
        if env_key:
            try:
                return bytes.fromhex(env_key)
            except ValueError:
                logger.warning("Bien moi truong DRM_LEDGER_SECRET khong hop le (phai la hex).")

        os.makedirs(os.path.dirname(self.secret_path), exist_ok=True)
        if os.path.exists(self.secret_path):
            with open(self.secret_path, "r") as f:
                return bytes.fromhex(f.read().strip())
        
        # Tạo key mới 32 bytes
        key = secrets.token_hex(32)
        with open(self.secret_path, "w") as f:
            f.write(key)
        logger.info("Da tao secret key moi cho HMAC/Encryption ledger.")
        return bytes.fromhex(key)

    def _encrypt_data(self, data) -> str:
        """Mã hóa dữ liệu sang chuỗi base64."""
        if data is None: return None
        json_data = json.dumps(data)
        return self._cipher.encrypt(json_data.encode()).decode()

    def _decrypt_data(self, encrypted_str: str):
        """Giải mã dữ liệu từ chuỗi base64."""
        if encrypted_str is None or not isinstance(encrypted_str, str): 
            return encrypted_str # Trả về luôn nếu không phải chuỗi mã hóa
        try:
            decrypted_data = self._cipher.decrypt(encrypted_str.encode()).decode()
            return json.loads(decrypted_data)
        except Exception as e:
            logger.error(f"Loi giai ma du lieu: {e}")
            return None

    def _sign_ledger(self, content: str) -> str:
        """Tính HMAC-SHA256 của nội dung ledger."""
        return hmac.new(self._secret_key, content.encode("utf-8"), hashlib.sha256).hexdigest()

    def _verify_ledger_signature(self, content: str) -> bool:
        """Kiểm tra chữ ký HMAC. Trả về False nếu file bị sửa."""
        if not os.path.exists(self.sig_path):
            logger.warning("Khong tim thay file chu ky HMAC. Ledger co the bi can thiep!")
            return False
        with open(self.sig_path, "r") as f:
            stored_sig = f.read().strip()
        expected_sig = self._sign_ledger(content)
        # So sánh constant-time để chống timing attack
        return hmac.compare_digest(stored_sig, expected_sig)

    def _load_ledger(self):
        if os.path.exists(self.ledger_path):
            with open(self.ledger_path, "r", encoding="utf-8") as f:
                raw_content = f.read()

            # Xác minh HMAC trước khi dùng
            if not self._verify_ledger_signature(raw_content):
                logger.error("CANH BAO BAO MAT: Ledger bi can thiep trai phep hoac chua co chu ky!")
                # Ghi lại genesis block an toàn
                self.ledger = []
                self._create_genesis_block()
                return

            self.ledger = json.loads(raw_content)
            # Kiểm tra tương thích dữ liệu cũ
            if self.ledger and ("hash" not in self.ledger[0] and self.ledger[0].get("index") != 0):
                logger.warning("Du lieu blockchain cu khong tuong thich. Dang khoi tao lai...")
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

    def proof_of_work(self, block, difficulty=None):
        """Proof of Work: tìm nonce để hash bắt đầu bằng n số 0 (difficulty từ config)."""
        if difficulty is None:
            difficulty = self.difficulty
        target = "0" * difficulty
        while True:
            hash_attempt = self.calculate_hash(block)
            if hash_attempt[:difficulty] == target:
                block["hash"] = hash_attempt
                return block
            block["nonce"] += 1

    def _save_ledger(self):
        """Lưu ledger và cập nhật chữ ký HMAC."""
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)
        content = json.dumps(self.ledger, indent=4)
        with open(self.ledger_path, "w", encoding="utf-8") as f:
            f.write(content)
        # Ký file sau khi ghi
        sig = self._sign_ledger(content)
        with open(self.sig_path, "w") as f:
            f.write(sig)
        logger.debug("Da luu ledger va cap nhat chu ky HMAC.")

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
        # Kiểm tra tính toàn vẹn của chuỗi hiện tại trước khi ghi mới
        if not self._verify_ledger_signature(json.dumps(self.ledger, indent=4)):
            return False, "Hệ thống bị can thiệp! Không thể ghi dữ liệu mới."

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
            "orb_features": self._encrypt_data(orb_features), # Mã hóa dữ liệu nhạy cảm
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
        """Kiểm tra tính toàn vẹn của toàn bộ chain."""
        pow_prefix = "0" * self.difficulty
        for i in range(1, len(self.ledger)):
            current_block = self.ledger[i]
            previous_block = self.ledger[i-1]

            # 1. Hash nội dung khối phải khớp
            if current_block["hash"] != self.calculate_hash(current_block):
                logger.error(f"Loi: Khoi {i} bi thay doi noi dung!")
                return False

            # 2. Liên kết với khối trước phải đúng
            if current_block["previous_hash"] != previous_block["hash"]:
                logger.error(f"Loi: Khoi {i} khong lien ket dung voi khoi {i-1}!")
                return False

            # 3. Proof of Work phải thỏa mãn difficulty hiện tại
            if not current_block["hash"].startswith(pow_prefix):
                logger.error(f"Loi: Khoi {i} khong thoa man Proof of Work (difficulty={self.difficulty})!")
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
                    encrypted_orb = entry.get("orb_features")
                    target_orb = self._decrypt_data(encrypted_orb) # Giải mã để so sánh
                    if target_orb:
                        match_ratio = ImageHasher.match_orb_features(current_orb, target_orb)
                        # Ngưỡng 0.15 (15%) là đủ để xác nhận ảnh bị xoay/cắt
                        if match_ratio > 0.15:
                            return True, entry, f"GEOMETRIC (Khớp đặc trưng hình học: {match_ratio*100:.1f}%)"
                        
        return False, None, "NONE"
