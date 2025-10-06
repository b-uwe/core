# Music Favorites Integration

## Overview

The Music Favorites integration allows you to manage and track your favorite bands, artists, festivals and venues within Home Assistant to get updates on what's cooking around your Music Favorites.

**Key Features:**

- Track your favorite artists with automatic sensor entities
- Monitor upcoming concerts with integrated calendar
- Get real-time notifications when tours are announced or cancelled
- Voice control through Home Assistant Assist
- Automatic updates from MusicBrainz and Bandsintown

## Quick Start

### Installation

**Prerequisites:** Home Assistant 2025.9 or later

**Via UI** (Recommended):

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Music Favorites"
4. Click **Add**

**Via configuration.yaml**:

```yaml
music_favorites:
```

Then restart Home Assistant.

### Integrating the Conversation Agent

1. Go to **Settings** → **Voice Assistants**
2. Click **+ Add assistant**
3. Configure a new Voice Assistant, Set the Language to English, and the Conversation Agent to "Music Favorites Assistant"
4. Either make the new Voice Assistant the Default Assistant, Connect it to a dedicated Voice Hardware or open Assist and change the Assistant there

### Adding Your First Favorite

**Using Voice:**
Say to Home Assistant Assist: _"Add Motörhead to music favorites"_

**Using Text input for Assist:**
Just type _"+ Motörhead"_

**Using Service Call:**

```yaml
action: music_favorites.add_favorite
data:
  musicbrainz_id: ca891d65-d9b0-4258-89f7-e6ba29d83767
```

Take note that Service Calls don't allow for disambiguaty, that's why a name is not sufficient.

### What You Get

After adding a favorite, you'll immediately see:

- `sensor.music_favorites_motorhead` - Shows band status (Active, On Tour, etc.) and provides additional information
- `calendar.music_favorites` - Displays all upcoming concerts
- `select.music_favorites_distance_filter` - Control concert distance filtering

## Entities

The integration creates multiple entity types to track your favorites:

### Artist Sensor Entities

Each favorite artist becomes a sensor entity with rich metadata and dynamic status tracking:

- **Entity ID**: `sensor.music_favorites_[artist_name]`
- **State**: Band status (Active, On Tour, Tour Planned, Disbanded, Reformed, Unknown)
- **Icon**: Dynamic icon based on status:
  - `mdi:guitar-electric` (Active)
  - `mdi:bus-marker` (On Tour)
  - `mdi:bus-clock` (Tour Planned)
  - `mdi:music-off` (Disbanded)
  - `mdi:set-none` (Reformed)
  - `mdi:help-circle` (Unknown)
- **Attributes**:
  - `musicbrainz_id`: Unique MusicBrainz identifier
  - `variants`: Alternative name variations and aliases
  - `upcoming_concerts`: Text summary of all upcoming concerts
  - `musicbrainz_url`: Link to MusicBrainz artist page
  - `bandsintown_url`: Link to Bandsintown artist page (when available)
  - Additional relation URLs

### Concert Calendar Entity

Aggregates upcoming concerts from all favorite artists into a single calendar:

- **Entity ID**: `calendar.music_favorites`
- **State**: `on` when an event is currently happening, `off` otherwise
- **Attributes**:
  - `next_shows`: Formatted text list of next 10 upcoming concerts
  - `message`: Current event details (when state is `on`)
  - `start_time`, `end_time`, `location`, `description`: Event details
- **Event Details**: Full concert information including venue, address, coordinates, and event link

### Distance Filter Select Entity

Controls the maximum distance for concert filtering in the calendar:

- **Entity ID**: `select.music_favorites_distance_filter`
- **State**: Currently selected distance (e.g., "50 km", "No limit")
- **Options**: ["25 km", "50 km", "100 km", "200 km", "500 km", "No limit"]
- **Icon**: `mdi:map-marker-radius`
- **Behavior**: Calendar automatically updates when selection changes

## Features

### Voice Control

Use natural language commands via Home Assistant Assist (requires Assist pipeline setup):

**Adding Artists:**

- "Add Bolt Thrower to music favorites"
- "Track Motörhead"
- "+ Dyscarnate"

**Removing Artists:**

- "Remove Bolt Thrower from music favorites"
- "Untrack Motörhead"
- "- Dyscarnate"

### Service Actions

#### `music_favorites.add_favorite`

Adds a new artist to your favorites collection.

**Parameters:**

- `musicbrainz_id` (required): The MusicBrainz ID of the favorite to add

