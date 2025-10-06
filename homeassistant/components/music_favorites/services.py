"""Service implementations for Music Favorites integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN
from .datatypes import MusicFavoritesConfigEntry
from .models import add_favorite, remove_favorite

_LOGGER = logging.getLogger(__name__)

# Service schemas
ADD_FAVORITE_SCHEMA = vol.Schema(
    {
        vol.Required("musicbrainz_id"): str,
    }
)

REMOVE_FAVORITE_SCHEMA = vol.Schema(
    {
        vol.Required("musicbrainz_id"): str,
    }
)


def _get_target_entry(hass: HomeAssistant) -> MusicFavoritesConfigEntry:
    """Get and validate the Music Favorites config entry.

    This helper function retrieves the single Music Favorites config entry and validates
    it's loaded and ready for service calls.

    Music Favorites is a single-instance integration - there's only ever one config entry
    representing the user's local favorites list. This simplifies service handling and
    ensures consistent behavior across all service calls.

    Args:
        hass: Home Assistant instance for config entry access

    Returns:
        MusicFavoritesConfigEntry: Validated, loaded config entry ready for service operations

    Raises:
        ServiceValidationError: When integration not found, not loaded, or not ready
                              (becomes user-visible error message in service response)

    Validation Checks:
        - Config entry exists in system
        - Config entry is in LOADED state (not failed, unloaded, or setting up)
        - Integration is ready to handle service calls
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError("No Music Favorites integration found")

    entry = entries[0]
    if entry.state != ConfigEntryState.LOADED:
        raise ServiceValidationError("Music Favorites integration is not loaded")

    return entry


async def add_favorite_service(call: ServiceCall) -> None:
    """Add a new favorite to the collection via service call.

    This service handler processes add_favorite service calls from users, voice commands,
    and automations. It validates input, delegates to the add_favorite function, and
    ensures proper error handling for service responses.

    Service Integration Points:
    - Called by HA service system → When music_favorites.add_favorite service invoked
    - Validates config entry state → Ensures integration is loaded and ready
    - Delegates to add_favorite() → Triggers full data flow and UI synchronization
    - Returns success/failure → HA service system handles response to caller

    Args:
        call: ServiceCall object containing service data and Home Assistant instance

    Returns:
        None (service failure communicated via exceptions)

    Raises:
        ServiceValidationError: When validation fails (config entry not found/loaded,
                              favorite already exists, MusicBrainz API errors)

    Side Effects:
        - Calls add_favorite() → Full synchronization cascade across all platforms
        - Logs service execution → Debugging and monitoring purposes
    """
    _LOGGER.debug("add_favorite service called with data: %s", call.data)

    hass = call.hass
    entry = _get_target_entry(hass)

    _LOGGER.debug(
        "Adding favorite with MusicBrainz ID '%s'",
        call.data["musicbrainz_id"],
    )

    await add_favorite(
        hass,
        entry,
        call.data["musicbrainz_id"],
    )

    _LOGGER.debug(
        "Successfully added favorite with ID '%s'", call.data["musicbrainz_id"]
    )


async def remove_favorite_service(call: ServiceCall) -> None:
    """Remove a favorite from the collection via service call.

    This service handler processes remove_favorite service calls, validating input
    and delegating to the remove_favorite function for the complete removal flow.

    Flow:
    - Called by HA service system → When music_favorites.remove_favorite service invoked
    - Validates config entry state → Ensures integration is loaded and ready
    - Delegates to remove_favorite() → Triggers entity removal and UI synchronization

    UI Impact Flow:
    1. Service call → Validation → remove_favorite() called
    2. Config entry updated → All platforms notified via listeners
    3. Entity removed from registry → Entity disappears from UI immediately
    4. Calendar cache updated → Concert events removed from calendar

    Args:
        call: ServiceCall object containing musicbrainz_id and Home Assistant instance

    Returns:
        None (service failure communicated via exceptions)

    Raises:
        ServiceValidationError: When validation fails (config entry not found/loaded,
                              favorite doesn't exist, or other removal errors)

    Side Effects:
        - Calls remove_favorite() → Full synchronization cascade across all platforms
        - Logs service execution → Debugging and monitoring purposes
    """
    _LOGGER.debug("remove_favorite service called with data: %s", call.data)

    hass = call.hass
    entry = _get_target_entry(hass)

    _LOGGER.debug(
        "Removing favorite with MusicBrainz ID '%s'",
        call.data["musicbrainz_id"],
    )

    await remove_favorite(hass, entry, call.data["musicbrainz_id"])

    _LOGGER.debug(
        "Successfully removed favorite with ID '%s'", call.data["musicbrainz_id"]
    )


def register_services(hass: HomeAssistant) -> None:
    """Register all Music Favorites services with Home Assistant's service registry.

    This function registers the integration's service handlers globally, making them
    available system-wide for users, automations, and voice commands.

    Services Registered:
    - music_favorites.add_favorite → Adds new favorite artist via MusicBrainz ID
    - music_favorites.remove_favorite → Removes existing favorite artist via MusicBrainz ID

    Service Features:
    - Schema validation → Input validated before handler called
    - Global availability → Services work from any context (UI, automations, voice)
    - Error handling → Service exceptions become user-visible messages

    Integration Points:
    - Called during async_setup() → Services available immediately after YAML/UI setup
    - Persistent registration → Services survive config entry reloads

    Args:
        hass: Home Assistant instance for service registry access

    Returns:
        None

    Side Effects:
        - Registers services in hass.services global registry
        - Services become available for external calls immediately
        - Schema validation configured for automatic input checking
    """
    _LOGGER.debug("Registering add_favorite service")
    hass.services.async_register(
        DOMAIN, "add_favorite", add_favorite_service, schema=ADD_FAVORITE_SCHEMA
    )

    _LOGGER.debug("Registering remove_favorite service")
    hass.services.async_register(
        DOMAIN,
        "remove_favorite",
        remove_favorite_service,
        schema=REMOVE_FAVORITE_SCHEMA,
    )
