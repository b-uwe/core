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
from .models import MusicFavoritesConfigEntry
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
    # We do not care about extra information! That's a choice for forward
    # compatibility!
    extra=vol.ALLOW_EXTRA,
)


async def _init_import_flow(hass: HomeAssistant) -> None:
    """Initialize config flow from YAML configuration.

    This internal helper function triggers the Home Assistant config flow system
    to create a config entry when the integration is loaded via YAML configuration.

    This function triggers the config flow which will
    eventually call async_setup_entry() and create all platform entities.

    Args:
        hass: Home Assistant instance that manages the config flow system

    Returns:
        None - This function has side effects on the HA config flow system

    Raises:
        UnknownFlow: Safely ignored - occurs during race conditions when multiple
                    initialization attempts happen simultaneously
    """
    try:
        # Trigger HA's config flow system to create a config entry via UI flow
        # context={"source": "import"} tells HA this comes from YAML import (not user-initiated)
        await hass.config_entries.flow.async_init(DOMAIN, context={"source": "import"})
    except UnknownFlow:
        # Ignore the error, it doesn't matter, as we're coming from IMPORT initialization
        _LOGGER.debug("Ignoring possible race condition when initializing Config Flow")


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up Music Favorites integration from YAML configuration.

    This function is called once during Home Assistant startup when the integration
    is listed in configuration.yaml. It performs global setup and triggers config
    entry creation if none exists.

    Flow:
    1. Register global services (add_favorite, remove_favorite)
    2. Check for existing config entries → Avoid duplicates
    3. If no entries exist → Trigger config flow → Creates config entry → Calls async_setup_entry()

    FAILURE CONDITIONS & EFFECTS:
    - This function should rarely fail as it performs minimal operations
    - If it returns False: Home Assistant marks the integration as failed to load
    - Effects of failure:
      * No services registered → Service calls will fail with "Service not found"
      * No config entries created → Integration unusable until manual intervention
      * Integration shows as "Failed to load" in UI
      * Any YAML config for this domain is ignored

    Args:
        hass: Home Assistant instance for service registration and config entry management
        _config: YAML configuration (currently unused, reserved for future config options)

    Returns:
        bool: True if setup successful (normal case), False if critical failure occurred
              (would prevent entire integration from functioning)

    Side Effects:
        - Registers global services in hass.services
        - May create a background task to initialize config flow
        - May trigger async_setup_entry() via config flow completion
    """
    _LOGGER.debug("Setting up Music Favorites")

    # Register all services
    register_services(hass)

    existing_entries = hass.config_entries.async_entries(DOMAIN)
    # We create an instance of the service - but only ONCE, hence the conditional
    if not existing_entries:
        _LOGGER.debug(
            "Creating initial Music Favorites Service to be managed from UI from there on"
        )
        # We're artificially running the Config Flow here once
        hass.async_create_task(_init_import_flow(hass))

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: MusicFavoritesConfigEntry
) -> bool:
    """Set up a Music Favorites config entry and initialize all platforms.

    This function is called after successful config flow completion and on
    restarts/reloads and performs the main setup of the integration's
    components and data structures.

    Setup Flow:
    1. Test MusicBrainz connectivity → Fail fast if unavailable
    2. Initialize data update coordinator → Manages external API polling
    3. Store runtime data in entry.runtime_data → Shared state for all platforms
    4. Forward setup to all platforms → Creates entities in each platform
    5. Register dummy update coordinator listener → Ensures automatic updates continue
    6. Start coordinator → Make sure it runs consistently in the background
    7. Initialize calendar cache → Filter concert events by distance from HA location

    CALENDAR CACHE EXPLANATION:
    The cache stores pre-filtered concert events from all favorites, applying distance
    filtering based on user settings and HA location. Events are collected from each
    favorite's Bandsintown data, enhanced with performer info, and filtered by distance.
    This avoids recalculating distances every time the calendar is accessed.
    Doing this LIVE would be too costly

    UI UPDATE POINTS:
    - Platform setup → Entities appear in UI immediately
    - Update Coordinator started → Entity states will update with fresh data (async)
    - Calendar cache populated → Calendar entity shows filtered concert events

    FAILURE CONDITIONS:
    This function always returns True in current implementation. It raises
    ConfigEntryNotReady instead of returning False. In HA architecture:
    - Returning False would mark config entry as failed setup (rare)
    - ConfigEntryNotReady allows HA to retry setup later (preferred for temp failures)
    - We use ConfigEntryNotReady because MusicBrainz outages are temporary and shouldn't require manual intervention

    Args:
        hass: Home Assistant instance for platform management and entity registration
        entry: Config entry containing user configuration and serving as data storage

    Returns:
        bool: Always True (function raises exceptions instead of returning False. See above)

    Raises:
        ConfigEntryNotReady: When MusicBrainz is temporarily unavailable
                           (HA will retry setup later automatically)

    Side Effects:
        - Creates entities in sensor, calendar, conversation, and select platforms
        - Starts background coordinator polling external APIs
        - Populates entry.runtime_data with shared components
        - Triggers UI updates as entities become available and populate with data
    """

    _LOGGER.debug("Setting up config entry: %s", entry.title)

    # Test MusicBrainz connectivity before setup
    _LOGGER.debug("Testing MusicBrainz connectivity during setup")
    try:
        musicbrainz_client = MusicBrainzClient(hass)
        await musicbrainz_client.search_artists("misery index", limit=1)
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

    # Initialize all platforms (sensor, calendar, conversation, select) - creates all entities
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    def dummy_listener() -> None:
        """Dummy listener to enable DataUpdateCoordinator automatic scheduling.

        TECHNICAL BACKGROUND:
        DataUpdateCoordinator only schedules future refresh cycles if it has registered
        listeners (see coordinator._schedule_refresh() method). The logic is:
        - if not self._listeners: return  # No scheduling!
        - if self._listeners: self._schedule_refresh()  # Schedule next run

        PROBLEM: Our entities don't inherit from CoordinatorEntity, so they don't
        register as listeners. Without listeners, coordinator runs once and stops.

        SOLUTION: Register a dummy listener that does nothing but ensures the
        coordinator continues its automatic scheduling every update_interval.

        ALTERNATIVES CONSIDERED:
        1. Make entities inherit from CoordinatorEntity - rejected because it would
           require restructuring data flow (entities would read from coordinator.data
           instead of config entry data)
        2. Manual scheduling - more complex and error-prone
        3. This dummy listener - simple, clean, preserves existing architecture
        """

    # Attach the dummy listener to ensure it running
    data_update_coordinator.async_add_listener(dummy_listener)

    # Start the coordinator with a quick first refresh AFTER platforms are set up
    await data_update_coordinator.async_config_entry_first_refresh()

    # Initialize filtered calendar cache after platforms are set up
    await update_filtered_calendar_cache(hass, entry)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MusicFavoritesConfigEntry
) -> bool:
    """Unload a config entry and clean up all associated resources.

    This function is called when a config entry is being removed or reloaded,
    ensuring proper cleanup of all platforms and background tasks.

    Cleanup Process:
    1. Unload all platforms → Removes all entities from UI immediately
    2. HA automatically stops coordinator → Background updates cease
    3. Config entry listeners cleaned → No more callbacks triggered
    4. Runtime data cleared → Temporary components garbage collected

    UI Impact:
    - All entities disappear from UI immediately
    - Services remain available (global registration)
    - Integration can be re-added without restart

    Args:
        hass: Home Assistant instance for platform management
        entry: Config entry being unloaded with associated platforms and data

    Returns:
        bool: True if unload successful, False if any platform failed to unload

    Side Effects:
        - All platform entities removed from UI
        - Background coordinator stopped automatically by HA
        - Runtime data cleared and references released
        - Config entry listeners automatically cleaned up
    """
    # The data update coordinator will be automatically stopped by Home Assistant
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
