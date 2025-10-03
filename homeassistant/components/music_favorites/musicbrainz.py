"""MusicBrainz API client for Music Favorites integration."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import RELATIONS_OF_INTEREST, STANDARD_UA_FOR_FETCHES

_LOGGER = logging.getLogger(__name__)

# MusicBrainz API configuration
MUSICBRAINZ_API_URL = "https://musicbrainz.org/ws/2"


class MusicBrainzError(HomeAssistantError):
    """Exception raised when MusicBrainz API communication or processing fails.

    Custom exception hierarchy for MusicBrainz-specific failures, providing clear error
    boundaries for API communication issues versus generic Home Assistant errors.
    This allows upstream code to distinguish between network failures and data
    processing issues for appropriate error handling and user feedback.

    Design Decision - Custom Client vs musicbrainzngs Library:
    - musicbrainzngs is synchronous → Incompatible with Home Assistant async requirements
    - musicbrainzngs uses XML parsing → JSON responses are more efficient and HA-native
    - musicbrainzngs lacks type hints → Reduces type safety and IDE support
    - Custom implementation provides minimal API surface → Simpler maintenance and debugging
    - Direct aiohttp usage → Integrates with HA's existing HTTP client session management

    Error Scenarios:
    - Network timeouts or connection failures → Wrapped aiohttp.ClientError exceptions
    - HTTP error responses (404, 500, etc.) → API status code validation failures
    - JSON parsing failures → Malformed response data from MusicBrainz
    - Rate limiting responses → HTTP 503 or similar from MusicBrainz servers

    Exception Hierarchy:
    MusicBrainzError (this class)
    └── HomeAssistantError (parent)
        └── Exception (grandparent)

    Usage Pattern:
    - Raised by: MusicBrainzClient methods when API operations fail
    - Caught by: Calling code (coordinator, services) for graceful degradation
    - Logged at: Error level with original exception context preserved
    """


class MusicBrainzClient:
    """Asynchronous MusicBrainz API client providing artist search and metadata retrieval.

    Custom API client implementation designed for Home Assistant's async architecture
    and integration requirements. Provides essential MusicBrainz functionality with
    minimal dependencies and optimized for the music favorites use case.

    Core Capabilities:
    - Artist search → Find artists by name with fuzzy matching and scoring
    - Artist metadata → Retrieve complete artist data including aliases and relations
    - Alias extraction → Handle alternative artist names for flexible matching
    - Relation parsing → Extract relevant third-party service URLs (Spotify, etc.)

    HTTP Client Integration:
    - Uses HA's shared aiohttp session → Consistent timeout and connection pooling
    - Standard User-Agent → Identifies requests as coming from HA for MusicBrainz logs
    - JSON response format → Native Python data structures for efficient processing

    Rate Limiting Compliance:
    - MusicBrainz allows 1 request/second → Client doesn't enforce this though, relies on coordinator
    - User-Agent identification → Required by MusicBrainz for responsible usage tracking
    - Single session reuse → Efficient connection management respects server resources

    Error Handling Strategy:
    - Network errors → Wrapped in MusicBrainzError with original context
    - HTTP errors → Status code validation with descriptive error messages
    - JSON parsing → Graceful handling of malformed responses
    - Empty results → Returned as empty lists rather than errors for normal flow
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the MusicBrainz client with Home Assistant session integration.

        Sets up the API client with Home Assistant's shared HTTP session for efficient
        connection management and consistent timeout handling. The client inherits
        all HTTP client configuration from the Home Assistant instance.

        Session Management:
        - Shared aiohttp session → Reuses HA's connection pool and timeout settings
        - Automatic SSL verification → Inherits HA's certificate validation configuration
        - Connection pooling → Efficient reuse of HTTP connections to MusicBrainz
        - Timeout inheritance → Uses HA's default request timeout values

        Args:
            hass: Home Assistant instance providing HTTP session and configuration access

        Sets:
            self.hass: Reference to HA instance for logging context and future extensions
            self.session: Shared aiohttp ClientSession for all API requests
        """
        self.hass = hass
        self.session = async_get_clientsession(hass)

    async def search_artists(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search MusicBrainz database for artists matching the provided name query.

        Performs fuzzy text search across artist names and aliases, returning ranked results
        with relevance scoring and comprehensive metadata. Optimized for interactive artist
        selection scenarios where users need to disambiguate between similar artists.

        Search Strategy:
        - Exact phrase matching → Wraps query in quotes for precise artist name searches
        - Limit enforcement → Prevents excessive API response sizes for performance

        Response Processing:
        - Alias deduplication → Removes duplicate alternative names while preserving order
        - Score preservation → Maintains MusicBrainz relevance ranking for future disambiguation
        - Data simplification → Extracts essential fields from complex API response
        - Empty result handling → Returns empty list rather than error for no matches

        Performance Considerations:
        - Single API request → Efficient batch retrieval of multiple candidates
        - JSON parsing → Direct Python data structures without XML overhead
        - Connection reuse → Leverages HA's shared HTTP session for efficiency
        - Response caching → No client-side caching; relies on HTTP-level caching

        Args:
            query: Artist name to search for in MusicBrainz database (case-insensitive)
            limit: Maximum number of artist results to return (default: 10)

        Returns:
            List of artist dictionaries containing:
            - id: MusicBrainz UUID for unique artist identification
            - name: Primary artist name as registered in MusicBrainz
            - disambiguation: Additional context (formation year, location, etc.)
            - score: Relevance score (0-100) for search query matching
            - aliases: List of alternative names and spellings (deduplicated)

        Raises:
            MusicBrainzError: Network failures, HTTP errors, or malformed responses

        Used By:
            - services.py search_artist_by_name() → Interactive artist discovery
            - conversation.py _search_artists() → Voice command artist resolution
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
            "User-Agent": STANDARD_UA_FOR_FETCHES,
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
                "aliases": list(
                    dict.fromkeys(
                        [
                            alias.get("name", "")
                            for alias in artist.get("aliases", [])
                            if alias.get("name")  # Only include non-empty alias names
                        ]
                    )  # Remove duplicates while preserving order
                ),
            }
            for artist in artists
        ]

        if simplified_artists:
            _LOGGER.debug(
                "Found %d artists for '%s', best match: '%s' (score: %d)",
                len(simplified_artists),
                query,
                simplified_artists[0]["name"],
                simplified_artists[0]["score"],
            )
            return simplified_artists

        _LOGGER.debug("No artists found for query '%s'", query)
        return []

    async def get_artist_by_id(self, artist_id: str) -> dict[str, Any]:
        """Retrieve complete artist metadata using MusicBrainz UUID identifier.

        Fetches comprehensive artist information including all aliases, external relations,
        and metadata required for favorite management and external service integration.
        This method provides the detailed data needed after artist selection.

        Data Retrieval Scope:
        - Core metadata → Artist name, disambiguation, formation details
        - Complete aliases → All alternative names and spellings
        - External relations → URLs to Bandsintown, songkick, etc.
        - Comprehensive attributes → All data needed for entity creation and service integration

        API Includes Parameter:
        - aliases → Alternative names for flexible matching
        - url-rels → External service URLs for integration features
        - No events/recordings → Focused on artist identity rather than discography because
          data quality isn't great with MusicBrainz on that front

        Args:
            artist_id: MusicBrainz UUID identifier for specific artist lookup

        Returns:
            Complete artist data dictionary containing:
            - name: Primary artist name from MusicBrainz
            - id: MusicBrainz UUID (same as input parameter)
            - disambiguation: Additional context information
            - aliases: Complete list of alternative names and spellings
            - relations: Raw relation data including external service URLs

        Raises:
            MusicBrainzError: Network failures, HTTP errors, invalid UUIDs, or API errors

        Used By:
            - services.py add_artist_to_favorites() → Artist data retrieval for favorite creation
            - coordinator.py _fetch_artist_complete_data() → Background data updates
        """
        _LOGGER.debug("Fetching MusicBrainz artist by ID: '%s'", artist_id)

        # Build MusicBrainz API URL for direct artist lookup
        url = f"{MUSICBRAINZ_API_URL}/artist/{artist_id}?inc=aliases+url-rels&fmt=json"

        headers = {
            "User-Agent": STANDARD_UA_FOR_FETCHES,
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
    """Extract and filter external service URLs from MusicBrainz artist relations data.

    Processes the complex MusicBrainz relations structure to extract URLs for services
    of interest (Spotify, Apple Music, social media, etc.), converting them into
    a simplified key-value format suitable for entity attributes and service integration.

    Relation Filtering Logic:
    - Service type matching → Compares relation types against RELATIONS_OF_INTEREST
    - Attribute naming → Converts relation types to standardized attribute names

    Args:
        artist_data: Complete MusicBrainz artist data containing relations array

    Returns:
        Dictionary mapping service types to URLs:
        - Keys: Lowercase service names with '_url' suffix (e.g., 'spotify_url')
        - Values: Direct URLs to external services (e.g., 'https://open.spotify.com/artist/...')

    Used By:
        - coordinator.py _process_artist_data() → Entity attribute generation
        - Future: Potential service integration features
    """
    relation_attributes = {}

    relations = artist_data.get("relations", [])
    for relation in relations:
        relation_type = relation.get("type")
        # Check if relation type matches any in RELATIONS_OF_INTEREST (case insensitive) 🤯
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
