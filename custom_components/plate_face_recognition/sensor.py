"""Sensor entities for Plate & Face Recognition."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_FACES,
    ATTR_IMAGE_TIMESTAMP,
    ATTR_LAST_UPDATE,
    ATTR_PLATES,
    ATTR_UNKNOWN_COUNT,
    CONF_CAMERAS,
    DOMAIN,
    NAME,
    SENSOR_TYPE_FACE,
    SENSOR_TYPE_PLATE,
    VERSION,
)
from .coordinator import PlateRecognitionCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities from a config entry."""
    coordinator: PlateRecognitionCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    cameras: list[str] = entry.options.get(
        CONF_CAMERAS, entry.data.get(CONF_CAMERAS, [])
    )

    entities: list[SensorEntity] = []
    for camera_entity_id in cameras:
        # Derive a clean slug from the camera entity id
        cam_slug = camera_entity_id.replace(".", "_").replace("-", "_")

        entities.append(
            LicensePlateSensor(coordinator, camera_entity_id, cam_slug, entry.entry_id)
        )
        entities.append(
            FaceSensor(coordinator, camera_entity_id, cam_slug, entry.entry_id)
        )

    # Also add a "known faces" sensor
    entities.append(KnownFacesSensor(coordinator, entry.entry_id))

    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Device info shared by all sensors of this entry
# ---------------------------------------------------------------------------

def _device_info(entry_id: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name=NAME,
        manufacturer="Community",
        model="Plate & Face Recognition",
        sw_version=VERSION,
    )


# ---------------------------------------------------------------------------
# License Plate Sensor
# ---------------------------------------------------------------------------

class LicensePlateSensor(CoordinatorEntity, SensorEntity):
    """Sensor that shows the currently detected license plate(s) for one camera."""

    _attr_icon = "mdi:car-info"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PlateRecognitionCoordinator,
        camera_entity_id: str,
        cam_slug: str,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._camera_entity_id = camera_entity_id
        self._cam_slug = cam_slug
        self._attr_unique_id = f"{entry_id}_{cam_slug}_{SENSOR_TYPE_PLATE}"
        self._attr_name = f"License Plate ({camera_entity_id})"
        self._attr_device_info = _device_info(entry_id)

    @property
    def native_value(self) -> str | None:
        """Return detected plate(s) as a comma-separated string."""
        result = self.coordinator.get_camera_result(self._camera_entity_id)
        plates: list[str] = result.get(ATTR_PLATES, [])
        return ", ".join(plates) if plates else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        result = self.coordinator.get_camera_result(self._camera_entity_id)
        return {
            "camera_entity_id": self._camera_entity_id,
            "plates_list": result.get(ATTR_PLATES, []),
            "last_update": result.get(ATTR_LAST_UPDATE),
            "image_timestamp": result.get(ATTR_IMAGE_TIMESTAMP),
        }

    @property
    def entity_id(self) -> str:  # type: ignore[override]
        return f"sensor.{self._cam_slug}_license_plate"

    @entity_id.setter
    def entity_id(self, value: str) -> None:  # type: ignore[override]
        self._attr_entity_id = value


# ---------------------------------------------------------------------------
# Face Sensor
# ---------------------------------------------------------------------------

class FaceSensor(CoordinatorEntity, SensorEntity):
    """Sensor that shows currently recognised person name(s) for one camera."""

    _attr_icon = "mdi:face-recognition"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PlateRecognitionCoordinator,
        camera_entity_id: str,
        cam_slug: str,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._camera_entity_id = camera_entity_id
        self._cam_slug = cam_slug
        self._attr_unique_id = f"{entry_id}_{cam_slug}_{SENSOR_TYPE_FACE}"
        self._attr_name = f"Detected Faces ({camera_entity_id})"
        self._attr_device_info = _device_info(entry_id)

    @property
    def native_value(self) -> str | None:
        """Return recognised name(s) as a comma-separated string."""
        result = self.coordinator.get_camera_result(self._camera_entity_id)
        faces: list[str] = result.get(ATTR_FACES, [])
        unknown: int = result.get(ATTR_UNKNOWN_COUNT, 0)

        parts = list(faces)
        if unknown > 0:
            parts.append(f"Unknown ({unknown})")

        return ", ".join(parts) if parts else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        result = self.coordinator.get_camera_result(self._camera_entity_id)
        return {
            "camera_entity_id": self._camera_entity_id,
            "recognised_names": result.get(ATTR_FACES, []),
            "unknown_faces": result.get(ATTR_UNKNOWN_COUNT, 0),
            "last_update": result.get(ATTR_LAST_UPDATE),
            "image_timestamp": result.get(ATTR_IMAGE_TIMESTAMP),
        }

    @property
    def entity_id(self) -> str:  # type: ignore[override]
        return f"sensor.{self._cam_slug}_detected_faces"

    @entity_id.setter
    def entity_id(self, value: str) -> None:  # type: ignore[override]
        self._attr_entity_id = value


# ---------------------------------------------------------------------------
# Known Faces Sensor
# ---------------------------------------------------------------------------

class KnownFacesSensor(CoordinatorEntity, SensorEntity):
    """Sensor that lists all registered faces in the database."""

    _attr_icon = "mdi:account-multiple"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PlateRecognitionCoordinator,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._attr_unique_id = f"{entry_id}_known_faces"
        self._attr_name = "Known Faces"
        self._attr_device_info = _device_info(entry_id)

    @property
    def native_value(self) -> str | None:
        """Return count of registered faces."""
        return str(len(self.coordinator.face_manager.known_names))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        face_counts = self.coordinator.face_manager.face_count()
        return {
            "names": self.coordinator.face_manager.known_names,
            "face_counts": face_counts,
        }

    @property
    def entity_id(self) -> str:  # type: ignore[override]
        return "sensor.plate_face_recognition_known_faces"

    @entity_id.setter
    def entity_id(self, value: str) -> None:  # type: ignore[override]
        self._attr_entity_id = value
