import cv2

def check_available_cameras():
    print("--- Đang quét các Camera khả dụng ---")
    available_cameras = []
    
    # Quét thử từ ID 0 đến 5
    for i in range(6):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW) # Sử dụng DSHOW cho Windows
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                print(f"[OK] Tìm thấy Camera với ID: {i}")
                available_cameras.append(i)
            cap.release()
        else:
            # Miễn cưỡng thử lại không có DSHOW nếu không mở được
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                print(f"[OK] Tìm thấy Camera với ID: {i} (Mặc định)")
                available_cameras.append(i)
                cap.release()
                
    if not available_cameras:
        print("!!! Không tìm thấy camera nào đang kết nối.")
    else:
        print(f"\n=> Bạn nên điền ID: {available_cameras[0]} vào file config.yaml")

if __name__ == "__main__":
    check_available_cameras()
