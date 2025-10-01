"""Type definitions for the Music Favorites integration.

This module provides custom type aliases used throughout the integration to ensure
type safety and consistency.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry

# Type alias for the Music Favorites config entry with runtime data specification
#
# This custom type extends the base ConfigEntry to include type hints for the runtime_data
# dictionary that stores shared components and cached data used across all platforms.
#
# Runtime Data Structure:
# - "update_interval": Update interval for coordinator scheduling
# - "musicbrainz_client": Shared MusicBrainz API client instance
# - "data_update_coordinator": Background data update coordinator
# - "filtered_calendar_events": Cached distance-filtered events for calendar display
# - "entity_manager": Dynamic entity manager for sensor platform
# - "calendar_entity": Calendar entity reference for cache refresh notifications
# - "pending_choices": Temporary storage for conversation disambiguation choices
#
# Config Entry Data Structure:
# - "favorites": Dict of MusicBrainz ID → favorite artist data
# - "distance_filter": Maximum distance in km for event filtering (or None for unlimited)
#
# Circular Import Prevention:
# By defining this type alias separately, all modules can import and use
# MusicFavoritesConfigEntry without creating circular dependency issues.
type MusicFavoritesConfigEntry = ConfigEntry[dict[str, Any]]