**Example:**

```yaml
action: music_favorites.add_favorite
data:
  musicbrainz_id: f0d05c64-9959-4ae1-899b-acf51b97638c
```

#### `music_favorites.remove_favorite`

Removes an artist from your favorites collection.

**Parameters:**

- `musicbrainz_id` (required): The MusicBrainz ID of the favorite to remove

**Example:**

```yaml
action: music_favorites.remove_favorite
data:
  musicbrainz_id: f0d05c64-9959-4ae1-899b-acf51b97638c
```

### Event System

The integration fires Home Assistant events for automation triggers:

**Status Change Events:**

- `music_favorites_status_changed` - When artist status changes (Active → On Tour, Disbanded → Reformed, etc.)

**Concert Events:**

- `music_favorites_event_added` - When a new concert is detected
- `music_favorites_event_removed` - When a concert is cancelled

### Data Management

**Storage:**

- All data stored locally in Home Assistant's config entry system
- Included in Home Assistant backup/restore procedures
- Preserved across Home Assistant updates

**Updates:**

- **Immediate**: Changes when using services or voice commands
- **Automatic**: Concert data checked every 24 hours (distributed to avoid rate limits)
- **External Sources**: MusicBrainz (artist metadata) and Bandsintown (concert data)

## Events

The Music Favorites integration automatically monitors concert schedules for your favorite artists and fires Home Assistant events when concerts are added or removed.

### Status Change Events

#### `music_favorites_status_changed`

Fired when an artist's status changes (e.g., from "Active" to "On Tour", "Disbanded" to "Reformed", etc.).

**Event Data:**

- `musicbrainz_id`: Unique MusicBrainz identifier for the artist
- `artist_name`: Name of the artist
- `old_status`: Previous status value
- `new_status`: New status value after update
- `reformed_date`: ISO date string (only when transitioning to "Reformed" status)

**Status Values:**

- **Active**: Band is active but no upcoming tour events detected
- **Disbanded**: Band has officially ended (according to MusicBrainz)
- **On Tour**: Band has concerts within the next 30 days or had concerts in the last 2 days
- **Reformed**: Band has recently reformed after being disbanded (shown for 6 months)
- **Tour Planned**: Band has concerts scheduled within the next 180 days
- **Unknown**: Status could not be determined

**Example Event Data:**

```yaml
event_type: music_favorites_status_changed
data:
  musicbrainz_id: "ca891d65-d9b0-4258-89f7-e6ba29d83767"
  artist_name: "Iron Maiden"
  old_status: "Disbanded"
  new_status: "Reformed"
  reformed_date: "2025-10-05"
```

### Concert Event Types

#### `music_favorites_event_added`

Fired when a new concert is detected for one of your favorite artists.

**Event Data:**

- `musicbrainz_id`: Unique MusicBrainz identifier for the artist
- `artist_name`: Name of the artist
- `event_title`: Concert/event title (e.g., "World Tour 2025")
- `event_date`: Date of the concert (YYYY-MM-DD format)
- `venue`: Venue name where the concert will take place
- `venue_address`: Full address of the venue (when available)
- `latitude`: Geographic latitude of the venue (when available)
- `longitude`: Geographic longitude of the venue (when available)
- `url`: Direct link to event details on Bandsintown

**Example Event Data:**

```yaml
event_type: music_favorites_event_added
data:
  musicbrainz_id: "ca891d65-d9b0-4258-89f7-e6ba29d83767"
  artist_name: "Iron Maiden"
  event_title: "The Future Past World Tour"
  event_date: "2025-07-15"
  venue: "Madison Square Garden"
  venue_address: "4 Pennsylvania Plaza, New York, NY 10001"
  latitude: 40.7505
  longitude: -73.9934
  url: "https://www.bandsintown.com/e/102845109"
```

#### `music_favorites_event_removed`

Fired when a previously announced concert is cancelled or removed from the schedule.

**Event Data:**

- `musicbrainz_id`: Unique MusicBrainz identifier for the artist
- `artist_name`: Name of the artist
- `event_title`: Concert/event title
- `event_date`: Original date of the cancelled concert
- `venue`: Venue name where the concert was scheduled
- `venue_address`: Address of the venue (when available)

**Example Event Data:**

```yaml
event_type: music_favorites_event_removed
data:
  musicbrainz_id: "ca891d65-d9b0-4258-89f7-e6ba29d83767"
  artist_name: "Iron Maiden"
  event_title: "The Future Past World Tour"
  event_date: "2025-07-15"
  venue: "Madison Square Garden"
  venue_address: "4 Pennsylvania Plaza, New York, NY 10001"
```

