"""Data update coordinator for Plate & Face Recognition (Add-on architecture).

Instead of running ML locally, this coordinator sends camera images to the
add-on REST API and stores the JSON results in self.data.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp
from homeassistant.components.camera import async_get_image
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api_client import PlateRecognitionApiClient
from .const import (
    ATTR_CAMERA,
    ATTR_FACES,
    ATTR_IMAGE_TIMESTAMP,
    ATTR_LAST_UPDATE,
    ATTR_PLATES,
    ATTR_UNKNOWN_COUNT,
    CONF_ADDON_URL,
    CONF_CAMERAS,
    CONF_ENABLE_FACES,
    CONF_ENABLE_PLATES,
    CONF_FACE_THRESHOLD,
    CONF_PLATE_MIN_CONFIDENCE,
    DATA_KEY_KNOWN_FACES,
    DEFAULT_ADDON_URL,
    DEFAULT_ENABLE_FACES,
    DEFAULT_ENABLE_PLATES,
    DEFAULT_FACE_THRESHOLD,
    DEFAULT_PLATE_MIN_CONFIDENCE,
    DOMAIN,
    EVENT_FACE_DETECTED,
    EVENT_PLATE_DETECTED,
)

_LOGGER = logging.getLogger(__name__)


class PlateRecognitionCoordinator(DataUpdateCoordinator):
    """
    Coordinator that subscribes to camera state-change events.

    When a camera entity updates its state (new image available), the
    coordinator fetches the image, POSTs it to the add-on REST API, and
    stores the detection results in ``self.data``.

    ``self.data`` structure::

        {
            "camera.front_door": {
                "camera_entity_id": "camera.front_door",
                "plates": ["W AB 1234"],
                "faces": ["Alice"],
                "unknown_faces_count": 0,
                "last_update": "2024-...",
                "image_timestamp": "2024-...",
            },
            "_known_faces": {
                "names": ["Alice", "Bob"],
                "total": 2,
                "face_counts": {"Alice": 2, "Bob": 1},
            },
        }
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_id: str,
        options: dict[str, Any],
    ) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN)
        self._config_entry_id = config_entry_id
        self._options = options

        # REST API client (shared aiohttp session from HA)
        session = aiohttp_client.async_get_clientsession(hass)
        addon_url = options.get(CONF_ADDON_URL, DEFAULT_ADDON_URL)
        self.api = PlateRecognitionApiClient(session, addon_url)

        # Initialise data store
        self.data: dict[str, Any] = {
            cam: _empty_result(cam)
            for cam in options.get(CONF_CAMERAS, [])
        }
        self.data[DATA_KEY_KNOWN_FACES] = {
            "names": [],
            "total": 0,
            "face_counts": {},
        }

        self._unsub_state_listener: list[Any] = []
        self._processing: set[str] = set()

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

        # Pre-fetch known faces once at startup
        await self._refresh_known_faces()

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
            return

        if entity_id in self._processing:
            _LOGGER.debug("Already processing %s – skipping.", entity_id)
            return

        self.hass.async_create_task(
            self._process_camera(entity_id, new_state)
        )

    async def _process_camera(self, entity_id: str, state: Any) -> None:
        """Fetch image and POST it to the add-on for recognition."""
        self._processing.add(entity_id)
        try:
            image_bytes = await self._fetch_camera_image(entity_id)
            if image_bytes is None:
                return

            enable_plates: bool = self._options.get(CONF_ENABLE_PLATES, DEFAULT_ENABLE_PLATES)
            enable_faces: bool = self._options.get(CONF_ENABLE_FACES, DEFAULT_ENABLE_FACES)
            plate_confidence: float = self._options.get(CONF_PLATE_MIN_CONFIDENCE, DEFAULT_PLATE_MIN_CONFIDENCE)
            face_tolerance: float = self._options.get(CONF_FACE_THRESHOLD, DEFAULT_FACE_THRESHOLD)

            # ----------------------------------------------------------------
            # Call the add-on API – no local ML, purely async HTTP
            # ----------------------------------------------------------------
            detection = await self.api.detect(
                image_bytes,
                enable_plates=enable_plates,
                enable_faces=enable_faces,
                plate_min_confidence=plate_confidence,
                face_threshold=face_tolerance,
            )

            plates: list[str] = detection.get("plates", [])
            faces: list[str] = detection.get("faces", [])
            unknown_count: int = detection.get("unknown_faces_count", 0)

            now = datetime.now(timezone.utc).isoformat()
            result: dict[str, Any] = {
                ATTR_CAMERA: entity_id,
                ATTR_PLATES: plates,
                ATTR_FACES: faces,
                ATTR_UNKNOWN_COUNT: unknown_count,
                ATTR_LAST_UPDATE: now,
                ATTR_IMAGE_TIMESTAMP: (
                    state.last_changed.isoformat() if state.last_changed else now
                ),
            }

            self.data[entity_id] = result
            self.async_set_updated_data(dict(self.data))

            # ----------------------------------------------------------------
            # Fire HA events for automations
            # ----------------------------------------------------------------
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
                entity_id, plates, faces, unknown_count,
            )

        except aiohttp.ClientError as exc:
            _LOGGER.error(
                "Add-on API unreachable while processing camera %s: %s", entity_id, exc
            )
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("Error processing camera %s: %s", entity_id, exc)
        finally:
            self._processing.discard(entity_id)

    # ------------------------------------------------------------------
    # Known-faces refresh
    # ------------------------------------------------------------------

    async def _refresh_known_faces(self) -> None:
        """Fetch the current known-faces list from the add-on."""
        try:
            data = await self.api.list_faces()
            self.data[DATA_KEY_KNOWN_FACES] = data
            self.async_set_updated_data(dict(self.data))
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Could not refresh known faces from add-on: %s", exc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _fetch_camera_image(self, entity_id: str) -> bytes | None:
        """Fetch the current image from a camera entity."""
        try:
            image = await async_get_image(self.hass, entity_id, timeout=10)
            return image.content
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Could not fetch image from %s: %s", entity_id, exc)
            return None

    def get_camera_result(self, entity_id: str) -> dict[str, Any]:
        """Return the latest recognition result for *entity_id*."""
        return self.data.get(entity_id, _empty_result(entity_id))

    def get_known_faces(self) -> dict[str, Any]:
        """Return the current known-faces data dict."""
        return self.data.get(
            DATA_KEY_KNOWN_FACES,
            {"names": [], "total": 0, "face_counts": {}},
        )


def _empty_result(entity_id: str) -> dict[str, Any]:
    return {
        ATTR_CAMERA: entity_id,
        ATTR_PLATES: [],
        ATTR_FACES: [],
        ATTR_UNKNOWN_COUNT: 0,
        ATTR_LAST_UPDATE: None,
        ATTR_IMAGE_TIMESTAMP: None,
    }
