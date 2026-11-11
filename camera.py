"""USB webcam streaming for the existing Flask rover API."""

import threading
import time

import cv2
from flask import Response, jsonify


# Try common USB webcam device indices. The first readable camera is used.
CAMERA_INDICES = (0, 1, 2, 3, 4)
_camera_lock = threading.Lock()


def _open_camera():
    for index in CAMERA_INDICES:
        camera = cv2.VideoCapture(index, cv2.CAP_V4L2)
        if not camera.isOpened():
            camera.release()
            continue

        camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        camera.set(cv2.CAP_PROP_FPS, 15)

        # Some webcams require a few reads before returning a frame.
        for _ in range(12):
            ok, frame = camera.read()
            if ok and frame is not None:
                return camera, index, frame
            time.sleep(0.05)
        camera.release()

    return None, None, None


def _jpeg_part(frame):
    ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
    if not ok:
        return None
    return b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"


def register_video_routes(app, is_authenticated):
    @app.route("/camera_check", methods=["GET"])
    def camera_check():
        # Check the webcam without requiring a GUI login.
        if not _camera_lock.acquire(blocking=False):
            return jsonify(success=True, message="Camera is already streaming.")

        camera = None
        try:
            camera, index, frame = _open_camera()
            if camera is None:
                return jsonify(success=False, message="No readable USB webcam found on indices 0 to 4."), 503
            return jsonify(success=True, message="USB webcam ready.", camera_index=index)
        finally:
            if camera is not None:
                camera.release()
            _camera_lock.release()

    @app.route("/video_feed", methods=["GET"])
    def video_feed():
        # Keep the camera stream protected by the normal login token.
        if not is_authenticated():
            return jsonify(success=False, message="Authentication required."), 401
        if not _camera_lock.acquire(blocking=False):
            return jsonify(success=False, message="Camera is already in use."), 409

        camera, index, first_frame = _open_camera()
        if camera is None:
            _camera_lock.release()
            return jsonify(success=False, message="USB webcam could not return a frame."), 503

        first_part = _jpeg_part(first_frame)
        if first_part is None:
            camera.release()
            _camera_lock.release()
            return jsonify(success=False, message="Camera JPEG encoding failed."), 503

        def generate_frames():
            try:
                yield first_part
                while True:
                    ok, frame = camera.read()
                    if not ok or frame is None:
                        break
                    part = _jpeg_part(frame)
                    if part is not None:
                        yield part
            finally:
                camera.release()
                _camera_lock.release()

        print(f"VIDEO: Streaming USB webcam index {index}")
        return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")
