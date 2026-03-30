# ⚙️ Tài Liệu Công Nghệ — Hệ Thống Bảo Vệ Bản Quyền Số

## Stack Tổng Quan

```
┌─────────────────────────────────────────────────────────┐
│  UI Layer          │  Tkinter (Python GUI)               │
├────────────────────┼────────────────────────────────────┤
│  Vision Engine     │  DeepFace (ArcFace) + OpenCV        │
├────────────────────┼────────────────────────────────────┤
│  DRM Engine        │  OpenCV Watermark + Steganography   │
├────────────────────┼────────────────────────────────────┤
│  Hashing Engine    │  SHA-256, wHash, DHash, ORB         │
├────────────────────┼────────────────────────────────────┤
│  Blockchain Layer  │  JSON Ledger (Local Simulation)     │
└─────────────────────────────────────────────────────────┘
```

---

## Chi Tiết Từng Công Nghệ

### 1. DeepFace + ArcFace — Nhận Diện Khuôn Mặt

| Thuộc tính | Giá trị |
|---|---|
| Thư viện | `deepface >= 0.0.92` |
| Model | **ArcFace** |
| Detector | `opencv` |
| Distance metric | Cosine similarity |
| Threshold | `0.35` (< 0.35 → nhận diện được) |
| Anti-Spoofing | Bật khi đăng ký (`extract_faces`) |

**ArcFace** (Additive Angular Margin Loss) là model nhận diện khuôn mặt state-of-the-art. Thay vì so sánh pixel, nó chiếu khuôn mặt vào không gian embedding 512 chiều, sau đó tính **cosine distance** giữa 2 vector — giá trị càng nhỏ càng giống nhau.

```
Ảnh mặt → [ArcFace Model] → Vector 512 chiều
                                    ↓
                          Cosine Distance vs DB
                                    ↓
                          < 0.35 → Nhận diện thành công
```

**Anti-Spoofing**: Khi đăng ký, DeepFace chạy model phân loại `is_real` để phát hiện ảnh in hoặc màn hình.

---

### 2. OpenCV — Xử Lý Ảnh

| Thư viện | `opencv-python >= 4.8.0` |
|---|---|
| Dùng cho | Đọc/ghi ảnh, resize, encode JPEG, ORB features |
| Hỗ trợ Unicode | `cv2.imdecode(np.fromfile(...))` |
| Camera backend | `CAP_DSHOW` → `CAP_MSMF` → default (thử tuần tự) |

OpenCV được dùng xuyên suốt: đọc frame camera, encode/decode ảnh, tính DHash, trích xuất ORB descriptor, và gắn watermark text.

---

### 3. Bộ Ba Mã Băm (Hashing Engine)

#### SHA-256 — Khớp Tuyệt Đối
```python
hashlib.sha256(image.tobytes()).hexdigest()
```
So khớp byte chính xác 100%. Chỉ khớp khi ảnh hoàn toàn không thay đổi.

#### Wavelet Hash (wHash) — Kháng Scale & Nén JPEG
```python
imagehash.whash(pil_image)  # → 64-bit hash
```
Sử dụng **biến đổi Wavelet** để phân tích tần số ảnh thay vì pixel trực tiếp. Ổn định hơn khi ảnh bị scale hoặc nén JPEG nhiều lần. Hamming distance ≤ 12/64 → khớp.

#### DHash 256-bit — Kháng Chỉnh Sáng/Tương Phản
```python
# Resize 17×16 → so sánh pixel cạnh nhau theo chiều ngang
diff = resized[:, :-1] > resized[:, 1:]  # → 256 bit
```
Mã băm cảm quan dựa trên **gradient ngang** của ảnh. Bền vững khi ảnh bị điều chỉnh màu sắc nhẹ. Hamming distance ≤ 32/256 → khớp.

#### ORB Features — Kháng Xoay & Thu Phóng
```python
orb = cv2.ORB_create(nfeatures=500)
keypoints, descriptors = orb.detectAndCompute(image, None)
```
**ORB** (Oriented FAST + Rotated BRIEF) trích xuất 500 điểm đặc trưng hình học. Sử dụng **Brute-Force Hamming Matcher** để so khớp giữa 2 tập descriptor. Match ratio ≥ 15% → khớp.

