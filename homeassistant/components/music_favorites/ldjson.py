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
    """Exception raised when LD+JSON extraction fails."""


async def fetch_and_extract_ldjson(
    hass: HomeAssistant, url: str
) -> list[dict[str, Any]]:
    """Fetch a URL and extract all LD+JSON data from the HTML.

    Args:
        hass: Home Assistant instance for HTTP session
        url: The URL to fetch and parse

    Returns:
        List of dictionaries containing parsed LD+JSON objects

    Raises:
        LdJsonError: When URL fetching or parsing fails
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
                        # Handle both single objects and arrays
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
