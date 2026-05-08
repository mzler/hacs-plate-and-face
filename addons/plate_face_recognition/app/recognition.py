"""Core recognition logic – standalone version for the HA Add-on.

Identical algorithm to the custom_component version, but without any
Home Assistant imports. All constants are inlined.
"""
from __future__ import annotations

import io
import logging
import re
from typing import Any

import numpy as np
from PIL import Image

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (inlined from custom_component const.py)
# ---------------------------------------------------------------------------

DEFAULT_FACE_THRESHOLD = 0.55
DEFAULT_PLATE_MIN_CONFIDENCE = 0.50

PLATE_PATTERNS = [
    # German:  AB CD 1234  or  AB-CD-1234
    r"[A-ZÄÖÜ]{1,3}[\s\-][A-Z]{1,2}[\s\-]\d{1,4}[EH]?",
    # Austrian
    r"[A-ZÄÖÜ]{1,2}[\s\-]\d{1,5}[A-Z]{0,2}",
    # Swiss
    r"[A-Z]{2}[\s\-]\d{1,6}",
    # Generic: 2-8 alphanumeric chars that look like a plate
    r"[A-Z0-9]{2,4}[\s\-][A-Z0-9]{2,4}",
    r"[A-Z]{1,3}\d{2,4}[A-Z]{0,3}",
]


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _bytes_to_numpy(image_bytes: bytes) -> np.ndarray:
    """Convert raw image bytes to a numpy array (BGR for OpenCV)."""
    import cv2

    pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_array = np.array(pil_image)
    return cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)


# ---------------------------------------------------------------------------
# License Plate Recognition
# ---------------------------------------------------------------------------

_ocr_reader = None  # Lazy-loaded EasyOCR reader


def _get_ocr_reader():
    """Return (cached) EasyOCR reader instance."""
    global _ocr_reader
    if _ocr_reader is None:
        try:
            import easyocr

            _ocr_reader = easyocr.Reader(["de", "en"], gpu=False, verbose=False)
            _LOGGER.info("EasyOCR reader initialised.")
        except Exception as exc:
            _LOGGER.error("Failed to initialise EasyOCR: %s", exc)
            raise
    return _ocr_reader


def _detect_plate_candidates(img_bgr: np.ndarray) -> list[np.ndarray]:
    """
    Use OpenCV contour analysis to find rectangular regions likely to be
    license plates. Returns a list of cropped BGR images.
    """
    import cv2

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.bilateralFilter(gray, 11, 17, 17)
    edges = cv2.Canny(blur, 30, 200)

    contours, _ = cv2.findContours(
        edges.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:20]

    candidates: list[np.ndarray] = []
    h_img, w_img = img_bgr.shape[:2]

    for cnt in contours:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.018 * peri, True)
        if len(approx) != 4:
            continue

        x, y, w, h = cv2.boundingRect(approx)
        aspect = w / max(h, 1)
        area_ratio = (w * h) / (w_img * h_img)

        if 1.5 < aspect < 7.0 and 0.005 < area_ratio < 0.3:
            roi = img_bgr[y : y + h, x : x + w]
            candidates.append(roi)

    # Always include full image as fallback
    candidates.append(img_bgr)
    return candidates


def _match_plate_text(text: str) -> str | None:
    """Return text if it matches a known plate pattern, else None."""
    cleaned = text.upper().strip()
    for pattern in PLATE_PATTERNS:
        if re.search(pattern, cleaned):
            return cleaned
    return None


def detect_license_plates(
    image_bytes: bytes,
    min_confidence: float = DEFAULT_PLATE_MIN_CONFIDENCE,
) -> list[str]:
    """
    Detect and read license plates from *image_bytes*.
    Returns a list of plate strings found (may be empty).
    """
    try:
        reader = _get_ocr_reader()
        img_bgr = _bytes_to_numpy(image_bytes)
    except Exception as exc:
        _LOGGER.error("Plate recognition initialisation error: %s", exc)
        return []

    found_plates: list[str] = []
    seen: set[str] = set()

    candidates = _detect_plate_candidates(img_bgr)

    for roi in candidates:
        try:
            results = reader.readtext(roi, detail=1, paragraph=False)
        except Exception as exc:
            _LOGGER.debug("EasyOCR error on ROI: %s", exc)
            continue

        for _bbox, text, confidence in results:
            if confidence < min_confidence:
                continue
            plate = _match_plate_text(text)
            if plate and plate not in seen:
                seen.add(plate)
                found_plates.append(plate)

    _LOGGER.debug("Detected plates: %s", found_plates)
    return found_plates


# ---------------------------------------------------------------------------
# Face Recognition
# ---------------------------------------------------------------------------

def detect_faces(
    image_bytes: bytes,
    known_encodings: list[np.ndarray],
    known_names: list[str],
    tolerance: float = DEFAULT_FACE_THRESHOLD,
) -> tuple[list[str], int]:
    """
    Detect faces in *image_bytes* and match against *known_encodings*.

    Returns:
        - List of recognised names (duplicates removed, sorted)
        - Count of faces that could not be identified
    """
    try:
        import face_recognition  # noqa: PLC0415
    except ImportError:
        _LOGGER.error("face_recognition library is not installed.")
        return [], 0

    try:
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        frame = np.array(pil_image)
    except Exception as exc:
        _LOGGER.error("Failed to decode image for face recognition: %s", exc)
        return [], 0

    try:
        face_locations = face_recognition.face_locations(frame, model="hog")
        if not face_locations:
            return [], 0

        face_encodings = face_recognition.face_encodings(frame, face_locations)
    except Exception as exc:
        _LOGGER.error("face_recognition error: %s", exc)
        return [], 0

    recognised: set[str] = set()
    unknown_count = 0

    for encoding in face_encodings:
        name = "Unknown"
        if known_encodings:
            matches = face_recognition.compare_faces(
                known_encodings, encoding, tolerance=tolerance
            )
            distances = face_recognition.face_distance(known_encodings, encoding)
            if True in matches:
                best_idx = int(np.argmin(distances))
                if matches[best_idx]:
                    name = known_names[best_idx]

        if name == "Unknown":
            unknown_count += 1
        else:
            recognised.add(name)

    _LOGGER.debug(
        "Detected faces: known=%s, unknown=%d", sorted(recognised), unknown_count
    )
    return sorted(recognised), unknown_count


def encode_face_image(image_bytes: bytes) -> list[np.ndarray]:
    """
    Extract all face encodings from *image_bytes*.
    Used when registering a new face.
    Returns list of encodings (one per face found).
    """
    try:
        import face_recognition  # noqa: PLC0415
    except ImportError:
        _LOGGER.error("face_recognition library is not installed.")
        return []

    try:
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        frame = np.array(pil_image)
    except Exception as exc:
        _LOGGER.error("Failed to decode face registration image: %s", exc)
        return []

    locations = face_recognition.face_locations(frame, model="hog")
    if not locations:
        _LOGGER.warning("No faces found in the registration image.")
        return []

    encodings = face_recognition.face_encodings(frame, locations)
    _LOGGER.debug("Found %d face(s) in registration image.", len(encodings))
    return encodings
