"""Conversation platform for Music Favorites integration."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.conversation import ConversationEntity, ConversationResult
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .models import add_favorite, remove_favorite

_LOGGER = logging.getLogger(__name__)

# Serialize entity updates for future API rate limiting
PARALLEL_UPDATES = 1


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Favorites conversation entity."""
    _LOGGER.debug("Setting up Music Favorites conversation platform")
    async_add_entities([MusicFavoritesConversationEntity(entry)])


class MusicFavoritesConversationEntity(ConversationEntity):
    """Music Favorites conversation entity."""

    _attr_has_entity_name = True
    _attr_name = "Music Favorites Assistant"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the Music Favorites conversation entity."""
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_conversation"
        _LOGGER.debug("Created Music Favorites conversation entity")

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return ["en"]  # Only English for now

    async def _async_handle_message(
        self, user_input: Any, chat_log: Any
    ) -> ConversationResult:
        """Handle the conversation message."""
        text = user_input.text.lower().strip()
        _LOGGER.debug("Conversation received: '%s'", text)

        # Check for untrack/remove first to avoid conflicts
        short_pattern = r"^-\s+(.+)"
        untrack_pattern = r"^untrack\s+(.+)"
        remove_pattern = r"remove\s+(.+?)\s+from\s+(?:music\s+)?favorites"

        short_match = re.search(short_pattern, text)
        untrack_match = re.search(untrack_pattern, text)
        remove_match = re.search(remove_pattern, text)

        if short_match or untrack_match or remove_match:
            artist_name = (
                short_match.group(1)
                if short_match
                else (
                    untrack_match.group(1)
                    if untrack_match
                    else remove_match.group(1)
                    if remove_match
                    else ""
                )
            ).strip()
            _LOGGER.debug("Untrack/remove request for: '%s'", artist_name)

            try:
                # Remove the favorite
                await remove_favorite(self.hass, self._entry, artist_name)

                # Create success response
                response = intent.IntentResponse(language="en")
                response.async_set_speech(f"No longer tracking {artist_name}")
                _LOGGER.debug("Successfully removed '%s'", artist_name)
                return ConversationResult(response=response)

            except ServiceValidationError as e:
                _LOGGER.debug("Failed to remove '%s': %s", artist_name, e)
                response = intent.IntentResponse(language="en")
                response.async_set_speech(
                    f"Failed to remove {artist_name} from your favorites"
                )
                return ConversationResult(response=response)

        # Pattern: "track [artist/band]" or "add [artist/band] to music favorites"
        short_pattern = r"^\+\s+(.+)"
        track_pattern = r"^track\s+(.+)"
        add_pattern = r"add\s+(.+?)\s+to\s+music\s+favorites"

        short_match = re.search(short_pattern, text)
        track_match = re.search(track_pattern, text)
        add_match = re.search(add_pattern, text)

        if short_match or track_match or add_match:
            artist_name = (
                short_match.group(1)
                if short_match
                else (
                    track_match.group(1)
                    if track_match
                    else add_match.group(1)
                    if add_match
                    else ""
                )
            ).strip()
            _LOGGER.debug("Track/add request for: '%s'", artist_name)

            try:
                # Add the favorite
                await add_favorite(self.hass, self._entry, artist_name, "band")

                # Create success response
                response = intent.IntentResponse(language="en")
                response.async_set_speech(f"Now tracking {artist_name}")
                _LOGGER.debug("Successfully added '%s'", artist_name)
                return ConversationResult(response=response)

            except ServiceValidationError as e:
                _LOGGER.debug("Failed to add '%s': %s", artist_name, e)
                response = intent.IntentResponse(language="en")
                response.async_set_speech(
                    f"Failed to add {artist_name}. They might already be in your favorites."
                )
                return ConversationResult(response=response)

        # Default response for unrecognized commands
        _LOGGER.debug("Unrecognized command: '%s'", text)
        response = intent.IntentResponse(language="en")
        response.async_set_speech(
            "Unrecognized command. "
            "I can help you track your favorite artists. "
            "Try saying 'track Motörhead', 'untrack Motörhead', or 'add Motörhead to Music Favorites', ..."
        )
        return ConversationResult(response=response)
