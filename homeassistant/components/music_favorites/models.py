"""Data models for the Music Favorites integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# The main favorites storage - a hopefully smart structure for fast lookups and variants
# Format: {"MusicBrainz ID": ["Display Name", "variant1", "variant2", ...]}
favorites: dict[str, list[str]] = {
    "f0d05c64-9959-4ae1-899b-acf51b97638c": ["Dyscarnate"],
    "f9b57146-c5ce-41ad-adfb-ee904a4f7b19": ["Misery Index"],
    "ab81255c-7a4f-4528-bb77-4a3fbd8e8317": ["Jungle Rot"],
}


async def add_favorite(
    hass: HomeAssistant,
    entry: ConfigEntry,
    name: str,
    favorite_type: str,
    musicbrainz_id: str,
) -> None:
    """Add a new favorite to the collection."""
    _LOGGER.debug("Adding favorite: %s (%s) - %s", name, favorite_type, musicbrainz_id)

    # Get current favorites
    current_favorites = dict(entry.data.get("favorites", {}))

    # Check if already exists
    if musicbrainz_id in current_favorites:
        raise ServiceValidationError(
            f"Favorite with MusicBrainz ID {musicbrainz_id} already exists"
        )

    # Add new favorite
    current_favorites[musicbrainz_id] = [name]

    # Update the config entry
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "favorites": current_favorites}
    )

    # For additions, we need to reload the platform to create new entities
    # This is the cleanest way to handle dynamic entity addition
    await hass.config_entries.async_reload(entry.entry_id)

    _LOGGER.info("Successfully added favorite: %s", name)


async def remove_favorite(
    hass: HomeAssistant,
    entry: ConfigEntry,
    name: str,
) -> None:
    """Remove a favorite from the collection."""
    _LOGGER.debug("Removing favorite: %s", name)

    # Get current favorites
    current_favorites = dict(entry.data.get("favorites", {}))

    # Find the favorite by name (case insensitive)
    musicbrainz_id_to_remove = None
    for musicbrainz_id, names in current_favorites.items():
        if any(stored_name.lower() == name.lower() for stored_name in names):
            musicbrainz_id_to_remove = musicbrainz_id
            break

    if musicbrainz_id_to_remove is None:
        raise ServiceValidationError(f"Favorite '{name}' not found")

    # Remove the favorite
    del current_favorites[musicbrainz_id_to_remove]

    # Update the config entry
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "favorites": current_favorites}
    )

    # Remove the old entity from entity registry
    entity_registry = er.async_get(hass)

    # Find and remove the entity for this favorite
    unique_id = f"music_favorites_favorite_{musicbrainz_id_to_remove}"
    if entity_id := entity_registry.async_get_entity_id(
        "sensor", "music_favorites", unique_id
    ):
        entity_registry.async_remove(entity_id)

    _LOGGER.info("Successfully removed favorite: %s", name)
