"""MusicBrainz API client for Music Favorites integration."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import VERSION

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
            List of artist dictionaries with id, name, and disambiguation

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

        # Return simplified artist data
        simplified_artists = [
            {
                "id": artist["id"],
                "name": artist["name"],
                "disambiguation": artist.get("disambiguation", ""),
                "score": int(artist.get("score", 0)),
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
