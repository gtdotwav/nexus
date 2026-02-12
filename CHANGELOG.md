# Changelog

All notable changes to NEXUS will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---


## [0.3.1] - 2026-02-12

### Fixed

- **consciousness.py: 3 more sync I/O points**: `_load_session_count()`, `_save_session_count()`, and `reflect_and_save()` were still blocking the event loop. All converted to aiofiles
- **event_bus.py: threadsafe emission broken**: `call_soon_threadsafe(asyncio.ensure_future, ...)` was wrong — `ensure_future` can't be called that way from a non-async context. Fixed to `asyncio.run_coroutine_threadsafe()`
- **brain/reasoning.py: boundary crash in creature tier**: `self.memory.floors[pos.z]` accessed before checking if `pos.z` exists. Rewritten with proper guard
- **brain/strategic.py: empty response crash**: `response.content[0].text` would IndexError if API returned empty content. Added null check
- **core/foundry.py: sync I/O in async**: `initialize()` and `_save_history()` used blocking `open()`. Migrated to aiofiles
- **core/recovery.py: uninitialized field**: `_last_recovery_end` was used in `start_recovery()` but never initialized, causing AttributeError on first death
- **core/state/game_state.py: listener iteration safety**: `_notify()` now copies callback list before iterating, preventing issues if listeners modify the list during dispatch
- **core/loops/metrics.py: null route crash**: `len(agent.navigator.active_route)` crashed if route was None. Added `or []` guard
- **brain/reasoning.py: null profile crash**: `get_reasoning_context()` would fail if `analyze()` never ran. Added None check

### Changed

- **Version alignment**: Fixed version inconsistency across 5 files — main.py (was 0.1.0), nexus_cli.py (was 0.1.0), config/settings.yaml (was 0.2.0) now all 0.3.1
- **main.py consolidated**: Was 174 lines duplicating nexus_cli.py logic with argparse. Now a thin redirect to the Click-based CLI
- **pyproject.toml deps complete**: Added missing `pydantic>=2.5.0` and `sqlite-utils>=3.36` to core deps. Fixed `[all]` extra to include `windows`
- **loops/__init__.py auto-discovery**: Wrapped in try/except for OSError/PermissionError safety

---

## [0.3.0] - 2026-02-12

### Fixed

- **EventBus silent error swallowing**: `except Exception: pass` in global handler dispatch replaced with proper `log.error()`. Extracted shared `_execute_handlers()` to eliminate duplicated handler logic
- **Consciousness blocking I/O**: 7 points of synchronous `open()` calls inside `async def` methods converted to `aiofiles`. Prevents event loop blocking during file writes (goals, mastery, memory log)
- **Strategic brain no retry/timeout**: API calls now have 15s timeout, exponential backoff retry (1s→2s→4s, max 3 attempts), and graceful fallback to `None` (maintain state) on total failure
- **Silent loop crashes**: `asyncio.create_task()` without error handling replaced by `_monitored_loop()` wrapper — logs crashes, emits events, auto-restarts with cooldown (max 3 restarts per loop)
- **Decision application cascade failure**: Single bad API decision (e.g., invalid mode name) no longer crashes entire `apply_decisions()`. Each decision block is individually wrapped with try/except

### Added

- **Loop auto-discovery check**: `core/loops/__init__.py` warns at startup if `.py` files exist in the loops directory but aren't registered in `ALL_LOOPS`
- **Configurable loop intervals**: `reasoning.cycle_seconds` and `metrics.cycle_seconds` now read from settings.yaml with sensible defaults
- **Loop TEMPLATE**: Moved from `core/loops/TEMPLATE.py` to `docs/LOOP_TEMPLATE.py` to avoid polluting production code
- **CI improvements**: Added `ruff` linting and `mypy` type checking as warning-only steps
- **CLAUDE.md Known Issues**: New section documenting what doesn't work yet, so all 3 Claude instances know the limitations

### Changed

- **Legacy deprecation**: `perception/game_reader.py` and `perception/spatial_memory.py` now have DEPRECATED notice as first line of docstring
- **requirements.txt**: Aligned with pyproject.toml — added aiofiles, fixed dashboard deps (aiohttp instead of fastapi/uvicorn)
- **pyproject.toml**: Added `aiofiles>=24.0.0` to core dependencies, version bump to 0.3.0

---

## [0.2.0] - 2026-02-12

### Added

