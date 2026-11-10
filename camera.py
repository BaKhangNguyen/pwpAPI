"""Stream USB webcam video through the existing Flask server."""

import threading
import cv2
from flask import Response, jsonify


CAMERA_INDEX = 0
_camera_lock = threading.Lock()


def register_video_routes(app, is_authenticated):
    # Add the camera endpoint to the existing Flask application.
    @app.route('/video_feed', methods=['GET'])
    def video_feed():
        if not is_authenticated():
            return jsonify(success=False, message='Authentication required.'), 401

        if not _camera_lock.acquire(blocking=False):
            return jsonify(success=False, message='Camera is already in use.'), 409

        camera = cv2.VideoCapture(CAMERA_INDEX)
        if not camera.isOpened():
            camera.release()
            _camera_lock.release()
            return jsonify(success=False, message='USB camera not available.'), 503

        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        camera.set(cv2.CAP_PROP_FPS, 15)

        def frames():
            # Send JPEG frames until the client disconnects.
            try:
                while True:
                    success, frame = camera.read()
                    if not success:
                        break
                    success, jpeg = cv2.imencode(
                        '.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70]
                    )
                    if not success:
                        continue
                    yield (
                        b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n'
                        + jpeg.tobytes()
                        + b'\r\n'
                    )
            finally:
                camera.release()
                _camera_lock.release()

        return Response(frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
