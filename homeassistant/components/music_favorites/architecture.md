# Architecture

This is more of an Uwe BrainDump on where I'm heading with this

## Goals

- User can add
  - Bands
  - Artists
  - Festivals
  - Venues
- The Integration tracks those and gives updates
  - Band is on tour
  - Band is going on a festival
  - New Bands on a festival
  - Festival has Running Order
  - Slot change on a Festival
  - New Concert in a Venue
  - ...

## Architectural Basics

- IN:
  - List of band and artist names
- Out:
  - Events
  - One sensor entity per favorite
    - Name
    - Type (Act, Festival, Venue, ...)
    - Last Update
    - Per Type attributes:
      - Location, Price
- Glue in between
  - Regular API calls to MusicBrainz, BandsInTown, ...

## Config Entry

- Singleton

## Services

- Adding and Removing Bands/Artists/Festivals/Venues

## Sensors

- Run adding and removing through Assist intents!
  - That's pretty much without alternative for all non-devs, because all other ways go
    either via Developer Tools or complicated MANUAL setups
- Event triggered by some internal logic, based on cloud polling

## Problems with this architecture

- No clue how to get the intents working. But I could get an own conversations running,
  so that we can bridge that for a while
- What I actually want is adding and removing favorite acts right from the list device 🤷
  in Devices & Services

### Sides notes

- The Calendar is not particularly useful. What's MORE useful is a list of upcoming
  events!
