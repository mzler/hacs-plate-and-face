"""Constants for Plate & Face Recognition integration."""

DOMAIN = "plate_face_recognition"
NAME = "Plate & Face Recognition"
VERSION = "1.0.0"

# Configuration keys
CONF_CAMERAS = "cameras"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_FACE_THRESHOLD = "face_threshold"
CONF_PLATE_MIN_CONFIDENCE = "plate_min_confidence"
CONF_ENABLE_PLATES = "enable_plates"
CONF_ENABLE_FACES = "enable_faces"

# Defaults
DEFAULT_SCAN_INTERVAL = 10  # seconds
DEFAULT_FACE_THRESHOLD = 0.55  # lower = stricter
DEFAULT_PLATE_MIN_CONFIDENCE = 0.5
DEFAULT_ENABLE_PLATES = True
DEFAULT_ENABLE_FACES = True
MAX_CAMERAS = 5

# Storage
STORAGE_KEY = f"{DOMAIN}.faces"
STORAGE_VERSION = 1
FACES_SUBDIR = "plate_face_recognition/known_faces"

# Sensor types
SENSOR_TYPE_PLATE = "license_plate"
SENSOR_TYPE_FACE = "detected_faces"

# Attributes
ATTR_PLATES = "plates"
ATTR_FACES = "faces"
ATTR_CAMERA = "camera_entity_id"
ATTR_LAST_UPDATE = "last_update"
ATTR_IMAGE_TIMESTAMP = "image_timestamp"
ATTR_UNKNOWN_COUNT = "unknown_faces_count"

# Service names
SERVICE_REGISTER_FACE = "register_face"
SERVICE_DELETE_FACE = "delete_face"
SERVICE_LIST_FACES = "list_faces"
SERVICE_CAPTURE_FACE = "capture_face_from_camera"

# Service attributes
ATTR_FACE_NAME = "name"
ATTR_FILE_PATH = "file_path"
ATTR_CAMERA_ENTITY = "camera_entity_id"

# Events
EVENT_PLATE_DETECTED = f"{DOMAIN}_plate_detected"
EVENT_FACE_DETECTED = f"{DOMAIN}_face_detected"

# Plate regex patterns (common European + US formats)
PLATE_PATTERNS = [
    # German: AB CD 1234 or AB-CD-1234
    r"[A-ZÄÖÜ]{1,3}[\s\-][A-Z]{1,2}[\s\-]\d{1,4}[EH]?",
    # Austrian
    r"[A-ZÄÖÜ]{1,2}[\s\-]\d{1,5}[A-Z]{0,2}",
    # Swiss
    r"[A-Z]{2}[\s\-]\d{1,6}",
    # Generic: 2-8 alphanumeric chars that look like a plate
    r"[A-Z0-9]{2,4}[\s\-][A-Z0-9]{2,4}",
    r"[A-Z]{1,3}\d{2,4}[A-Z]{0,3}",
]
