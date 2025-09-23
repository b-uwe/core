# Architecture

  HA Devices Page:
  └── Gig Radar - Dad's Music Profile  [MASTER DEVICE]
      ├── Config Entry: Dad's Favorite Bands     [4 entities]
      ├── Config Entry: Dad's Favorite Festivals [3 entities]
      ├── Config Entry: Dad's Favorite Concerts  [2 entities]
      └── Config Entry: Dad's Favorite Venues    [3 entities]

  └── Gig Radar - Mom's Music Profile  [MASTER DEVICE]
      ├── Config Entry: Mom's Favorite Bands     [6 entities]
      ├── Config Entry: Mom's Favorite Festivals [2 entities]
      └── Config Entry: Mom's Favorite Venues    [1 entity]

# File Structure Explanation:

  homeassistant/components/gig_radar/
  └── manifest.json       ← Integration metadata
  ├── __init__.py         ← The functions in __init__.py get called when HA starts/stops our integration
  ├── models.py           ← Storage
  ├── config_flow.py      ← User interface for setup
  ├── const.py            ← Constants

## __init__.py

1. Makes the folder importable
2. Entry point for the integration
3. Contains setup/teardown functions:
  async def async_setup_entry():  # Called when integration starts
  async def async_unload_entry(): # Called when integration stops