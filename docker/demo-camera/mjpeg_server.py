"""
Minimal MJPEG server that generates demo frames with timestamps.
Frames contain a simulated license plate text and a colored background
so the integration has something to process.

Access: http://localhost:8554/stream
"""
import io
import random
import socket
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from PIL import Image, ImageDraw, ImageFont

# Demo license plates that rotate through frames
DEMO_PLATES = ["W AB 1234", "M XY 5678", "B CD 9999", "GD EF 4321", ""]
FRAME_RATE = 1  # frames per second (low to save CPU)
PORT = 8554

# Global frame storage
_current_frame: bytes = b""


def _generate_frame(plate: str, frame_no: int) -> bytes:
    """Create a 640x480 JPEG demo image."""
    # Cycling background colour
    hue = (frame_no * 7) % 360
    r = int(128 + 60 * abs((hue % 120) / 60 - 1))
    g = int(128 + 60 * abs(((hue - 40) % 120) / 60 - 1))
    b = int(128 + 60 * abs(((hue - 80) % 120) / 60 - 1))

    img = Image.new("RGB", (640, 480), color=(r, g, b))
    draw = ImageDraw.Draw(img)

    # Timestamp
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    draw.rectangle([0, 0, 640, 50], fill=(30, 30, 30))
    draw.text((10, 12), f"Demo Camera – {ts}", fill="white")

    # Simulated license plate
    if plate:
        draw.rectangle([170, 190, 470, 290], fill="white", outline="black", width=4)
        draw.rectangle([180, 200, 460, 280], fill="white")
        # Big plate text
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
        except Exception:
            font = ImageFont.load_default()
        # Center the text
        bbox = draw.textbbox((0, 0), plate, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((320 - tw // 2, 240 - th // 2), plate, fill="black", font=font)
        draw.text((10, 320), f"Plate visible: {plate}", fill=(20, 20, 20))
    else:
        draw.text((200, 230), "No plate in frame", fill=(60, 60, 60))

    draw.text((10, 440), f"Frame #{frame_no}", fill=(40, 40, 40))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return buf.getvalue()


def _frame_generator():
    """Background thread: generate frames at FRAME_RATE."""
    global _current_frame
    frame_no = 0
    plate_idx = 0
    while True:
        # Rotate plate every 10 frames
        if frame_no % 10 == 0:
            plate_idx = (plate_idx + 1) % len(DEMO_PLATES)
        plate = DEMO_PLATES[plate_idx]
        _current_frame = _generate_frame(plate, frame_no)
        frame_no += 1
        time.sleep(1 / FRAME_RATE)


class MJPEGHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress access logs

    def do_GET(self):
        if self.path == "/stream":
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "multipart/x-mixed-replace; boundary=--jpegboundary",
            )
            self.end_headers()
            try:
                while True:
                    frame = _current_frame
                    if frame:
                        self.wfile.write(b"--jpegboundary\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(
                            f"Content-Length: {len(frame)}\r\n\r\n".encode()
                        )
                        self.wfile.write(frame)
                        self.wfile.write(b"\r\n")
                    time.sleep(1 / FRAME_RATE)
            except (BrokenPipeError, ConnectionResetError):
                pass

        elif self.path == "/snapshot":
            # Single JPEG snapshot (for HA still_image_url)
            frame = _current_frame
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(frame)))
            self.end_headers()
            self.wfile.write(frame)

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found. Use /stream or /snapshot")


if __name__ == "__main__":
    t = Thread(target=_frame_generator, daemon=True)
    t.start()

    # Brief warm-up
    time.sleep(0.5)

    print(f"MJPEG Demo Camera running on port {PORT}")
    print(f"  Stream:   http://0.0.0.0:{PORT}/stream")
    print(f"  Snapshot: http://0.0.0.0:{PORT}/snapshot")

    server = HTTPServer(("0.0.0.0", PORT), MJPEGHandler)
    server.serve_forever()
