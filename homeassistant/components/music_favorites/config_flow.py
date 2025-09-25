"""Config flow for the Music Favorites integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN
from .models import favorites

_LOGGER = logging.getLogger(__name__)

# Schema for adding a new favorite band/artist
STEP_USER_DATA_SCHEMA = vol.Schema({})


class MusicFavoritesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Music Favorites."""

    VERSION = 1

    async def async_step_import(
        self, imported_data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle import from YAML configuration. Just forwarding..."""

        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the UI Config Flow Creation - which comes without a form."""

        # Set unique ID to prevent multiple instances of this service integration
        await self.async_set_unique_id("music_favorites")
        self._abort_if_unique_id_configured()

        _LOGGER.debug("Creating default Config Entry for first time use")

        return self.async_create_entry(
            title="Music Favorites", data={"favorites": favorites}
        )
