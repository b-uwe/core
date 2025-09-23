"""Sensor platform for the Music Favorites integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MusicFavoritesConfigEntry
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicFavoritesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Favorites sensors from a config entry."""

    # Get our favorites data from the config entry
    favorites_data: dict[str, list[str]] = entry.data.get("bands", {})

    # Create a Device that holds all Favorites
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_favorites")},
        name="Favorites",
        manufacturer="Music Favorites",
        model="Favorites Collection",
    )

    # Create one sensor entity for each favorite
    entities = []
    for favorite_key, favorite_variants in favorites_data.items():
        entities.append(FavoriteSensor(favorite_key, favorite_variants, device_info))

    # Add all entities to Home Assistant
    # Side note: I HATE how this is NOT async
    async_add_entities(entities)


class FavoriteSensor(SensorEntity):
    """Sensor for a single favorite."""

    def __init__(
        self, favorite_key: str, favorite_variants: list[str], device_info: DeviceInfo
    ) -> None:
        """Initialize the favorite sensor."""
        self._favorite_key = favorite_key
        self._favorite_variants = favorite_variants
        self._attr_name = favorite_variants[0]  # Display name (first variant)
        self._attr_unique_id = f"music_favorites_favorite_{favorite_key}"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        # For now, just return the favorite name
        # Later: could be "next concert date" or "tour status"
        return self._attr_name
