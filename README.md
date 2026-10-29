# Princess Slayer Achievement Mod

An in-game achievement and gallery guide for **Slay the Princess — The Pristine Cut** on Windows Steam.

The guide reads each player's current Steam achievements and gallery progress, recommends useful runs, and highlights the next choice in gold. New players start with recommendations based on their own progress; returning players get recommendations for what they still need.

**Current version: v0.2.3.** Tested against Steam build **19054935**, using Ren'Py **8.0.3.22090809**. Other game builds are not verified. The guide checks the game's story files and disables guidance if they do not match.

[**Download the latest release**](https://github.com/BoostedMage1612/Princess-Slayer-Achievement-Mod/releases/latest) · [All versions](https://github.com/BoostedMage1612/Princess-Slayer-Achievement-Mod/releases) · [Changelog](CHANGELOG.md)

## Install or update

1. Close Slay the Princess.
2. Download the installer ZIP attached to the latest release.
3. Right-click the ZIP and choose **Extract All**.
4. Run **1_Install_Guide.cmd**. The installer finds the Steam installation or lets you choose it.
5. Launch the game through Steam and press **F8**.
6. Choose a recommended run and select **Start this guided run** to begin a fresh game.

Use the attached installer ZIP rather than GitHub's automatically generated “Source code” downloads. No separate Python installation is needed.

The installer can update an older guide in place. It backs up the previous guide, replaces its files, and removes stale compiled guide files. Original story files and saves are preserved.

## Playing with the guide

- **F8:** open the guide and refresh Steam achievement and gallery progress.
- **F10:** show or hide the small guide panel.
- Follow the gold choice and advance dialogue normally. You still make every choice yourself.
- Keep playing the dialogue after a route's final planned choice: an achievement may trigger later in the scene.
- Make a normal game save to stop. Load that save to continue the guided run. Starting a guided run starts a fresh game.
- If you leave the recommended path, guidance pauses. A compatible route may offer **Join at the current choice**.

The game keeps its usual **F5 Quick Save** and **F9 Quick Load** controls.

The guide reads achievement status and recalculates its recommendations. It never grants, clears, or rewrites Steam achievements, and it does not change story or gallery flags. Achievements are earned through normal gameplay.

## Coverage and limits

- 131 Steam achievements in the catalog.
- 562 modeled decision traces covering 130 direct achievements and all 464 gallery requirements; gallery completion awards the remaining achievement through normal game logic.
- 556 indexed story menus, including compiled and archived menu support.
- Recommendations prioritize remaining achievements, then gallery progress, then fewer choices. They do not guarantee the mathematically smallest number of playthroughs.
- Steam must be available to confirm achievement ownership. Unknown achievement status remains in the plan.
- The guide can reveal spoilers. Other mods that change menus may conflict.
- An arbitrary existing save may not have a compatible route. One mapped scene intentionally closes the game; follow the guide's relaunch instruction.

## Troubleshooting and removal

If guidance stops, leave the game briefly at the affected choice, close it normally, and run **2_Collect_Troubleshooting.cmd**. The collector creates a troubleshooting ZIP with game/error logs and bounded guide diagnostics. It excludes saves and game assets.

For a bug report, include the mod version, game build, the choice where guidance stopped, and any error message.

To remove the mod, close the game and run **3_Uninstall_Guide.cmd**. Original scripts, saves, and earned achievements remain.

## Versions

This repository is the home for future versions. Each release gets its own version tag, notes, and installer ZIP. Older downloads remain available under **Releases**, and the latest-release link above points to the newest release.

v0.2.3 is the first published GitHub release. It retains the working package already tested on a Windows Steam installation. The package's original internal name, “Slay the Princess Achievement Guide,” remains unchanged.

## Source and validation

The repository includes the mod, Windows installer, route data, and developer regression checks. The runtime and installer are unchanged from the tested v0.2.3 package.

Portable checks:

```sh
python developer_tests/test_runtime.py
python developer_tests/test_locator.py
python developer_tests/test_routes.py
```

All 21 portable checks passed during publication preparation. See [VALIDATION.txt](VALIDATION.txt) for the original engine and installer test record and [SOURCE_NOTES.txt](SOURCE_NOTES.txt) for implementation details. Those files preserve the pre-playtest record; a subsequent Windows Steam playtest reported the mod working successfully. This does not establish compatibility with every game build or every possible save.

This is an unofficial fan-made mod. A copy of the game is required. Game content belongs to its creators; the package does not include game art, audio, fonts, executables, the engine SDK, saves, or the original game-script archive.

