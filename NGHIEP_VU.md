# 📋 Tài Liệu Nghiệp Vụ — Hệ Thống Bảo Vệ Bản Quyền Số

## Tổng Quan

Hệ thống **DRM Blockchain** là ứng dụng desktop giúp **đăng ký và xác thực bản quyền ảnh số**, kết hợp xác thực danh tính chủ sở hữu qua **nhận diện khuôn mặt (FaceID)**. Toàn bộ dữ liệu bản quyền được lưu vào một **sổ cái phi tập trung (blockchain ledger)** cục bộ.

---

## Các Chức Năng Chính

| STT | Chức năng | Mô tả ngắn |
|-----|-----------|------------|
| 0a | Đăng ký khuôn mặt qua Camera | Chụp mặt trực tiếp từ webcam |
| 0b | Đăng ký khuôn mặt từ File ảnh | Chọn ảnh đã chụp sẵn để đăng ký |
| 1 | Đăng ký bản quyền ảnh | FaceID → gắn watermark → ghi Blockchain |
| 2 | Xác thực bản quyền ảnh | Kiểm tra ảnh có trong Blockchain không |
| 3 | Quét khuôn mặt (FaceID) | Nhận diện nhanh người dùng hiện tại |

---

## Luồng Nghiệp Vụ Chi Tiết

### 0a. Đăng Ký Khuôn Mặt Qua Camera

```
Người dùng nhấn "0. Đăng ký từ Camera"
    → Nhập tên người dùng
    → Mở cửa sổ Live Camera
    → Nhấn "Chụp ảnh"
    → [Anti-Spoofing] Kiểm tra mặt thật hay giả mạo
    → [Duplicate Check] Kiểm tra mặt đã đăng ký chưa
    → Lưu ảnh vào thư mục models/vision/faces/{tên}/
    → Thông báo kết quả
```

### 0b. Đăng Ký Khuôn Mặt Từ File Ảnh

```
Người dùng nhấn "0b. Đăng ký từ Ảnh File"
    → Nhập tên người dùng
    → Mở hộp thoại chọn file (.jpg/.jpeg/.png)
    → Đọc ảnh từ file
    → [Anti-Spoofing] Kiểm tra mặt thật hay giả mạo
    → [Duplicate Check] Kiểm tra mặt đã đăng ký chưa
    → Lưu vào models/vision/faces/{tên}/
    → Thông báo kết quả
```

### 1. Đăng Ký Bản Quyền Ảnh

```
Người dùng chọn file ảnh cần bảo vệ
    │
    ├─ Bước 1: [FaceID] Mở camera → Xác thực chủ sở hữu
    │       Nếu không nhận diện → Từ chối, dừng quy trình
    │
    ├─ Bước 2: [DRM Watermark] Gắn chữ "DRM_PROTECTED" vào ảnh
    │           Embed pixel marker (steganography đơn giản)
    │
    ├─ Bước 3: [Hashing] Tính toán các mã băm
    │       • SHA-256 hash (ảnh gốc + ảnh đã bảo vệ)
    │       • Wavelet Hash (wHash) — kháng scale/nén
    │       • DHash 256-bit — cảm quan (perceptual)
    │       • ORB Features — đặc trưng hình học (kháng xoay)
    │
    ├─ Bước 4: [Blockchain] Ghi vào sổ cái (JSON ledger)
    │       { index, timestamp, hashes, p_hash, w_hash,
    │         orb_features, owner, previous_hash }
    │
    └─ Bước 5: Xuất file ảnh bảo vệ → protected_images/DRM_{tên file}
```

### 2. Xác Thực Bản Quyền Ảnh

```
Người dùng chọn ảnh cần kiểm tra
    │
    ├─ Tính toán: content_hash, p_hash, w_hash
    │
    ├─ Tầng 1 — EXACT: So khớp SHA-256 tuyệt đối
    │       ✅ Khớp → "Nguyên bản 100%"
    │
    ├─ Tầng 2 — WAVELET: So khớp Wavelet Hash (Hamming ≤ 12)
    │       ✅ Khớp → "Đã scale hoặc nén JPEG"
    │
    ├─ Tầng 2b — FUZZY: So khớp DHash (Hamming ≤ 32/256)
    │       ✅ Khớp → "Đã chỉnh sửa nhẹ"
    │
    ├─ Tầng 3 — GEOMETRIC: So khớp ORB features (≥ 15%)
    │       ✅ Khớp → "Bất kể xoay/thu phóng"
    │
    └─ Không khớp → "Không tìm thấy bản quyền"
```

### 3. Quét Khuôn Mặt (FaceID Nhanh)

```
Người dùng nhấn "3. Quét Khuôn mặt"
    → Mở Live Camera
    → Nhấn "Xác nhận"
    → ArcFace so khớp với database
    → Hiển thị tên người dùng hoặc "Không nhận diện được"
```

---

## Cấu Trúc Dữ Liệu

### Database Khuôn Mặt
```
models/vision/faces/
    ├── Nguyen_Van_A/
    │   ├── Nguyen_Van_A_1711432100.jpg
    │   └── Nguyen_Van_A_1711432200.jpg
    └── Tran_Thi_B/
        └── Tran_Thi_B_1711432300.jpg
```

### Blockchain Ledger (`models/blockchain_ledger.json`)
```json
{
  "index": 1,
  "timestamp": 1711432000.0,
  "hashes": ["sha256_goc", "sha256_protected"],
  "p_hash": "abc123...64ký_tự",
  "w_hash": "0f3a...16ký_tự",
  "orb_features": [[...], ...],
  "owner": "Nguyen_Van_A",
  "previous_hash": "0"
}
```

### Ảnh Đầu Ra (`protected_images/`)
```
protected_images/
    └── DRM_anh_goc.jpg   ← Ảnh đã gắn watermark + pixel marker
```

---

## Quy Tắc Nghiệp Vụ

- ✅ **Chỉ chủ sở hữu đã đăng ký** mặt mới được đăng ký bản quyền
- ✅ **Mỗi ảnh chỉ đăng ký được 1 lần** — trùng hash sẽ bị từ chối
- ✅ **Khuôn mặt không được trùng tên** — 1 mặt chỉ thuộc 1 người
- ✅ **Anti-Spoofing** — từ chối ảnh in/màn hình khi đăng ký
- ✅ **Xác thực đa tầng** — ngay cả ảnh bị chỉnh sửa/xoay vẫn bị phát hiện