---

### 4. SSIM — Chỉ Số Độ Tương Đồng Cấu Trúc

```python
from skimage.metrics import structural_similarity as ssim
score, _ = ssim(gray1, gray2, full=True)
```

**SSIM** (Structural Similarity Index) đo độ tương đồng dựa trên luminance, contrast, và structure. Được thêm vào `ImageHasher` để dùng khi cần so sánh chi tiết 2 ảnh cụ thể (không dùng trong verify pipeline hiện tại, nhưng sẵn sàng mở rộng).

---

### 5. Blockchain Ledger (JSON Local)

```json
{
  "index": 1,
  "timestamp": 1711432000.0,
  "hashes": ["hash_goc", "hash_protected"],
  "p_hash": "...",
  "w_hash": "...",
  "orb_features": [[...]],
  "owner": "ten_nguoi_dung",
  "previous_hash": "hash_block_truoc"
}
```

**Không dùng blockchain thật** (Ethereum/Ganache) trong bản hiện tại — thay bằng **JSON ledger file** lưu cục bộ tại `models/blockchain_ledger.json`. Mỗi block mới lưu `previous_hash` của block trước (mô phỏng chuỗi hash), tạo tính liên kết nhưng chưa phân tán.

> **Có thể nâng cấp** kết nối thật lên Hardhat/Ganache qua Web3.py (config đã có `provider` và `contract_address`).

---

### 6. DRM Watermark & Steganography

```python
# Watermark nhìn thấy được
cv2.putText(image, "DRM_PROTECTED", position, ...)

# Pixel marker ẩn (steganography đơn giản)
image[0, 0] = [255, 0, 0]  # Pixel đỏ góc trên trái
```

Hiện tại dùng **steganography đơn giản** (thay đổi 1 pixel). Đủ dùng cho demo; trong thực tế nên dùng LSB steganography hoặc invisible watermark CNN.

---

### 7. Tkinter — Giao Diện Desktop

Giao diện người dùng xây dựng bằng **Tkinter** (built-in Python):
- `CameraDialog`: Cửa sổ xem live camera, chụp frame
- `DRMAppGUI`: Cửa sổ chính với log area và các nút chức năng
- Tất cả tác vụ nặng chạy trong `threading.Thread(daemon=True)` để không đóng băng UI

---

## Thư Viện & Phiên Bản

| Thư viện | Phiên bản | Mục đích |
|---|---|---|
| `deepface` | ≥ 0.0.92 | ArcFace nhận diện khuôn mặt |
| `tf-keras` | ≥ 2.15.0 | Backend cho DeepFace models |
| `opencv-python` | ≥ 4.8.0 | Xử lý ảnh, camera, ORB |
| `mediapipe` | ≥ 0.10.0 | (Dependency của DeepFace) |
| `numpy` | ≥ 1.26.0 | Xử lý ma trận ảnh |
| `Pillow` | ≥ 10.0.0 | Đọc ảnh cho imagehash |
| `imagehash` | ≥ 4.3.1 | Wavelet Hash (wHash) |
| `scikit-image` | ≥ 0.21.0 | SSIM score |
| `scipy` | ≥ 1.11.0 | Dependency của scikit-image |
| `pyyaml` | ≥ 6.0 | Đọc file config.yaml |

---

## Cấu Trúc Module

```
DRM_Blockchain/
├── main.py                          # UI + điều phối luồng
├── config.yaml                      # Cấu hình toàn hệ thống
├── core/
│   └── config_loader.py             # Đọc YAML config
├── engines/
│   ├── vision/
│   │   ├── face_manager.py          # ArcFace nhận diện/đăng ký mặt
│   │   └── security_engine.py       # Wrapper xác thực
│   ├── blockchain/
│   │   ├── blockchain_manager.py    # Ghi/đọc ledger + verify đa tầng
│   │   └── image_hasher.py          # SHA256, wHash, DHash, ORB, SSIM
│   └── drm/
│       └── drm_manager.py           # Watermark + Steganography
├── models/
│   ├── vision/faces/                # DB khuôn mặt
│   └── blockchain_ledger.json       # Sổ cái bản quyền
└── protected_images/                # Ảnh đầu ra đã bảo vệ
```
