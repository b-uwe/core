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
## Architectural Basics
* IN:
  * List of Name/Type Tuples
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