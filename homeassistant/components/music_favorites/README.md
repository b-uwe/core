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

## Supported Functions

The Music Favorites integration provides comprehensive functionality for managing your favorite artists and integrating them into Home Assistant automations.

### **Core Functionality**

#### **Artist Management**
- **Add Favorites**: Add artists and bands to your personal collection
- **Remove Favorites**: Remove artists from your collection
- **Automatic Validation**: Validate artist names against MusicBrainz database
- **Metadata Storage**: Store MusicBrainz IDs and alternative name variants
- **Duplicate Prevention**: Automatic detection and prevention of duplicate entries

#### **Entity Creation**
- **Sensor Entities**: Each favorite automatically becomes a Home Assistant sensor entity
- **Calendar Entity**: Concert calendar showing upcoming events for all favorite artists
- **Next Shows Display**: Calendar includes "next_shows" attribute with upcoming concert list
- **Unique Identification**: Entities use stable, unique IDs for reliable automation
- **Attribute Exposure**: Artist metadata exposed as entity attributes
- **State Management**: Entity states available for automation triggers

### **Integration Features**

#### **Voice Control**
- **Natural Language**: Support for conversational commands via Home Assistant Assist
- **Add Commands**: "Track [Artist]", "Add [Artist] to music favorites", "+ [Artist]"
- **Remove Commands**: "Untrack [Artist]", "Remove [Artist] from music favorites", "- [Artist]"
- **Built-in Agent**: Integrated conversation agent requires no additional configuration

#### **Service Actions**
- **Programmatic Control**: Add and Delete access through Home Assistant services
- **Automation Integration**: Services can be called from automations, scripts, and scenes

#### **Home Assistant Integration**
- **Config Flow**: Full UI-based configuration with connectivity testing
- **Repair System**: Automatic issue detection and guided resolution for connectivity problems
- **Diagnostics**: Built-in diagnostic data collection for troubleshooting
- **Device Registry**: Integration appears as a device with associated entities

### **Data Management**

#### **Storage and Persistence**
- **Local Storage**: All data stored locally in Home Assistant's database
- **Automatic Backup**: Data included in Home Assistant backup/restore procedures
- **Migration Support**: Data preserved across Home Assistant updates
- **Config Entry**: Integration of Home Assistant's config entry system

#### **External Data Integration**
- **MusicBrainz Integration**: Real-time artist validation and metadata retrieval
- **Connectivity Monitoring**: Automatic detection of MusicBrainz connectivity issues
- **Rate Limiting**: Intelligent request management to respect API limits
- **Error Recovery**: Graceful handling of temporary service outages

### **Automation and Integration Points**

#### **Event System**
- **State Changes**: Entity state changes trigger automation events
- **Service Calls**: Service execution generates trackable events
- **Error Events**: Integration errors can trigger automation responses
- **Custom Events**: Support for custom event generation in future versions

#### **Template Support**
- **Entity Filtering**: Template support for filtering favorite entities
- **Dynamic Lists**: Generate dynamic lists of favorites for dashboards
- **Counting**: Template functions for counting and summarizing favorites
- **Sorting**: Support for sorting favorites by various criteria

#### **Dashboard Integration**
- **Entity Cards**: Favorites appear in standard entity cards
- **Auto-Entities**: Support for dynamic entity discovery in dashboards
- **Custom Cards**: Integration with custom Lovelace cards
- **Grouping**: Support for grouping and organizing favorite entities

### **Platform Support**

#### **Sensor Platform**
- **Entity Type**: Each favorite creates a sensor entity
- **State Information**: Current state (None, with future expansion planned)
- **Attributes**: Rich metadata including MusicBrainz ID and variants
- **Device Class**: Appropriate device classification for voice control

#### **Conversation Platform**
- **Intent Processing**: Built-in conversation agent for natural language commands
- **Command Recognition**: Pattern matching for add/remove operations
- **Response Generation**: Appropriate responses to voice commands
- **Integration Points**: Works with all Home Assistant voice assistant platforms

## Entities

