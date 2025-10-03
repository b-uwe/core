"""Shared fixtures for Music Favorites tests."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_musicbrainz_client():
    """Mock MusicBrainz client fixture - auto-applied to all tests."""
    # Patch the imported symbol in __init__.py and coordinator.py
    with (
        patch(
            "homeassistant.components.music_favorites.MusicBrainzClient"
        ) as mock_client_class_init,
        patch(
            "homeassistant.components.music_favorites.coordinator.MusicBrainzClient"
        ) as mock_client_class_coordinator,
    ):
        # Create mock instance
        mock_client = AsyncMock()
        mock_client_class_init.return_value = mock_client
        mock_client_class_coordinator.return_value = mock_client

        # Mock successful search response
        mock_client.search_artists.return_value = [
            {
                "id": "test-artist-id",
                "name": "Test Artist",
                "disambiguation": "",
                "score": 100,
            }
        ]

        yield mock_client
