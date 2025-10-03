"""Config flow for the Music Favorites integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DEFAULT_MAX_DISTANCE_KM, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Schema for adding a new favorite band/artist
STEP_USER_DATA_SCHEMA = vol.Schema({})


class MusicFavoritesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Music Favorites."""

    VERSION = 1

    async def _test_connectivity_and_create_entry(self) -> ConfigFlowResult:
        """Create config entry with default settings.

        This shared method handles the core logic for both UI and YAML flows:
        1. Creates config entry with default settings

        Note: Connectivity validation is performed later in async_setup_entry()
        which allows for proper retry handling via ConfigEntryNotReady.

        Returns:
            ConfigFlowResult: Config entry creation result

        Raises:
            No exceptions - all errors are caught and converted to ConfigFlowResult
        """
        _LOGGER.debug("Creating Config Entry with default settings")

        return self.async_create_entry(
            title="Music Favorites",
            data={
                "favorites": {
                    "17b53d9f-5c63-4a09-a593-dde4608e0db9": {
                        "variants": ["The Kinks"],
                        "status": "Disbanded",
                        "events": [],
                        "musicbrainz_url": "https://musicbrainz.org/artist/17b53d9f-5c63-4a09-a593-dde4608e0db9",
                        "allmusic_url": "https://www.allmusic.com/artist/mn0000100160",
                        "discogs_url": "https://www.discogs.com/artist/94078",
                        "songkick_url": "https://www.songkick.com/artists/442154",
                    }
                },
                "distance_filter": DEFAULT_MAX_DISTANCE_KM,
            },
        )

    async def async_step_import(
        self, _imported_data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle configuration import from YAML setup with direct config entry creation.

        This method is called when the integration is configured via YAML in
        configuration.yaml. It skips the UI form and creates the config entry
        directly.

        YAML Integration Flow:
        1. async_setup() detects YAML config → Triggers async_init() with source="import"
        2. Config flow system → Calls this async_step_import() method
        3. Set unique ID → Prevents multiple integration instances
        4. Create config entry → Integration becomes available with empty favorites

        Args:
            imported_data: Optional YAML configuration data (currently unused as
                          YAML schema only allows empty dict, reserved for future use)

        Returns:
            ConfigFlowResult: Either config entry creation or abort result (if already configured)

        Side Effects:
            - Sets unique ID → Prevents duplicate config entries
            - Creates config entry → Triggers async_setup_entry() and integration initialization
        """
        # Set unique ID to prevent multiple instances of this service integration
        await self.async_set_unique_id("music_favorites")
        self._abort_if_unique_id_configured()

        # Use shared method to create entry
        return await self._test_connectivity_and_create_entry()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the main UI config flow and config entry creation.

        This method implements the core config flow logic for UI-initiated setups.
        It presents a minimal form to the user and creates the config entry.

        Config Flow Logic:
        1. Set unique ID → Prevents multiple integration instances (enforces single instance)
        2. Show empty form → User confirms setup (no actual input required currently)
        3. Create config entry → Initialize integration with empty favorites and default settings

        Note: Connectivity validation is performed later in async_setup_entry()
        which allows for proper retry handling via ConfigEntryNotReady.

        Args:
            user_input: User form submission data (None for initial form display,
                       empty dict {} after form submission due to empty schema)

        Returns:
            ConfigFlowResult: Either form display (if user_input is None)
                             or config entry creation (if form submitted)

        Side Effects:
            - Sets unique ID → Prevents duplicate config entries
            - Creates config entry → Triggers async_setup_entry() and integration initialization
        """
        # Set unique ID to prevent multiple instances of this service integration
        await self.async_set_unique_id("music_favorites")
        self._abort_if_unique_id_configured()

        if user_input is None:
            # Show form to user (even though it's empty, we need the submit action)
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                description_placeholders={
                    "note": "The integration will test MusicBrainz connectivity during setup."
                },
            )

        # User submitted the form - use shared method to create entry
        return await self._test_connectivity_and_create_entry()
