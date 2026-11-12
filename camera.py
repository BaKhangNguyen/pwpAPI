"""Share one Raspberry Pi USB webcam with two independent video streams."""

import threading
import time

import cv2
from flask import Response, jsonify


CAMERA_INDICES = (0, 1, 2, 3, 4)


class SharedCamera:
    def __init__(self):
        self.condition = threading.Condition()
        self.started = False
        self.jpeg = None
        self.sequence = 0
        self.camera_index = None
        self.last_error = "Camera starting."

    def start(self):
        with self.condition:
            if self.started:
                return
            self.started = True
        threading.Thread(target=self.capture_loop, daemon=True, name="USB-Camera-Capture").start()

    def open_camera(self):
        for index in CAMERA_INDICES:
            for backend in (cv2.CAP_V4L2, cv2.CAP_ANY):
                capture = cv2.VideoCapture(index, backend)
                if not capture.isOpened():
                    capture.release()
                    continue

                capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                capture.set(cv2.CAP_PROP_FPS, 15)

                for _ in range(12):
                    ok, frame = capture.read()
                    if ok and frame is not None:
                        return capture, index, frame
                    time.sleep(0.05)
                capture.release()
        return None, None, None

    def capture_loop(self):
        while True:
            capture, index, frame = self.open_camera()
            if capture is None:
                with self.condition:
                    self.jpeg = None
                    self.camera_index = None
                    self.last_error = "No readable USB webcam found (indices 0 to 4)."
                    self.condition.notify_all()
                time.sleep(2)
                continue

            print(f"VIDEO: USB webcam opened on /dev/video{index}", flush=True)
            with self.condition:
                self.camera_index = index
                self.last_error = None

            try:
                while True:
                    ok, encoded = cv2.imencode(
                        ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75]
                    )
                    if ok:
                        with self.condition:
                            self.jpeg = encoded.tobytes()
                            self.sequence += 1
                            self.condition.notify_all()

                    ok, frame = capture.read()
                    if not ok or frame is None:
                        break
                    time.sleep(0.015)
            except Exception as error:
                with self.condition:
                    self.last_error = str(error)
            finally:
                capture.release()
                with self.condition:
                    self.jpeg = None
                    self.camera_index = None
                    self.last_error = self.last_error or "Camera disconnected. Reconnecting."
                    self.condition.notify_all()
                time.sleep(1)

    def wait_for_frame(self, after_sequence=0, timeout=6):
        with self.condition:
            available = self.condition.wait_for(
                lambda: self.jpeg is not None and self.sequence > after_sequence,
                timeout=timeout,
            )
            if not available:
                return None
            return self.sequence, self.jpeg

    def status(self):
        with self.condition:
            return self.camera_index, self.last_error


camera = SharedCamera()


def register_video_routes(app, is_authenticated):
    @app.route("/camera_check", methods=["GET"])
    def camera_check():
        camera.start()
        frame = camera.wait_for_frame(timeout=5)
        index, error = camera.status()
        if frame is None:
            return jsonify(success=False, message=error or "Camera did not return a frame."), 503
        return jsonify(success=True, message="USB webcam ready.", camera_index=index)

    @app.route("/video_feed", methods=["GET"])
    @app.route("/video_feed/<int:stream_number>", methods=["GET"])
    def video_feed(stream_number=1):
        if stream_number not in (1, 2):
            return jsonify(success=False, message="Unknown video stream."), 404
        if not is_authenticated():
            return jsonify(success=False, message="Authentication required."), 401

        camera.start()
        first = camera.wait_for_frame(timeout=5)
        if first is None:
            _, error = camera.status()
            return jsonify(success=False, message=error or "Webcam unavailable."), 503

        def generate_frames():
            current = first
            while current is not None:
                sequence, jpeg = current
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    + f"Content-Length: {len(jpeg)}\r\n".encode("ascii")
                    + b"\r\n" + jpeg + b"\r\n"
                )
                current = camera.wait_for_frame(after_sequence=sequence, timeout=6)

        print(f"VIDEO: Stream {stream_number} connected", flush=True)
        return Response(
            generate_frames(),
            mimetype="multipart/x-mixed-replace; boundary=frame",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
