"""Config flow for Plate & Face Recognition (Add-on architecture)."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, selector

from .api_client import PlateRecognitionApiClient
from .const import (
    CONF_ADDON_URL,
    CONF_CAMERAS,
    CONF_ENABLE_FACES,
    CONF_ENABLE_PLATES,
    CONF_FACE_THRESHOLD,
    CONF_PLATE_MIN_CONFIDENCE,
    DEFAULT_ADDON_URL,
    DEFAULT_ENABLE_FACES,
    DEFAULT_ENABLE_PLATES,
    DEFAULT_FACE_THRESHOLD,
    DEFAULT_PLATE_MIN_CONFIDENCE,
    DOMAIN,
    MAX_CAMERAS,
    NAME,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema builders
# ---------------------------------------------------------------------------

def _step1_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Step 1: Add-on URL + connection test."""
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_ADDON_URL,
                default=d.get(CONF_ADDON_URL, DEFAULT_ADDON_URL),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
            ),
        }
    )


def _step2_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Step 2: Camera selection + options."""
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_CAMERAS,
                default=d.get(CONF_CAMERAS, []),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="camera", multiple=True)
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


def _options_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Combined schema for options flow (URL + cameras + settings)."""
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_ADDON_URL,
                default=d.get(CONF_ADDON_URL, DEFAULT_ADDON_URL),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
            ),
            vol.Required(
                CONF_CAMERAS,
                default=d.get(CONF_CAMERAS, []),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="camera", multiple=True)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _test_addon_connection(
    session: aiohttp.ClientSession, url: str
) -> bool:
    """Return True if the add-on responds to a health check."""
    client = PlateRecognitionApiClient(session, url)
    return await client.health_check()


def _validate_cameras(cameras: list[str]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not cameras:
        errors[CONF_CAMERAS] = "no_cameras"
    elif len(cameras) > MAX_CAMERAS:
        errors[CONF_CAMERAS] = "too_many_cameras"
    return errors


# ---------------------------------------------------------------------------
# Config flow (2-step: URL → cameras/options)
# ---------------------------------------------------------------------------

class PlateRecognitionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup config flow."""

    VERSION = 2

    def __init__(self) -> None:
        self._addon_url: str = DEFAULT_ADDON_URL

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 1 – enter add-on URL and verify connectivity."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_ADDON_URL]
            session = aiohttp_client.async_get_clientsession(self.hass)
            reachable = await _test_addon_connection(session, url)
            if not reachable:
                errors[CONF_ADDON_URL] = "cannot_connect"
            else:
                self._addon_url = url
                return await self.async_step_cameras()

        return self.async_show_form(
            step_id="user",
            data_schema=_step1_schema(user_input),
            errors=errors,
            description_placeholders={"max_cameras": str(MAX_CAMERAS)},
        )

    async def async_step_cameras(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 2 – select cameras and recognition options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_cameras(user_input.get(CONF_CAMERAS, []))
            if not errors:
                options = {CONF_ADDON_URL: self._addon_url, **user_input}
                return self.async_create_entry(
                    title=NAME,
                    data={},
                    options=options,
                )

        return self.async_show_form(
            step_id="cameras",
            data_schema=_step2_schema(user_input),
            errors=errors,
            description_placeholders={"max_cameras": str(MAX_CAMERAS)},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return PlateRecognitionOptionsFlow(config_entry)


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------

class PlateRecognitionOptionsFlow(config_entries.OptionsFlow):
    """Handle the options flow (Edit after initial setup)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate add-on connectivity
            url = user_input.get(CONF_ADDON_URL, DEFAULT_ADDON_URL)
            session = aiohttp_client.async_get_clientsession(self.hass)
            reachable = await _test_addon_connection(session, url)
            if not reachable:
                errors[CONF_ADDON_URL] = "cannot_connect"
            else:
                errors = _validate_cameras(user_input.get(CONF_CAMERAS, []))
                if not errors:
                    return self.async_create_entry(title="", data=user_input)

        current = dict(self._config_entry.options)
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(
                current if user_input is None else user_input
            ),
            errors=errors,
            description_placeholders={"max_cameras": str(MAX_CAMERAS)},
        )
