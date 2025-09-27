"""Data models for the Music Favorites integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .musicbrainz import MusicBrainzClient, MusicBrainzError

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
    musicbrainz_id: str,
) -> None:
    """Add a new favorite to the collection."""
    _LOGGER.debug("Adding favorite with MusicBrainz ID: %s", musicbrainz_id)

    # Get current favorites
    current_favorites = dict(entry.data.get("favorites", {}))

    # Check if already exists
    if musicbrainz_id in current_favorites:
        raise ServiceValidationError(
            f"Favorite with MusicBrainz ID {musicbrainz_id} already exists"
        )

    # Fetch complete artist data from MusicBrainz
    client = MusicBrainzClient(hass)
    try:
        artist_data = await client.get_artist_by_id(musicbrainz_id)
    except MusicBrainzError as err:
        _LOGGER.error("Failed to fetch artist data for %s: %s", musicbrainz_id, err)
        raise ServiceValidationError(
            f"Could not fetch artist data from MusicBrainz: {err}"
        ) from err

    # Extract name and aliases from MusicBrainz response
    name = artist_data["name"]
    aliases = [
        alias.get("name", "")
        for alias in artist_data.get("aliases", [])
        if alias.get("name")  # Only include non-empty alias names
    ]

    # Add new favorite with name and aliases from MusicBrainz
    favorite_variants = [name]
    if aliases:
        favorite_variants.extend(aliases)
    current_favorites[musicbrainz_id] = favorite_variants

    # Update the config entry
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "favorites": current_favorites}
    )

    # Add the new entity dynamically using the entity manager
    # Only add entity if runtime_data exists and contains entity_manager
    # (during tests or before setup, this might not be available)
    if hasattr(entry, "runtime_data") and entry.runtime_data:
        entity_manager = entry.runtime_data.get("entity_manager")
        if entity_manager:
            _LOGGER.debug("Calling entity_manager.add_favorite_entity for %s", name)
            entity_manager.add_favorite_entity(musicbrainz_id, favorite_variants)
        else:
            _LOGGER.warning(
                "Entity manager not found in runtime_data - new entity will not be created immediately"
            )
    else:
        _LOGGER.warning(
            "No runtime_data available - new entity will not be created immediately"
        )

    _LOGGER.info("Successfully added favorite: %s", name)


async def remove_favorite(
    hass: HomeAssistant,
    entry: ConfigEntry,
    musicbrainz_id: str,
) -> None:
    """Remove a favorite from the collection."""
    _LOGGER.debug("Removing favorite with MusicBrainz ID: %s", musicbrainz_id)

    # Get current favorites
    current_favorites = dict(entry.data.get("favorites", {}))

    # Check if the favorite exists
    if musicbrainz_id not in current_favorites:
        raise ServiceValidationError(
            f"Favorite with MusicBrainz ID '{musicbrainz_id}' not found"
        )

    # Get the name for logging
    favorite_name = (
        current_favorites[musicbrainz_id][0]
        if current_favorites[musicbrainz_id]
        else "Unknown"
    )

    # Remove the favorite
    del current_favorites[musicbrainz_id]

    # Update the config entry
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "favorites": current_favorites}
    )

    # Remove the entity from entity registry
    entity_registry = er.async_get(hass)

    # Find and remove the entity for this favorite
    unique_id = f"favorite_{musicbrainz_id}"
    if entity_id := entity_registry.async_get_entity_id(
        "sensor", "music_favorites", unique_id
    ):
        entity_registry.async_remove(entity_id)

    _LOGGER.info("Successfully removed favorite: %s", favorite_name)


async def resolve_artist_from_name(
    hass: HomeAssistant,
    artist_name: str,
) -> dict[str, Any] | None:
    """Resolve artist name to MusicBrainz ID using the decision logic.

    Args:
        hass: Home Assistant instance
        artist_name: The artist name to search for

    Returns:
        Dictionary with one of:
        - {"action": "create", "name": "exact_name", "musicbrainz_id": "id"} - Exact match found
        - {"action": "choose", "options": [{"name": "...", "musicbrainz_id": "..."}, ...]} - Multiple matches
        - {"action": "not_found"} - No matches found
        - None if MusicBrainz API error
    """
    _LOGGER.debug("Resolving artist name: '%s'", artist_name)

    try:
        client = MusicBrainzClient(hass)
        matches = await client.search_artists(artist_name, limit=10)

        _LOGGER.debug(
            "MusicBrainz returned %d matches for '%s'", len(matches), artist_name
        )

        # Case 1: No matches found
        if len(matches) == 0:
            _LOGGER.info("No MusicBrainz matches found for '%s'", artist_name)
            return {"action": "not_found"}

        # Case 2: Exactly 1 match AND exact name match (case insensitive)
        if len(matches) == 1 and matches[0]["name"].lower() == artist_name.lower():
            _LOGGER.info(
                "Exact match found for '%s': %s (%s)",
                artist_name,
                matches[0]["name"],
                matches[0]["id"],
            )
            return {
                "action": "create",
                "name": matches[0]["name"],  # Use the exact name from MusicBrainz
                "musicbrainz_id": matches[0]["id"],
                "aliases": matches[0].get("aliases", []),
            }

        # Case 3: Multiple matches OR single match with different name
        _LOGGER.info(
            "Multiple matches found for '%s', user needs to choose", artist_name
        )
        options = [
            {
                "name": match["name"],
                "musicbrainz_id": match["id"],
                "disambiguation": match.get("disambiguation", ""),
                "score": match.get("score", 0),
                "aliases": match.get("aliases", []),
            }
            for match in matches[:5]  # Limit to top 5 options
        ]

        return {"action": "choose", "options": options}  # noqa: TRY300, conflicts ´with RET505 🤷

    except MusicBrainzError as err:
        _LOGGER.error(
            "MusicBrainz API error while resolving '%s': %s", artist_name, err
        )
        return None
    except Exception:
        # Broad catch for any unexpected errors during artist resolution
        _LOGGER.exception("Unexpected error while resolving '%s'", artist_name)
        return None
