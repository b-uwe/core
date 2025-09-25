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
        data={"favorites": {"test-id": ["Test Band"]}},
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

        # Verify add_favorite was called
        mock_add.assert_called_once()
        call_args = mock_add.call_args[0]
        assert call_args[2] == "motörhead"  # name (normalized to lowercase)
        assert call_args[3] == "band"  # type


async def test_track_command_short_syntax(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test successful '+' shorthand command."""
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

        # Verify add_favorite was called
        mock_add.assert_called_once()
        call_args = mock_add.call_args[0]
        assert call_args[2] == "iron maiden"  # name (normalized to lowercase)
        assert call_args[3] == "band"  # type


async def test_add_to_favorites_command(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test 'add to music favorites' command."""
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

        # Verify add_favorite was called
        mock_add.assert_called_once()
        call_args = mock_add.call_args[0]
        assert call_args[2] == "black sabbath"  # name (normalized to lowercase)


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

        # Verify remove_favorite was called
        mock_remove.assert_called_once()
        call_args = mock_remove.call_args[0]
        assert call_args[2] == "motörhead"  # name (normalized to lowercase)


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

        # Verify remove_favorite was called
        mock_remove.assert_called_once()
        call_args = mock_remove.call_args[0]
        assert call_args[2] == "iron maiden"  # name (normalized to lowercase)


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

        # Verify remove_favorite was called
        mock_remove.assert_called_once()
        call_args = mock_remove.call_args[0]
        assert call_args[2] == "black sabbath"  # name (normalized to lowercase)


async def test_track_command_failure(hass: HomeAssistant, conversation_entity) -> None:
    """Test track command when add_favorite fails."""
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
        "homeassistant.components.music_favorites.conversation.add_favorite"
    ) as mock_add:
        mock_add.return_value = None

        user_input = MockUserInput("  track   Motörhead  ")
        result = await conversation_entity._async_handle_message(user_input, None)

        # Verify response (shown as UPPERCASE, but internal name normalized to lowercase and stripped)
        assert (
            "Now tracking MOTÖRHEAD"
            in result.response.as_dict()["speech"]["plain"]["speech"]
        )

        # Verify add_favorite was called with cleaned name
        mock_add.assert_called_once()
        call_args = mock_add.call_args[0]
        assert call_args[2] == "motörhead"  # name should be stripped and lowercase


async def test_case_insensitive_commands(
    hass: HomeAssistant, conversation_entity
) -> None:
    """Test that commands work regardless of case."""
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

        # Verify add_favorite was called
        mock_add.assert_called_once()


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
