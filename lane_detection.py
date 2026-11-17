
import cv2
import numpy as np


def region_selection(image):
    """Keep the lower road region where lane markings are expected."""

    height, width = image.shape[:2]

    mask = np.zeros_like(image)

    vertices = np.array([[
        (int(width * 0.10), height),
        (int(width * 0.40), int(height * 0.60)),
        (int(width * 0.60), int(height * 0.60)),
        (int(width * 0.90), height)
    ]], dtype=np.int32)

    cv2.fillPoly(mask, vertices, 255)

    return cv2.bitwise_and(image, mask)


def hough_transform(image):
    """Detect line segments using the Hough Transform."""

    return cv2.HoughLinesP(
        image,
        rho=1,
        theta=np.pi / 180,
        threshold=20,
        minLineLength=20,
        maxLineGap=100
    )


def average_slope_intercept(lines):
    """Calculate representative left and right lane lines."""

    left_lines = []
    left_weights = []

    right_lines = []
    right_weights = []

    if lines is None:
        return None, None

    for line in lines:
        for x1, y1, x2, y2 in line:

            if x2 == x1:
                continue

            slope = (y2 - y1) / (x2 - x1)
            intercept = y1 - slope * x1

            length = np.hypot(x2 - x1, y2 - y1)

            # Ignore nearly horizontal lines.
            if abs(slope) < 0.4:
                continue

            if slope < 0:
                left_lines.append((slope, intercept))
                left_weights.append(length)
            else:
                right_lines.append((slope, intercept))
                right_weights.append(length)

    left_lane = None
    right_lane = None

    if left_weights:
        left_lane = np.average(
            left_lines,
            axis=0,
            weights=left_weights
        )

    if right_weights:
        right_lane = np.average(
            right_lines,
            axis=0,
            weights=right_weights
        )

    return left_lane, right_lane


def pixel_points(y1, y2, line, width):
    """Convert slope/intercept into image coordinates."""

    if line is None:
        return None

    slope, intercept = line

    if abs(slope) < 0.001:
        return None

    x1 = int((y1 - intercept) / slope)
    x2 = int((y2 - intercept) / slope)

    x1 = max(0, min(width - 1, x1))
    x2 = max(0, min(width - 1, x2))

    return ((x1, int(y1)), (x2, int(y2)))


def lane_lines(image, lines):
    """Create left and right lane lines."""

    left_lane, right_lane = average_slope_intercept(lines)

    height, width = image.shape[:2]

    y1 = height - 1
    y2 = int(height * 0.60)

    left_line = pixel_points(
        y1, y2, left_lane, width
    )

    right_line = pixel_points(
        y1, y2, right_lane, width
    )

    return left_line, right_line


def draw_lane_lines(image, lines):
    """Overlay detected lane lines on the original image."""

    line_image = np.zeros_like(image)

    for line in lines:
        if line is not None:
            cv2.line(
                line_image,
                line[0],
                line[1],
                (0, 0, 255),
                5
            )

    return cv2.addWeighted(
        image, 1.0,
        line_image, 1.0,
        0.0
    )


def frame_processor(image):
    """Process one live BGR camera frame."""

    if image is None:
        return image

    grayscale = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

    blur = cv2.GaussianBlur(
        grayscale,
        (5, 5),
        0
    )

    edges = cv2.Canny(
        blur,
        50,
        150
    )

    region = region_selection(edges)

    hough = hough_transform(region)

    lines = lane_lines(image, hough)

    result = draw_lane_lines(
        image,
        lines
    )

    return result
