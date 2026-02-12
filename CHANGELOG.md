# Changelog

All notable changes to NEXUS will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---


## [0.5.0] - 2026-02-12

### Added
- **Zero-Knowledge Learning System** — The agent now learns by playing, with zero hardcoded game knowledge
  - Works on any Tibia variant: OT servers, Pokemon Tibia, custom servers
  - No wikis, no pre-configured skills needed — the agent discovers everything itself
- **Knowledge Engine** (`core/knowledge.py`) — SQLite-backed persistent knowledge store
  - 6 tables: learned_creatures, learned_spells, learned_items, learned_locations, learned_mechanics, confidence_history
  - Upsert with confidence boosting on re-observations
  - Spatial knowledge queries (`get_nearby_knowledge`)
  - Confidence decay over time (old knowledge fades)
  - Token-efficient summaries for strategic brain context
- **Vision Loop** (`core/loops/vision.py`) — 10th async loop using Claude Haiku
  - Sends compressed screenshots (768px JPEG, ~50KB) every 5 seconds
  - Passive scene observation: detects creatures, NPCs, items, location type, chat messages, tutorials
  - Routes all observations to Knowledge Engine automatically
  - Triggers auto-skill generation when enough safe creatures are discovered
  - Cost: ~$0.30/hr with Haiku at 5s intervals
- **Vision Utilities** (`brain/vision_utils.py`) — Shared frame compression and multimodal message building
  - `frame_to_base64()` — BGR numpy → JPEG base64 with configurable quality/size
  - `build_vision_message()` — Builds Anthropic Vision API content arrays
- **Strategic Brain Vision Analysis** — `analyze_with_vision()` method for important decisions using Sonnet with screenshots
- **Auto-Skill Generation from Knowledge** — `skill_engine.auto_generate_from_knowledge()` builds hunting skills purely from learned facts
  - Targeting from safe creatures, flee-from from dangerous creatures
  - Healing inference from discovered spells
  - Zero API calls needed — pure knowledge-to-YAML transformation
- **Zero-Knowledge Bootstrap** — When no skills exist at startup, agent enters EXPLORING mode
  - Vision loop accumulates knowledge passively
  - When enough safe creatures are found, auto-generates first hunting skill
  - Switches to HUNTING mode automatically

### Changed
- `core/agent.py` — Knowledge Engine initialization, zero-knowledge bootstrap flow, knowledge stats in session report
- `brain/strategic.py` — Knowledge context injected into `_build_context()`, knowledge reference for cross-system access
- `perception/screen_capture.py` — Frame caching via `last_frame` property for vision loop consumption
- `skills/engine.py` — Added `auto_generate_from_knowledge()` and `get_available_skills()` methods
- `core/loops/__init__.py` — Vision loop registered as 10th loop
- `config/settings.yaml.example` — Added `vision:` and `knowledge:` configuration sections
- Agent docstring updated from "9 loops" to "10 loops"
- Version bump to 0.5.0

---

## [0.4.2] - 2026-02-12

### Added
- **Textual TUI Dashboard** — Primary local interface that runs in the terminal
  - 3 screens: Game Select (F1), Monitor (F2), Skills (F3)
  - Real-time HP/Mana bars with color gradients
  - Event stream with color-coded entries (kills, loot, heals, mode changes)
  - Battle list with inline HP bars and target indicator
  - Session stats panel (XP/hr, Gold/hr, K/D, close calls)
  - Strategic brain metrics (calls, latency, error rate, circuit breaker)
  - Consciousness panel (emotion, goals, recent memories)
  - Game selection cards with ready/coming-soon status
  - Demo mode with simulated data when no agent is running
  - Keybindings: F1-F3 screens, P pause, D demo toggle, Q quit
- `dashboard/tui.py` — Main Textual app (NexusTUI) with 3 screens
- `dashboard/tui_widgets.py` — 9 custom widgets (VitalBar, BattleListWidget, etc.)
- `dashboard/tui_models.py` — TUIState data bridge between agent and widgets
- `--tui/--no-tui` CLI flag (default: `--tui`)

### Changed
- `nexus start` now launches TUI by default (use `--no-tui` for headless)
- `--dashboard` now defaults to off (TUI is the primary interface)
- Web dashboard remains available as secondary/remote interface
- `textual>=0.85.0` added to dependencies

---

## [0.4.1] - 2026-02-12

### Added

- **Circuit breaker for Claude API**: StrategicBrain now has a 3-state circuit breaker (CLOSED → OPEN → HALF_OPEN). After 5 failures in 60s, stops hammering the API and fails fast. Probes every 30s. Prevents cascade failure if Claude API is unavailable
- **Test infrastructure**: 46 tests covering EventBus (parallel handlers, error isolation, priority), GameState, StrategicBrain (circuit breaker, cache, state-diff, JSON parsing), and config validation. `pytest` + `pytest-asyncio`
- **Config validation with Pydantic**: `core/config.py` — validates settings.yaml at startup. Typos and invalid values now crash immediately with clear error messages instead of failing silently mid-session. All config models have sensible defaults
- **EventBus parallel handler execution**: Async handlers now run concurrently via `asyncio.gather` instead of sequentially. One slow handler (dashboard broadcast) no longer blocks others (healing reaction)