The Music Favorites integration creates multiple types of entities:

### **Artist Sensor Entities**

Each favorite artist becomes a sensor entity with the following properties:

- **Entity ID**: `sensor.music_favorites_[artist_name]`
- **State**: Currently returns `None` (reserved for future features)
- **Attributes**:
  - `musicbrainz_id`: Unique identifier for the artist
  - `variants`: Alternative name variations
  - `friendly_name`: Display name for the artist
  - `icon`: Entity icon (mdi:account-music)

#### Example Artist Entity

```
Entity: sensor.music_favorites_misery_index
State: None
Attributes:
  musicbrainz_id: f9b57146-c5ce-41ad-adfb-ee904a4f7b19
  variants: []
  friendly_name: "Misery Index"
  icon: mdi:account-music
```

### **Concert Calendar Entity**

The integration also creates a calendar entity that displays upcoming concerts:

- **Entity ID**: `calendar.concert_calendar`
- **State**: Current calendar state (active/inactive)
- **Attributes**:
  - `next_shows`: Formatted list of next 10 upcoming concerts
  - `friendly_name`: "Concert Calendar"

#### Example Calendar Entity

```
Entity: calendar.concert_calendar
State: off
Attributes:
  next_shows: "1. Artist Name @ Venue Name - Jan 15, 2025 8:00 PM // 2. Another Artist @ Another Venue - Jan 20, 2025 7:30 PM // ..."
  friendly_name: "Concert Calendar"
```

#### Using the Next Shows Attribute

You can access the upcoming shows list in templates and automations:

```yaml
# Template example
{{ state_attr('calendar.concert_calendar', 'next_shows') }}

# Automation example
- alias: "Display Next Shows"
  trigger:
    platform: state
    entity_id: calendar.concert_calendar
    attribute: next_shows
  action:
    service: notify.mobile_app
    data:
      message: "Upcoming concerts: {{ state_attr('calendar.concert_calendar', 'next_shows') }}"
```

## Automation Examples

### Basic Favorite Management

#### Log Favorite Changes

Keep a record of all favorite additions and removals:

```yaml
automation:
  - alias: "Log Favorite Changes"
    trigger:
      - platform: event
        event_type: call_service
        event_data:
          domain: music_favorites
          service: add_favorite
      - platform: event
        event_type: call_service
        event_data:
          domain: music_favorites
          service: remove_favorite
    action:
      service: logbook.log
      data:
        name: "Music Favorites"
        message: >
          {% if trigger.event.data.service == 'add_favorite' %}
            Added "{{ trigger.event.data.service_data.name }}" to favorites
          {% else %}
            Removed "{{ trigger.event.data.service_data.name }}" from favorites
          {% endif %}
```

### Voice Assistant Integration

#### Voice-Controlled Favorite Management

The Music Favorites integration includes a built-in conversation agent that enables natural language control through Home Assistant Assist. You can use simple voice commands to manage your favorites:

**Supported Voice Commands:**

- **Adding Artists**: "Track Motörhead", "Add Bolt Thrower to music favorites", "+ Dyscarnate"
- **Removing Artists**: "Untrack Motörhead", "Remove Bolt Thrower from music favorites", "- Dyscarnate"

The integration's conversation agent automatically handles these commands without requiring additional configuration. Simply speak naturally to Home Assistant's voice assistant, and the commands will be processed automatically.

#### Custom Voice Integration

For advanced users who want to extend voice functionality, you can add custom conversation intents:

```yaml
# Custom conversation intents (add to configuration.yaml)
conversation:
  intents:
    AddMusicFavoriteCustom:
      - "I want to track {artist}"
      - "Please add {artist} to my collection"
      - "{artist} is my new favorite"
    RemoveMusicFavoriteCustom:
      - "I'm done with {artist}"
      - "Please remove {artist} from my collection"
      - "I no longer like {artist}"

# Intent handling automation
automation:
  - alias: "Handle Custom Music Favorite Intents"
    trigger:
      platform: conversation
      command:
        - "I want to track *"
        - "Please add * to my collection"
    action:
      service: music_favorites.add_favorite
      data:
        name: "{{ trigger.slots.artist }}"
        type: "artist"
```

