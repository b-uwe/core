# Architecture

## Goals
* User can add
  * Bands
  * Artists
  * Festivals
  * Venues
* The Integration tracks those and gives updates
  * Band is on tour
  * Band is going on a festival
  * New Bands on a festival
  * Festival has Running Order
  * Slot change on a Festival
  * New Concert in a Venue
  * ...
## Architectual Basics
* IN:
  * List of Name/Type Tupels
* Out:
  * Events containing Text
  * One sensor entity per favorite
    * Name
    * Type (Band, Artist, Festival, Venue, ...)
    * Last Messages
    * Last Update
    * Per Type attributes:
      * Location, Price
* Glue in between
  * Regular API calls to MusicBrainz, BandsInTown, ...
## Config Entry
* Singleton
## Services
* Adding and Removing Bands/Artists/Festivals/Venues
## Sensors
* Run adding and removing through Assist intents!
  * That's pretty much without alternative for all non-devs, because all other ways go either via Developer Tools
      or complicated MANUAL setups
* Event triggered by some internal logic, based on cloud polling
## Problems with this architecture
* No clue how to get the intents working. But I could get an own conversations running, so that we can bridge that for a while

# File Structure Explanation:

  homeassistant/components/gig_radar/
  └── manifest.json       ← Integration metadata
  ├── __init__.py         ← The functions in __init__.py get called when HA starts/stops our integration
  ├── models.py           ← Storage
  ├── config_flow.py      ← User interface for setup
  ├── const.py            ← Constants
  ├── sensor.py           ← Sensors

## const.py
1. Holds all constants, out of which "DOMAIN" is the only REQUIRED one

## __init__.py
1. Makes the folder importable
2. Entry point for the integration
3. Contains setup/teardown functions:
  * async_setup():        # Called when the integration starts from YAML
    * We make this run async_setup_entry() internally
    * \_init_flow() is a helper for that
    * \_init_flow() calls the Import Flow, which triggers MusicFavoritesConfigFlow.async_step_import() from config_flow.py
  * async_setup_entry():  # Called when the integration starts from UI
    * Initalizes all Platform (=Entity Type) modules (only SENSOR from sensor.py in our case)
  * async_unload_entry(): # Called when the integration stops

## config_flow.py
1. Most importantly, this defines the UI of the config flow, starting with the fields to show, which is reflected in
   STEP_USER_DATA_SCHEMA. In our case, it's just simply EMPTY, which simplifies the WHOLE file massively
2. The class MusicFavoritesConfigFlow defines
  * A Config Flow Version, in case the data gathered from the Config Flow needs to change at some point
  * A method to read a config from YAML
  * A method to read the (non existing) config from the empty Config Flow

## sensor.py
1. Defines the sensors we will use in the integration
  * Right now, there's only one: FavoriteSensor
2. async_setup_entry