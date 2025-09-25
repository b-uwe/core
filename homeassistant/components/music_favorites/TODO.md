# Music Favorites Integration Development TODO

## Development Phases

### Phase 1: Foundation (Bronze Essentials)
- [x] **Data Models** (`models.py`) - Most simplistic data model to get us started
- [x] **Config Flow** - Most simplistic Config Flow to get us started
- [x] **Persistent Data** - Create very first storage structure
- [x] **Basic Sensor Platform** - One (most simplistic) sensor per band
- [x] **First Visual Usage** - See the integration in action for the first time

### Phase 2: First Config Flow that actually works
- [x] **Add a logo** - Add a first logo for this integration - It's not a great one, but it does the job
- [x] **Entity Icons** - Set Entity Icons
- [x] **A proper Config Flow** - Create a very first "proper" Config Flow

### Phase 3: Core Features (Bronze Complete)
- [x] **Runtime Data** - Create very first storage structure
- [x] **Entity Unique IDs** - Proper identification
- [x] **Entity Naming** - `has_entity_name` pattern
- [x] **Testing Infrastructure** - 99% test coverage across all modules at the point of ticking this

### Phase 4: More Tiers
- [x] **Tick all the boxes** - and try not to cheat 😅
      To be fair, this isn't easy at all, but what's probably more important: I need to untick boxes
      again when moving forward!

### Phase 5: First API connections
- [x] **Connect to MusicBrainz** - Raw aiohttp implementation, no external deps
      Decision AGAINST an official API as this wouldn't meet quality standards in multiple ways
  - [x] Reset test-before-configure, test-before-setup, dependency-transparency
  - [x] Reset appropriate-polling, repair-issues (now todo - conservative approach)
  - [x] **Connectivity testing** - Config flow + setup entry validation
  - [x] **Error handling** - Specific exceptions + broad catch with logging
  - [x] **Async implementation** - No blocking calls, proper websession injection
- [ ] Allow Adding VIA MusicBrainz ID
- [ ] Feed name into MusicBrainz to get an ID back
- [ ] Error handling for "not" found
- [ ] Storing the ID from the first entry found
- [ ] Handling multiple entries by asking back with the user
- [ ] Storing all Aliases
- [ ] Attach BandsInTown
- [ ] Pull Events
  - [ ] Reset entity-event-setup

### Phase 6: YAML Setup
- [ ] Allow Setup 100% from YAML
- [ ] Disallow modifying Config set up from YAML

### Phase 7: Favorite Types
- [ ] **Split Acts into two** - distinguish bands from solo artists
- [ ] **Add Festivals** - Allow defining favorite festivals

## Architecture Notes

### Current Understanding
- **Local Storage**: Primary focus on local band/artist management
- **Future Cloud Integration**: ~25% chance of optional or necessary LOGIN to external services
- **Device Model**: ONE Instance of the Integration, ONE Device, one sensor entity per band/artist
- **Data Storage**: Case-insensitive band names, locally stored
- **Quality Target**: Platinum level from the start

## Checkboxes to tick
### Bronze
- [x] `action-setup` - Service actions are registered in async_setup
- [ ] `appropriate-polling` - If it's a polling integration, set an appropriate polling interval *(TODO: decide polling strategy for MusicBrainz)*
- [x] `brands` - Has branding assets available for the integration
- [x] `common-modules` - Place common patterns in common modules *(EXEMPT: no duplicate patterns)*
- [x] `config-flow-test-coverage` - Full test coverage for the config flow
- [x] `config-flow` - Integration needs to be able to be set up via the UI
- [x] `dependency-transparency` - Dependency transparency *(DONE: no external deps, raw aiohttp)*
- [x] `docs-actions` - The documentation describes the provided service actions that can be used
- [x] `docs-high-level-description` - The documentation includes a high-level description of the integration brand, product, or service
- [x] `docs-installation-instructions` - The documentation provides step-by-step installation instructions for the integration, including, if needed, prerequisites
- [x] `docs-removal-instructions` - The documentation provides removal instructions
- [x] `entity-event-setup` - Entity events are subscribed in the correct lifecycle methods *(EXEMPT: no external events)*
- [x] `entity-unique-id` - Entities have a unique ID
- [x] `has-entity-name` - Entities use has_entity_name = True
- [x] `runtime-data` - Use ConfigEntry.runtime_data to store runtime data
- [x] `test-before-configure` - Test a connection in the config flow *(DONE: MusicBrainz connectivity test)*
- [x] `test-before-setup` - Check during integration initialization if we are able to set it up correctly *(DONE: MusicBrainz connectivity test)*
- [x] `unique-config-entry` - Don't allow the same device or service to be able to be set up twice