### Dashboard and UI Integration

#### Create a Favorites Dashboard Card

Display your music favorites on a Home Assistant dashboard:

```yaml
# Lovelace dashboard card
type: entities
title: "🎵 My Music Favorites"
entities:
  - entity: sensor.music_favorites_pink_floyd
    name: "Pink Floyd"
  - entity: sensor.music_favorites_led_zeppelin
    name: "Led Zeppelin"
  - entity: sensor.music_favorites_metallica
    name: "Metallica"
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

### Advanced Automations

#### Spotify Integration Example

Automatically add currently playing artists to favorites (requires Spotify integration):

```yaml
automation:
  - alias: "Add Currently Playing to Favorites"
    trigger:
      platform: state
      entity_id: media_player.spotify
      attribute: media_artist
    condition:
      - condition: state
        entity_id: media_player.spotify
        state: "playing"
      - condition: template
        value_template: "{{ trigger.to_state.attributes.media_artist != trigger.from_state.attributes.media_artist }}"
    action:
      - service: input_boolean.turn_on
        target:
          entity_id: input_boolean.ask_add_favorite
      - delay: "00:00:05"
      - service: notify.mobile_app
        data:
          message: "Add {{ trigger.to_state.attributes.media_artist }} to favorites?"
          data:
            actions:
              - action: "ADD_FAVORITE"
                title: "Yes, Add to Favorites"
              - action: "SKIP_FAVORITE"
                title: "No, Skip"

  - alias: "Handle Add Favorite Response"
    trigger:
      platform: event
      event_type: mobile_app_notification_action
      event_data:
        action: "ADD_FAVORITE"
    action:
      service: music_favorites.add_favorite
      data:
        name: "{{ states.media_player.spotify.attributes.media_artist }}"
        type: "artist"
```

### Template Examples

#### Recently Added Favorites

Show your most recently added favorites:

```yaml
sensor:
  - platform: template
    sensors:
      recently_added_favorites:
        friendly_name: "Recently Added Favorites"
        value_template: >
          {{ states | selectattr('entity_id', 'match', '^sensor\.music_favorites_') |
             sort(attribute='last_changed', reverse=true) |
             map(attribute='name') | list | join(', ') | truncate(100) }}
        icon_template: mdi:clock-plus-outline
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

## Known Limitations

The Music Favorites integration has several current limitations that may be addressed in future versions:

### **Entity and Automation Constraints**

- **Static Entity States**: Favorite entities currently show `None` state - future versions will include concert/event data
- **Limited Metadata**: Entities only expose MusicBrainz ID and name variants, no additional artist information

### **Future Enhancements**

Many limitations are planned to be addressed in upcoming versions:

- Event/concert data integration
- Geographic filtering and location-based features

## Data Updates

### How Data is Updated

The Music Favorites integration uses multiple update mechanisms to keep your favorite artists' information current:

#### **Local Data Updates**

- **Immediate Updates**: When you add or remove favorites via service calls, changes are applied instantly
- **Entity State Changes**: Sensor entities are updated immediately when favorites are added/removed
- **Storage Persistence**: All changes are saved to Home Assistant's local database automatically

#### **MusicBrainz Integration**

- **Artist Validation**: When adding favorites, the integration queries MusicBrainz to validate artist names and retrieve metadata
- **Unique Identifiers**: MusicBrainz IDs are fetched and stored for each artist to ensure data consistency
- **Alternative Names**: Name variants and aliases are collected from MusicBrainz for improved matching

#### **Update Frequency**

- **User Actions**: Instant updates when using services or voice commands
- **External Data**: MusicBrainz queries occur only when adding new favorites (not on a schedule)
- **Connectivity Checks**: MusicBrainz connectivity is tested during setup and when connection issues are detected

#### **Future Update Plans**

