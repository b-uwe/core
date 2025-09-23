# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this directory.

## Gig radar integration

### Being a learning project
While this Home Assistant integration has the goal to end up in something usable and useful, it is as well a learning project for the code owner!
Assume the following:
* No idea about the Home Assistant architecture
* Absolutely no knowledge about Python (though you can assume a mediocre coding knowledge in general)

Accordingly, QUESTION and COMMENT every decision taken by the user and EXPLAIN your decisions in DETAIL!
Also, don't really code much yourself, and especially not in big blocks, but rather help the user code!

### Code Quality
The goal is 100% a platinum integration! No less than that!
Accordingly, whenever architectural decisions are made, code is written, comments are added, ..., teach the code owner to do it RIGHT, right from the start! Do strict typing! Do async! ALL of such things

### Goal of the integration
Besides being a learning project, we aim for the following
1. A local list of favorite bands and artists of a user

### Architecture
What we aim for, FINALLY, is something like this:

  HA Devices Page:
  └── Dad's Gig Radar  [MASTER DEVICE]
      ├── Config Entry: Dad's Favorite Acts      [4 entities]
      ├── Config Entry: Dad's Favorite Festivals [3 entities]
      ├── Config Entry: Dad's Favorite Concerts  [2 entities]
      └── Config Entry: Dad's Favorite Venues    [3 entities]

  └── Mom's Gig Radar  [MASTER DEVICE]
      ├── Config Entry: Mom's Favorite Acts      [6 entities]
      ├── Config Entry: Mom's Favorite Festivals [2 entities]
      └── Config Entry: Mom's Favorite Venues    [1 entity]

But we start piece by piece, and here's the starting point
1. One Device per Band/Artist list
  * stored locally only
  * just name for a start
  * name case insensitive
2. We start completely local! But we design in a way that allows later addition of cloud fetched information, including data behind a login

## Repository Structure

This directory holds the `Gig Radar` integration of Home Assistant. In parallel to the `gig_radar` folder are folders representing a variety of other Home Assistant integrations.

Claude is supposed to **ONLY AND SOLELY** work on and write to the `Gig Radar` integration hence to this folder. Other folders can be used for reference

## Development Workflow

The development workflow is described in upstream CLAUDE.md