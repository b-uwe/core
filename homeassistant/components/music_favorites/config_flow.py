"""Config flow for the Music Favorites integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DEFAULT_MAX_DISTANCE_KM, DOMAIN
from .models import favorites
from .musicbrainz import MusicBrainzClient, MusicBrainzError

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
        """Handle the UI Config Flow Creation - which comes with a super simplistic form."""
        errors: dict[str, str] = {}

        # Set unique ID to prevent multiple instances of this service integration
        await self.async_set_unique_id("music_favorites")
        self._abort_if_unique_id_configured()

        if user_input is None:
            # Show form to user (even though it's empty, we need the submit action)
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
                description_placeholders={
                    "note": "The integration will test MusicBrainz connectivity during setup."
                },
            )

        # User submitted the form - now test MusicBrainz connectivity
        _LOGGER.debug("Testing MusicBrainz connectivity before creating config entry")

        try:
            # Test MusicBrainz connectivity with a simple search
            client = MusicBrainzClient(self.hass)
            await client.search_artists("test", limit=1)
            _LOGGER.debug("MusicBrainz connectivity test successful")

        except MusicBrainzError as err:
            _LOGGER.error("MusicBrainz API error during connectivity test: %s", err)
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
                description_placeholders={
                    "note": "MusicBrainz API returned an error. Please try again later."
                },
            )

        except aiohttp.ClientConnectorError as err:
            _LOGGER.warning("Cannot reach MusicBrainz server: %s", err)
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
                description_placeholders={
                    "note": "Cannot reach MusicBrainz servers. Please check your internet connection."
                },
            )

        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP client error during MusicBrainz test: %s", err)
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
                description_placeholders={
                    "note": "Network error connecting to MusicBrainz. Please try again."
                },
            )

        except TimeoutError:
            _LOGGER.error("Timeout connecting to MusicBrainz")
            errors["base"] = "timeout"
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
                description_placeholders={
                    "note": "Connection to MusicBrainz timed out. Please try again."
                },
            )

        except Exception:
            _LOGGER.exception("Unexpected error during MusicBrainz connectivity test")
            errors["base"] = "unknown"
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
                description_placeholders={
                    "note": "An unexpected error occurred during setup."
                },
            )

        # Connectivity test passed - create the config entry
        _LOGGER.debug("Creating default Config Entry for first time use")

        return self.async_create_entry(
            title="Music Favorites",
            data={
                "favorites": favorites,
                "distance_filter": DEFAULT_MAX_DISTANCE_KM,
            },
        )
