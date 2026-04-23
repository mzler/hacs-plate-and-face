"""Config flow for Plate & Face Recognition."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CAMERAS,
    CONF_ENABLE_FACES,
    CONF_ENABLE_PLATES,
    CONF_FACE_THRESHOLD,
    CONF_PLATE_MIN_CONFIDENCE,
    CONF_SCAN_INTERVAL,
    DEFAULT_ENABLE_FACES,
    DEFAULT_ENABLE_PLATES,
    DEFAULT_FACE_THRESHOLD,
    DEFAULT_PLATE_MIN_CONFIDENCE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_CAMERAS,
    NAME,
)

_LOGGER = logging.getLogger(__name__)


def _build_schema(
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    """Build the configuration schema with optional default values."""
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_CAMERAS,
                default=d.get(CONF_CAMERAS, []),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="camera",
                    multiple=True,
                )
            ),
            vol.Optional(
                CONF_ENABLE_PLATES,
                default=d.get(CONF_ENABLE_PLATES, DEFAULT_ENABLE_PLATES),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_ENABLE_FACES,
                default=d.get(CONF_ENABLE_FACES, DEFAULT_ENABLE_FACES),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_FACE_THRESHOLD,
                default=d.get(CONF_FACE_THRESHOLD, DEFAULT_FACE_THRESHOLD),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.1,
                    max=1.0,
                    step=0.05,
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            vol.Optional(
                CONF_PLATE_MIN_CONFIDENCE,
                default=d.get(CONF_PLATE_MIN_CONFIDENCE, DEFAULT_PLATE_MIN_CONFIDENCE),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.1,
                    max=1.0,
                    step=0.05,
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
        }
    )


def _validate(user_input: dict[str, Any]) -> dict[str, str]:
    """Return a dict of field → error key (empty means OK)."""
    errors: dict[str, str] = {}
    cameras = user_input.get(CONF_CAMERAS, [])
    if not cameras:
        errors[CONF_CAMERAS] = "no_cameras"
    elif len(cameras) > MAX_CAMERAS:
        errors[CONF_CAMERAS] = "too_many_cameras"
    return errors


class PlateRecognitionConfigFlow(
    config_entries.ConfigFlow, domain=DOMAIN
):
    """Handle the initial setup config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Show setup form to the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(
                    title=NAME,
                    data={},          # static config
                    options=user_input,  # everything goes into options (editable)
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(user_input),
            errors=errors,
            description_placeholders={"max_cameras": str(MAX_CAMERAS)},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return PlateRecognitionOptionsFlow(config_entry)


class PlateRecognitionOptionsFlow(config_entries.OptionsFlow):
    """Handle the options flow (Edit after initial setup)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        current = dict(self._config_entry.options)
        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(current if user_input is None else user_input),
            errors=errors,
            description_placeholders={"max_cameras": str(MAX_CAMERAS)},
        )
