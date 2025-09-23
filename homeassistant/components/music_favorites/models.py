"""Data models for the Music Favorites integration."""

# The main favorites storage - a hopefully smart structure for fast lookups and variants
# Format: {"normalized_key": ["Display Name", "variant1", "variant2", ...]}
# Example: {"acdc": ["AC/DC", "ac/dc", "ac dc", "ac⚡️dc"]}
# - Key: normalized internal representation (lowercase, no spaces/punctuation)
# - First list item: canonical display name (how we show it to user)
# - Other items: alternative spellings/variants/maybeTypos for lookup
# TODO: Add smart normalization function to generate keys from user input
# TODO: Add variant detection/suggestion system
favorites: dict[str, list[str]] = {
    "metallica": ["Metallica", "metallica"],
    "ironmaiden": ["Iron Maiden", "iron maiden"],
    "acdc": ["AC/DC", "ac/dc", "ac dc"],
}


def add_favorite(name: str) -> bool:
    """Add a new favorite to our collection.

    For now, we'll do basic normalization. Later we'll add smart variant detection.
    """
    # Simple normalization for now - just lowercase and remove spaces
    key: str = name.lower().replace(" ", "").replace("/", "")

    # Check if this favorite already exists (any variant)
    if key in favorites:
        return False  # Already exists

    # Add new favorite with user's input as the canonical display name
    favorites[key] = [name, name.lower()]
    return True


def list_favorites() -> list[str]:
    """Get all favorites for display (canonical names only)."""
    return [favorite_variants[0] for favorite_variants in favorites.values()]


def get_favorite_count() -> int:
    """Get total number of favorites in collection."""
    return len(favorites)