## Usage Examples

### Status Change Notifications

Get notified when your favorite artists' status changes:

```yaml
alias: Act Status Change
description: Raises an alert when the status of a favorite act changes
triggers:
  - trigger: event
    event_type: music_favorites_status_changed
conditions: []
actions:
  - data:
      message: >-
        Status of {{ trigger.event.data.artist_name }} changed from {{
        trigger.event.data.old_status }} to {{ trigger.event.data.new_status }}
    action: notify.persistent_notification
mode: single
```

### Concert Announcement Alerts

Get notified when bands announce tours:

```yaml
alias: New Concert Alert
description: Raises an alert when there is a new concert of one of my favorite acts
triggers:
  - trigger: event
    event_type: music_favorites_event_added
conditions: []
actions:
  - data:
      message: >
        🎵 New Concert Alert! {{ trigger.event.data.artist_name }} announced a
        concert! 📅 {{ trigger.event.data.event_date }} 📍 {{
        trigger.event.data.venue }} 🔗 {{ trigger.event.data.url }}
    action: notify.persistent_notification
mode: single
```

### Smart Home Integration

Change your smart home settings when concerts are announced:

```yaml
description: Concert Mood Lighting
mode: single
triggers:
  - trigger: event
    event_type: music_favorites_event_added
conditions:
  - condition: template
    value_template: >-
      {{ trigger.event.data.artist_name in ['Iron Maiden', 'Motörhead', 'Black Sabbath'] }}
actions:
  - action: light.turn_on
    target:
      entity_id: light.living_room_light
    data:
      color_name: red
      brightness: 255
  - action: tts.speak
    metadata: {}
    data:
      entity_id: media_player.living_room_speaker
      message: "{{ trigger.event.data.artist_name }} just announced a concert!"
alias: Concert Mood Lighting
```

### Dashboard Examples

#### Create a Favorites Dashboard Card

Display your music favorites on a Home Assistant dashboard:

```yaml
type: entities
title: "🎵 My Music Favorites"
entities:
  - entity: sensor.music_favorites_dyscarnate
    name: "Dyscarnate"
  - entity: sensor.music_favorites_misery_index
    name: "Misery Index"
  - entity: sensor.music_favorites_watain
    name: "Watain"
show_header_toggle: false
```

#### Dynamic Favorites List

Automatically show all music favorite entities:

```yaml
type: auto-entities
card:
  type: entities
  title: "🎵 Music Favorites"
filter:
  include:
    - entity_id: "sensor.music_favorites_*"
  exclude: []
sort:
  method: name
```

#### Calendar Integration

Display upcoming concerts in a calendar card:

```yaml
type: calendar
entities:
  - calendar.music_favorites
```

## Advanced Topics

### Technical Details

- **Storage**: Local SQLite database via Home Assistant's config entry system
- **API Rate Limiting**: Intelligent request management to respect API limits
- **Parallel Updates**: Limited to 1 concurrent update to respect API limits
- **Supported Devices**: Service-based integration (no physical devices)

### Data Updates

**Update Frequency:**

- User Actions: Instant updates when using services or voice commands
- Concert Data: Checked every 24 hours across all favorite artists
- Update Distribution: Checks distributed evenly across 24-hour interval to avoid rate limits
- MusicBrainz Refresh: Artist metadata refreshed during each concert data update cycle
- Connectivity Checks: External service connectivity monitored continuously

**External Data Sources:**

- **MusicBrainz**: Artist validation, metadata, name variants, relation links
- **Bandsintown**: Concert schedules, venue information, geographic data

### Removal Instructions

**Remove Integration:**

1. Go to Settings → Devices & Services
2. Find "Music Favorites" integration
3. Click the three dots menu → Delete
4. (Optional) Clean up remaining entities in Settings → Devices & Services → Entities

**Data Removal:**
All favorite data is automatically removed when the integration is deleted. No additional cleanup is required.

### Known Limitations

**Current Limitations:**

- Concert data only available through Bandsintown (limited artist coverage)
- Distance filtering requires Home Assistant location to be configured
- No support for festivals or venues as separate favorites (artist-only currently)

**Future Enhancements:**

- Additional concert data sources
- Festival and venue tracking
- Enhanced filtering options
- Historical concert data

## Support

Go away and come back when this is at least Beta 😅!
