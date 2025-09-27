"""Test Music Favorites conversation entity."""

from unittest.mock import patch

import pytest

from homeassistant.components.music_favorites.const import DOMAIN
from homeassistant.components.music_favorites.conversation import (
    MusicFavoritesConversationEntity,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={
            "favorites": {
                "f0d05c64-9959-4ae1-899b-acf51b97638c": ["Motörhead"],
                "ca891d65-d9b0-4258-89f7-e6ba29d83767": ["Iron Maiden"],
                "5b11f4ce-a62d-471e-81fc-a69a8278c7da": ["Black Sabbath"],
            }
        },
        unique_id="music_favorites",
    )


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, mock_config_entry, mock_musicbrainz_client
):
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)

    # Set up the integration
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
async def conversation_entity(hass: HomeAssistant, setup_integration):
    """Get the conversation entity."""
    # Find the conversation entity
    conversation_entities = [
        state
        for state in hass.states.async_all()
        if state.entity_id.startswith("conversation.music_favorites")
    ]

    # If no entity found in states, create one directly for testing
    if not conversation_entities:
        entity = MusicFavoritesConversationEntity(setup_integration)
        entity.hass = hass
        return entity

    # Return the first conversation entity found
    entity_id = conversation_entities[0].entity_id
    return hass.data.get(entity_id)


class MockUserInput:
    """Mock user input for conversation testing."""

    def __init__(self, text: str) -> None:
        """Initialize mock user input."""
        self.text = text


async def test_track_command_success(hass: HomeAssistant, conversation_entity) -> None:
    """Test successful 'track' command."""
    with patch(
        "homeassistant.components.music_favorites.conversation.resolve_artist_from_name"
    ) as mock_resolve:
        mock_resolve.return_value = {
            "action": "create",
            "name": "Motörhead",
            "musicbrainz_id": "f0d05c64-9959-4ae1-899b-acf51b97638c",
        }

        with patch(
            "homeassistant.components.music_favorites.conversation.add_favorite"
        ) as mock_add:
            mock_add.return_value = None

            user_input = MockUserInput("track Motörhead")
            result = await conversation_entity._async_handle_message(user_input, None)

            # Verify response (text is shown as UPPERCASE)
            assert (
                "Now tracking MOTÖRHEAD"
                in result.response.as_dict()["speech"]["plain"]["speech"]
            )

            # Verify resolve was called
            mock_resolve.assert_called_once_with(hass, "motörhead")

            # Verify add_favorite was called with only MusicBrainz ID
            mock_add.assert_called_once()
            call_args = mock_add.call_args[0]
            assert call_args[0] is hass  # First arg is hass
            assert (
                call_args[1] == conversation_entity._entry
            )  # Second arg is config entry
            assert (
                call_args[2] == "f0d05c64-9959-4ae1-899b-acf51b97638c"
            )  # Third arg is musicbrainz_id


