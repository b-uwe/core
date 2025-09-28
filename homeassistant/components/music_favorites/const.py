"""Constants for the Music Favorites integration."""

from datetime import timedelta
from enum import StrEnum


class BandStatus(StrEnum):
    """Band status enumeration."""

    ACTIVE = "Active"
    DISBANDED = "Disbanded"
    ON_TOUR = "On Tour"
    REFORMED = "Reformed"
    TOUR_PLANNED = "Tour Planned"
    UNKNOWN = "Unknown"


# Status icons mapping
BAND_STATUS_ICONS = {
    BandStatus.ACTIVE: "mdi:guitar-electric",
    BandStatus.DISBANDED: "mdi:music-off",
    BandStatus.ON_TOUR: "mdi:bus-marker",
    BandStatus.REFORMED: "mdi:set-none",
    BandStatus.TOUR_PLANNED: "mdi:bus-clock",
    BandStatus.UNKNOWN: "mdi:help-circle",
}
DOMAIN = "music_favorites"
PENDING_CHOICES_CLEANUP_TIMEOUT = 300
REFORMED_DISPLAY_PERIOD = timedelta(days=180)  # 6 months for showing Reformed status
RELATIONS_OF_INTEREST = [
    "AllMusic",
    "Bandsintown",
    "Discogs",
    "Songkick",
]
TOUR_GRACE_PERIOD = timedelta(days=2)  # Show "On Tour" 2 days after last event
TOUR_PLANNED_PERIOD = timedelta(days=180)
TOUR_PREVIEW_PERIOD = timedelta(days=30)  # Show "On Tour" 30 days before
VERSION = "0.0.5"
