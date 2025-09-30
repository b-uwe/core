"""Constants for the Music Favorites integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "music_favorites"
PENDING_CHOICES_CLEANUP_TIMEOUT = 300
RELATIONS_OF_INTEREST = [
    "AllMusic",
    "Bandsintown",
    "Discogs",
    "Songkick",
]
VERSION = "0.1.0"

# Standard User-Agent for external HTTP requests (must come after VERSION)
STANDARD_UA_FOR_FETCHES = f"Music Favorites {VERSION} (https://home-assistant.io/integrations/music_favorites)"

# Distance filter constants
DEFAULT_MAX_DISTANCE_KM = 100
DISTANCE_FILTER_OPTIONS = ["25", "50", "100", "200", "500", "No limit"]

# Update interval constants
DEFAULT_UPDATE_INTERVAL = timedelta(hours=6)
