"""MusicBrainz API client for Music Favorites integration."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import RELATIONS_OF_INTEREST, VERSION

_LOGGER = logging.getLogger(__name__)

# MusicBrainz API configuration
MUSICBRAINZ_API_URL = "https://musicbrainz.org/ws/2"
USER_AGENT = f"Music Favorites {VERSION} (https://home-assistant.io/integrations/music_favorites)"


class MusicBrainzError(HomeAssistantError):
    """Exception raised when MusicBrainz API fails.

    I decided against musicbrainzngs because
    * That one is sync
    * It's not well typed
    * It uses XML under the hood whereas JSON is native to HA
    * THIS API is simple!
    """


class MusicBrainzClient:
    """Own async MusicBrainz API client using aiohttp."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the MusicBrainz client."""
        self.hass = hass
        self.session = async_get_clientsession(hass)

    async def search_artists(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search for artists matching the query.

        Args:
            query: Artist name to search for
            limit: Maximum number of results to return

        Returns:
            List of artist dictionaries with id, name, disambiguation, score, aliases and third party links

        Raises:
            MusicBrainzError: When API call fails
        """
        _LOGGER.debug(
            "Searching MusicBrainz for artist: '%s' (limit: %d)", query, limit
        )

        # Build MusicBrainz API query parameters
        params = {
            "query": f'artist:"{query}"',
            "fmt": "json",
            "limit": str(limit),
            "inc": "aliases url-rels",
        }
        url = f"{MUSICBRAINZ_API_URL}/artist/?{urlencode(params)}"

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }

        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise MusicBrainzError(
                        f"MusicBrainz API returned status {response.status}"
                    )

                data = await response.json()

        except aiohttp.ClientError as err:
            _LOGGER.error(
                "Failed to search MusicBrainz for artist '%s': %s", query, err
            )
            raise MusicBrainzError(f"MusicBrainz search failed: {err}") from err

        # Extract the artists from MusicBrainz response format
        artists = data.get("artists", [])
        _LOGGER.debug(
            "MusicBrainz returned %d artists for query '%s'", len(artists), query
        )

        # Return simplified artist data with aliases
        simplified_artists = [
            {
                "id": artist["id"],
                "name": artist["name"],
                "disambiguation": artist.get("disambiguation", ""),
                "score": int(artist.get("score", 0)),
                "aliases": [
                    alias.get("name", "")
                    for alias in artist.get("aliases", [])
                    if alias.get("name")  # Only include non-empty alias names
                ],
            }
            for artist in artists
        ]

        if simplified_artists:
            _LOGGER.info(
                "Found %d artists for '%s', best match: '%s' (score: %d)",
                len(simplified_artists),
                query,
                simplified_artists[0]["name"],
                simplified_artists[0]["score"],
            )
            return simplified_artists

        _LOGGER.info("No artists found for query '%s'", query)
        return []

    async def get_artist_by_id(self, artist_id: str) -> dict[str, Any]:
        """Get complete artist data by MusicBrainz ID.

        Args:
            artist_id: MusicBrainz artist ID

        Returns:
            Complete artist data with name, aliases, and all relations

        Raises:
            MusicBrainzError: When API call fails
        """
        _LOGGER.debug("Fetching MusicBrainz artist by ID: '%s'", artist_id)

        # Build MusicBrainz API URL for direct artist lookup
        url = f"{MUSICBRAINZ_API_URL}/artist/{artist_id}?inc=aliases+url-rels&fmt=json"

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }

        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise MusicBrainzError(
                        f"MusicBrainz API returned status {response.status} for artist {artist_id}"
                    )

                data: dict[str, Any] = await response.json()

        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to fetch MusicBrainz artist '%s': %s", artist_id, err)
            raise MusicBrainzError(f"MusicBrainz artist lookup failed: {err}") from err

        _LOGGER.debug(
            "Fetched artist '%s' (%s) with %d aliases and %d relations",
            data.get("name", "Unknown"),
            artist_id,
            len(data.get("aliases", [])),
            len(data.get("relations", [])),
        )

        return data


def extract_relation_links(artist_data: dict[str, Any]) -> dict[str, str]:
    """Extract relevant relation links from MusicBrainz artist data.

    Args:
        artist_data: Complete MusicBrainz artist data with relations

    Returns:
        Dictionary with relation URLs as direct attributes
    """
    relation_attributes = {}

    relations = artist_data.get("relations", [])
    for relation in relations:
        relation_type = relation.get("type")
        # Check if relation type matches any in RELATIONS_OF_INTEREST (case insensitive)
        if any(
            relation_type.lower() == interest.lower()
            for interest in RELATIONS_OF_INTEREST
        ):
            url_data = relation.get("url")
            if url_data and url_data.get("resource"):
                # Store only URL as attribute
                url_attr = f"{relation_type.lower()}_url"
                relation_attributes[url_attr] = url_data["resource"]

    _LOGGER.debug(
        "Extracted %d relation URLs for artist '%s': %s",
        len(relation_attributes),
        artist_data.get("name", "Unknown"),
        list(relation_attributes.keys()),
    )

    return relation_attributes
