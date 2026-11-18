"""Capture one USB webcam and stream raw and lane-overlay video separately."""

import threading
import time

import cv2
from flask import Response, jsonify

from lane_detection import LaneDetector

CAMERA_INDICES = (0, 1, 2, 3, 4)
JPEG_QUALITY = 75


class SharedCamera:
    def __init__(self):
        self.condition = threading.Condition()
        self.started = False
        self.running = threading.Event()
        self.capture_thread = None
        self.processing_thread = None
        self.camera_index = None
        self.last_error = "Camera starting."
        self.raw_frame = None
        self.raw_jpeg = None
        self.overlay_jpeg = None
        self.raw_sequence = 0
        self.overlay_sequence = 0
        self.lane_status = {"left": False, "right": False, "center": False}

    def start(self):
        with self.condition:
            if self.started:
                return
            self.started = True
            self.running.set()
        self.capture_thread = threading.Thread(
            target=self.capture_loop, daemon=True, name="USB-Camera-Capture")
        self.processing_thread = threading.Thread(
            target=self.overlay_loop, daemon=True, name="Lane-Detection")
        self.capture_thread.start()
        self.processing_thread.start()

    def stop(self):
        self.running.clear()
        with self.condition:
            self.condition.notify_all()
        for thread in (self.capture_thread, self.processing_thread):
            if thread is not None and thread.is_alive():
                thread.join(timeout=3)

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
                    success, frame = capture.read()
                    if success and frame is not None:
                        return capture, index, frame
                    time.sleep(0.05)
                capture.release()
        return None, None, None

    def capture_loop(self):
        while self.running.is_set():
            capture, index, frame = self.open_camera()
            if capture is None:
                with self.condition:
                    self.camera_index = None
                    self.raw_jpeg = None
                    self.raw_frame = None
                    self.overlay_jpeg = None
                    self.last_error = "USB camera unavailable. Check /dev/video*."
                    self.condition.notify_all()
                time.sleep(2)
                continue

            print(f"VIDEO: Webcam opened on /dev/video{index}", flush=True)
            with self.condition:
                self.camera_index = index
                self.last_error = None

            try:
                while self.running.is_set():
                    success, encoded = cv2.imencode(
                        ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
                    )
                    if success:
                        with self.condition:
                            self.raw_frame = frame.copy()
                            self.raw_jpeg = encoded.tobytes()
                            self.raw_sequence += 1
                            self.condition.notify_all()
                    success, frame = capture.read()
                    if not success or frame is None:
                        break
                    time.sleep(0.015)
            except Exception as error:
                with self.condition:
                    self.last_error = str(error)
            finally:
                capture.release()
                with self.condition:
                    self.camera_index = None
                    self.raw_jpeg = None
                    self.raw_frame = None
                    self.overlay_jpeg = None
                    self.last_error = self.last_error or "Camera disconnected. Reconnecting."
                    self.condition.notify_all()
                if self.running.is_set():
                    time.sleep(1)

    def overlay_loop(self):
        processor = LaneDetector()
        last_processed = 0
        while self.running.is_set():
            with self.condition:
                available = self.condition.wait_for(
                    lambda: not self.running.is_set() or
                    (self.raw_frame is not None and self.raw_sequence > last_processed),
                    timeout=3,
                )
                if not available or not self.running.is_set():
                    continue
                frame = self.raw_frame.copy()
                last_processed = self.raw_sequence
            try:
                result = processor.process(frame)
                success, encoded = cv2.imencode(
                    ".jpg", result, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
                )
                if success:
                    with self.condition:
                        self.overlay_jpeg = encoded.tobytes()
                        self.overlay_sequence += 1
                        self.lane_status = processor.last_detection.copy()
                        self.condition.notify_all()
            except Exception as error:
                with self.condition:
                    self.last_error = f"Lane detection: {error}"
                    self.condition.notify_all()
                time.sleep(0.1)

    def wait_for_frame(self, stream_number=2, after_sequence=0, timeout=6):
        # Stream 1 is the overlay. Stream 2 is the raw webcam image.
        with self.condition:
            if stream_number == 1:
                available = self.condition.wait_for(
                    lambda: not self.running.is_set() or
                    (self.overlay_jpeg is not None
                    and self.overlay_sequence > after_sequence), timeout=timeout)
                if available and self.running.is_set():
                    return self.overlay_sequence, self.overlay_jpeg
            else:
                available = self.condition.wait_for(
                    lambda: not self.running.is_set() or
                    (self.raw_jpeg is not None
                    and self.raw_sequence > after_sequence), timeout=timeout)
                if available and self.running.is_set():
                    return self.raw_sequence, self.raw_jpeg
        return None

    def status(self):
        with self.condition:
            return self.camera_index, self.last_error, self.lane_status.copy()


camera = SharedCamera()


def register_video_routes(app, is_authenticated):
    @app.route("/camera_check", methods=["GET"])
    def camera_check():
        camera.start()
        first = camera.wait_for_frame(stream_number=2, timeout=5)
        index, error, lanes = camera.status()
        if first is None:
            return jsonify(success=False, message=error or "Camera not producing frames."), 503
        return jsonify(success=True, camera_index=index,
                       message="USB webcam ready.", lanes=lanes)

    @app.route("/video_feed", methods=["GET"])
    @app.route("/video_feed/<int:stream_number>", methods=["GET"])
    def video_feed(stream_number=1):
        if stream_number not in (1, 2):
            return jsonify(success=False, message="Invalid stream number."), 404
        if not is_authenticated():
            return jsonify(success=False, message="Authentication required."), 401

        camera.start()
        first = camera.wait_for_frame(stream_number=stream_number, timeout=8)
        if first is None:
            _, error, _ = camera.status()
            return jsonify(success=False, message=error or "Video not ready."), 503

        def generate_frames():
            current = first
            while current is not None:
                sequence, jpeg = current
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n"
                       + f"Content-Length: {len(jpeg)}\r\n".encode("ascii")
                       + b"\r\n" + jpeg + b"\r\n")
                current = camera.wait_for_frame(
                    stream_number=stream_number, after_sequence=sequence, timeout=8)

        print(f"VIDEO: Stream {stream_number} connected", flush=True)
        return Response(generate_frames(),
                        mimetype="multipart/x-mixed-replace; boundary=frame",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