### Silver
- [x] `action-exceptions` - Service actions raise exceptions when encountering failures
- [x] `config-entry-unloading` - Support config entry unloading
- [x] `docs-configuration-parameters` - The documentation describes all integration configuration options
- [x] `docs-installation-parameters` - The documentation describes all integration installation parameters
- [x] `entity-unavailable` - Mark entity unavailable if appropriate *(DONE: entities handle unavailability properly)*
- [x] `integration-owner` - Has an integration owner
- [x] `log-when-unavailable` - If internet/device/service is unavailable, log once when unavailable and once when back connected *(EXEMPT: local data only)*
- [x] `parallel-updates` - Number of parallel updates is specified
- [x] `reauthentication-flow` - Reauthentication needs to be available via the UI *(EXEMPT: no authentication)*
- [x] `test-coverage` - Above 95% test coverage for all integration modules

### Gold
- [x] `devices` - The integration creates devices
- [x] `diagnostics` - Implements diagnostics
- [x] `discovery-update-info` - Integration uses discovery info to update network information *(EXEMPT: local data only)*
- [x] `discovery` - Devices can be discovered *(EXEMPT: local data only)*
- [ ] `docs-data-update` - The documentation describes how data is updated
- [ ] `docs-examples` - The documentation provides automation examples the user can use.
- [ ] `docs-known-limitations` - The documentation describes known limitations of the integration (not to be confused with bugs)
- [ ] `docs-supported-devices` - The documentation describes known supported / unsupported devices
- [x] `docs-supported-functions` - The documentation describes the supported functionality, including entities, and platforms
- [ ] `docs-troubleshooting` - The documentation provides troubleshooting information
- [x] `docs-use-cases` - The documentation describes use cases to illustrate how this integration can be used
- [x] `dynamic-devices` - Devices added after integration setup *(EXEMPT: favorites managed via services)*
- [x] `entity-category` - Entities are assigned an appropriate EntityCategory *(EXEMPT: favorites are main content)*
- [x] `entity-device-class` - Entities use device classes where possible *(EXEMPT: no specific device class for favorites)*
- [x] `entity-disabled-by-default` - Integration disables less popular (or noisy) entities *(EXEMPT: all favorites should be visible)*
- [x] `entity-translations` - Entities have translated names
- [x] `exception-translations` - Exception messages are translatable *(EXEMPT: using standard HA exceptions)*
- [x] `icon-translations` - Entities implement icon translations
- [x] `reconfiguration-flow` - Integrations should have a reconfigure flow *(EXEMPT: no configuration to reconfigure)*
- [ ] `repair-issues` - Repair issues and repair flows are used when user intervention is needed *(TODO: MusicBrainz connectivity issues)*
- [x] `stale-devices` - Stale devices are removed *(EXEMPT: all data locally managed)*

### Platinum
- [x] `async-dependency` - Dependency is async *(DONE: pure aiohttp implementation)*
- [x] `inject-websession` - The integration dependency supports passing in a websession *(DONE: uses async_get_clientsession)*
- [x] `strict-typing` - Strict typing