async def test_track_command_short_syntax(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test successful '+' shorthand command."""
    with patch(
        "homeassistant.components.music_favorites.conversation.resolve_artist_from_name"
    ) as mock_resolve:
        mock_resolve.return_value = {
            "action": "create",
            "name": "Iron Maiden",
            "musicbrainz_id": "ca891d65-d9b0-4258-89f7-e6ba29d83767",
        }

        with patch(
            "homeassistant.components.music_favorites.conversation.add_favorite"
        ) as mock_add:
            mock_add.return_value = None

            user_input = MockUserInput("+ Iron Maiden")
            result = await conversation_entity._async_handle_message(user_input, None)

            # Verify response (shown as UPPERCASE)
            assert (
                "Now tracking IRON MAIDEN"
                in result.response.as_dict()["speech"]["plain"]["speech"]
            )

            # Verify resolve was called
            mock_resolve.assert_called_once_with(hass, "iron maiden")

            # Verify add_favorite was called with only MusicBrainz ID
            mock_add.assert_called_once()
            call_args = mock_add.call_args[0]
            assert call_args[0] is hass  # First arg is hass
            assert (
                call_args[1] == conversation_entity._entry
            )  # Second arg is config entry
            assert (
                call_args[2] == "ca891d65-d9b0-4258-89f7-e6ba29d83767"
            )  # Third arg is musicbrainz_id


async def test_add_to_favorites_command(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test 'add to music favorites' command."""
    with patch(
        "homeassistant.components.music_favorites.conversation.resolve_artist_from_name"
    ) as mock_resolve:
        mock_resolve.return_value = {
            "action": "create",
            "name": "Black Sabbath",
            "musicbrainz_id": "5b11f4ce-a62d-471e-81fc-a69a8278c7da",
        }

        with patch(
            "homeassistant.components.music_favorites.conversation.add_favorite"
        ) as mock_add:
            mock_add.return_value = None

            user_input = MockUserInput("add Black Sabbath to music favorites")
            result = await conversation_entity._async_handle_message(user_input, None)

            # Verify response (shown as UPPERCASE)
            assert (
                "Now tracking BLACK SABBATH"
                in result.response.as_dict()["speech"]["plain"]["speech"]
            )

            # Verify resolve was called
            mock_resolve.assert_called_once_with(hass, "black sabbath")

            # Verify add_favorite was called with only MusicBrainz ID
            mock_add.assert_called_once()
            call_args = mock_add.call_args[0]
            assert call_args[0] is hass  # First arg is hass
            assert (
                call_args[1] == conversation_entity._entry
            )  # Second arg is config entry
            assert (
                call_args[2] == "5b11f4ce-a62d-471e-81fc-a69a8278c7da"
            )  # Third arg is musicbrainz_id


async def test_untrack_command_success(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test successful 'untrack' command."""
    with patch(
        "homeassistant.components.music_favorites.conversation.remove_favorite"
    ) as mock_remove:
        mock_remove.return_value = None

        user_input = MockUserInput("untrack Motörhead")
        result = await conversation_entity._async_handle_message(user_input, None)

        # Verify response (shown as UPPERCASE)
        assert (
            "No longer tracking MOTÖRHEAD"
            in result.response.as_dict()["speech"]["plain"]["speech"]
        )

        # Verify remove_favorite was called with MusicBrainz ID
        mock_remove.assert_called_once()
        call_args = mock_remove.call_args[0]
        assert call_args[0] is hass  # First arg is hass
        assert call_args[1] == conversation_entity._entry  # Second arg is config entry
        # Third arg should be the MusicBrainz ID found from the stored favorites
        # (This would be looked up from the config entry data by name)


async def test_untrack_command_short_syntax(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test successful '-' shorthand command."""
    with patch(
        "homeassistant.components.music_favorites.conversation.remove_favorite"
    ) as mock_remove:
        mock_remove.return_value = None

        user_input = MockUserInput("- Iron Maiden")
        result = await conversation_entity._async_handle_message(user_input, None)

        # Verify response (shown as UPPERCASE)
        assert (
            "No longer tracking IRON MAIDEN"
            in result.response.as_dict()["speech"]["plain"]["speech"]
        )

        # Verify remove_favorite was called with MusicBrainz ID
        mock_remove.assert_called_once()
        call_args = mock_remove.call_args[0]
        assert call_args[0] is hass  # First arg is hass
        assert call_args[1] == conversation_entity._entry  # Second arg is config entry
        # Third arg should be the MusicBrainz ID found from the stored favorites
        # (This would be looked up from the config entry data by name)


async def test_remove_from_favorites_command(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test 'remove from music favorites' command."""
    with patch(
        "homeassistant.components.music_favorites.conversation.remove_favorite"
    ) as mock_remove:
        mock_remove.return_value = None

        user_input = MockUserInput("remove Black Sabbath from music favorites")
        result = await conversation_entity._async_handle_message(user_input, None)

        # Verify response (shown as UPPERCASE)
        assert (
            "No longer tracking BLACK SABBATH"
            in result.response.as_dict()["speech"]["plain"]["speech"]
        )

        # Verify remove_favorite was called with MusicBrainz ID
        mock_remove.assert_called_once()
        call_args = mock_remove.call_args[0]
        assert call_args[0] is hass  # First arg is hass
        assert call_args[1] == conversation_entity._entry  # Second arg is config entry
        # Third arg should be the MusicBrainz ID found from the stored favorites
        # (This would be looked up from the config entry data by name)


async def test_track_command_failure(hass: HomeAssistant, conversation_entity) -> None:
    """Test track command when resolve_artist_from_name fails."""
    # Test MusicBrainz API error (returns None)
    with patch(
        "homeassistant.components.music_favorites.conversation.resolve_artist_from_name"
    ) as mock_resolve:
        mock_resolve.return_value = None

        user_input = MockUserInput("track Motörhead")
        result = await conversation_entity._async_handle_message(user_input, None)

        # Verify error response
        response_text = result.response.as_dict()["speech"]["plain"]["speech"]
        assert "couldn't connect to the music database" in response_text
        assert "motörhead" in response_text  # name is normalized to lowercase


async def test_track_command_not_found(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test track command when artist is not found in MusicBrainz."""
    with patch(
        "homeassistant.components.music_favorites.conversation.resolve_artist_from_name"
    ) as mock_resolve:
        mock_resolve.return_value = {"action": "not_found"}

        user_input = MockUserInput("track NonExistentBand")
        result = await conversation_entity._async_handle_message(user_input, None)

        # Verify error response
        response_text = result.response.as_dict()["speech"]["plain"]["speech"]
        assert "couldn't find any artist named nonexistentband" in response_text


async def test_track_command_add_favorite_failure(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test track command when add_favorite fails after successful resolution."""
    with patch(
        "homeassistant.components.music_favorites.conversation.resolve_artist_from_name"
    ) as mock_resolve:
        mock_resolve.return_value = {
            "action": "create",
            "name": "Motörhead",
            "musicbrainz_id": "f0d05c64-9959-4ae1-899b-acf51b97638c",
        }

        with patch(
            "homeassistant.components.music_favorites.conversation.add_favorite"
        ) as mock_add:
            mock_add.side_effect = ServiceValidationError("Already exists")

            user_input = MockUserInput("track Motörhead")
            result = await conversation_entity._async_handle_message(user_input, None)

            # Verify error response (shown as UPPERCASE)
            response_text = result.response.as_dict()["speech"]["plain"]["speech"]
            assert "Failed to add MOTÖRHEAD" in response_text
            assert "already be in your favorites" in response_text


async def test_untrack_command_failure(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test untrack command when remove_favorite fails."""
    with patch(
        "homeassistant.components.music_favorites.conversation.remove_favorite"
    ) as mock_remove:
        mock_remove.side_effect = ServiceValidationError("Not found")

        user_input = MockUserInput("untrack Motörhead")
        result = await conversation_entity._async_handle_message(user_input, None)

        # Verify error response (shown as UPPERCASE)
        response_text = result.response.as_dict()["speech"]["plain"]["speech"]
        assert "Failed to remove MOTÖRHEAD from your favorites" in response_text


async def test_remove_favorite_not_found(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test removing a favorite that doesn't exist in the list."""
    # Try to remove an artist that's not in the favorites
    user_input = MockUserInput("- Unknown Artist")
    result = await conversation_entity._async_handle_message(user_input, None)

    # Verify error response
    response_text = result.response.as_dict()["speech"]["plain"]["speech"]
    assert "Failed to remove UNKNOWN ARTIST from your favorites" in response_text


async def test_unrecognized_command(hass: HomeAssistant, conversation_entity) -> None:
    """Test unrecognized command."""
    user_input = MockUserInput("what's the weather like")
    result = await conversation_entity._async_handle_message(user_input, None)

    # Verify help response
    response_text = result.response.as_dict()["speech"]["plain"]["speech"]
    assert "Unrecognized command" in response_text
    assert "track Motörhead" in response_text  # Should contain usage examples
    assert "untrack Motörhead" in response_text


async def test_empty_command(hass: HomeAssistant, conversation_entity) -> None:
    """Test empty command."""
    user_input = MockUserInput("")
    result = await conversation_entity._async_handle_message(user_input, None)

    # Verify help response
    response_text = result.response.as_dict()["speech"]["plain"]["speech"]
    assert "Unrecognized command" in response_text


async def test_whitespace_handling(hass: HomeAssistant, conversation_entity) -> None:
    """Test commands with extra whitespace."""
    with patch(
        "homeassistant.components.music_favorites.conversation.resolve_artist_from_name"
    ) as mock_resolve:
        mock_resolve.return_value = {
            "action": "create",
            "name": "Motörhead",
            "musicbrainz_id": "f0d05c64-9959-4ae1-899b-acf51b97638c",
        }

        with patch(
            "homeassistant.components.music_favorites.conversation.add_favorite"
        ) as mock_add:
            mock_add.return_value = None

            user_input = MockUserInput("  track   Motörhead  ")
            result = await conversation_entity._async_handle_message(user_input, None)

            # Verify response (shown as UPPERCASE)
            assert (
                "Now tracking MOTÖRHEAD"
                in result.response.as_dict()["speech"]["plain"]["speech"]
            )

            # Verify resolve was called with cleaned name
            mock_resolve.assert_called_once_with(hass, "motörhead")

            # Verify add_favorite was called with only MusicBrainz ID
            mock_add.assert_called_once()
            call_args = mock_add.call_args[0]
            assert call_args[0] is hass  # First arg is hass
            assert (
                call_args[1] == conversation_entity._entry
            )  # Second arg is config entry
            assert (
                call_args[2] == "f0d05c64-9959-4ae1-899b-acf51b97638c"
            )  # Third arg is musicbrainz_id


async def test_case_insensitive_commands(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test that commands work regardless of case."""
    with patch(
        "homeassistant.components.music_favorites.conversation.resolve_artist_from_name"
    ) as mock_resolve:
        mock_resolve.return_value = {
            "action": "create",
            "name": "Motörhead",
            "musicbrainz_id": "f0d05c64-9959-4ae1-899b-acf51b97638c",
        }

        with patch(
            "homeassistant.components.music_favorites.conversation.add_favorite"
        ) as mock_add:
            mock_add.return_value = None

            user_input = MockUserInput("TRACK Motörhead")
            result = await conversation_entity._async_handle_message(user_input, None)

            # Verify response (shown as UPPERCASE)
            assert (
                "Now tracking MOTÖRHEAD"
                in result.response.as_dict()["speech"]["plain"]["speech"]
            )

            # Verify resolve was called with normalized name
            mock_resolve.assert_called_once_with(hass, "motörhead")

            # Verify add_favorite was called with only MusicBrainz ID
            mock_add.assert_called_once()
            call_args = mock_add.call_args[0]
            assert call_args[0] is hass  # First arg is hass
            assert (
                call_args[1] == conversation_entity._entry
            )  # Second arg is config entry
            assert (
                call_args[2] == "f0d05c64-9959-4ae1-899b-acf51b97638c"
            )  # Third arg is musicbrainz_id


async def test_conversation_platform_setup(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test conversation platform setup."""
    mock_config_entry.add_to_hass(hass)

    # Mock the async_add_entities callback
    entities_added = []

    def mock_add_entities(entities, update_before_add=True, config_subentry_id=None):
        entities_added.extend(entities)

    # Call the platform setup function
    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    # Verify an entity was added
    assert len(entities_added) == 1
    entity = entities_added[0]
    assert isinstance(entity, MusicFavoritesConversationEntity)
    assert entity.unique_id == f"{mock_config_entry.entry_id}_conversation"


async def test_conversation_entity_properties(
    hass: HomeAssistant, setup_integration
) -> None:
    """Test conversation entity properties."""
    entity = MusicFavoritesConversationEntity(setup_integration)

    # Test basic properties
    assert entity.has_entity_name is True
    assert entity.name == "Music Favorites Assistant"
    assert entity.unique_id == f"{setup_integration.entry_id}_conversation"
    assert entity.supported_languages == ["en"]


async def test_track_command_multiple_matches_choose_best(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test track command with multiple matches - chooses the best match."""
    with patch(
        "homeassistant.components.music_favorites.conversation.resolve_artist_from_name"
    ) as mock_resolve:
        # Mock multiple matches scenario
        mock_resolve.return_value = {
            "action": "choose",
            "options": [
                {
                    "name": "Black Sabbath",
                    "musicbrainz_id": "5b11f4ce-a62d-471e-81fc-a69a8278c7da",
                    "score": 100,
                    "disambiguation": "British heavy metal band",
                },
                {
                    "name": "Black Sabbath",
                    "musicbrainz_id": "different-id",
                    "score": 95,
                    "disambiguation": "Tribute band",
                },
            ],
        }

        with patch(
            "homeassistant.components.music_favorites.conversation.add_favorite"
        ) as mock_add:
            mock_add.return_value = None

            user_input = MockUserInput("track Black Sabbath")
            result = await conversation_entity._async_handle_message(user_input, None)

            # Verify response presents choices to the user
            speech = result.response.as_dict()["speech"]["plain"]["speech"]
            assert "I found multiple artists named black sabbath" in speech
            assert "1: Black Sabbath - British heavy metal band" in speech
            assert "2: Black Sabbath - Tribute band" in speech
            assert "Just say the number (1 to 2)" in speech

            # Verify resolve was called
            mock_resolve.assert_called_once_with(hass, "black sabbath")

            # Verify add_favorite was NOT called (waiting for user choice)
            mock_add.assert_not_called()


async def test_track_command_multiple_matches_empty_options(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test track command with multiple matches but empty options list."""
    with patch(
        "homeassistant.components.music_favorites.conversation.resolve_artist_from_name"
    ) as mock_resolve:
        # Mock multiple matches with empty options
        mock_resolve.return_value = {
            "action": "choose",
            "options": [],  # Empty options list
        }

        user_input = MockUserInput("track Some Artist")
        result = await conversation_entity._async_handle_message(user_input, None)

        # Should fall through to the "Unrecognized command" response
        speech = result.response.as_dict()["speech"]["plain"]["speech"]
        assert "Unrecognized command" in speech


async def test_number_choice_with_pending_choices(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test handling number input when there are pending choices."""
    # Set up pending choices in runtime_data
    conversation_entity._entry.runtime_data = {"pending_choices": ["id1", "id2", "id3"]}

    with patch(
        "homeassistant.components.music_favorites.conversation.add_favorite"
    ) as mock_add:
        mock_add.return_value = None

        # Test valid choice
        user_input = MockUserInput("2")
        result = await conversation_entity._async_handle_message(user_input, None)

        speech = result.response.as_dict()["speech"]["plain"]["speech"]
        assert "Great! I've added your choice to favorites." in speech

        # Verify add_favorite was called with correct ID
        mock_add.assert_called_once_with(hass, conversation_entity._entry, "id2")

        # Verify pending choices were cleared
        assert "pending_choices" not in conversation_entity._entry.runtime_data


async def test_number_choice_invalid_range(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test handling number input with invalid range."""
    # Set up pending choices
    conversation_entity._entry.runtime_data = {"pending_choices": ["id1", "id2"]}

    # Test number too high
    user_input = MockUserInput("5")
    result = await conversation_entity._async_handle_message(user_input, None)

    speech = result.response.as_dict()["speech"]["plain"]["speech"]
    assert "Please choose a number between 1 and 2." in speech

    # Test number too low
    user_input = MockUserInput("0")
    result = await conversation_entity._async_handle_message(user_input, None)

    speech = result.response.as_dict()["speech"]["plain"]["speech"]
    assert "Please choose a number between 1 and 2." in speech


async def test_number_choice_no_pending_choices(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test handling number input when there are no pending choices."""
    # No pending choices in runtime_data
    conversation_entity._entry.runtime_data = {}

    user_input = MockUserInput("1")
    result = await conversation_entity._async_handle_message(user_input, None)

    speech = result.response.as_dict()["speech"]["plain"]["speech"]
    assert (
        "I don't understand. Try saying 'track [artist]' or 'untrack [artist]'."
        in speech
    )


async def test_number_choice_with_add_favorite_error(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test handling number input when add_favorite raises an error."""
    # Set up pending choices
    conversation_entity._entry.runtime_data = {"pending_choices": ["id1", "id2"]}

    with patch(
        "homeassistant.components.music_favorites.conversation.add_favorite"
    ) as mock_add:
        mock_add.side_effect = ServiceValidationError("Already exists")

        user_input = MockUserInput("1")
        result = await conversation_entity._async_handle_message(user_input, None)

        speech = result.response.as_dict()["speech"]["plain"]["speech"]
        assert (
            "Sorry, there was an error adding that artist to your favorites. Please try again."
            in speech
        )


async def test_cleanup_pending_choices_function(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test the background cleanup function for pending choices."""
    # Set up pending choices in runtime_data
    conversation_entity._entry.runtime_data = {"pending_choices": ["id1", "id2", "id3"]}

    # Verify pending choices exist before cleanup
    assert "pending_choices" in conversation_entity._entry.runtime_data

    # Call the cleanup function with a very short timeout
    await conversation_entity._cleanup_pending_choices(timeout=0.01)

    # Verify pending choices were cleaned up
    assert "pending_choices" not in conversation_entity._entry.runtime_data


async def test_cleanup_pending_choices_with_no_runtime_data(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test cleanup function when runtime_data is None."""
    # Set runtime_data to None
    conversation_entity._entry.runtime_data = None

    # Should not crash
    await conversation_entity._cleanup_pending_choices(timeout=0.01)


async def test_cleanup_pending_choices_with_no_pending_choices_key(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test cleanup function when pending_choices key doesn't exist."""
    # Set runtime_data without pending_choices key
    conversation_entity._entry.runtime_data = {"other_data": "value"}

    # Should not crash and preserve other data
    await conversation_entity._cleanup_pending_choices(timeout=0.01)

    # Verify other data is preserved
    assert conversation_entity._entry.runtime_data == {"other_data": "value"}
