"""Find the two taped lane boundaries and draw their center line."""

import cv2
import numpy as np


def region_selection(edges):
    height, width = edges.shape[:2]
    mask = np.zeros_like(edges)
    points = np.array([[
        (0, height - 1),
        (int(width * 0.08), int(height * 0.38)),
        (int(width * 0.92), int(height * 0.38)),
        (width - 1, height - 1),
    ]], dtype=np.int32)
    cv2.fillPoly(mask, points, 255)
    return cv2.bitwise_and(edges, mask)


def _weighted_median(values, weights):
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    order = np.argsort(values)
    values, weights = values[order], weights[order]
    return float(values[np.searchsorted(np.cumsum(weights), weights.sum() / 2)])


def _representative_line(segments, width):
    if not segments:
        return None
    base = np.array([item[0] for item in segments])
    tips = np.array([item[1] for item in segments])
    weights = np.array([item[2] for item in segments])
    median = _weighted_median(base, weights)
    deviations = np.abs(base - median)
    # Reject stray line segments before averaging.
    allowed = max(width * 0.08, 2.5 * _weighted_median(deviations, weights))
    accepted = deviations <= allowed
    if not np.any(accepted):
        return None
    return (float(np.average(base[accepted], weights=weights[accepted])),
            float(np.average(tips[accepted], weights=weights[accepted])))


def detect_lanes(image):
    """Return the left/right line endpoints or None if not detected."""
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 45, 135)

    # Include edges of colored tape that is close in brightness to the floor.
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    saturation = cv2.inRange(hsv, (0, 70, 45), (179, 255, 255))
    edges = cv2.bitwise_or(edges, cv2.Canny(saturation, 40, 120))
    edges = region_selection(edges)

    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=25,
                            minLineLength=30, maxLineGap=65)
    if lines is None:
        return None, None

    bottom_y = height - 1
    top_y = int(height * 0.42)
    left, right = [], []
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        dy = float(y2 - y1)
        dx = float(x2 - x1)
        length = float(np.hypot(dx, dy))
        if abs(dy) < 10 or abs(dy) / length < 0.30:
            continue
        change = dx / dy
        bottom_x = x1 + change * (bottom_y - y1)
        top_x = x1 + change * (top_y - y1)
        # Avoid extrapolating short segments into implausible lane edges.
        if not (-0.35 * width <= bottom_x <= 1.35 * width):
            continue
        if not (-0.25 * width <= top_x <= 1.25 * width):
            continue
        if bottom_x < 0.45 * width and top_x < 0.62 * width and bottom_x <= top_x + 0.14 * width:
            left.append((bottom_x, top_x, length))
        elif bottom_x > 0.55 * width and top_x > 0.38 * width and bottom_x >= top_x - 0.14 * width:
            right.append((bottom_x, top_x, length))

    return _representative_line(left, width), _representative_line(right, width)


def _points(line, width, height):
    if line is None:
        return None
    bottom_x, top_x = line
    bottom_y = height - 1
    top_y = int(height * 0.42)
    return ((int(np.clip(bottom_x, 0, width - 1)), bottom_y),
            (int(np.clip(top_x, 0, width - 1)), top_y))


class LaneDetector:
    def __init__(self):
        self.previous_left = None
        self.previous_right = None
        self.missing_left = 0
        self.missing_right = 0
        self.last_detection = {"left": False, "right": False, "center": False}

    def _stabilize(self, current, previous, missed):
        if current is None:
            missed += 1
            return (previous if missed <= 5 else None), missed
        if previous is not None:
            current = (0.65 * previous[0] + 0.35 * current[0],
                       0.65 * previous[1] + 0.35 * current[1])
        return current, 0

    def process(self, frame):
        if frame is None:
            return None
        height, width = frame.shape[:2]
        left, right = detect_lanes(frame)
        self.previous_left, self.missing_left = self._stabilize(
            left, self.previous_left, self.missing_left)
        self.previous_right, self.missing_right = self._stabilize(
            right, self.previous_right, self.missing_right)

        left_points = _points(self.previous_left, width, height)
        right_points = _points(self.previous_right, width, height)
        result = frame.copy()
        if left_points is not None:
            cv2.line(result, *left_points, (0, 0, 255), 5)
        if right_points is not None:
            cv2.line(result, *right_points, (255, 0, 0), 5)

        center = None
        if left_points is not None and right_points is not None:
            left_bottom, left_top = left_points
            right_bottom, right_top = right_points
            if (right_bottom[0] - left_bottom[0] > width * 0.15 and
                    right_top[0] - left_top[0] > width * 0.04):
                center = (
                    ((left_bottom[0] + right_bottom[0]) // 2, left_bottom[1]),
                    ((left_top[0] + right_top[0]) // 2, left_top[1]),
                )
                cv2.line(result, *center, (0, 255, 0), 5)

        self.last_detection = {
            "left": left_points is not None,
            "right": right_points is not None,
            "center": center is not None,
        }
        return result


def frame_processor(image):
    """Simple one-frame interface for testing with still images."""
    return LaneDetector().process(image)
