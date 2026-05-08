"""Async HTTP client for the Plate & Face Recognition Add-on REST API."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

# Timeout for image processing calls (OCR + face_recognition can be slow)
_DETECT_TIMEOUT = aiohttp.ClientTimeout(total=60)
_DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=15)
_HEALTH_TIMEOUT = aiohttp.ClientTimeout(total=5)


class PlateRecognitionApiClient:
    """
    Lightweight async HTTP client that talks to the add-on's FastAPI server.

    All heavy ML work (dlib, EasyOCR, OpenCV) runs inside the add-on
    container; the custom component only sends/receives JSON + image bytes.
    """

    def __init__(self, session: aiohttp.ClientSession, base_url: str) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Health / connectivity
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Return True if the add-on API responds with HTTP 200."""
        try:
            async with self._session.get(
                f"{self._base_url}/health",
                timeout=_HEALTH_TIMEOUT,
            ) as resp:
                return resp.status == 200
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("Add-on health check failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    async def detect(
        self,
        image_bytes: bytes,
        enable_plates: bool = True,
        enable_faces: bool = True,
        plate_min_confidence: float = 0.5,
        face_threshold: float = 0.55,
    ) -> dict[str, Any]:
        """
        Send *image_bytes* to the add-on for plate + face detection.

        Returns::

            {
                "plates": ["W AB 1234"],
                "faces": ["Alice"],
                "unknown_faces_count": 0,
            }
        """
        form = aiohttp.FormData()
        form.add_field("image", image_bytes, content_type="image/jpeg")
        form.add_field("enable_plates", str(enable_plates).lower())
        form.add_field("enable_faces", str(enable_faces).lower())
        form.add_field("plate_min_confidence", str(plate_min_confidence))
        form.add_field("face_threshold", str(face_threshold))

        async with self._session.post(
            f"{self._base_url}/detect",
            data=form,
            timeout=_DETECT_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    # ------------------------------------------------------------------
    # Face management
    # ------------------------------------------------------------------

    async def list_faces(self) -> dict[str, Any]:
        """Return full face list response from the add-on."""
        async with self._session.get(
            f"{self._base_url}/faces",
            timeout=_DEFAULT_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def face_count(self) -> dict[str, int]:
        """Return per-name encoding count mapping."""
        async with self._session.get(
            f"{self._base_url}/faces/count",
            timeout=_DEFAULT_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def register_face(self, name: str, image_bytes: bytes) -> dict[str, Any]:
        """
        Register a face in the add-on database.

        Raises :class:`aiohttp.ClientResponseError` (422) if no face is detected
        in the image.
        """
        form = aiohttp.FormData()
        form.add_field("name", name)
        form.add_field("image", image_bytes, content_type="image/jpeg")

        async with self._session.post(
            f"{self._base_url}/faces/register",
            data=form,
            timeout=_DETECT_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def delete_face(self, name: str) -> bool:
        """Delete a face from the add-on database. Returns True on success."""
        async with self._session.delete(
            f"{self._base_url}/faces/{name}",
            timeout=_DEFAULT_TIMEOUT,
        ) as resp:
            return resp.status == 200

    # ------------------------------------------------------------------
    # Profile management
    # ------------------------------------------------------------------

    async def get_profiles(self) -> list[dict[str, Any]]:
        """Return all person profiles from the add-on."""
        async with self._session.get(
            f"{self._base_url}/profiles",
            timeout=_DEFAULT_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def update_profile(self, name: str, plates: str = "", user_id: str | None = None) -> bool:
        """Create or update a person profile (plates + user link)."""
        payload = {
            "name": name,
            "plates": plates,
            "user_id": user_id,
        }
        async with self._session.post(
            f"{self._base_url}/profiles",
            json=payload,
            timeout=_DEFAULT_TIMEOUT,
        ) as resp:
            return resp.status == 200

    async def delete_profile(self, name: str) -> bool:
        """Delete a person profile from the add-on."""
        async with self._session.delete(
            f"{self._base_url}/profiles/{name}",
            timeout=_DEFAULT_TIMEOUT,
        ) as resp:
            return resp.status == 200
