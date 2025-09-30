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
- [x] Feed name into MusicBrainz to get an ID back
- [x] Error handling for "not found"
- [x] Storing the ID from the first entry found
- [x] Handling multiple entries by asking back with the user
- [x] Storing all Aliases
- [x] Add inc=url-rels parameter to API calls and store links with the entity data
- [x] Check for whether an act is still active
- [x] Attach BandsInTown
- [x] Pull Events with automatic concert monitoring
- [x] Fire events for concert additions and removals
- [x] Implement smart update coordinator with snapshot cycles
- [x] Add comprehensive event data (venue, coordinates, dates)
- [ ] Attach setlist.fm
- [ ] Attribute the services used

### Phase 6: YAML Setup

- [ ] Allow Setup 100% from YAML
- [ ] Disallow modifying Config set up from YAML

### Phase 7: Favorite Types

- [ ] **Add Festivals** - Allow defining favorite festivals
- [ ] **Add Venues** - Allow defining favorite venues

## Architecture Notes

See architecture.md

## Checkboxes to watch for changes

### Bronze

- [x] `appropriate-polling` - Currently marked DONE because we don't update information yet
- [x] `common-modules` - To be re-evaluted every once in a while
- [x] `docs-actions` - To be re-checked should actions change
- [x] `docs-high-level-description` - To constantly be re-checked
- [x] `docs-installation-instructions` - To constantly be re-checked

### Silver

- [x] `docs-configuration-parameters` - To constantly be re-checked
- [x] `docs-installation-parameters` - To be re-checked once we dig deep into YAML-config
- [x] `log-when-unavailable` - To constantly be re-checked
- [x] `test-coverage` - To constantly be re-checked

### Gold

- [x] `diagnostics` - Can forever remain checked, but we should update contents every once in a while 😅
- [x] `docs-data-update` - To constantly be re-checked
- [x] `docs-examples` - To constantly be re-checked
- [x] `docs-known-limitations` - To constantly be re-checked
- [x] `docs-troubleshooting` - To constantly be re-checked
- [x] `docs-use-cases` - To constantly be re-checked

### Platinum

- [x] `async-dependency` - Check every once in a while
- [x] `inject-websession` - To be re-evaluated every once in a while
