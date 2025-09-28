"""Bandsintown integration utilities for Music Favorites integration."""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


def extract_music_events(ldjson_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract and parse MusicEvent objects from Bandsintown LD+JSON data.

    Args:
        ldjson_data: List of LD+JSON objects from Bandsintown that will be extracted by ldjson.py

    Returns:
        List of simplified event dictionaries with text, dates, links, and geolocation
    """
    music_events = []

    for obj in ldjson_data:
        if obj.get("@type") == "MusicEvent":
            # Extract simplified event data
            event_data = {
                "text": obj.get("name", "Unknown Event"),
                "start_date": obj.get("startDate"),
                "end_date": obj.get("endDate"),
                "url": obj.get("url"),
                "location": obj.get("location", {}).get("name"),
                "venue_address": None,
                "performer": obj.get("performer", {}).get("name"),
                "latitude": None,
                "longitude": None,
            }

            # Extract venue details if available
            location = obj.get("location", {})
            if location:
                # Extract address
                if location.get("address"):
                    address = location["address"]
                    venue_parts = []
                    if address.get("streetAddress"):
                        venue_parts.append(address["streetAddress"])
                    if address.get("addressLocality"):
                        venue_parts.append(address["addressLocality"])
                    if address.get("addressCountry"):
                        venue_parts.append(address["addressCountry"])
                    event_data["venue_address"] = (
                        ", ".join(venue_parts) if venue_parts else None
                    )

                # Extract geolocation coordinates
                if location.get("geo"):
                    geo = location["geo"]
                    if geo.get("@type") == "GeoCoordinates":
                        event_data["latitude"] = geo.get("latitude")
                        event_data["longitude"] = geo.get("longitude")

            music_events.append(event_data)

    _LOGGER.debug(
        "Extracted %d MusicEvent objects from Bandsintown data", len(music_events)
    )
    return music_events
