"""Plate & Face Recognition – Home Assistant Custom Integration (Add-on architecture).

All ML work is delegated to the companion HA Add-on via REST API calls.
The custom component itself has zero heavy Python dependencies.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components.camera import async_get_image
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_CAMERA_ENTITY,
    ATTR_FACE_NAME,
    ATTR_FILE_PATH,
    CONF_CAMERAS,
    DOMAIN,
    SERVICE_CAPTURE_FACE,
    SERVICE_DELETE_FACE,
    SERVICE_LIST_FACES,
    SERVICE_REGISTER_FACE,
)
from .coordinator import PlateRecognitionCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Plate & Face Recognition from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    options = dict(entry.options)

    coordinator = PlateRecognitionCoordinator(
        hass,
        entry.entry_id,
        options,
    )
    await coordinator.async_setup()

    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _register_services(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: PlateRecognitionCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    await coordinator.async_unload()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

def _get_coordinator(hass: HomeAssistant) -> PlateRecognitionCoordinator:
    """Return the first available coordinator (single-entry assumption)."""
    for entry_data in hass.data.get(DOMAIN, {}).values():
        return entry_data["coordinator"]
    raise HomeAssistantError(f"{DOMAIN} is not configured.")


def _register_services(hass: HomeAssistant) -> None:
    """Register integration services (idempotent)."""

    if hass.services.has_service(DOMAIN, SERVICE_REGISTER_FACE):
        return  # Already registered

    # ----------------------------------------------------------------
    # register_face – register a new face from a file path
    # ----------------------------------------------------------------
    async def handle_register_face(call: ServiceCall) -> None:
        name: str = call.data[ATTR_FACE_NAME]
        file_path: str = call.data[ATTR_FILE_PATH]

        if not Path(file_path).is_file():
            raise HomeAssistantError(f"File not found: {file_path}")

        coordinator = _get_coordinator(hass)

        with open(file_path, "rb") as f:
            image_bytes = f.read()

        try:
            result = await coordinator.api.register_face(name, image_bytes)
        except Exception as exc:
            raise HomeAssistantError(
                f"Could not register face '{name}': {exc}"
            ) from exc

        _LOGGER.info(
            "Registered %d encoding(s) for '%s' (total: %d).",
            result.get("encodings_added", 0),
            name,
            result.get("total_encodings", 0),
        )
        # Refresh known-faces sensor
        await coordinator._refresh_known_faces()  # noqa: SLF001

    hass.services.async_register(
        DOMAIN,
        SERVICE_REGISTER_FACE,
        handle_register_face,
        schema=vol.Schema(
            {
                vol.Required(ATTR_FACE_NAME): cv.string,
                vol.Required(ATTR_FILE_PATH): cv.string,
            }
        ),
    )

    # ----------------------------------------------------------------
    # capture_face_from_camera – snapshot → register
    # ----------------------------------------------------------------
    async def handle_capture_face(call: ServiceCall) -> None:
        name: str = call.data[ATTR_FACE_NAME]
        camera_entity_id: str = call.data[ATTR_CAMERA_ENTITY]

        coordinator = _get_coordinator(hass)

        image = await async_get_image(hass, camera_entity_id, timeout=10)
        if image is None:
            raise HomeAssistantError(
                f"Could not capture image from camera '{camera_entity_id}'."
            )

        try:
            result = await coordinator.api.register_face(name, image.content)
        except Exception as exc:
            raise HomeAssistantError(
                f"Could not register face '{name}' from camera '{camera_entity_id}': {exc}"
            ) from exc

        _LOGGER.info(
            "Captured & registered %d face(s) for '%s' from %s.",
            result.get("encodings_added", 0),
            name,
            camera_entity_id,
        )
        await coordinator._refresh_known_faces()  # noqa: SLF001

    hass.services.async_register(
        DOMAIN,
        SERVICE_CAPTURE_FACE,
        handle_capture_face,
        schema=vol.Schema(
            {
                vol.Required(ATTR_FACE_NAME): cv.string,
                vol.Required(ATTR_CAMERA_ENTITY): cv.entity_id,
            }
        ),
    )

    # ----------------------------------------------------------------
    # delete_face – remove a person from the database
    # ----------------------------------------------------------------
    async def handle_delete_face(call: ServiceCall) -> None:
        name: str = call.data[ATTR_FACE_NAME]
        coordinator = _get_coordinator(hass)
        found = await coordinator.api.delete_face(name)
        if not found:
            raise HomeAssistantError(f"Face '{name}' not found in database.")
        await coordinator._refresh_known_faces()  # noqa: SLF001

    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_FACE,
        handle_delete_face,
        schema=vol.Schema({vol.Required(ATTR_FACE_NAME): cv.string}),
    )

    # ----------------------------------------------------------------
    # list_faces – fire an event listing all known faces
    # ----------------------------------------------------------------
    async def handle_list_faces(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        data = await coordinator.api.list_faces()
        names = data.get("names", [])
        counts = data.get("face_counts", {})
        hass.bus.async_fire(
            f"{DOMAIN}_faces_listed",
            {"names": names, "face_counts": counts},
        )
        _LOGGER.info("Known faces: %s", names)

    hass.services.async_register(DOMAIN, SERVICE_LIST_FACES, handle_list_faces)

    # ----------------------------------------------------------------
    # save_profile – associate name with plates and HA user
    # ----------------------------------------------------------------
    async def handle_save_profile(call: ServiceCall) -> None:
        name: str = call.data[ATTR_FACE_NAME]
        plates: str = call.data.get("plates", "")
        user_id: str | None = call.data.get("user_id")
        
        coordinator = _get_coordinator(hass)
        success = await coordinator.api.update_profile(name, plates, user_id)
        if not success:
            raise HomeAssistantError(f"Could not save profile for {name}")
        await coordinator._refresh_known_faces()

    hass.services.async_register(
        DOMAIN,
        "save_profile",
        handle_save_profile,
        schema=vol.Schema({
            vol.Required(ATTR_FACE_NAME): cv.string,
            vol.Optional("plates"): cv.string,
            vol.Optional("user_id"): vol.Any(cv.string, None),
        }),
    )

    # ----------------------------------------------------------------
    # delete_profile – remove a person profile
    # ----------------------------------------------------------------
    async def handle_delete_profile(call: ServiceCall) -> None:
        name: str = call.data[ATTR_FACE_NAME]
        coordinator = _get_coordinator(hass)
        await coordinator.api.delete_profile(name)
        await coordinator._refresh_known_faces()

    hass.services.async_register(
        DOMAIN,
        "delete_profile",
        handle_delete_profile,
        schema=vol.Schema({vol.Required(ATTR_FACE_NAME): cv.string}),
    )
