# Changelog

## v0.2.3 — First GitHub release

Published as **Princess Slayer Achievement Mod**. The installer package is unchanged from the working v0.2.3 build.

- Recognizes source, compiled-only, and archived story menus.
- Uses the loaded menu's identity and full option fingerprint to validate matches.
- Handles Windows path capitalization, separators, and .rpy/.rpyc filenames.
- Preserves guided route progress through normal saves and loads.
- Adds bounded menu lookup diagnostics to troubleshooting reports.
- Displays the running version in the F8 panel.
- Uses F10 for guide visibility, leaving F9 available for the game's Quick Load.
- Retains the existing 562 achievement and gallery traces.

Validation: 21 portable regression checks passed during publication preparation. Earlier matching-engine checks covered source, compiled-only, and archived menus plus save/load behavior. The user subsequently confirmed the mod working on Windows Steam.

## Future releases

New versions will be published in this repository with separate version tags, release notes, and installer ZIPs. Previous release downloads will remain available.

