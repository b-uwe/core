# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this directory.

## Music Favorites integration

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
See Architecture.md

## Repository Structure

This directory holds the `Music Favorites` integration of Home Assistant. In parallel to the `music_favorites` folder are folders representing a variety of other Home Assistant integrations.

Claude is supposed to **ONLY AND SOLELY** work on and write to the `Music Favorites` integration hence to this folder. Other folders can be used for reference

## Development Workflow

1. The development workflow is described in upstream CLAUDE.md
2. I expect claude to ALWAYS ruff, mypy and lint its code before claiming anything would be done! That also applies to test code!
3. NO, ABSOLUTELY NO, error you find is irrelevant, independent of whether it has to do with your last changes or even the rough code area you want to touch. GO FIX EVERY error you find1
4. After each new feature implementation new tests are supposed to be created ALWAYS, so that coverage stays above 99%
5. After each new feature implementation check README.md and propose changes!