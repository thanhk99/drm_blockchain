import os
import sys
import io
import json
import logging
import cv2
import time
import shutil
import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


# Tắt log DEBUG để dễ nhìn
logging.getLogger("BlockchainManager").setLevel(logging.INFO)

from core.config_loader import load_config
from engines.blockchain.blockchain_manager import BlockchainManager
from engines.blockchain.image_hasher import ImageHasher

def print_separator(title):
    print(f"\n{'='*70}")
    print(f"[{title}]")
    print(f"{'='*70}\n")

def attack_1_ledger_tampering(config):
    print_separator("KỊCH BẢN 1: TẤN CÔNG CHỈNH SỬA SỔ CÁI (LEDGER TAMPERING)")
    print("Mục tiêu: Đổi tên chủ sở hữu của một bản quyền trực tiếp trong file ledger.json")
    
    # Tạo node Alice và đăng ký một khối giả để có dữ liệu
    alice_bm = BlockchainManager(config, node_name="Alice")
    
    # Thêm một khối hợp lệ vào sổ cái của Alice
    if len(alice_bm.ledger) == 1: # Chỉ có Genesis
        print("[*] Tạo một khối hợp lệ cho Alice trước khi tấn công...")
        success, msg = alice_bm.register_copyright(["hash_test_1"], "phash_1", "whash_1", None, "Alice")
        print(f"[*] Đăng ký khối hợp lệ: {msg}")
    
    # Bắt đầu tấn công
    ledger_path = alice_bm.ledger_path
    
    # Đọc ledger hiện tại
    with open(ledger_path, "r", encoding="utf-8") as f:
        tampered_ledger = json.load(f)
        
    if len(tampered_ledger) > 1:
        original_owner = tampered_ledger[1]["owner"]
        print(f"[!] Đang đổi owner từ '{original_owner}' thành 'Hacker' trong khối 1...")
        tampered_ledger[1]["owner"] = "Hacker"
        
        # Lưu file đã bị sửa
        with open(ledger_path, "w", encoding="utf-8") as f:
            json.dump(tampered_ledger, f, indent=4)
            
        print("[!] Sổ cái đã bị thay đổi (không có khóa ký).")
        
        print("\n[*] Đang tải lại sổ cái từ disk và chạy kiểm tra tính toàn vẹn (is_chain_valid)...")
        alice_bm._load_ledger() # Tải lại từ file bị sửa
        is_valid = alice_bm.is_chain_valid()
            
        if not is_valid:
            print("\n>>> KẾT QUẢ: THẤT BẠI. Hệ thống ĐÃ PHÁT HIỆN dữ liệu bị can thiệp!")
        else:
            print("\n>>> KẾT QUẢ: THÀNH CÔNG. Hệ thống KHÔNG PHÁT HIỆN được can thiệp!")
            
        # Khôi phục lại dữ liệu gốc cho Alice
        tampered_ledger[1]["owner"] = original_owner
        with open(ledger_path, "w", encoding="utf-8") as f:
            json.dump(tampered_ledger, f, indent=4)
        print("[*] Đã khôi phục sổ cái của Alice.")

def attack_2_double_registration(config):
    print_separator("KỊCH BẢN 2: ĐĂNG KÝ TRÙNG LẶP (DOUBLE REGISTRATION)")
    print("Mục tiêu: Hacker lấy một ảnh đã được bảo vệ và cố gắng đăng ký dưới tên mình.")
    
    hasher = ImageHasher()
    # Đường dẫn ảnh test
    test_img_path = "protected_images/DRM_a.jpg"
    if not os.path.exists(test_img_path):
        print(f"[!] Không tìm thấy ảnh test {test_img_path}. Bỏ qua kịch bản này.")
        return
        
    img_data = cv2.imread(test_img_path)
    
    print("[*] Khởi tạo Node: Alice (Nạn nhân) và Hacker (Kẻ tấn công)")
    alice_bm = BlockchainManager(config, node_name="Alice")
    hacker_bm = BlockchainManager(config, node_name="Hacker")
    
    # Alice đăng ký ảnh này trước
    print("\n[*] Alice đang đăng ký ảnh lên Blockchain...")
    h_orig = hasher.get_content_hash(img_data)
    p_h = hasher.get_perceptual_hash(img_data)
    w_h = hasher.get_wavelet_hash(img_data)
    orb = hasher.get_orb_features(img_data)
    
    success, msg = alice_bm.register_copyright([h_orig], p_h, w_h, orb, "Alice")
    if success:
        print("[+] Alice đăng ký thành công.")
    else:
        print(f"[-] Alice đăng ký thất bại (có thể đã đăng ký trước đó): {msg}")
        
    # Đồng bộ toàn bộ khối của Alice sang Hacker để đảm bảo cùng chung một chain
    print("[*] Đồng bộ Blockchain từ Alice sang Hacker...")
    # Hacker khởi tạo lại với ledger gốc
    hacker_bm.ledger = [hacker_bm.ledger[0]] # Chỉ giữ lại Genesis
    for i in range(1, len(alice_bm.ledger)):
        hacker_bm.receive_block(alice_bm.ledger[i])
        
    # Hacker cố gắng đăng ký lại ảnh y hệt
    print("\n[!] Hacker đang cố gắng đăng ký cùng bức ảnh dưới tên 'Hacker'...")
    success_hack, msg_hack = hacker_bm.register_copyright([h_orig], p_h, w_h, orb, "Hacker")
    
    if not success_hack:
        print(f"\n>>> KẾT QUẢ: THẤT BẠI. Hệ thống CHẶN ĐỨT hacker với thông báo: '{msg_hack}'")
    else:
        print("\n>>> KẾT QUẢ: THÀNH CÔNG. Hacker đã đăng ký thành công tác phẩm của Alice!")


