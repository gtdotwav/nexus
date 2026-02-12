<p align="center">
  <img src="https://img.shields.io/badge/NEXUS-v0.1.1-blueviolet?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAyTDIgNy4zMTJsMTAgNi4xNTYgMTAtNi4xNTZMMTIgMnptMCAxMy41NjRMMy4zMTIgOS44NzUgMiAxMC42ODhsMTAgNi4xNTYgMTAtNi4xNTZMMS42ODggOS44NzUgMTIgMTUuNTY0em0wIDUuMDYyTDMuMzEyIDE0LjkzOCAyIDE1Ljc1bDEwIDYuMTU2IDEwLTYuMTU2LTEuMzEyLS44MTJMMTIgMjAuNjI2eiIvPjwvc3ZnPg==" alt="NEXUS">
  <br>
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/AI-Claude%20API-cc785c?style=flat-square&logo=anthropic&logoColor=white" alt="Claude">
  <img src="https://img.shields.io/badge/status-alpha-orange?style=flat-square" alt="Status">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/github/last-commit/gtdotwav/nexus?style=flat-square&color=blue" alt="Last Commit">
</p>

<h1 align="center">N E X U S</h1>
<h3 align="center">Autonomous Gaming Agent with Dual-Brain AI Architecture</h3>
<p align="center"><i>Not a bot. Not an assistant. A living intelligence that masters games.</i></p>

---

## What is NEXUS?

NEXUS is an autonomous gaming agent that goes beyond scripted bots. It combines a **reactive brain** (sub-25ms instinct at 40 ticks/s) with a **strategic brain** (Claude API reasoning every 3s) running through an always-on **consciousness layer** with persistent memory, emotional dynamics, and self-evolution capabilities.

The player controls start/stop. Everything else is NEXUS.

```
  PERCEPTION ──► REACTIVE BRAIN ──► ACTIONS
    (vision)       (<25ms)          (humanized I/O)
       │                │
       └──► STRATEGIC BRAIN ──► CONSCIOUSNESS
              (Claude API)        (memory, goals, emotions)
                    │
               FOUNDRY
            (self-evolution)
```

---

## Architecture

```
╔═══════════════════════════════════════════════════════════════╗
║                     N E X U S  v0.1.1                        ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║   CONSCIOUSNESS (Always-On)                                   ║
║   ├── Identity & Emotional Dynamics                           ║
║   ├── 3-Tier Memory (Working → Episodic → Core)              ║
║   ├── Goal System & Mastery Tracker                           ║
║   └── Multi-Frequency Awareness (1s/10s/2m/10m)              ║
║                                                               ║
║   ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   ║
║   │  REACTIVE    │  │  STRATEGIC   │  │     FOUNDRY      │   ║
║   │  BRAIN       │  │  BRAIN       │  │  (Self-Evolve)   │   ║
║   │  <25ms       │  │  Claude API  │  │  Observe→Analyze │   ║
║   │  40 ticks/s  │  │  3s cycle    │  │  Create→Test     │   ║
║   │  Instinct    │  │  Deep think  │  │  Deploy→Archive  │   ║
║   └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘   ║
║          └─────────────────┼───────────────────┘              ║
║                            ▼                                  ║
║   ┌──────────────────────────────────────────────────────┐   ║
║   │  STATE MANAGER + EVENT BUS                            │   ║
║   │  HP, Mana, Position, Battle List, Cooldowns, Metrics │   ║
║   └──────┬────────────────┬────────────────┬─────────────┘   ║
║          ▼                ▼                ▼                  ║
║   PERCEPTION        ACTION LAYER     SKILL ENGINE            ║
║   dxcam 30fps       Humanized I/O    YAML-based              ║
║   OpenCV+Pixel      Bezier mouse     Auto-create             ║
║   SQLite spatial     Anti-detect      A/B testing             ║
╚═══════════════════════════════════════════════════════════════╝
```

---

## Why NEXUS is Different

| Dimension | Traditional Bot | NEXUS |
|-----------|----------------|-------|
| **Memory** | Forgets between sessions | 3-tier persistent memory (Working → Episodic → Core) |
| **Awareness** | Reacts to events | Multi-frequency consciousness (instinct/awareness/reflection/deep) |
| **Learning** | Fixed logic | Self-evolving via Foundry — creates, tests, deploys improvements |
| **Decisions** | If/then rules | Claude API with full consciousness context |
| **Personality** | None | Emotional dynamics modify decision parameters in real-time |
| **Perception** | Memory reading | Vision-only (pixel analysis) — undetectable |

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Reactive Brain | Python asyncio | Sub-25ms decision loop, 40 ticks/s |
| Strategic Brain | Claude API (Anthropic) | Deep reasoning with state-diff skip (~30% savings) |
| Perception | dxcam + OpenCV + pixel analysis | GPU-accelerated screen capture, <2ms per frame |
| Spatial Memory | SQLite (WAL mode) | Persistent map knowledge, batched writes |
| Event System | Custom EventBus | Typed async pub/sub with thread-safe emission |
| Input | pynput (singleton) | Humanized Bezier curves, anti-detection |
| Skills | YAML configs | Modular, auto-created, A/B tested |
| Dashboard | aiohttp + WebSocket | Real-time monitoring |
| CLI | Click + Rich | `nexus hunt`, `nexus status`, `nexus setup` |