- **CLAUDE.md**: Shared context file for 3 Claude AI instances — auto-read at session start, contains full architecture map, conventions, dependency warnings, and recent changes
- **core/loops/ package**: 9 independent loop files extracted from agent.py — each dev can modify their own loop without conflicts
- **core/state/ package**: State split into enums.py, models.py, game_state.py with backward-compatible `__init__.py` re-exports

### Changed

- **core/agent.py**: Refactored from 845 to 414 lines — now a thin orchestrator that imports loops from `core/loops/` package via `ALL_LOOPS` registry
- **CI workflow**: Updated to verify 37 modules (was 24) including all new state/ and loops/ submodules
- **README.md**: Updated project structure to reflect new package architecture
- **pyproject.toml**: Version bump to 0.2.0

### Removed

- **core/state.py** (monolithic): Replaced by `core/state/` package with 4 files

### Architecture

- 3 devs can now work simultaneously: Dev A on `core/loops/strategic.py`, Dev B on `core/loops/perception.py`, Dev C on `core/state/models.py` — zero merge conflicts
- New loop = create file + register in `core/loops/__init__.py` — no need to touch agent.py
- New data model = add to `core/state/models.py` — no need to touch game_state.py

---

## [0.1.1] - 2026-02-12

### Added

- **GitHub Actions CI**: Automated syntax check, import verification, secret leak detection on every push to main
- **Git Hooks (pre-push)**: Local protection blocking syntax errors and API key leaks before push
- **Git Hooks (pre-commit)**: Blocks accidental commit of settings.yaml and debug breakpoints
- **CONTRIBUTING.md**: Complete collaboration guide with 6 failure modes analysis, dependency map, workflow protocol
- **README.md**: Professional README with badges, architecture diagram, tech stack, quick start, roadmap
- **CHANGELOG.md**: Version tracking with Keep a Changelog format
- **Version Bump Script**: `scripts/bump_version.py` auto-updates pyproject.toml, README badge, and CHANGELOG
- **Settings Example**: `config/settings.yaml.example` for safe onboarding without exposing API keys

### Changed

- **pyproject.toml**: Fixed URLs to point to gtdotwav/nexus, added Changelog link

---

## [0.1.0] - 2026-02-11

### Added

- **Dual-Brain Architecture**: Reactive brain (<25ms, 40 ticks/s) + Strategic brain (Claude API, 3s cycle)
- **Consciousness Layer**: Always-on multi-frequency awareness (1s/10s/2m/10m), 3-tier memory (Working/Episodic/Core), emotional dynamics, goal system, mastery tracker
- **EventBus**: Typed async pub/sub event system with thread-safe emission, history ring buffer, bridged to GameState events
- **GameReaderV2**: Pixel-based perception replacing EasyOCR — from 200-500ms down to <2ms per frame via ThreadPoolExecutor
- **SpatialMemoryV2**: SQLite-backed spatial memory with WAL mode, batched writes (buffer=200), SQL-based area queries, A* pathfinding
- **Strategic Brain State-Diff Skip**: Hashes key state signals (HP/mana/mode/threats), skips API calls when state unchanged (~30% savings)
- **Pynput Singleton**: Controllers created once in `__init__` instead of per-call (eliminated 3-5ms overhead per input)
- **Foundry Engine**: Self-evolution system — observe, analyze, create, test, deploy, archive
- **Skill Engine**: YAML-based modular skills with auto-create, auto-improve, and A/B testing
- **Navigator**: A* pathfinding with waypoint system
- **Loot Engine**: Automatic looting with priority system
- **Supply Manager**: Supply tracking and restocking logic
- **Explorer**: Map exploration with spatial memory integration
- **Death Recovery**: Automated recovery after death
- **Game Adapter System**: Abstract interface with Tibia as first adapter
- **Dashboard**: Real-time WebSocket monitoring with HTML dashboard
- **CLI**: Click-based CLI with Rich output (`nexus hunt`, `nexus status`, `nexus setup`)
- **Installers**: macOS (shell) and Windows (PowerShell) installers
- **Setup Wizard**: Interactive configuration wizard

### Technical Details

- 47 files, 14,400+ lines, 62 classes, 243 methods
- Python 3.11+, asyncio-based architecture
- Zero syntax errors verified across all modules
- All cross-module imports verified

---

*For the full architecture details, see [ARCHITECTURE.md](ARCHITECTURE.md).*