- **Event Data**: Planned integration with concert/event APIs for live updates
- **Periodic Refresh**: Future versions will include scheduled updates for artist information
- **Smart Polling**: Update frequency will adapt based on data freshness and user activity

## Supported Devices

The Music Favorites integration is a service-based integration that does not directly interact with physical devices. However, it integrates with various Home Assistant components and external services.

## Technical Details

- **Storage**: Local SQLite database via Home Assistant's config entry system
- **API Rate Limiting**: Configured for future external API integration
- **Parallel Updates**: Limited to 1 concurrent update to respect future API limits

## Troubleshooting

This section covers common issues and their solutions when using the Music Favorites integration.

### **Setup and Configuration Issues**

#### **Integration Won't Load**
**Symptoms**: Integration doesn't appear in Devices & Services, or fails to load on startup.

**Solutions**:
1. **Check Home Assistant Version**: Ensure you're running Home Assistant 2025.9 or later
2. **Verify Configuration**: If using YAML setup, check `configuration.yaml` syntax
3. **Restart Home Assistant**: After adding YAML configuration, restart is required
4. **Check Logs**: Look for errors in Home Assistant logs (`Settings` → `System` → `Logs`)

**Log Examples to Look For**:
```
ERROR (MainThread) [homeassistant.setup] Setup failed for music_favorites
ERROR (MainThread) [homeassistant.loader] Unable to find integration music_favorites
```

#### **MusicBrainz Connectivity Problems**
**Symptoms**: Setup fails with "Cannot connect to MusicBrainz" error.

**Solutions**:
1. **Check Internet Connection**: Verify Home Assistant can access the internet
2. **Test MusicBrainz Access**: Try visiting `https://musicbrainz.org` from your network
3. **Firewall Settings**: Ensure outbound HTTPS (port 443) access is allowed
4. **Use Repair Flow**: The integration provides guided troubleshooting via Settings → System → Repairs

**Manual Connectivity Test**:
```bash
# From Home Assistant system/container:
curl -I https://musicbrainz.org/ws/2/artist
# Should return: HTTP/2 200
```

#### **Duplicate Integration Error**
**Symptoms**: "Single instance allowed" error when trying to add integration.

**Solutions**:
1. **Check Existing Installation**: Go to `Settings` → `Devices & Services` to see if already installed
2. **Remove Existing**: Delete existing installation before adding new one
3. **Clear Cache**: Restart Home Assistant if removal doesn't clear the restriction

### **Voice Control Issues**

#### **Voice Commands Not Working**
**Symptoms**: Voice assistant doesn't recognize music favorites commands.

**Solutions**:
1. **Check Assist Setup**: Verify Home Assistant Assist is configured in `Settings` → `Voice Assistants`
2. **Verify Conversation Entity**: Look for conversation entity in `Settings` → `Voice Assistants` → `Assist`
3. **Test Simple Commands**: Try basic commands like "Track Metallica" first
4. **Check Entity Names**: Voice commands work better with simpler artist names

**Troubleshooting Steps**:
```yaml
# Test if conversation agent is working:
# Go to Developer Tools → Services
service: conversation.process
data:
  text: "Track Metallica"
  language: en
```

#### **Artist Names Not Recognized**
**Symptoms**: Voice assistant can't understand specific artist names.

**Solutions**:
1. **Use Simpler Names**: Try using simpler variations of artist names
2. **Check Pronunciation**: Ensure clear pronunciation of artist names
3. **Alternative Names**: Try different variations (e.g., "Pink Floyd" vs "Floyd")
4. **Manual Service Calls**: Use services directly for problematic names

### **Service and Automation Issues**

#### **Service Calls Failing**
**Symptoms**: `music_favorites.add_favorite` service returns errors.

**Solutions**:
1. **Check Service Parameters**: Ensure required fields (`name`, `type`) are provided
2. **Verify Integration Status**: Confirm integration is loaded in Devices & Services
3. **Test MusicBrainz**: Service calls require MusicBrainz connectivity for new artists
4. **Check Logs**: Look for specific error messages in Home Assistant logs

