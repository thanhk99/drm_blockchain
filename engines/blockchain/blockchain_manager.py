import logging
import time
import json
import os
import hashlib
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

logger = logging.getLogger("BlockchainManager")

class BlockchainManager:
    def __init__(self, config, node_name="Default"):
        """
        Khởi tạo Blockchain Manager cho một Node cụ thể.
        Mỗi node có thư mục riêng, sổ cái riêng và cặp khóa Ed25519 riêng.
        """
        self.config = config
        self.node_name = node_name
        self.base_dir = f"nodes/{node_name}"
        
        self.ledger_path = os.path.join(self.base_dir, "ledger.json")
        self.wallet_path = os.path.join(self.base_dir, "wallets.json")
        self.key_dir = os.path.join(self.base_dir, "keys")
        self.priv_key_path = os.path.join(self.key_dir, "private.pem")
        self.pub_key_path = os.path.join(self.key_dir, "public.pem")
        
        # Đọc difficulty từ config, mặc định 4
        self.difficulty = self.config.get("blockchain", {}).get("pow_difficulty", 4)
        
        # Đảm bảo thư mục tồn tại
        os.makedirs(self.key_dir, exist_ok=True)
        
        # Khởi tạo khóa và tải dữ liệu
        self._private_key, self._public_key = self._load_or_generate_keys()
        self._load_ledger()
        self._load_wallets()

    def _load_or_generate_keys(self):
        """Tải cặp khóa Ed25519 từ file hoặc tạo mới nếu chưa có."""
        if os.path.exists(self.priv_key_path) and os.path.exists(self.pub_key_path):
            with open(self.priv_key_path, "rb") as f:
                private_key = serialization.load_pem_private_key(f.read(), password=None)
            with open(self.pub_key_path, "rb") as f:
                public_key = serialization.load_pem_public_key(f.read())
            return private_key, public_key
        
        # Tạo khóa mới
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # Lưu Private Key
        with open(self.priv_key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
            
        # Lưu Public Key
        with open(self.pub_key_path, "wb") as f:
            f.write(public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ))
            
        logger.info(f"Da tao cap khoa Ed25519 moi cho node: {self.node_name}")
        return private_key, public_key

    def _encrypt_data(self, data) -> str:
        """Mã hóa dữ liệu đơn giản sang base64 (chỉ để giả lập, không phải bảo mật thực)."""
        if data is None: return None
        json_data = json.dumps(data)
        return base64.b64encode(json_data.encode()).decode()

    def _decrypt_data(self, encoded_str: str):
        """Giải mã dữ liệu từ base64."""
        if encoded_str is None or not isinstance(encoded_str, str): 
            return encoded_str
        try:
            return json.loads(base64.b64decode(encoded_str.encode()).decode())
        except Exception:
            return None

    def _get_peer_public_key(self, node_name: str):
        """Tải Public Key của một node khác từ thư mục của họ."""
        pub_path = f"nodes/{node_name}/keys/public.pem"
        if not os.path.exists(pub_path):
            return None
        try:
            with open(pub_path, "rb") as f:
                return serialization.load_pem_public_key(f.read())
        except Exception:
            return None

    def _sign_block(self, block_data: dict) -> str:
        """Ký một khối bằng Private Key của node."""
        # Gom các trường để ký (ngoại trừ chính trường signature)
        block_copy = {k: v for k, v in block_data.items() if k != "signature"}
        message = json.dumps(block_copy, sort_keys=True).encode()
        signature = self._private_key.sign(message)
        return base64.b64encode(signature).decode()

    def _verify_block_signature(self, block_data: dict) -> bool:
        """
        Xác thực chữ ký của một khối. 
        Tự động tìm Public Key dựa trên trường 'owner' của khối.
        """
        if "signature" not in block_data:
            return False
            
        owner = block_data.get("owner", "System")
        
        # Nếu là mình ký, dùng khóa của mình. Nếu là người khác, tìm khóa của họ.
        if owner == self.node_name or owner == "System":
            pub_key = self._public_key
        else:
            pub_key = self._get_peer_public_key(owner)
            
        if not pub_key:
            logger.warning(f"Khong tim thay Public Key cho owner: {owner}")
            return False

        block_copy = {k: v for k, v in block_data.items() if k != "signature"}
        message = json.dumps(block_copy, sort_keys=True).encode()
        try:
            signature = base64.b64decode(block_data["signature"])
            pub_key.verify(signature, message)
            return True
        except Exception:
            return False


    def _load_ledger(self):
        if os.path.exists(self.ledger_path):
            with open(self.ledger_path, "r", encoding="utf-8") as f:
                self.ledger = json.load(f)
            
            # Kiểm tra tính toàn vẹn của chuỗi (bao gồm chữ ký số) ngay khi tải
            if not self.is_chain_valid():
                logger.error(f"CANH BAO BAO MAT: Sổ cái của node {self.node_name} bị can thiệp trái phép!")
                # Trong thực tế sẽ cần cơ chế đồng bộ lại từ node khác
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
        # Ký SAU KHI tính hash (hoặc ít nhất là sau khi các trường cố định)
        genesis_block["signature"] = self._sign_block(genesis_block)
        self.ledger.append(genesis_block)
        self._save_ledger()
        logger.info(f"Đã khởi tạo Genesis Block cho node: {self.node_name}")

    def calculate_hash(self, block):
        """Tính toán mã băm SHA-256 cho một khối."""
        # Tạo một bản sao để không ảnh hưởng đến khối gốc và loại bỏ trường hash/signature nếu có
        block_copy = {k: v for k, v in block.items() if k not in ["hash", "signature"]}
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
        """Lưu ledger vào file JSON."""
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)
        with open(self.ledger_path, "w", encoding="utf-8") as f:
            json.dump(self.ledger, f, indent=4)
        logger.debug(f"Da luu ledger cho node {self.node_name}.")

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
        if not self.is_chain_valid():
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
        
        # Ký khối SAU KHI đào (để chốt nonce và hash)
        new_block["signature"] = self._sign_block(new_block)
        
        self.ledger.append(new_block)
        self._save_ledger()
        
        # --- BƯỚC MỚI: Phát sóng khối này đến mọi Node khác ---
        self.broadcast_block(new_block)
        
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

            # 3. Chữ ký số phải hợp lệ
            if not self._verify_block_signature(current_block):
                logger.error(f"Loi: Chu ky cua khoi {i} khong hop le!")
                return False
                
            # 4. Proof of Work phải thỏa mãn difficulty hiện tại
            if not current_block["hash"].startswith(pow_prefix):
                logger.error(f"Loi: Khoi {i} khong thoa man Proof of Work (difficulty={self.difficulty})!")
                return False

        return True

    def broadcast_block(self, block):
        """Phát sóng khối mới đến tất cả các node khác trong hệ thống."""
        all_nodes = self.list_all_nodes()
        peers = [node for node in all_nodes if node != self.node_name]
        
        for peer in peers:
            try:
                # Giả lập gửi qua mạng bằng cách khởi tạo Manager của peer và gọi nhận khối
                peer_bm = BlockchainManager(self.config, node_name=peer)
                peer_bm.receive_block(block)
            except Exception as e:
                logger.error(f"Loi khi broadcast den {peer}: {e}")

    def receive_block(self, block):
        """Nhận và kiểm tra khối từ node khác."""
        # 1. Kiểm tra xem khối đã tồn tại chưa
        for b in self.ledger:
            if b["hash"] == block["hash"]:
                return False # Đã có rồi
        
        # 2. Kiểm tra chỉ số Index (phải là kế tiếp)
        if block["index"] != len(self.ledger):
            logger.warning(f"Node {self.node_name} tu choi khoi {block['index']} do sai Index (can {len(self.ledger)})")
            return False

        # 3. Xác thực chữ ký (hàm verify_block_signature sẽ tự tìm Public Key của owner)
        if not self._verify_block_signature(block):
            logger.error(f"Node {self.node_name} phat hien chu ky gia mau tu owner: {block.get('owner')}")
            return False
            
        # 4. Kiểm tra liên kết Hash
        if block["previous_hash"] != self.ledger[-1]["hash"]:
            logger.error(f"Node {self.node_name} tu choi khoi {block['index']} do sai lien ket hash")
            return False

        # Nếu mọi thứ OK, thêm vào sổ cái
        self.ledger.append(block)
        self._save_ledger()
        logger.info(f"Node {self.node_name} da dong bo va chap nhan khoi moi tu {block.get('owner')}")
        return True

    @staticmethod
    def list_all_nodes():
        """Liệt kê danh sách tất cả các node hiện có."""
        nodes_dir = "nodes"
        if not os.path.exists(nodes_dir):
            return []
        return [d for d in os.listdir(nodes_dir) if os.path.isdir(os.path.join(nodes_dir, d))]

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
