"""LD+JSON extraction utilities for Music Favorites integration."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import STANDARD_UA_FOR_FETCHES

_LOGGER = logging.getLogger(__name__)


class LdJsonError(HomeAssistantError):
    """Exception raised when LD+JSON structured data extraction or parsing fails.

    Custom exception hierarchy for LD+JSON processing failures, providing clear error
    boundaries for web scraping operations versus generic Home Assistant errors.
    This allows calling code to distinguish between network issues, HTML parsing
    problems, and JSON format errors for appropriate error handling.

    Error Scenarios:
    - HTTP request failures → Network timeouts, DNS resolution, connection errors
    - HTTP response errors → 404, 500, or other non-200 status codes
    - HTML parsing failures → Malformed HTML that BeautifulSoup cannot process
    - JSON parsing errors → Invalid JSON content in LD+JSON script tags
    - Missing script tags → No LD+JSON elements found in HTML content

    Exception Usage:
    - Raised by: fetch_and_extract_ldjson() when any processing step fails
    - Caught by: Bandsintown website fetch client and other LD+JSON consumers
    - Context preservation → Original exception details maintained with 'from' clause
    """


async def fetch_and_extract_ldjson(
    hass: HomeAssistant, url: str
) -> list[dict[str, Any]]:
    """Fetch web page content and extract all embedded LD+JSON structured data.

    Performs some web scraping to extract JSON-LD structured data from HTML pages. This
    enables retrieving data from websites that embed information in structured format.

    Processing Pipeline:
    1. HTTP Request → Fetch HTML content with appropriate headers and User-Agent
    2. HTML Parsing → Parse content using BeautifulSoup for robust tag extraction
    3. Script Discovery → Find all <script type="application/ld+json"> elements
    4. JSON Parsing → Extract and parse JSON content from each script tag
    5. Data Aggregation → Combine all LD+JSON objects into unified list

    LD+JSON Format Handling:
    - Single objects → Wrapped in list for consistent return format
    - Array objects → Flattened into main result list
    - Multiple scripts → All LD+JSON blocks processed and combined
    - Invalid JSON → Logged as warning but doesn't fail entire operation

    HTTP Client Configuration:
    - Shared HA session → Inherits connection pooling and timeout settings
    - User-Agent identification → Standard HA user agent for responsible scraping
    - Error handling → Network failures wrapped in custom exception type

    Args:
        hass: Home Assistant instance providing HTTP session and logging context
        url: Target URL to fetch and parse for LD+JSON content

    Returns:
        List of dictionaries containing all parsed LD+JSON objects found on page.
        Empty list if no LD+JSON content found or all parsing fails.

    Raises:
        LdJsonError: HTTP request failures, non-200 responses, or critical parsing errors

    Used By:
        - Bandsintown client → Extract concert event data from venue pages
        - Future: Additional structured data extraction for music services
    """
    _LOGGER.debug("Fetching URL to extract LD+JSON: %s", url)

    session = async_get_clientsession(hass)

    headers = {
        "User-Agent": STANDARD_UA_FOR_FETCHES,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    }

    try:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                raise LdJsonError(f"HTTP request failed with status {response.status}")

            html_content = await response.text()

            # Parse HTML and extract LD+JSON scripts directly
            soup = BeautifulSoup(html_content, "html.parser")
            ldjson_scripts = soup.find_all("script", type="application/ld+json")

            ldjson_data: list[dict[str, Any]] = []

            for script in ldjson_scripts:
                script_content = (
                    script.get_text()
                    if hasattr(script, "get_text")
                    else getattr(script, "string", None)
                )
                if script_content:
                    try:
                        parsed_json = json.loads(script_content)
                        # Handle both single objects and arrays for flexible LD+JSON format support
                        if isinstance(parsed_json, list):
                            ldjson_data.extend(parsed_json)
                        else:
                            ldjson_data.append(parsed_json)

                    except json.JSONDecodeError as err:
                        _LOGGER.warning(
                            "Invalid JSON in LD+JSON script from '%s': %s", url, err
                        )
                        continue

    except aiohttp.ClientError as err:
        _LOGGER.error("Failed to fetch URL '%s': %s", url, err)
        raise LdJsonError(f"Failed to fetch URL: {err}") from err

    _LOGGER.debug("Extracted %d LD+JSON objects from %s", len(ldjson_data), url)
    return ldjson_data