---

## Project Structure

```
nexus/
├── core/                    # Core systems
│   ├── agent.py             # Main orchestrator
│   ├── state.py             # Thread-safe state + events
│   ├── consciousness.py     # Memory, goals, emotions
│   ├── event_bus.py         # Typed async event system
│   ├── foundry.py           # Self-evolution engine
│   └── recovery.py          # Death recovery system
├── brain/                   # Decision layers
│   ├── reactive.py          # Fast instinct (<25ms)
│   ├── strategic.py         # Claude API reasoning
│   └── reasoning.py         # Reasoning engine
├── perception/              # Vision systems
│   ├── screen_capture.py    # dxcam/mss capture
│   ├── game_reader.py       # Legacy pixel reader
│   ├── game_reader_v2.py    # Optimized pixel reader (<2ms)
│   ├── spatial_memory.py    # Legacy JSON-based
│   └── spatial_memory_v2.py # SQLite-backed (WAL mode)
├── actions/                 # Game interactions
│   ├── navigator.py         # A* pathfinding
│   ├── looting.py           # Loot engine
│   ├── explorer.py          # Map exploration
│   ├── supply_manager.py    # Supply management
│   └── behaviors.py         # Behavior patterns
├── skills/                  # Skill system
│   ├── engine.py            # Skill loader + A/B testing
│   └── tibia/               # Game-specific skills
├── games/                   # Game adapters
│   ├── base.py              # Abstract game interface
│   ├── registry.py          # Game registry
│   └── tibia/               # Tibia adapter
├── dashboard/               # Monitoring
│   ├── server.py            # WebSocket server
│   └── app.html             # Real-time dashboard
├── scripts/                 # Setup & install
│   ├── setup_wizard.py      # Interactive setup
│   ├── install_macos.sh     # macOS installer
│   └── install_windows.ps1  # Windows installer
├── config/settings.yaml     # Configuration
├── main.py                  # Entry point
├── launcher.py              # Process launcher
├── nexus_cli.py             # CLI interface
├── pyproject.toml           # Package config
└── requirements.txt         # Dependencies
```

**47 files | 14,400+ lines | 62 classes | 243 methods**

---

## Quick Start

```bash
# Clone
git clone https://github.com/gtdotwav/nexus.git
cd nexus

# Setup (Python 3.11+ required)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e ".[all]"

# Configure
cp config/settings.yaml.example config/settings.yaml
# Edit settings.yaml with your Anthropic API key and game settings

# Run setup wizard
nexus setup

# Start hunting
nexus hunt --skill darashia_dragons_ek
```

---

## Configuration

Edit `config/settings.yaml`:

```yaml
ai:
  api_key: "sk-ant-..."          # Your Anthropic API key
  model: "claude-sonnet-4-20250514"

perception:
  method: "pixel"                 # pixel (fast) or ocr (accurate)
  fps: 30

hotkeys:
  heal_strong: "f1"
  heal_light: "f2"
  mana_potion: "f3"
  attack: "f4"
  haste: "f5"
```

---

## Roadmap

- [x] **Phase 1 — Foundation**: Dual-brain architecture, consciousness, EventBus, Foundry, persistent memory
- [x] **Phase 1.5 — Optimization**: GameReaderV2 (pixel), SpatialMemoryV2 (SQLite), state-diff skip, pynput singleton
- [ ] **Phase 2 — Tibia Integration**: Screen calibration, HP/Mana reading, battle list, first autonomous hunt
- [ ] **Phase 3 — Intelligence**: Death pattern analysis, market intelligence, PvP assessment, route optimization
- [ ] **Phase 4 — Mastery**: Cross-session learning, auto skill generation, self-tuning, advanced anti-PK
- [ ] **Phase 5 — Multi-Game**: Abstract game interface, second game integration, cross-game strategy transfer

---

## Contributing

NEXUS is actively developed by **GTzen** and **cbrviny13**. Both contributors push directly to `main`.

To contribute:

```bash
git clone https://github.com/gtdotwav/nexus.git
cd nexus
git checkout -b feature/your-feature
# Make changes
git push origin feature/your-feature
# Open a PR
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  <b>Built with obsession by <a href="https://github.com/gtdotwav">GTzen</a> & <a href="https://github.com/cbrviny13">cbrviny13</a></b>
  <br>
  <i>Powered by Claude API</i>
</p>
