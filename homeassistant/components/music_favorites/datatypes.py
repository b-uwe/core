"""Type definitions for the Music Favorites integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry

# Type alias for the Music Favorites config entry
# This avoids circular imports by keeping the type definition separate
type MusicFavoritesConfigEntry = ConfigEntry[dict[str, Any]]
