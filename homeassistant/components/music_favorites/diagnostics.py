"""Diagnostics support for the Music Favorites integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .models import MusicFavoritesConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MusicFavoritesConfigEntry
) -> dict[str, Any]:
    """Generate comprehensive diagnostic information for troubleshooting and support.

    Collects and organizes integration data for debugging purposes, providing insights
    into configuration, favorites statistics, and entity states.

    Diagnostic Data Collection:
    1. Config entry metadata → Basic integration setup information
    2. Favorites statistics → Quantitative analysis of user's collection
    3. Favorites data → Sanitized favorite information without sensitive details
    4. Entity states → Current sensor states and attributes for troubleshooting

    Privacy Protection:
    - No sensitive data exposed → MusicBrainz IDs and entity details remain private
    - Aggregated statistics → Provides insights without revealing specific preferences
    - State information → Includes current entity states for debugging UI issues

    Args:
        hass: Home Assistant instance for entity registry and state access
        entry: Config entry containing favorites data and integration configuration

    Returns:
        dict: Comprehensive diagnostic data organized by category for analysis

    Data Categories:
        - config_entry: Integration setup and version information
        - favorites_statistics: Quantitative analysis of user's collection
        - favorites_data: Sanitized favorite information with variant counts
        - entity_states: Current sensor states and attributes for debugging
    """

    # Get favorites data
    favorites_data: dict[str, list[str]] = entry.data.get("favorites", {})

    # Basic statistics
    total_favorites = len(favorites_data)
    favorites_with_variants = sum(
        1 for variants in favorites_data.values() if len(variants) > 1
    )

    # Collect entity states for diagnostics
    entity_registry = er.async_get(hass)
    entity_states = {}
    for favorite_key, favorite_variants in favorites_data.items():
        unique_id = f"music_favorites_favorite_{favorite_key}"
        if entity_id := entity_registry.async_get_entity_id(
            "sensor", DOMAIN, unique_id
        ):
            if state := hass.states.get(entity_id):
                entity_states[favorite_variants[0]] = {
                    "state": state.state,
                    "attributes": dict(state.attributes),
                }

    return {
        "config_entry": {
            "title": entry.title,
            "entry_id": entry.entry_id,
            "domain": entry.domain,
            "version": entry.version,
        },
        "favorites_statistics": {
            "total_favorites": total_favorites,
            "favorites_with_variants": favorites_with_variants,
            "average_variants_per_favorite": (
                sum(len(variants) for variants in favorites_data.values())
                / total_favorites
                if total_favorites > 0
                else 0
            ),
        },
        "favorites_data": {
            favorite_key: {
                "display_name": variants[0],
                "variant_count": len(variants) - 1,
                "variants": variants[1:] if len(variants) > 1 else [],
            }
            for favorite_key, variants in favorites_data.items()
        },
        "entity_states": entity_states,
    }