def attack_3_bypass_modification(config):
    print_separator("KỊCH BẢN 3: LÁCH LUẬT BẢN QUYỀN BẰNG CÁCH CHỈNH SỬA ẢNH")
    print("Mục tiêu: Hacker chỉnh sửa ảnh (xoay chiều) để thay đổi mã băm SHA256, hy vọng vượt qua bộ lọc.")
    
    hasher = ImageHasher()
    test_img_path = "protected_images/DRM_a.jpg"
    if not os.path.exists(test_img_path):
        print(f"[!] Không tìm thấy ảnh test {test_img_path}. Bỏ qua kịch bản này.")
        return
        
    original_img = cv2.imread(test_img_path)
    
    print("[*] Đang mô phỏng Hacker chỉnh sửa ảnh (Thu nhỏ ảnh 20% - Resize)...")
    hacked_img = cv2.resize(original_img, (0, 0), fx=0.8, fy=0.8)
    
    h_hack = hasher.get_content_hash(hacked_img)
    p_hack = hasher.get_perceptual_hash(hacked_img)
    w_hack = hasher.get_wavelet_hash(hacked_img)
    orb_hack = hasher.get_orb_features(hacked_img)
    
    print(f"   [+] SHA256 Ảnh gốc: {hasher.get_content_hash(original_img)[:15]}...")
    print(f"   [!] SHA256 Ảnh bị sửa: {h_hack[:15]}...")
    print("   -> Mã băm đã hoàn toàn khác nhau!")
    
    print("\n[*] Hacker đẩy ảnh bị sửa vào quá trình Xác thực (Verify) của mạng lưới...")
    
    hacker_bm = BlockchainManager(config, node_name="Hacker")
    
    # Bước này mô phỏng hàm verify_copyright
    found, record, match_type = hacker_bm.verify_copyright(h_hack, p_hack, w_hack, hacked_img)
    
    if not found:
        # Nếu chưa tìm thấy ở node hacker, quét toàn mạng (giống main.py)
        all_nodes = BlockchainManager.list_all_nodes()
        for node_name in all_nodes:
            if node_name == "Hacker": continue
            temp_bm = BlockchainManager(config, node_name=node_name)
            found, record, match_type = temp_bm.verify_copyright(h_hack, p_hack, w_hack, hacked_img)
            if found:
                break
    
    if found:
        print(f"\n>>> KẾT QUẢ: THẤT BẠI. Hệ thống PHÁT HIỆN ĐẠO NHÁI!")
        print(f"    - Ảnh gốc thuộc về: {record['owner']}")
        print(f"    - Phương pháp phát hiện: {match_type}")
    else:
        print("\n>>> KẾT QUẢ: THÀNH CÔNG. Hacker đã vượt qua hệ thống bằng cách chỉnh sửa ảnh!")


if __name__ == "__main__":
    config = load_config("config.yaml")
    
    # Dọn dẹp môi trường test cũ (chỉ xóa Alice và Hacker)
    for node in ["Alice", "Hacker"]:
        if os.path.exists(f"nodes/{node}"):
            shutil.rmtree(f"nodes/{node}")
            
    print(" BẮT ĐẦU CHẠY CÁC KỊCH BẢN TẤN CÔNG ".center(70, "="))
    
    attack_1_ledger_tampering(config)
    attack_2_double_registration(config)
    attack_3_bypass_modification(config)
    
    print("\n" + "="*70)
    print(" HOÀN TẤT ".center(70, "="))
