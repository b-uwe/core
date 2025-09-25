"""Sensor platform for the Music Favorites integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, VERSION
from .types import MusicFavoritesConfigEntry

# Serialize entity updates for future API rate limiting
PARALLEL_UPDATES = 1


class FavoriteSensor(SensorEntity):
    """Sensor for a single favorite."""

    def __init__(
        self, favorite_key: str, favorite_variants: list[str], device_info: DeviceInfo
    ) -> None:
        """Initialize the favorite sensor."""
        self._favorite_key = favorite_key
        self._favorite_variants = favorite_variants
        self._attr_name = favorite_variants[0]  # Display name for the entity
        self._attr_translation_key = "favorite_act"  # Translation key
        self._attr_unique_id = f"music_favorites_favorite_{favorite_key}"
        self._attr_device_info = device_info
        self._attr_entity_id = f"music_favorites_{favorite_variants[0].lower()}"
        self._attr_icon = "mdi:guitar-electric"
        self._attr_has_entity_name = True

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Attributes of the entity."""
        return {
            "musicbrainz_id": self._favorite_key,
            "variants": self._favorite_variants[1:],  # All except display name
        }

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        # For now, just return the favorite name
        # Later: could be "next concert date" or "tour status"
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicFavoritesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Favorites sensors from a config entry."""

    # Get our favorites data from the config entry
    favorites_data: dict[str, list[str]] = entry.data.get("favorites", {})

    # Gold Tier: Multiple devices for different favorite types
    # For now, we'll create separate devices based on future categorization
    # Currently all favorites go to "Bands & Artists" device until we add
    # type support

    bands_device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_acts")},
        name=f"{entry.title} - Bands & Artists",
        manufacturer="Music Favorites Integration",
        model="Bands & Artists Collection",
        sw_version=VERSION,
        configuration_url=f"homeassistant://config/integrations/integration/{DOMAIN}",
    )

    # Future: Add more device types when we implement type categorization
    # festivals_device_info = DeviceInfo(
    #     identifiers={(DOMAIN, f"{entry.entry_id}_festivals")},
    #     name=f"{entry.title} - Festivals",
    #     manufacturer="Music Favorites Integration",
    #     model="Festival Collection",
    # )

    # Create one sensor entity for each favorite
    # TO DO: When we add type support, assign to appropriate device
    entities = []
    for favorite_key, favorite_variants in favorites_data.items():
        entities.append(
            FavoriteSensor(favorite_key, favorite_variants, bands_device_info)
        )

    # Add all entities to Home Assistant
    # Side note: I HATE how this is NOT async
    async_add_entities(entities)
