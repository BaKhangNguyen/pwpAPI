"""Test the USB webcam directly on the Raspberry Pi."""

import glob
import cv2

print("Video devices:", ", ".join(sorted(glob.glob("/dev/video*"))) or "none")
found = False

for index in range(5):
    camera = cv2.VideoCapture(index, cv2.CAP_V4L2)
    try:
        if not camera.isOpened():
            print(f"Camera {index}: cannot open")
            continue
        ok, frame = camera.read()
        if ok and frame is not None:
            print(f"Camera {index}: OK, frame size {frame.shape[1]}x{frame.shape[0]}")
            found = True
        else:
            print(f"Camera {index}: opened, but could not read a frame")
    finally:
        camera.release()

print("RESULT:", "USB camera detected" if found else "No working USB camera detected")
