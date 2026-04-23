"""Data update coordinator for Plate & Face Recognition."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.camera import async_get_image
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ATTR_CAMERA,
    ATTR_FACES,
    ATTR_IMAGE_TIMESTAMP,
    ATTR_LAST_UPDATE,
    ATTR_PLATES,
    ATTR_UNKNOWN_COUNT,
    CONF_CAMERAS,
    CONF_ENABLE_FACES,
    CONF_ENABLE_PLATES,
    CONF_FACE_THRESHOLD,
    CONF_PLATE_MIN_CONFIDENCE,
    DEFAULT_ENABLE_FACES,
    DEFAULT_ENABLE_PLATES,
    DEFAULT_FACE_THRESHOLD,
    DEFAULT_PLATE_MIN_CONFIDENCE,
    DOMAIN,
    EVENT_FACE_DETECTED,
    EVENT_PLATE_DETECTED,
)
from .face_manager import FaceManager
from .recognition import detect_faces, detect_license_plates

_LOGGER = logging.getLogger(__name__)


class PlateRecognitionCoordinator(DataUpdateCoordinator):
    """
    Coordinator that subscribes to camera state-change events.

    When a camera entity updates its state (new image available), the
    coordinator fetches the image and runs license-plate and face
    recognition.  Results are stored in ``self.data`` keyed by camera
    entity-id and consumed by sensor entities via listeners.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_id: str,
        options: dict[str, Any],
        face_manager: FaceManager,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            # No timed polling – we push updates on state changes
        )
        self._config_entry_id = config_entry_id
        self._options = options
        self.face_manager = face_manager

        # camera_entity_id → latest result dict
        self.data: dict[str, dict[str, Any]] = {
            cam: _empty_result(cam) for cam in options.get(CONF_CAMERAS, [])
        }

        self._unsub_state_listener: list[Any] = []
        self._processing: set[str] = set()  # prevent concurrent processing per camera

    # ------------------------------------------------------------------
    # Life-cycle
    # ------------------------------------------------------------------

    async def async_setup(self) -> None:
        """Subscribe to state changes for all configured cameras."""
        cameras: list[str] = self._options.get(CONF_CAMERAS, [])
        if not cameras:
            _LOGGER.warning("No cameras configured for %s.", DOMAIN)
            return

        unsub = async_track_state_change_event(
            self.hass, cameras, self._handle_camera_state_change
        )
        self._unsub_state_listener.append(unsub)
        _LOGGER.info(
            "Plate & Face Recognition subscribed to %d camera(s): %s",
            len(cameras),
            cameras,
        )

    async def async_unload(self) -> None:
        """Unsubscribe from state change events."""
        for unsub in self._unsub_state_listener:
            unsub()
        self._unsub_state_listener.clear()

    # ------------------------------------------------------------------
    # State-change handler
    # ------------------------------------------------------------------

    @callback
    def _handle_camera_state_change(self, event: Event) -> None:
        """Called when a tracked camera entity changes state."""
        entity_id: str = event.data["entity_id"]
        new_state = event.data.get("new_state")

        if new_state is None:
            return  # entity removed

        # Prevent concurrent processing of the same camera
        if entity_id in self._processing:
            _LOGGER.debug("Already processing %s – skipping.", entity_id)
            return

        # Schedule recognition in the background
        self.hass.async_create_task(
            self._process_camera(entity_id, new_state)
        )

    async def _process_camera(self, entity_id: str, state: Any) -> None:
        """Fetch image and run recognition for *entity_id*."""
        self._processing.add(entity_id)
        try:
            image_bytes = await self._fetch_camera_image(entity_id)
            if image_bytes is None:
                return

            enable_plates: bool = self._options.get(
                CONF_ENABLE_PLATES, DEFAULT_ENABLE_PLATES
            )
            enable_faces: bool = self._options.get(
                CONF_ENABLE_FACES, DEFAULT_ENABLE_FACES
            )
            plate_confidence: float = self._options.get(
                CONF_PLATE_MIN_CONFIDENCE, DEFAULT_PLATE_MIN_CONFIDENCE
            )
            face_tolerance: float = self._options.get(
                CONF_FACE_THRESHOLD, DEFAULT_FACE_THRESHOLD
            )

            plates: list[str] = []
            faces: list[str] = []
            unknown_count = 0

            # Run recognition in executor to avoid blocking the event loop
            if enable_plates:
                plates = await self.hass.async_add_executor_job(
                    detect_license_plates, image_bytes, plate_confidence
                )

            if enable_faces:
                encodings, names = self.face_manager.flat_encodings_and_names()
                faces, unknown_count = await self.hass.async_add_executor_job(
                    detect_faces, image_bytes, encodings, names, face_tolerance
                )

            now = datetime.now(timezone.utc).isoformat()
            result: dict[str, Any] = {
                ATTR_CAMERA: entity_id,
                ATTR_PLATES: plates,
                ATTR_FACES: faces,
                ATTR_UNKNOWN_COUNT: unknown_count,
                ATTR_LAST_UPDATE: now,
                ATTR_IMAGE_TIMESTAMP: state.last_changed.isoformat()
                if state.last_changed
                else now,
            }

            self.data[entity_id] = result
            self.async_set_updated_data(dict(self.data))

            # Fire HA events for automations
            if plates:
                self.hass.bus.async_fire(
                    EVENT_PLATE_DETECTED,
                    {"camera": entity_id, "plates": plates},
                )
            if faces:
                self.hass.bus.async_fire(
                    EVENT_FACE_DETECTED,
                    {"camera": entity_id, "faces": faces, "unknown": unknown_count},
                )

            _LOGGER.debug(
                "Camera %s → plates=%s, faces=%s, unknown=%d",
                entity_id,
                plates,
                faces,
                unknown_count,
            )

        except Exception as exc:
            _LOGGER.error("Error processing camera %s: %s", entity_id, exc)
        finally:
            self._processing.discard(entity_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _fetch_camera_image(self, entity_id: str) -> bytes | None:
        """Fetch the current image from a camera entity."""
        try:
            image = await async_get_image(self.hass, entity_id, timeout=10)
            return image.content
        except Exception as exc:
            _LOGGER.warning("Could not fetch image from %s: %s", entity_id, exc)
            return None

    def get_camera_result(self, entity_id: str) -> dict[str, Any]:
        """Return the latest recognition result for *entity_id*."""
        return self.data.get(entity_id, _empty_result(entity_id))


def _empty_result(entity_id: str) -> dict[str, Any]:
    return {
        ATTR_CAMERA: entity_id,
        ATTR_PLATES: [],
        ATTR_FACES: [],
        ATTR_UNKNOWN_COUNT: 0,
        ATTR_LAST_UPDATE: None,
        ATTR_IMAGE_TIMESTAMP: None,
    }
