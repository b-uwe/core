# Music Favorites Integration

## Overview

The Music Favorites integration allows you to manage and track your favorite bands, artists, festivals and venues within Home Assistant to get updates on what's going out of it.

### Key Features

- **Local Storage**: All data is stored locally in your Home Assistant instance
- **Entity Creation**: Each favorite artist becomes a sensor entity for automation use
- **Service Actions**: Programmatic control through Home Assistant services
- **Voice Control**: Add and remove artists using voice (which ACTUALLY is a hack)

## Installation Instructions

### Prerequisites

- Home Assistant 2025.9 or later
- Access to Home Assistant configuration files

### Setup Steps

1. **Add to Configuration**
   Add the following to your `configuration.yaml`:
   ```yaml
   music_favorites:
   ```

2. **Restart Home Assistant**
   Restart your Home Assistant instance to load the integration.

3. **Configure via UI** (Alternative)
   - Go to **Settings** → **Devices & Services**
   - Click **+ Add Integration**
   - Search for "Music Favorites"
   - Click **Add** (no configuration parameters required)

4. **Verify Installation**
   - Check **Developer Tools** → **Services** for `music_favorites.add_favorite`
   - Look for the conversation entity in **Settings** → **Voice Assistants**

### Installation Parameters

The Music Favorites integration uses a simplified installation process:

**UI Installation Parameters:**
- **No parameters required**: The integration uses an automatic "done immediately" configuration flow
- **Unique ID**: Automatically set to `music_favorites` (only one instance allowed)
- **Title**: Automatically set to "Music Favorites"

**YAML Installation Parameters:**
- **Domain**: `music_favorites` (required in configuration.yaml)
- **Options**: No additional options available during installation

**Installation Notes:**
- **Automatic Setup**: No user input required during installation
- **Single Instance**: Attempting to add a second instance will be prevented automatically
- **Immediate Activation**: Integration becomes active immediately after installation

## Configuration

### YAML Configuration

The Music Favorites integration can be configured via `configuration.yaml` with the following options:

```yaml
music_favorites:
  # Basic configuration (no parameters required)
```

**Configuration Parameters:**

Currently, the integration does not require any configuration parameters. Simply add `music_favorites:` to your `configuration.yaml` to enable the integration.

### Configuration Notes

- **Single Instance**: Only one Music Favorites integration instance is supported per Home Assistant installation
- **Local Storage**: All configuration and favorite data is stored locally in Home Assistant's database
- **No External Dependencies**: The integration works entirely offline and does not require internet connectivity for now. This is subject to change in the future

## Usage

### Voice Commands

Use Home Assistant's Assist feature with these natural language commands:

- **Adding Artists**:
  - "Track Motörhead
  - "Add Bolt Thrower to music favorites"
  - "+ Dyscarnate"

- **Removing Artists**:
  - "Untrack Motörhead"
  - "Remove Bolt Thrower from music favorites"
  - "- Dyscarnate"

### Service Actions

The integration provides the following service actions:

#### `music_favorites.add_favorite`

Adds a new artist to your favorites collection.

**Parameters**:
- `name` (required): Name of the artist or band
- `type` (required): Type of favorite ("band" or "artist")
- `config_entry` (optional): Specific config entry ID (auto-detected if not provided)

**Example**:
```yaml
service: music_favorites.add_favorite
data:
  name: "Pink Floyd"
  type: "band"
```

#### `music_favorites.remove_favorite`

Removes an artist from your favorites collection.

**Parameters**:
- `name` (required): Name of the artist or band to remove
- `config_entry` (optional): Specific config entry ID (auto-detected if not provided)

**Example**:
```yaml
service: music_favorites.remove_favorite
data:
  name: "Pink Floyd"
```

## Entities

Each favorite artist becomes a sensor entity with the following properties:

- **Entity ID**: `sensor.music_favorites_[artist_name]`
- **State**: Currently returns `None` (reserved for future features)
- **Attributes**:
  - `musicbrainz_id`: Unique identifier for the artist
  - `variants`: Alternative name variations

### Example Entity

```
Entity: sensor.music_favorites_misery_index
State: None
Attributes:
  musicbrainz_id: f9b57146-c5ce-41ad-adfb-ee904a4f7b19
  variants: []
```

## Automation Examples

### Notification on New Favorite

```yaml
automation:
  - alias: "New Favorite Added"
    trigger:
      platform: event
      event_type: state_changed
    condition:
      condition: template
      value_template: "{{ trigger.to_state.entity_id.startswith('sensor.music_favorites_') }}"
    action:
      service: notify.mobile_app
      data:
        message: "Added {{ trigger.to_state.name }} to your music favorites!"
```

## Removal Instructions

### Remove Integration

1. **Via UI**:
   - Go to **Settings** → **Devices & Services**
   - Find "Music Favorites" integration
   - Click the three dots menu → **Delete**

2. **Clean Up Entities** (if needed):
   - Go to **Settings** → **Devices & Services** → **Entities**
   - Filter by "music_favorites"
   - Remove any remaining entities manually

### Data Removal

All favorite data is automatically removed when the integration is deleted. No additional cleanup is required.

## Technical Details

- **Update Interval**: 6 hours (configurable in future versions)
- **Storage**: Local SQLite database via Home Assistant's config entry system
- **API Rate Limiting**: Configured for future external API integration
- **Parallel Updates**: Limited to 1 concurrent update to respect future API limits

## Troubleshooting

tbd.

This is Pre-Alpha 😅

## Support

Go away!