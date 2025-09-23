# Gig Radar Integration Development TODO

## Current Development Phase: Foundation

### Phase 1: Foundation (Bronze Essentials)
- [ ] **Data Models** (`models.py`) - Define how bands/artists are stored
- [ ] **Config Flow** - Redesign for adding bands (not connection-based)
- [ ] **Runtime Data** - Create proper storage structure
- [ ] **Basic Sensor Platform** - One sensor per band

### Phase 2: Core Features (Bronze Complete)
- [ ] **Entity Unique IDs** - Proper identification
- [ ] **Entity Naming** - `has_entity_name` pattern
- [ ] **Testing Infrastructure** - Config flow tests

### Phase 3: Robustness (Silver Features)
- [ ] **Entity Unavailability** - When bands are removed
- [ ] **Config Entry Unloading** - Proper cleanup
- [ ] **Parallel Updates** - Performance optimization

### Phase 4: Advanced Features (Gold/Platinum)
- [ ] **Device Management** - Proper device registry
- [ ] **Strict Typing** - Full type annotations
- [ ] **Diagnostics** - Debug information

## Architecture Notes

### Current Understanding
- **Local Storage**: Primary focus on local band/artist management
- **Future Cloud Integration**: ~25% chance of optional login to external services
- **Device Model**: One HA device per band/artist
- **Data Storage**: Case-insensitive band names, locally stored
- **Quality Target**: Platinum level from the start

### Key Design Decisions
1. **Hybrid Architecture**: Local-first with optional cloud enhancement
2. **No Required Authentication**: Core functionality works offline
3. **Optional Services**: Future integrations remain optional
4. **Case-Insensitive**: Band name normalization throughout