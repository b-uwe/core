"""Service implementations for Music Favorites integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN
from .models import add_favorite, remove_favorite
from .types import MusicFavoritesConfigEntry

_LOGGER = logging.getLogger(__name__)

# Service schemas
ADD_FAVORITE_SCHEMA = vol.Schema(
    {
        vol.Required("name"): str,
        vol.Required("musicbrainz_id"): str,
    }
)

REMOVE_FAVORITE_SCHEMA = vol.Schema(
    {
        vol.Required("name"): str,
    }
)


def _get_target_entry(
    hass: HomeAssistant, call: ServiceCall
) -> MusicFavoritesConfigEntry:
    """Get the target config entry for a service call."""
    config_entry_id = call.data.get("config_entry")
    if config_entry_id:
        target_entry = hass.config_entries.async_get_entry(config_entry_id)
        if not target_entry:
            raise ServiceValidationError(f"Config entry {config_entry_id} not found")
    else:
        # For voice commands, auto-find the music_favorites entry
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise ServiceValidationError("No Music Favorites integration found")
        target_entry = entries[0]  # Use the first (and typically only) entry

    if target_entry.state != ConfigEntryState.LOADED:
        raise ServiceValidationError(
            f"Config entry {target_entry.entry_id} is not loaded"
        )

    return target_entry


async def add_favorite_service(call: ServiceCall) -> None:
    """Add a new favorite to the collection."""
    _LOGGER.debug("add_favorite service called with data: %s", call.data)

    hass = call.hass  # Get hass from the call object
    target_entry = _get_target_entry(hass, call)

    _LOGGER.debug(
        "Adding favorite '%s' to entry %s",
        call.data["name"],
        target_entry.entry_id,
    )

    await add_favorite(
        hass,
        target_entry,
        call.data["name"],
        call.data["musicbrainz_id"],
    )

    _LOGGER.debug("Successfully added favorite '%s'", call.data["name"])


async def remove_favorite_service(call: ServiceCall) -> None:
    """Remove a favorite from the collection."""
    _LOGGER.debug("remove_favorite service called with data: %s", call.data)

    hass = call.hass  # Get hass from the call object
    target_entry = _get_target_entry(hass, call)

    _LOGGER.debug(
        "Removing favorite '%s' from entry %s", call.data["name"], target_entry.entry_id
    )

    await remove_favorite(hass, target_entry, call.data["name"])

    _LOGGER.debug("Successfully removed favorite '%s'", call.data["name"])


def register_services(hass: HomeAssistant) -> None:
    """Register all Music Favorites services."""
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