### Fixed

- **games/tibia/adapter.py — CRITICAL broken import**: `from perception.game_reader import GameReader` referenced deleted v1 file. Would crash with ImportError at runtime. Fixed to use `GameReaderV2`
- **core/consciousness.py — fingerprint dedup lost ordering**: `_recent_fingerprints` was a `set` with manual pruning via `set(list(set)[-300:])`. Sets are unordered, so pruning kept random fingerprints instead of most recent. Replaced with `deque(maxlen=500)` which auto-evicts oldest
- **brain/strategic.py — conversation history memory leak**: `_conversation` list was appended to but only trimmed at API call time via slice, not after append. Added explicit trim after every append
- **brain/strategic.py — unsafe creature dict access**: `c['name']` and `c['hp']` in `_build_context()` crashed on malformed creature dicts. Changed to safe `.get()` with defaults
- **actions/explorer.py — diagonal movement without input lock**: `_move()` pressed keys without `asyncio.Lock`, risking interleaved press/release with other async tasks
- **actions/explorer.py — duplicate import**: `import random` at module level AND inside `_move()`. Removed duplicate
- **brain/reasoning.py — unused Counter import**: Imported but never used. Removed
- **brain/reasoning.py, actions/explorer.py — stale TYPE_CHECKING imports**: Referenced deleted `spatial_memory.py`. Updated to `spatial_memory_v2`

### Infrastructure

- CI: Added pytest step (runs 46 tests)
- CI: Added `core.config` to import check list
- `pyproject.toml`: Version 0.4.1, added pytest config section
- `config/settings.yaml.example`: Version 0.4.1

---

## [0.4.0] - 2026-02-12

### Removed (Stack Cleanup)

- **perception/game_reader.py**: Deleted legacy v1 game reader (OCR-based). Use game_reader_v2.py
- **perception/spatial_memory.py**: Deleted legacy v1 spatial memory (JSON-based). Use spatial_memory_v2.py
- **perception/__init__.py**: Rewritten to export v2 as canonical names (GameReader, SpatialMemory)

### Fixed (Critical)

- **brain/strategic.py — cache NEVER worked**: Both state-diff hash and response cache used Python's `hash()` which is randomized per session via PYTHONHASHSEED. Every API call was a cache miss. Replaced with `hashlib.md5` and `hashlib.sha256` for deterministic hashing. This alone saves ~30-50% of API calls
- **brain/strategic.py — _build_context() crash**: Directly accessed `snapshot["character"]`, etc. which crashes on missing keys. Now uses safe `.get()` everywhere
- **brain/strategic.py — null response.content**: `analyze_for_skill_creation()` and `analyze_skill_performance()` crashed on empty API responses
- **brain/reactive.py — keyboard race condition**: Multiple async tasks could interleave press/release calls on shared pynput keyboard singleton, leaving keys stuck. Added `asyncio.Lock` to all keyboard operations
- **brain/reactive.py — _press_diagonal() unprotected**: Same race condition. Now uses the shared input lock
- **brain/reactive.py — null keyboard/mouse**: `press_key()` and `click()` didn't check if `_keyboard`/`_mouse` were actually initialized. Added null guards
- **brain/reasoning.py — Inference timestamps all identical**: `default_factory=time.time` evaluates once at class definition, not per-instance. Fixed to `lambda: time.time()`
- **brain/reasoning.py — _analyze_topology() phantom cells**: `floor.get(x, y)` auto-creates empty cells, inflating walkability analysis. Changed to `floor.cells.get(key)` with None check
- **core/recovery.py — duplicate _last_recovery_end**: Variable defined twice (lines 80-81). Removed duplicate
- **core/loops/metrics.py — AttributeError crash**: Accessed `reasoning_engine.current_profile.recommended_action` without null check. Also accessed `strategic_brain._skipped_calls` (private)
- **dashboard/server.py — navigation crash**: `len(agent.navigator.active_route)` crashed when route is None
- **dashboard/server.py — private attribute access**: Replaced `._calls` with public properties
- **actions/explorer.py — diagonal movement broken**: `_move()` mapped diagonal directions to single keys ("ne" → "up"). Now presses both keys simultaneously

### Changed

- **Version management**: Single source of truth from `pyproject.toml` via `importlib.metadata`. Removed hardcoded VERSION in nexus_cli.py
- **CI pipeline**: Dependencies installed via `pip install -e ".[dev]"` instead of hardcoded pip install list
- **pyproject.toml**: Added `[tool.setuptools.package-data]` for dashboard HTML inclusion in distribution

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
