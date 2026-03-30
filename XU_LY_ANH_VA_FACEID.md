# 🔬 Giải Thích Chi Tiết: Xử Lý Ảnh & Xác Minh Khuôn Mặt

## Mục Lục
1. [Tổng quan pipeline](#1-tổng-quan-pipeline)
2. [Xử lý ảnh — DRM Hashing](#2-xử-lý-ảnh--drm-hashing)
   - [SHA-256 (Exact Match)](#21-sha-256--exact-match)
   - [Wavelet Hash (wHash)](#22-wavelet-hash-whash)
   - [DHash 256-bit](#23-dhash-256-bit)
   - [ORB Feature Matching](#24-orb-feature-matching)
3. [Xác minh khuôn mặt — FaceID](#3-xác-minh-khuôn-mặt--faceid)
   - [ArcFace Embedding](#31-arcface-embedding)
   - [Anti-Spoofing](#32-anti-spoofing)
   - [Quy trình identify_face](#33-quy-trình-identify_face)

---

## 1. Tổng Quan Pipeline

```
  ┌──────────────────────────────────────────────────────────┐
  │             ĐĂNG KÝ BẢN QUYỀN                           │
  │                                                          │
  │  [Ảnh gốc]                                              │
  │      │                                                   │
  │      ├──→ SHA-256(pixel bytes)   ──→ hash_original      │
  │      ├──→ SHA-256(DRM version)   ──→ hash_protected      │
  │      ├──→ Wavelet Hash           ──→ w_hash             │
  │      ├──→ DHash 256-bit          ──→ p_hash             │
  │      └──→ ORB Descriptors        ──→ orb_features       │
  │                     │                                    │
  │              [Blockchain Ledger]                         │
  └──────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────┐
  │             XÁC THỰC BẢN QUYỀN                          │
  │                                                          │
  │  [Ảnh cần kiểm tra]                                     │
  │      │                                                   │
  │      ├── Tầng 1: SHA-256     → So khớp EXACT?          │
  │      ├── Tầng 2: wHash       → Hamming ≤ 12?           │
  │      ├── Tầng 2b: DHash      → Hamming ≤ 32?           │
  │      └── Tầng 3: ORB         → Match ratio ≥ 15%?       │
  └──────────────────────────────────────────────────────────┘
```

---

## 2. Xử Lý Ảnh — DRM Hashing

### 2.1 SHA-256 — Exact Match

**Nguyên lý:** Hash toàn bộ dữ liệu pixel của ảnh. Chỉ 1 pixel thay đổi sẽ tạo ra hash hoàn toàn khác.

```python
# File: engines/blockchain/image_hasher.py

@staticmethod
def get_content_hash(image: np.ndarray) -> str:
    """
    Tính hash dựa trên nội dung điểm ảnh (pixel data).
    image.tobytes() chuyển toàn bộ ma trận numpy thành chuỗi byte thô.
    """
    return hashlib.sha256(image.tobytes()).hexdigest()
```

**Ví dụ thực tế:**
```
Ảnh gốc:   → SHA256 = "a3f2c1d4..."
Ảnh gốc:   → SHA256 = "a3f2c1d4..."  ✅ EXACT MATCH
Ảnh +1px:  → SHA256 = "9b7e3a12..."  ❌ KHÔNG KHỚP
```

**Giải thích:**
- Hệ thống tính **2 hash**: hash ảnh gốc và hash ảnh đã gắn watermark DRM
- Cả 2 đều được lưu vào ledger dưới dạng `"hashes": [hash_original, hash_protected]`
- Khi verify, chỉ cần 1 trong 2 khớp là xác nhận thành công ở tầng này

---

### 2.2 Wavelet Hash (wHash)

**Nguyên lý:** Áp dụng biến đổi Wavelet (phân tích tần số ảnh theo nhiều tỉ lệ), lấy thành phần tần số thấp để tạo hash 64-bit. Bền vững hơn DHash khi ảnh bị scale hoặc nén JPEG nhiều lần.

```python
# File: engines/blockchain/image_hasher.py

@staticmethod
def get_wavelet_hash(image: np.ndarray) -> str:
    """
    Wavelet Hash (wHash) - kháng scale & JPEG compress.
    """
    import imagehash
    from PIL import Image

    # Bước 1: Chuyển OpenCV BGR → PIL RGB (imagehash dùng PIL)
    img_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

    # Bước 2: imagehash.whash tự động:
    #   - Resize ảnh về 8×8
    #   - Chạy biến đổi Discrete Wavelet Transform (DWT)
    #   - Lấy 64 bit low-frequency coefficients
    #   - So sánh với mean → tạo chuỗi bit 0/1
    return str(imagehash.whash(img_pil))  # Ví dụ: "0f3a7c2b9e1d4a8f"
```

**So sánh với DHash:**
| | DHash | wHash |
|---|---|---|
| Kháng thay đổi màu nhẹ | ✅ | ✅ |
| Kháng scale/resize | ❌ | ✅ |
| Kháng JPEG nén nhiều lần | ❌ | ✅ |
| Kháng xoay | ❌ | ❌ |
| Bit length | 256 bit | 64 bit |
| Ngưỡng Hamming | ≤ 32 | ≤ 12 |

**Cách so khớp trong blockchain_manager.py:**
```python
import imagehash

h1 = imagehash.hex_to_hash(current_w_hash)   # hash của ảnh cần kiểm tra
h2 = imagehash.hex_to_hash(entry["w_hash"])   # hash trong ledger

# Khoảng cách Hamming: đếm số bit khác nhau giữa 2 hash 64-bit
distance = h1 - h2   # toán tử "-" trong imagehash = Hamming distance

if distance <= 12:   # 12/64 bit khác → ~81% giống nhau
    similarity = ((64 - distance) / 64) * 100
    return True, entry, f"WAVELET ({similarity:.1f}%)"
```

---

### 2.3 DHash 256-bit

**Nguyên lý:** Thay vì nhìn giá trị tuyệt đối của pixel, DHash nhìn vào **sự khác biệt giữa các pixel liền kề** theo chiều ngang — tạo ra "fingerprint cấu trúc" bền vững với thay đổi độ sáng tổng thể.

```python
# File: engines/blockchain/image_hasher.py

@staticmethod
def get_perceptual_hash(image: np.ndarray) -> str:
    """
    DHash 256-bit — kháng thay đổi sáng/tương phản nhẹ.
    """
    # Bước 1: Chuyển sang ảnh xám (loại bỏ màu sắc, chỉ giữ độ sáng)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Bước 2: Resize về 17×16
    #   → 17 cột để so sánh 16 cặp pixel cạnh nhau (17-1=16)
    #   → 16 hàng
    #   → Tổng: 16×16 = 256 phép so sánh → 256 bit
    resized = cv2.resize(gray, (17, 16), interpolation=cv2.INTER_AREA)

    # Bước 3: So sánh pixel trái vs pixel phải trên cùng hàng
    #   resized[:, :-1] = tất cả cột trừ cột cuối (cột "trái")
    #   resized[:, 1:]  = tất cả cột trừ cột đầu  (cột "phải")
    #   Kết quả: ma trận 16×16 boolean (True/False)
    diff = resized[:, :-1] > resized[:, 1:]

    # Bước 4: Chuyển ma trận boolean → chuỗi bit → hex 64 ký tự
    hash_binary = "".join(['1' if x else '0' for x in diff.flatten()])
    hash_int = int(hash_binary, 2)
    hash_hex = hex(hash_int)[2:].zfill(64)   # 256 bit = 64 hex chars
    return hash_hex
```

**Minh hoạ trực quan DHash:**
```
Ảnh xám resize 17×16:

Hàng 0: [120, 115, 130, 125, ...]
          ↓    ↓    ↓    ↓
So sánh: 120>115? 115>130? 130>125? ...
          True     False    True   ...
          → bit:    1        0       1  ...

→ 256 bit → "a3f2..." (64 hex ký tự)
```

**So khớp bằng Hamming Distance:**
```python
@staticmethod
def hamming_distance(hash1: str, hash2: str) -> int:
    """Đếm số bit khác nhau giữa 2 hash hex 256-bit."""
    h1 = int(hash1, 16)
    h2 = int(hash2, 16)
    # XOR: bit giống nhau → 0, bit khác → 1
    # count('1') đếm số bit khác nhau
    return bin(h1 ^ h2).count('1')

# Ngưỡng: distance ≤ 32 (≤ 12.5% bit khác nhau) → khớp
```

---

### 2.4 ORB Feature Matching

**Nguyên lý:** Thay vì so sánh toàn bộ ảnh, ORB tìm các **điểm đặc trưng nổi bật** (góc cạnh, vết nứt, đường viền) và mô tả chúng bằng vector nhị phân. Bền vững với xoay, thu phóng, và thay đổi góc nhìn.

```python
# File: engines/blockchain/image_hasher.py

@staticmethod
def get_orb_features(image: np.ndarray):
    """
    ORB = Oriented FAST + Rotated BRIEF
    Trích xuất 500 điểm đặc trưng từ ảnh.
    """
    orb = cv2.ORB_create(nfeatures=500)

    # detectAndCompute trả về:
    # keypoints: list toạ độ (x, y) của 500 điểm đặc trưng
    # descriptors: ma trận 500×32 (mỗi điểm mô tả bằng 32 byte = 256 bit)
    keypoints, descriptors = orb.detectAndCompute(image, None)

    if descriptors is not None:
        return descriptors.tolist()  # Lưu vào JSON ledger
    return None


@staticmethod
def match_orb_features(desc1_list, desc2_list):
    """So khớp 2 tập descriptor, trả về tỉ lệ khớp 0.0-1.0."""
    desc1 = np.array(desc1_list, dtype=np.uint8)  # (N×32)
    desc2 = np.array(desc2_list, dtype=np.uint8)  # (M×32)

    # BFMatcher với Hamming distance (phù hợp cho ORB binary descriptor)
    # crossCheck=True: chỉ giữ match 2 chiều (A→B và B→A đều khớp)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(desc1, desc2)

    # Sắp xếp theo khoảng cách Hamming (nhỏ = tốt hơn)
    matches = sorted(matches, key=lambda x: x.distance)

    # Lấy các match "tốt" (khoảng cách Hamming < 50/256)
    good_matches = [m for m in matches if m.distance < 50]

    # Tỉ lệ: số match tốt / tổng số descriptor lớn hơn
    match_ratio = len(good_matches) / max(len(desc1), len(desc2))
    return match_ratio   # ≥ 0.15 → khớp hình học
```

**Minh hoạ ORB hoạt động:**
```
Ảnh gốc (0°):          Ảnh xoay 30°:
  ●                         ●
    ●   ●                     ●  ●
  ●       ●                 ●      ●

ORB tìm điểm đặc trưng ở cả 2 ảnh
→ Mô tả chúng bằng vector nhị phân bền vững với xoay
→ BFMatcher ghép cặp điểm giống nhau
→ 80/500 cặp khớp tốt → ratio = 80/500 = 16% ≥ 15% → GEOMETRIC MATCH
```

---

## 3. Xác Minh Khuôn Mặt — FaceID

### 3.1 ArcFace Embedding

**Nguyên lý:** ArcFace không "nhận dạng" khuôn mặt theo kiểu phân loại thông thường. Thay vào đó, nó chiếu ảnh khuôn mặt vào **không gian vector 512 chiều** sao cho:
- Ảnh của **cùng một người** → 2 vector **gần nhau** (cosine distance nhỏ)
- Ảnh của **người khác nhau** → 2 vector **xa nhau** (cosine distance lớn)

```
[Ảnh khuôn mặt 224×224]
        │
        ▼
[ResNet-50 Backbone]       ← Trích xuất đặc trưng sâu
        │
        ▼
[ArcFace Loss Layer]       ← Huấn luyện với Angular Margin
        │
        ▼
[Embedding Vector 512D]    ← "Dấu vân tay" khuôn mặt

Cosine Distance(v1, v2) = 1 - (v1·v2)/(|v1||v2|)
             ↓
       < 0.35 → CÙNG NGƯỜI
       ≥ 0.35 → NGƯỜI KHÁC
```

**Tại sao ArcFace tốt hơn các model khác?**

ArcFace sử dụng **Additive Angular Margin (arccos + margin)** khi training, ép buộc các embedding của cùng người phải rất gần nhau trong không gian hình cầu. Điều này làm tăng độ phân tách giữa các danh tính.

```python
# File: engines/vision/face_manager.py

class FaceManager:
    def __init__(self):
        self.model_name = "ArcFace"       # Model nhận diện
        self.detector_backend = "opencv"   # Bộ phát hiện vị trí mặt
        self.threshold = 0.35              # Ngưỡng cosine distance
        self.anti_spoofing = True          # Bật chống giả mạo khi đăng ký
```

---

### 3.2 Anti-Spoofing

**Nguyên lý:** Khi đăng ký khuôn mặt, hệ thống chạy thêm một model phân loại nhị phân `is_real` để phân biệt **mặt thật (3D)** vs **ảnh in/màn hình (2D)**. Dựa vào texture của da, phản chiếu ánh sáng, và depth information.

```python
# File: engines/vision/face_manager.py — hàm register_face()

# Trích xuất mặt và kiểm tra liveness (anti-spoofing)
objs = DeepFace.extract_faces(
    img_path=target_path,
    detector_backend=self.detector_backend,
    enforce_detection=True,
    anti_spoofing=self.anti_spoofing   # ← Bật model liveness
)

# Kiểm tra kết quả is_real
if self.anti_spoofing:
    all_real = all(obj.get("is_real", True) for obj in objs)
    if not all_real:
        os.remove(target_path)   # Xóa ảnh vừa lưu
        return False, "Phát hiện khuôn mặt giả mạo (Spoofing)!"
```

> **Lưu ý:** Anti-spoofing chỉ bật khi **đăng ký** (`register_face`). Khi **nhận diện** (`identify_face`) thì tắt vì DeepFace.find chưa hỗ trợ ổn định parameter này.

---

### 3.3 Quy Trình identify_face()

```python
# File: engines/vision/face_manager.py

def identify_face(self, frame):
    """Nhận diện khuôn mặt trong một frame."""
    try:
        # DeepFace.find sẽ:
        # 1. Phát hiện khuôn mặt trong frame (dùng opencv detector)
        # 2. Cắt & align khuôn mặt
        # 3. Chạy ArcFace → tạo embedding vector 512D
        # 4. So sánh cosine distance với TẤT CẢ ảnh trong db_path
        # 5. Trả về DataFrame chứa các cặp (identity, distance)
        results = DeepFace.find(
            img_path=frame,               # Frame từ camera (numpy array)
            db_path=self.faces_dir,       # Thư mục chứa DB khuôn mặt
            model_name=self.model_name,   # "ArcFace"
            detector_backend=self.detector_backend,  # "opencv"
            distance_metric='cosine',     # Dùng cosine distance
            enforce_detection=False,      # Không throw lỗi nếu mặt mờ
            silent=True                   # Tắt log spam của DeepFace
        )

        # results là list DataFrame, mỗi DataFrame cho 1 khuôn mặt detected
        if len(results) > 0 and not results[0].empty:
            best_match = results[0].iloc[0]   # Lấy hàng đầu (distance nhỏ nhất)

            # Tự tìm tên cột distance (thay đổi theo phiên bản DeepFace)
            # Có thể là "ArcFace_cosine" hoặc chỉ "distance"
            dist_col = None
            for col in results[0].columns:
                if 'cosine' in col.lower() or 'distance' in col.lower():
                    dist_col = col
                    break

            distance = best_match[dist_col]   # Ví dụ: 0.28

            if distance < self.threshold:     # 0.28 < 0.35 → NHẬN DIỆN ĐƯỢC
                # Lấy tên người từ tên thư mục cha của file ảnh khớp
                # Ví dụ path: models/vision/faces/Nguyen_Van_A/img.jpg
                #                                   ↑ basename của dirname
                best_match_path = best_match['identity']
                user_name = os.path.basename(os.path.dirname(best_match_path))
                return user_name    # "Nguyen_Van_A"
            else:
                # distance quá lớn → người lạ
                logger.warning(f"Người lạ - dist={distance:.4f} > {self.threshold}")

        return "Unknown"

    except Exception as e:
        logger.error(f"Lỗi nhận diện: {e}")
        return "Unknown"
```

**Luồng dữ liệu đầy đủ:**

```
Camera frame (numpy array BGR)
        │
        ▼
DeepFace.find()
    ├─ opencv detector → tìm bounding box khuôn mặt
    ├─ Crop & align khuôn mặt về 112×112
    ├─ ArcFace model → embedding vector 512D
    └─ So sánh với TẤT CẢ ảnh trong models/vision/faces/
            │
            ▼
    DataFrame kết quả:
    ┌─────────────────────────────────────────┐
    │ identity                    │ distance  │
    │─────────────────────────────│───────────│
    │ .../Nguyen_Van_A/img1.jpg   │   0.28    │← best match
    │ .../Tran_Thi_B/img1.jpg     │   0.67    │
    └─────────────────────────────────────────┘
            │
            ▼
    0.28 < 0.35 → return "Nguyen_Van_A" ✅
```

---

## Tóm Tắt Ngưỡng Quyết Định

| Thuật toán | Metric | Ngưỡng | Ý nghĩa |
|---|---|---|---|
| ArcFace | Cosine distance | `< 0.35` | Cùng người |
| wHash | Hamming / 64 bit | `≤ 12` | Ảnh tương đồng (≥ 81%) |
| DHash | Hamming / 256 bit | `≤ 32` | Ảnh tương đồng (≥ 87.5%) |
| ORB | Match ratio | `≥ 0.15` | Khớp hình học (≥ 15% điểm) |
| SHA-256 | Exact equality | `==` | Byte-perfect |
