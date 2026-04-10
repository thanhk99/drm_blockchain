import sys
import os
import cv2
import numpy as np
sys.path.append(os.getcwd())

from engines.vision.face_manager import FaceManager

def test_identity_integrity():
    fm = FaceManager()
    name = "UniqueTestUser"
    
    # Clean up before test
    import shutil
    shutil.rmtree(os.path.join(fm.faces_dir, name), ignore_errors=True)
    shutil.rmtree(os.path.join(fm.node_base_dir, name), ignore_errors=True)
    
    # Create a dummy face frame (black image with some noise)
    dummy_frame = np.zeros((224, 224, 3), dtype=np.uint8)
    cv2.putText(dummy_frame, "FACE", (50, 110), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    print("--- 1. Registering TestUser (Dual-Save) ---")
    # Note: DeepFace.extract_faces will fail on a dummy frame if detector_backend='opencv'
    # For testing, we might need a real face or bypass the extraction check.
    # But I'll assume for now we use a frame that can be detected.
    
    success, msg = fm.register_face(name, frame=dummy_frame)
    if not success:
        print("Registration failed as expected (no real face found).")
        # Even if it fails, let's manually place files to test the integrity logic
        os.makedirs(os.path.join(fm.faces_dir, name), exist_ok=True)
        os.makedirs(os.path.join(fm.node_base_dir, name, "face_samples"), exist_ok=True)
        
        test_file = os.path.join(fm.faces_dir, name, "test.jpg")
        test_file_node = os.path.join(fm.node_base_dir, name, "face_samples", "test.jpg")
        
        cv2.imwrite(test_file, dummy_frame)
        cv2.imwrite(test_file_node, dummy_frame)
        print("Manually created redundant files for testing.")
    else:
        print("Registration successful.")

    print("\n--- 2. Checking Integrity (Valid Case) ---")
    is_ok, err = fm.check_identity_integrity(name)
    print(f"Integrity check: {is_ok}, {err}")
    assert is_ok is True

    print("\n--- 3. Tampering Test (Modify Node copy) ---")
    node_file = os.path.join(fm.node_base_dir, name, "face_samples")
    files = [f for f in os.listdir(node_file) if f.endswith(".jpg")]
    if files:
        target = os.path.join(node_file, files[0])
        with open(target, "a") as f:
            f.write("TAMPERED") # Append some noise to change hash
        
        is_ok_after, err_after = fm.check_identity_integrity(name)
        print(f"Integrity check after tamper: {is_ok_after}, {err_after}")
        assert is_ok_after is False
        print("Tampering correctly detected!")
    else:
        print("No files found to tamper.")

    print("\nSUCCESS: Identity integrity tests passed.")

if __name__ == "__main__":
    test_identity_integrity()
