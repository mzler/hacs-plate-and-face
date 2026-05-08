"""FastAPI REST server for the Plate & Face Recognition HA Add-on."""
from __future__ import annotations
import logging
import os
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Dict, List, Optional
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from face_manager import FaceManager
from profile_manager import ProfileManager
from recognition import (
    detect_faces,
    detect_license_plates,
    encode_face_image,
)

# ---------------------------------------------------------------------------
# Globals & Setup
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_LOGGER = logging.getLogger("PFR-API")
_DATA_DIR = Path(os.environ.get("PFR_DATA_DIR", "/data"))
_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Manager direkt beim Import initialisieren für maximale Stabilität
face_manager = FaceManager(db_path=_DATA_DIR / "known_faces.pkl")
profile_manager = ProfileManager(data_dir=str(_DATA_DIR))

class ProfileUpdate(BaseModel):
    name: str
    plates: Optional[str] = ""
    user_id: Optional[str] = None

# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------
app = FastAPI(title="PFR API", version="1.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health():
    return {"status": "ok", "faces": len(face_manager.known_names), "profiles": len(profile_manager.profiles)}

# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
@app.post("/detect")
async def detect(image: Annotated[bytes, File()], enable_plates: bool = Form(True), enable_faces: bool = Form(True)):
    plates: list[str] = []
    faces: list[str] = []
    if enable_plates:
        try:
            detected_plates = detect_license_plates(image, 0.5)
            for plate in detected_plates:
                plates.append(plate)
                name = profile_manager.get_name_by_plate(plate)
                if name: faces.append(name)
        except Exception as e: _LOGGER.error(f"Plate error: {e}")
    if enable_faces:
        try:
            enc, names = face_manager.flat_encodings_and_names()
            dfaces, _ = detect_faces(image, enc, names, 0.55)
            for f in dfaces: 
                if f not in faces: faces.append(f)
        except Exception as e: _LOGGER.error(f"Face error: {e}")
    return {"plates": plates, "faces": faces}

# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------
@app.get("/profiles")
async def list_profiles():
    return profile_manager.get_profiles()

@app.post("/profiles")
async def update_profile(data: ProfileUpdate):
    _LOGGER.info(f"Updating profile for: {data.name}")
    plate_list = [p.strip().upper() for p in data.plates.split(",") if p.strip()]
    profile_manager.update_profile(data.name.strip(), plate_list, data.user_id)
    _LOGGER.info(f"Profile {data.name} saved successfully.")
    return {"status": "ok"}

@app.delete("/profiles/{name}")
async def delete_profile(name: str):
    profile_manager.delete_profile(name)
    return {"status": "deleted"}

# ---------------------------------------------------------------------------
# HA Users (for dropdown in management UI)
# ---------------------------------------------------------------------------

class HaUsersUpdate(BaseModel):
    users: List[Dict]  # [{"name": "Max", "user_id": "abc123"}, ...]

@app.get("/ha_users")
async def get_ha_users():
    return profile_manager.get_ha_users()

@app.post("/ha_users")
async def set_ha_users(data: HaUsersUpdate):
    profile_manager.set_ha_users(data.users)
    return {"status": "ok", "count": len(data.users)}

# ---------------------------------------------------------------------------
# Faces
# ---------------------------------------------------------------------------
@app.get("/faces")
async def list_faces():
    return {"names": face_manager.known_names, "face_counts": face_manager.face_count()}

@app.post("/faces/register")
async def register_face(name: str = Form(...), image: UploadFile = File(...)):
    if not name.strip():
        raise HTTPException(422, "Name must not be empty.")
    image_bytes = await image.read()
    enc = encode_face_image(image_bytes)
    if not enc:
        raise HTTPException(422, "No face detected in the provided image. Please use a clear portrait photo with one visible face.")
    total = face_manager.add_face(name.strip(), enc)
    return {"name": name.strip(), "encodings_added": len(enc), "total": total}

@app.delete("/faces/{name}")
async def delete_face(name: str):
    face_manager.delete_face(name)
    return {"status": "deleted"}
