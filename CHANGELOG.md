# Changelog

All notable changes to NEXUS will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
