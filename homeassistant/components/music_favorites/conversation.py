"""Conversation platform for Music Favorites integration."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, NoReturn

from homeassistant.components.conversation import ConversationEntity, ConversationResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PENDING_CHOICES_CLEANUP_TIMEOUT
from .datatypes import MusicFavoritesConfigEntry
from .models import add_favorite, remove_favorite, resolve_artist_from_name

_LOGGER = logging.getLogger(__name__)

# Serialize entity updates for future API rate limiting
PARALLEL_UPDATES = 1


def _raise_favorite_not_found(artist_name: str) -> NoReturn:
    """Raise ServiceValidationError for favorite not found."""
    raise ServiceValidationError(f"Favorite '{artist_name}' not found")


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: MusicFavoritesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Favorites conversation entity."""
    _LOGGER.debug("Setting up Music Favorites conversation platform")
    async_add_entities([MusicFavoritesConversationEntity(entry)])


class MusicFavoritesConversationEntity(ConversationEntity):
    """Music Favorites conversation entity."""

    _attr_has_entity_name = True
    _attr_name = "Music Favorites Assistant"

    def __init__(self, entry: MusicFavoritesConfigEntry) -> None:
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

        # Check for number input for pending artist choices
        if text.isdigit():
            return await self._handle_number_choice(text)

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
                # Find the MusicBrainz ID for the artist name
                current_favorites = self._entry.data.get("favorites", {})
                musicbrainz_id_to_remove = None
                for musicbrainz_id, favorite_data in current_favorites.items():
                    variants = favorite_data.get("variants", [])
                    if any(
                        stored_name.lower() == artist_name.lower()
                        for stored_name in variants
                    ):
                        musicbrainz_id_to_remove = musicbrainz_id
                        break

                if musicbrainz_id_to_remove is None:
                    _raise_favorite_not_found(artist_name)

                # Remove the favorite
                await remove_favorite(self.hass, self._entry, musicbrainz_id_to_remove)

                # Create success response
                response = intent.IntentResponse(language="en")
                response.async_set_speech(f"No longer tracking {artist_name.upper()}")
                _LOGGER.debug("Successfully removed '%s'", artist_name)
                return ConversationResult(response=response)

            except ServiceValidationError as e:
                _LOGGER.debug("Failed to remove '%s': %s", artist_name, e)
                response = intent.IntentResponse(language="en")
                response.async_set_speech(
                    f"Failed to remove {artist_name.upper()} from your favorites"
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
            response = intent.IntentResponse(language="en")

            try:
                # Resolve artist name using MusicBrainz
                resolution = await resolve_artist_from_name(self.hass, artist_name)

                if resolution is None:
                    # MusicBrainz API error
                    response.async_set_speech(
                        f"Sorry, I couldn't connect to the music database to add {artist_name}. Please try again later."
                    )
                    return ConversationResult(response=response)

                if resolution["action"] == "not_found":
                    # No matches found
                    response.async_set_speech(
                        f"Sorry, I couldn't find any artist named {artist_name} in the music database."
                    )
                    return ConversationResult(response=response)

                if resolution["action"] == "create":
                    # Exact match found - add the favorite
                    artist_name_resolved = str(resolution["name"])
                    musicbrainz_id = str(resolution["musicbrainz_id"])
                    await add_favorite(
                        self.hass,
                        self._entry,
                        musicbrainz_id,
                    )
                    response.async_set_speech(
                        f"Now tracking {artist_name_resolved.upper()}"
                    )
                    _LOGGER.debug(
                        "Successfully added '%s' (%s)",
                        artist_name_resolved,
                        musicbrainz_id,
                    )
                    return ConversationResult(response=response)

                if resolution["action"] == "choose":
                    # Multiple matches - present choices to user
                    options = resolution["options"]
                    if isinstance(options, list) and len(options) > 0:
                        # Store the MusicBrainz IDs for user selection
                        musicbrainz_ids = [
                            str(option["musicbrainz_id"]) for option in options
                        ]
                        self._entry.runtime_data["pending_choices"] = musicbrainz_ids

                        # Start cleanup timer
                        self.hass.async_create_task(self._cleanup_pending_choices())

                        # Build the choice presentation
                        choice_text = f"I found multiple artists named {artist_name}. Which one is the one you targeted?\n"
                        for i, option in enumerate(options, 1):
                            name = str(option["name"])
                            disambiguation = option.get("disambiguation", "")

                            # Build description with disambiguation only
                            description = (
                                f" - {disambiguation}" if disambiguation else ""
                            )
                            choice_text += f"{i}: {name}{description}\n"

                        choice_text += f"\nJust say the number (1 to {len(options)})."

                        response.async_set_speech(choice_text)
                        _LOGGER.debug(
                            "Presented %d choices for '%s', stored IDs: %s",
                            len(options),
                            artist_name,
                            musicbrainz_ids,
                        )
                        return ConversationResult(response=response)

            except ServiceValidationError as e:
                _LOGGER.debug("Failed to add '%s': %s", artist_name, e)
                response.async_set_speech(
                    f"Failed to add {artist_name.upper()}. They might already be in your favorites."
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

    async def _cleanup_pending_choices(
        self, timeout: float = PENDING_CHOICES_CLEANUP_TIMEOUT
    ) -> None:
        """Clean up pending choices after timeout."""
        await asyncio.sleep(timeout)
        if (
            hasattr(self._entry, "runtime_data")
            and self._entry.runtime_data
            and "pending_choices" in self._entry.runtime_data
        ):
            del self._entry.runtime_data["pending_choices"]
            _LOGGER.debug("Cleaned up expired pending choices")

    async def _handle_number_choice(self, number_text: str) -> ConversationResult:
        """Handle user number choice for pending artist selection."""
        response = intent.IntentResponse(language="en")

        # Check if we have pending choices
        if (
            not hasattr(self._entry, "runtime_data")
            or not self._entry.runtime_data
            or not self._entry.runtime_data.get("pending_choices")
        ):
            response.async_set_speech(
                "I don't understand. Try saying 'track [artist]' or 'untrack [artist]'."
            )
            return ConversationResult(response=response)

        pending_choices = self._entry.runtime_data["pending_choices"]

        # Convert to int and validate range (isdigit() guarantees this won't raise ValueError)
        choice_number = int(number_text)
        if choice_number < 1 or choice_number > len(pending_choices):
            response.async_set_speech(
                f"Please choose a number between 1 and {len(pending_choices)}."
            )
            return ConversationResult(response=response)

        # Get the selected MusicBrainz ID (convert to 0-based index)
        selected_musicbrainz_id = pending_choices[choice_number - 1]

        # Clear the pending choices
        del self._entry.runtime_data["pending_choices"]

        try:
            # Add the selected favorite
            await add_favorite(
                self.hass,
                self._entry,
                selected_musicbrainz_id,
            )

            response.async_set_speech("Great! I've added your choice to favorites.")

            _LOGGER.debug(
                "User selected choice %d, added MusicBrainz ID: %s",
                choice_number,
                selected_musicbrainz_id,
            )
            return ConversationResult(response=response)

        except ServiceValidationError as err:
            # Error adding favorite (duplicate or API error)
            _LOGGER.error("Error adding selected favorite: %s", err)
            response.async_set_speech(
                "Sorry, there was an error adding that artist to your favorites. Please try again."
            )
            return ConversationResult(response=response)
