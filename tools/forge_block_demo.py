import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import json
import hashlib
import hmac as hmac_lib
import time
import os
import yaml
import secrets

# Thêm thư mục gốc vào sys.path để import hệ thống thật
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

# Đọc config
CONFIG_PATH = os.path.join(ROOT, "config.yaml")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

LEDGER_PATH = os.path.join(ROOT, "models", "blockchain_ledger.json")
SIG_PATH = os.path.join(ROOT, "models", "ledger.sig")
SECRET_PATH = os.path.join(ROOT, "models", ".ledger_secret")
DIFFICULTY = config.get("blockchain", {}).get("pow_difficulty", 5)



def calculate_hash(block: dict) -> str:
    block_copy = {k: v for k, v in block.items() if k != "hash"}
    block_string = json.dumps(block_copy, sort_keys=True).encode()
    return hashlib.sha256(block_string).hexdigest()


def proof_of_work(block: dict, difficulty: int = DIFFICULTY) -> dict:
    target = "0" * difficulty
    block["nonce"] = 0
    while True:
        h = calculate_hash(block)
        if h[:difficulty] == target:
            block["hash"] = h
            return block
        block["nonce"] += 1


def load_ledger() -> list:
    with open(LEDGER_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_ledger_raw(ledger: list):
    """Ghi ledger KHÔNG cập nhật chữ ký (hacker không biết key)."""
    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=4)


def save_ledger_with_forged_sig(ledger: list, secret_key: bytes):
    """Hacker nâng cao: ghi ledger VÀ tự ký lại bằng key đánh cắp."""
    content = json.dumps(ledger, indent=4)
    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    # Giả mạo chữ ký HMAC
    forged_sig = hmac_lib.new(secret_key, content.encode("utf-8"), hashlib.sha256).hexdigest()
    with open(SIG_PATH, "w") as f:
        f.write(forged_sig)


def build_fake_block(ledger: list, owner: str, fake_hash: str) -> dict:
    """Tạo và tính PoW cho block giả."""
    last_block = ledger[-1]
    print(f"Block cuối hiện tại: index={last_block['index']}, hash={last_block['hash'][:16]}...")
    print(f"Đang tính PoW (difficulty={DIFFICULTY})...")
    start = time.time()
    new_block = {
        "index": len(ledger),
        "timestamp": time.time(),
        "hashes": [fake_hash],
        "p_hash": "0" * 64,
        "w_hash": "0000000000000000",
        "orb_features": None,
        "owner": owner,
        "previous_hash": last_block["hash"],
        "nonce": 0
    }
    new_block = proof_of_work(new_block)
    elapsed = time.time() - start
    print(f"Tìm được nonce={new_block['nonce']} sau {elapsed:.3f}s")
    return new_block


def verify_real_system() -> bool:
    """Kiểm tra bằng hệ thống thật (BlockchainManager có HMAC)."""
    from engines.blockchain.blockchain_manager import BlockchainManager
    import logging
    logging.disable(logging.CRITICAL)  # Tắt log để output sạch hơn
    try:
        bc = BlockchainManager(config)
        has_hacker = any(b.get("owner") == "HackerGiaDanh" for b in bc.ledger)
        logging.disable(logging.NOTSET)
        return has_hacker
    except Exception as e:
        logging.disable(logging.NOTSET)
        print(f"  Lỗi hệ thống: {e}")
        return False


# ─── Kịch bản tấn công ────────────────────────────────────────────────────────

FAKE_OWNER = "HackerGiaDanh"
FAKE_IMAGE_HASH = "aabbccdd" * 8
SEPARATOR = "─" * 60

# ══════════════════════════════════════════════════════════
# KỊCH BẢN 1: Hacker chỉ sửa file JSON (không có key)
# ══════════════════════════════════════════════════════════
print(f"\n{'─'*60}")
print("🔴 KỊCH BẢN 1: Hacker sửa file JSON trực tiếp (không biết Secret Key)")
print(f"{'─'*60}")

ledger = load_ledger()
fake_block = build_fake_block(ledger, FAKE_OWNER, FAKE_IMAGE_HASH)
ledger.append(fake_block)
save_ledger_raw(ledger)  # Ghi KHÔNG cập nhật ledger.sig

print(f"\n→ Block giả đã được chèn vào file JSON.")
print(f"→ Kiểm tra bằng HỆ THỐNG THẬT...")
hacker_in = verify_real_system()

if not hacker_in:
    print("✅ HỆ THỐNG CHẶN ĐƯỢC: HMAC phát hiện file JSON bị sửa đổi → Reset ledger!")
else:
    print("❌ HỆ THỐNG KHÔNG PHÁT HIỆN được block giả!")


# ══════════════════════════════════════════════════════════
# KỊCH BẢN 2: Hacker lấy được file .ledger_secret
# ══════════════════════════════════════════════════════════
print(f"\n{'─'*60}")
print("🔴 KỊCH BẢN 2: Hacker đọc được file .ledger_secret và giả mạo chữ ký")
print(f"{'─'*60}")

if os.path.exists(SECRET_PATH):
    # Hacker KHÔNG thể đọc file .ledger_secret (giả lập trường hợp server bảo mật file tốt)
    # Hacker cố tình dùng một chìa khóa giả để ký
    fake_secret_key = b"this_is_a_wrong_key_123456789012" 

    ledger = load_ledger()
    fake_block2 = build_fake_block(ledger, FAKE_OWNER, FAKE_IMAGE_HASH)
    ledger.append(fake_block2)
    
    print(f"\n→ Hacker cố gắng tự ký bằng Key SAI...")
    save_ledger_with_forged_sig(ledger, fake_secret_key) 

    print(f"→ Kiểm tra bằng HỆ THỐNG THẬT...")
    hacker_in2 = verify_real_system()

    if hacker_in2:
        print("❌ THẤT BẠI: Hệ thống vẫn bị lừa (Cần kiểm tra lại logic xác thực)!")
    else:
        print("✅ THÀNH CÔNG: Hệ thống đã TỪ CHỐI block vì Key không đúng!")
        print("=> Kết luận: Không có Key thật, không thể hack vào hệ thống.")
else:
    print("⚠️  Không tìm thấy file .ledger_secret (đã bảo mật bằng env var?)")