**Example Correct Service Call**:
```yaml
service: music_favorites.add_favorite
data:
  name: "Led Zeppelin"
  type: "band"
```

#### **Entities Not Appearing**
**Symptoms**: Added favorites don't create sensor entities.

**Solutions**:
1. **Check Entity Registry**: Go to `Settings` → `Devices & Services` → `Entities`
2. **Verify Entity Names**: Look for `sensor.music_favorites_*` pattern
3. **Restart Integration**: Try reloading the integration
4. **Check Entity Status**: Entities might be disabled by default

### **Data and Storage Issues**

#### **Favorites Disappearing**
**Symptoms**: Previously added favorites are no longer visible.

**Solutions**:
1. **Check Integration Status**: Verify integration is still loaded and working
2. **Database Issues**: Check Home Assistant database integrity
3. **Backup Restore**: Use Home Assistant backup if data was recently lost
4. **Re-add Favorites**: May need to re-add favorites if storage was corrupted

#### **Duplicate Favorites**
**Symptoms**: Same artist appears multiple times or with different names.

**Solutions**:
1. **Name Consistency**: Use consistent naming when adding favorites
2. **MusicBrainz Matching**: Integration should prevent duplicates via MusicBrainz IDs
3. **Manual Cleanup**: Remove duplicate entries through UI or service calls
4. **Check Entity Registry**: Verify no orphaned entities exist

### **Performance and Connectivity Issues**

#### **Slow Response Times**
**Symptoms**: Adding favorites or voice commands are slow to respond.

**Solutions**:
1. **Check Internet Speed**: MusicBrainz queries require internet access
2. **Rate Limiting**: Adding many favorites quickly may trigger rate limits
3. **System Resources**: Verify Home Assistant system has adequate resources
4. **Network Latency**: Check network connectivity to MusicBrainz servers

#### **Integration Becomes Unavailable**
**Symptoms**: Integration shows as unavailable or entities become unavailable.

**Solutions**:
1. **Check System Status**: Verify Home Assistant core is running properly
2. **Restart Integration**: Try reloading the integration
3. **Check Dependencies**: Ensure all required Home Assistant components are working
4. **System Restart**: Full Home Assistant restart may resolve system-level issues

### **Getting Help and Diagnostics**

#### **Collecting Diagnostic Information**
When reporting issues, collect the following information:

1. **Home Assistant Version**: `Settings` → `System` → `About`
2. **Integration Diagnostics**: Download from `Settings` → `Devices & Services` → Music Favorites
3. **Relevant Logs**: Copy from `Settings` → `System` → `Logs`
4. **Configuration Details**: Sanitized configuration (remove sensitive data)

#### **Enable Debug Logging**
For detailed troubleshooting, enable debug logging:

```yaml
# Add to configuration.yaml
logger:
  default: info
  logs:
    homeassistant.components.music_favorites: debug
    homeassistant.components.music_favorites.musicbrainz: debug
```

#### **Common Log Messages**
- `MusicBrainz search failed: ...` - Network or API issues
- `Artist already exists: ...` - Duplicate prevention working correctly
- `Failed to add favorite: ...` - Service call or validation error
- `Repair issue created: ...` - Automatic problem detection

### **Advanced Troubleshooting**

#### **Network Proxy Issues**
If behind a corporate firewall or proxy:

1. **Configure Home Assistant Proxy**: Set up proxy settings in Home Assistant
2. **Whitelist MusicBrainz**: Add `musicbrainz.org` to proxy whitelist
3. **Test Direct Access**: Verify direct access to MusicBrainz API endpoints

#### **Custom Installation Issues**
For advanced users with custom setups:

1. **Container Networking**: Ensure container has internet access
2. **DNS Resolution**: Verify DNS can resolve `musicbrainz.org`
3. **Certificate Issues**: Check if TLS/SSL certificates are properly configured
4. **Firewall Rules**: Verify outbound HTTPS traffic is allowed

## Use Cases

The Music Favorites integration enables various practical applications for music enthusiasts and smart home automation.

## Support

Go away and come back when this is at least Beta 😅!
