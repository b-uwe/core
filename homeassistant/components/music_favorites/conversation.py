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
from .models import (
    MusicFavoritesConfigEntry,
    add_favorite,
    remove_favorite,
    resolve_artist_from_name,
)

_LOGGER = logging.getLogger(__name__)

# Serialize entity updates for future API rate limiting
PARALLEL_UPDATES = 1


def _raise_favorite_not_found(artist_name: str) -> NoReturn:
    """Raise standardized error for favorite artist not found in collection.

    Helper function that provides consistent error messaging when users reference
    an artist that is not in their favorites collection during voice commands.

    Args:
        artist_name: Name of the artist that was not found in favorites

    Raises:
        ServiceValidationError: Always raised with descriptive message about missing favorite

    Returns:
        NoReturn: Function never returns due to exception
    """
    raise ServiceValidationError(f"Favorite '{artist_name}' not found")


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: MusicFavoritesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up conversation platform from config entry with voice command integration.

    Creates a conversation entity that provides voice command support for managing
    favorite artists. Users can add and remove favorites using natural language
    voice commands through Home Assistant's conversation system.
    This was meant as some sort of hack until I can implement proper intents which again
    is a hack because what I want is a NATIVE MUTABLE list of entities 🫣 right in the
    associated device (and I didn't find a better hack yet)

    Conversation Platform Setup:
    1. Create conversation entity → Enables voice command processing
    2. Register with specific entity ID → Ensures consistent conversation agent identification
    3. Connect to config entry → Provides access to favorites data and services

    Voice Command Integration:
    - Add commands: "track [artist]", "+ [artist]", "add [artist] to music favorites"
    - Remove commands: "untrack [artist]", "- [artist]", "remove [artist] from favorites"
    - Choice handling: Number responses for multiple artist matches
    - Error responses: Clear feedback for unrecognized commands or failures

    Args:
        _hass: Home Assistant instance (unused but required by platform interface)
        entry: Config entry containing favorites data and serving as central data store
        async_add_entities: HA callback to register conversation entity

    Returns:
        None

    Side Effects:
        - Creates conversation entity → Voice commands become available immediately
        - Entity registers with fixed ID → "conversation.music_favorites_assistant"
        - Connects to service layer → Voice commands trigger add_favorite/remove_favorite
    """
    _LOGGER.debug("Setting up Music Favorites conversation platform")
    async_add_entities([MusicFavoritesConversationEntity(entry)])


class MusicFavoritesConversationEntity(ConversationEntity):
    """Conversation entity for managing music favorites through natural language voice commands.

    This entity provides a conversational interface for users to add and remove favorite
    artists using voice commands through Home Assistant's conversation system. It supports
    multiple command patterns and handles artist name resolution with disambiguation.

    Voice Command Patterns:
    - Add: "track [artist]", "+ [artist]", "add [artist] to music favorites"
    - Remove: "untrack [artist]", "- [artist]", "remove [artist] from favorites"
    - Choice selection: Number responses (1, 2, 3...) for multiple artist matches

    Artist Resolution Flow:
    1. Voice command received → Parse command pattern and extract artist name
    2. MusicBrainz search → Find matching artists in music database
    3. Single match → Add directly to favorites with confirmation
    4. Multiple matches → Present numbered choices to user
    5. User choice → Add selected artist to favorites
    6. No matches → Inform user artist not found

    State Management:
    - Pending choices stored in runtime_data → Temporary storage for user selections
    - Automatic cleanup → Pending choices expire after timeout to prevent memory leaks
    - Error handling → Clear feedback for API failures and invalid commands

    Integration Points:
    - Uses add_favorite/remove_favorite → Triggers full synchronization cascade
    - Connects to MusicBrainz API → Artist search and disambiguation
    - Voice feedback → Natural language responses via intent system
    """

    _attr_has_entity_name = True
    _attr_name = "Music Favorites Assistant"

    def __init__(self, entry: MusicFavoritesConfigEntry) -> None:
        """Initialize conversation entity with config entry connection and fixed entity ID.

        Sets up the conversation entity that processes natural language voice commands
        for managing favorite artists. The entity connects to the config entry for
        data access and uses a fixed entity ID for consistent conversation routing.

        Entity Configuration:
        - Name: "Music Favorites Assistant" → Clear identification in conversation system
        - Fixed entity ID → "conversation.music_favorites_assistant" for routing consistency
        - Unique ID: Based on config entry → Survives restarts and reloads
        - Config entry connection → Access to favorites data and service layer

        Args:
            entry: Config entry containing favorites data and serving as central data store

        Returns:
            None

        Side Effects:
            - Sets fixed entity_id → Ensures conversation system routes commands correctly
            - Stores config entry reference → Enables access to favorites data and services
            - Logs entity creation → Debugging and monitoring purposes
        """
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_conversation"
        # Set entity_id explicitly to ensure it matches expected conversation agent ID
        self.entity_id = "conversation.music_favorites_assistant"
        _LOGGER.debug("Created Music Favorites conversation entity")

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages for voice command processing.

        Currently supports only English language voice commands. This property
        tells Home Assistant which languages this conversation entity can handle.

        Returns:
            list[str]: List of supported language codes, currently only ["en"]

        Future Expansion:
            Additional languages can be added as regex patterns and responses
            are internationalized for broader voice command support.
        """
        return ["en"]  # Only English for now

    async def _async_handle_message(
        self, user_input: Any, chat_log: Any
    ) -> ConversationResult:
        """Process voice commands and return appropriate responses with full synchronization integration.

        This is the main entry point for all voice commands directed to the Music Favorites
        assistant. It parses natural language input, extracts commands and artist names,
        and executes the appropriate actions with comprehensive error handling.

        Command Processing Flow:
        1. Extract and normalize user text → Convert to lowercase and strip whitespace
        2. Check for number input → Handle pending artist choice selections
        3. Parse remove commands → "untrack", "- artist", "remove from favorites"
        4. Parse add commands → "track", "+ artist", "add to music favorites"
        5. Execute actions → Call add_favorite/remove_favorite with full sync cascade
        6. Generate responses → Natural language feedback via speech synthesis

        Supported Command Patterns:
        - Add: "track [artist]", "+ [artist]", "add [artist] to music favorites"
        - Remove: "untrack [artist]", "- [artist]", "remove [artist] from favorites"
        - Choice: "1", "2", "3" (numbers for selecting from multiple artist matches)

        Artist Resolution Process:
        - Single match → Add directly with confirmation
        - Multiple matches → Present numbered choices with disambiguation
        - No matches → Clear error message about artist not found
        - API errors → Informative error responses with retry suggestions

        Synchronization Integration:
        - Uses add_favorite() → Triggers full entity creation and UI updates
        - Uses remove_favorite() → Triggers entity removal and UI refresh
        - Voice confirmations → Immediate feedback while background sync occurs

        Args:
            user_input: User voice command input object containing text and metadata
            chat_log: Conversation history (unused but required by HA interface)

        Returns:
            ConversationResult: Response object with speech text for user feedback

        Side Effects:
            - May add/remove favorites → Triggers full synchronization cascade
            - May store pending choices → Temporary state for user selection
            - Starts cleanup timers → Automatic memory management for pending state
            - Logs all interactions → Debugging and monitoring purposes
        """
        text = user_input.text.lower().strip()
        _LOGGER.debug("Conversation received: '%s'", text)

        # Check for number input for pending artist choices
        if text.isdigit():
            return await self._handle_number_choice(text)

        # Check for untrack/remove first to avoid conflicts
        # Combined pattern: short form (-), untrack command, or remove from (music) favorites
        remove_pattern = (
            r"^-\s*(.+)|^untrack\s+(.+)|remove\s+(.+?)\s+from\s+(?:music\s+)?favorites"
        )

        if remove_match := re.search(remove_pattern, text):
            # Extract artist name from whichever group matched
            artist_name = (
                remove_match.group(1) or remove_match.group(2) or remove_match.group(3)
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
        # Combined pattern: short form (+), track command, or add to (music) favorites
        add_pattern = (
            r"^\+\s*(.+)|^track\s+(.+)|add\s+(.+?)\s+to\s+(?:music\s+)?favorites"
        )

        if add_match := re.search(add_pattern, text):
            # Extract artist name from whichever group matched
            artist_name = (
                add_match.group(1) or add_match.group(2) or add_match.group(3)
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
                        f"Sorry, I couldn't find any artist named {artist_name} in the music database. You're too underground 😅!"
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
        """Automatically clean up pending artist choices after timeout to prevent memory leaks.

        This background task removes pending artist choice data from runtime storage
        after a specified timeout period, ensuring that temporary state doesn't
        accumulate indefinitely if users don't complete their selections.

        Cleanup Process:
        1. Wait for timeout period → Default timeout from PENDING_CHOICES_CLEANUP_TIMEOUT
        2. Check runtime_data existence → Validate config entry and runtime storage
        3. Remove pending choices → Delete temporary selection data
        4. Log cleanup completion → Debugging and monitoring

        Args:
            timeout: Cleanup delay in seconds, defaults to PENDING_CHOICES_CLEANUP_TIMEOUT

        Returns:
            None

        Side Effects:
            - Removes pending_choices from runtime_data → Temporary state cleaned up
            - Logs cleanup action → Debugging information
            - No impact on active conversations → Only affects expired selections
        """
        await asyncio.sleep(timeout)
        if (
            hasattr(self._entry, "runtime_data")
            and self._entry.runtime_data
            and "pending_choices" in self._entry.runtime_data
        ):
            del self._entry.runtime_data["pending_choices"]
            _LOGGER.debug("Cleaned up expired pending choices")

    async def _handle_number_choice(self, number_text: str) -> ConversationResult:
        """Process user's numeric choice for artist disambiguation with full synchronization cascade.

        This method handles the second phase of artist addition when multiple matches
        were found during MusicBrainz search. It validates the user's numeric choice,
        retrieves the corresponding MusicBrainz ID, and completes the add favorite process.

        Choice Processing Flow:
        1. Validate pending choices → Ensure user has active selection context
        2. Parse and validate number → Convert to integer and check range
        3. Retrieve MusicBrainz ID → Get stored ID from pending choices array
        4. Clear pending state → Remove temporary selection data
        5. Add favorite → Call add_favorite() with full synchronization cascade
        6. Generate confirmation → Natural language success/error feedback

        State Management:
        - Retrieves from runtime_data → Accesses stored MusicBrainz IDs from previous search
        - Clears pending choices → Removes temporary state after processing
        - Error handling → Clear messages for invalid selections or missing context

        Synchronization Integration:
        - Calls add_favorite() → Triggers entity creation and UI updates
        - Voice confirmation → Immediate feedback while background sync occurs
        - Error responses → Clear feedback for duplicate favorites or API failures

        Args:
            number_text: User's numeric choice as string (e.g., "1", "2", "3")

        Returns:
            ConversationResult: Response with success confirmation or error message

        Side Effects:
            - Removes pending_choices from runtime_data → Clears temporary selection state
            - May add favorite → Triggers full synchronization cascade if successful
            - Logs selection and outcome → Debugging and monitoring purposes
        """
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
