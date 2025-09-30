"""The Music Favorites integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import UnknownFlow
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType

from .calendar_utils import update_filtered_calendar_cache
from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from .coordinator import MusicFavoritesCoordinator
from .datatypes import MusicFavoritesConfigEntry
from .musicbrainz import MusicBrainzClient, MusicBrainzError
from .services import register_services

_LOGGER = logging.getLogger(__name__)


_LOGGER.debug("Music Favorites module imported!")


_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.CONVERSATION,
    Platform.CALENDAR,
    Platform.SELECT,
]

# Make this integration be accessible from both UI as well as YAML
# TO DO: Long term goal would be make YAML imported config immutable
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                # YAML configuration schema:
                # TBD! For now, it just creates three arbitrary favorites
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def _init_flow(hass: HomeAssistant) -> None:
    """Internal Helper function! Used to call the Config Flow Initialization from the YAML initialization."""
    try:
        await hass.config_entries.flow.async_init(DOMAIN, context={"source": "import"})
    except UnknownFlow:
        # Ignore the error, it doesn't matter, as we're coming from IMPORT initialization
        _LOGGER.debug("Ignoring possible race condition when initializing Config Flow")


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up Music Favorites."""
    _LOGGER.debug("Setting up Music Favorites")

    # Register all services
    register_services(hass)

    # We are not registered in the Integrations list, hence we can only load via
    # configuration.yaml.
    # When this loads we create an instance of the service - but only ONCE, hence
    # the conditional
    existing_entries = hass.config_entries.async_entries(DOMAIN)
    if not existing_entries:
        _LOGGER.debug(
            "Creating initial Music Favorites Service to be managed from UI from there on"
        )
        # We're artificially running the Config Flow here once
        hass.async_create_task(_init_flow(hass))

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: MusicFavoritesConfigEntry
) -> bool:
    """Set up a Music Favorites Config Entry."""

    _LOGGER.debug("Setting up config entry: %s", entry.title)

    # Test MusicBrainz connectivity before setup
    _LOGGER.debug("Testing MusicBrainz connectivity during setup")
    try:
        musicbrainz_client = MusicBrainzClient(hass)
        await musicbrainz_client.search_artists("test", limit=1)
        _LOGGER.debug("MusicBrainz connectivity confirmed during setup")

    except MusicBrainzError as err:
        _LOGGER.warning("MusicBrainz unavailable during setup: %s", err)
        raise ConfigEntryNotReady(f"MusicBrainz service unavailable: {err}") from err

    except Exception as err:
        _LOGGER.exception("Unexpected error testing MusicBrainz connectivity")
        raise ConfigEntryNotReady(
            f"Failed to verify MusicBrainz connectivity: {err}"
        ) from err

    # Initialize data update coordinator
    data_update_coordinator = MusicFavoritesCoordinator(hass, entry)

    # Initialize runtime data dict with coordinator and other components
    entry.runtime_data = {
        "update_interval": DEFAULT_UPDATE_INTERVAL,
        "musicbrainz_client": musicbrainz_client,
        "data_update_coordinator": data_update_coordinator,
        "filtered_calendar_events": [],  # Cache for distance-filtered events
    }

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    # CRITICAL: Add a dummy listener to ensure coordinator schedules future updates
    #
    # TECHNICAL BACKGROUND:
    # DataUpdateCoordinator only schedules future refresh cycles if it has registered
    # listeners (see coordinator._schedule_refresh() method). The logic is:
    # - if not self._listeners: return  # No scheduling!
    # - if self._listeners: self._schedule_refresh()  # Schedule next run
    #
    # PROBLEM: Our entities don't inherit from CoordinatorEntity, so they don't
    # register as listeners. Without listeners, coordinator runs once and stops.
    #
    # SOLUTION: Register a dummy listener that does nothing but ensures the
    # coordinator continues its automatic scheduling every update_interval.
    #
    # ALTERNATIVES CONSIDERED:
    # 1. Make entities inherit from CoordinatorEntity - rejected because it would
    #    require restructuring data flow (entities would read from coordinator.data
    #    instead of config entry data)
    # 2. Manual scheduling - more complex and error-prone
    # 3. This dummy listener - simple, clean, preserves existing architecture
    def dummy_listener() -> None:
        """Dummy listener to enable DataUpdateCoordinator automatic scheduling.

        This function intentionally does nothing. Its sole purpose is to ensure
        the coordinator has at least one registered listener, which triggers
        the coordinator's internal scheduling mechanism for future updates.
        """

    data_update_coordinator.async_add_listener(dummy_listener)

    # Start the coordinator with a quick first refresh AFTER platforms are set up
    await data_update_coordinator.async_config_entry_first_refresh()

    # Initialize filtered calendar cache after platforms are set up
    await update_filtered_calendar_cache(hass, entry)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MusicFavoritesConfigEntry
) -> bool:
    """Unload a config entry."""
    # The data update coordinator will be automatically stopped by Home Assistant
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
