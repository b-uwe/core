"""Config flow for the Music Favorites integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DEFAULT_MAX_DISTANCE_KM, DOMAIN
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
        """Handle configuration import from YAML setup and forward to user flow.

        This method is called when the integration is configured via YAML in
        configuration.yaml. It provides a bridge between YAML-based setup and
        the standard UI config flow, ensuring consistent behavior regardless
        of configuration method.
        We can ofc. only do this because the Flow doesn't include any user input.
        So, this will break should we ever consider a more sophisticated Config Flow.

        YAML Integration Flow:
        1. async_setup() detects YAML config → Triggers async_init() with source="import"
        2. Config flow system → Calls this async_step_import() method
        3. Forward to user flow → Delegates to async_step_user() for actual setup
        4. Config entry created → Integration becomes available with empty favorites

        Args:
            imported_data: Optional YAML configuration data (currently unused as
                          YAML schema only allows empty dict, reserved for future use)

        Returns:
            ConfigFlowResult: Result from async_step_user() - either form display or entry creation

        Side Effects:
            - Delegates to async_step_user() → May create config entry immediately
            - No validation needed → YAML schema already validated input
        """

        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the main UI config flow with connectivity validation and config entry creation.

        This method implements the core config flow logic for both UI-initiated and
        YAML-imported setups. It presents a minimal form to the user and performs
        essential connectivity validation before creating the config entry.

        Config Flow Logic:
        1. Set unique ID → Prevents multiple integration instances (enforces single instance)
        2. Show empty form → User confirms setup (no actual input required currently)
        3. Validate connectivity → Test MusicBrainz API access before setup
        4. Create config entry → Initialize integration with empty favorites and default settings

        Connectivity Validation:
        - Tests MusicBrainz API → Ensures external dependency is accessible
        - Comprehensive error handling → Provides specific error messages for different failure types
        - Fail-fast approach → Prevents config entry creation if API unavailable

        Error Handling Categories:
        - MusicBrainzError → API-specific errors (rate limits, API down)
        - ClientConnectorError → Network connectivity issues
        - ClientError → General HTTP client problems
        - TimeoutError → Request timeout scenarios
        - Exception → Catch-all for unexpected errors

        Args:
            user_input: User form submission data (None for initial form display,
                       empty dict {} after form submission due to empty schema)

        Returns:
            ConfigFlowResult: Either form display (if user_input is None or errors occurred)
                             or config entry creation (if connectivity test passed)

        Side Effects:
            - Sets unique ID → Prevents duplicate config entries
            - Tests external API → May fail if MusicBrainz unavailable
            - Creates config entry → Triggers async_setup_entry() and integration initialization
        """
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
                "favorites": {},
                "distance_filter": DEFAULT_MAX_DISTANCE_KM,
            },
        )
