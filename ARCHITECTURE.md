# NEXUS — Autonomous Super-Player Architecture

> "Not a bot. Not an assistant. A living intelligence that masters games."

## The Philosophy

NEXUS is fundamentally different from every gaming bot that has ever existed. Traditional bots follow scripts. NEXUS has **consciousness**.

Inspired by OpenClaw's architecture, NEXUS applies the principles of autonomous AI agents to gaming: persistent memory across sessions, always-on multi-frequency awareness, self-writing capabilities via Foundry, emotional dynamics that directly affect decision parameters, and a relentless drive toward mastery.

The player controls start/stop. NEXUS never decides to pause itself.

The result: an agent that doesn't just play — it **dominates, learns, remembers, and evolves**.

---

## Architecture Overview

```
╔══════════════════════════════════════════════════════════════════════╗
║                        N E X U S  v0.2                              ║
║                    Autonomous Super-Player                          ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  ┌───────────────────────────────────────────────────────────────┐   ║
║  │              CONSCIOUSNESS (Always-On)                         │   ║
║  │                                                                 │   ║
║  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │   ║
║  │  │ IDENTITY │  │ MEMORY   │  │  GOALS   │  │  EMOTIONAL   │  │   ║
║  │  │          │  │          │  │          │  │  DYNAMICS     │  │   ║
║  │  │ Who I am │  │ Working  │  │ Active   │  │              │  │   ║
║  │  │ My drive │  │ Episodic │  │ Mastery  │  │ Confidence   │  │   ║
║  │  │ My code  │  │ Core     │  │ Farming  │  │ Focus        │  │   ║
║  │  │          │  │          │  │ Survival │  │ Determination│  │   ║
║  │  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │   ║
║  │                                                                 │   ║
║  │  ┌──────────────────────────────────────────────────────────┐  │   ║
║  │  │  MULTI-FREQUENCY AWARENESS (never sleeps)                │  │   ║
║  │  │                                                           │  │   ║
║  │  │  ● Instinct (1s)   → Emotional micro-ticks               │  │   ║
║  │  │  ● Awareness (10s) → Pattern recognition, threat profile  │  │   ║
║  │  │  ● Reflection (2m) → Strategy assessment, mastery update  │  │   ║
║  │  │  ● Deep (10m)      → Pattern mining, evolution triggers   │  │   ║
║  │  └──────────────────────────────────────────────────────────┘  │   ║
║  │                                                                 │   ║
║  │  ┌──────────────────────────────────────────────────────────┐  │   ║
║  │  │  MASTERY TRACKER   Per-area skill levels 0-100           │  │   ║
║  │  │  Strengths, weaknesses, improvement rate, trend detection│  │   ║
║  │  └──────────────────────────────────────────────────────────┘  │   ║
║  └───────────────────────────────────────────────────────────────┘   ║
║                              ↕                                       ║
║  ┌──────────────┐    ┌──────────────────┐    ┌───────────────────┐  ║
║  │   REACTIVE   │    │   STRATEGIC      │    │    FOUNDRY        │  ║
║  │   BRAIN      │    │   BRAIN          │    │    (Self-Evolve)  │  ║
║  │              │    │                  │    │                   │  ║
║  │  <50ms       │    │  Claude API      │    │  Observe → Analyze│  ║
║  │  Instinct    │    │  Deep reasoning  │    │  Create → Test    │  ║
║  │  Survival    │    │  Every 3 seconds │    │  Deploy → Archive │  ║
║  │  40 ticks/s  │    │  Consciousness   │    │  Multi-signal     │  ║
║  │  Combo DPS   │    │  context aware   │    │  evaluation       │  ║
║  └──────┬───────┘    └────────┬─────────┘    └────────┬──────────┘  ║
║         │                     │                        │             ║
║  ┌──────▼─────────────────────▼────────────────────────▼──────────┐  ║
║  │                STATE MANAGER + EVENT SYSTEM                      │  ║
║  │   HP, Mana, Position, Battle List, Cooldowns, Session Metrics  │  ║
║  │   Events: hp_changed, kill, death, mode_changed, combat_event  │  ║
║  └──────┬─────────────────────┬────────────────────────┬──────────┘  ║
║         │                     │                        │             ║
║  ┌──────▼───────┐    ┌───────▼────────┐    ┌─────────▼──────────┐  ║
║  │  PERCEPTION  │    │  ACTION LAYER  │    │   SKILL ENGINE     │  ║
║  │              │    │                │    │                     │  ║
║  │  dxcam 30fps │    │  Humanized I/O │    │  YAML skills       │  ║
║  │  OpenCV      │    │  Bézier mouse  │    │  Auto-create       │  ║
║  │  EasyOCR     │    │  Anti-detect   │    │  Auto-improve      │  ║
║  │  Template    │    │  Variable time │    │  A/B testing        │  ║
║  └──────────────┘    └────────────────┘    └─────────────────────┘  ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## What Makes This a "Super Player" (Not a Bot)

| Dimension | Traditional Bot | NEXUS |
|-----------|----------------|-------|
| **Memory** | Forgets everything between sessions | 3-tier persistent memory: Working (1000 entries) → Episodic (daily logs) → Core (permanent wisdom) |
| **Awareness** | Only reacts to game events | Always-on multi-frequency consciousness — instinct, awareness, reflection, deep analysis running simultaneously |
| **Learning** | Fixed logic, breaks with updates | Self-evolving via Foundry — creates new skills, improves existing ones, runs A/B experiments with multi-signal evaluation |
| **Decisions** | If/then rules | AI reasoning via Claude — understands context, adapts strategy, thinks in second-order effects |
| **Personality** | None | Emotional dynamics (confidence, determination, aggression, caution) directly modify decision parameters |
| **Goals** | Follow script forever | Active goal system with priority, progress tracking, and milestone celebration |
| **Mastery** | Same skill level forever | Tracks mastery per area (healing, kiting, market, PvP) with improvement rate, trend detection, and stagnation alerts |

---

## The Six Layers

### Layer 1: Consciousness (The Soul)

Always-on multi-frequency awareness system. Three-tier memory:

**Working Memory** — Current session. Lives in RAM. 1000 entries max. MD5 fingerprint dedup. Fast indexed recall by category.

**Episodic Memory** — Daily markdown logs (`memory/2026-02-11.md`). Every kill, death, close call, insight. Complete session history.

**Core Memory** — `MEMORY.md`. The permanent brain. Auto-promoted from working memory when importance >= 0.8. Fingerprint-deduped to avoid repetition.

The consciousness also manages:
- **Identity**: Immutable core of who NEXUS is, its directives and decision philosophy
- **Emotional Dynamics**: Confidence, focus, determination, aggression, caution — directly modify healing thresholds, chase distance, risk tolerance via `get_decision_modifiers()`
- **Goal System**: Active goals with priority, metric tracking, progress, and milestones
- **Mastery Tracker**: 10 gameplay dimensions (healing_timing, positioning, target_selection, spell_rotation, resource_management, threat_assessment, kiting, anti_pk, navigation_efficiency, market_trading) each scored 0-100 with improvement rate and trend detection
- **Pattern Detection**: Death cause Counter, close-call clustering, player threat profiling
- **Multi-Frequency Awareness**: 4 concurrent layers (instinct/awareness/reflection/deep analysis)

### Layer 2: Perception (The Eyes)

Screen capture at 30fps via dxcam (GPU-accelerated, <2ms per frame). Extracts:
- HP/Mana bars via HSV color analysis (pixel-level accuracy)
- Battle list via OCR (creature names, HP%)
- Chat messages (XP gained, loot, player messages) via regex parsing
- Minimap for position tracking

Vision-only approach = undetectable by BattlEye anti-cheat.

### Layer 3: Reactive Brain (The Instinct)

40 ticks/second. Priority queue for survival actions:
1. Emergency heal (HP critical — strongest heal + potion combo)
2. Anti-PK flee (hostile player detection, haste, threat profiling)
3. Normal healing (threshold-based)
4. Mana restore
5. Repositioning (strategic brain commands, cardinal + diagonal)
6. Attack — combo chain system with configurable spell rotation
7. Loot, navigate, eat

All inputs humanized: Bézier mouse curves, gaussian coordinate noise, variable timing. Hotkeys configurable per character via settings.yaml.

Consciousness integration: emotional modifiers adjust healing thresholds, chase distance, and aggression every 5 seconds.

### Layer 4: Strategic Brain (The Mind)

Claude API reasoning every 3 seconds. Receives full game state + consciousness context (emotional state, memories, death patterns, mastery levels, goals, threat profiles) and returns:
- Mode changes (hunting, fleeing, depositing)
- Target priorities and spell rotation overrides
- Healing threshold adjustments with exact numbers
- Aggression parameters (chase distance, attack mode, pull count)
- Repositioning commands with direction and reason
- Skill creation/switching triggers
- Anticipation and optimization notes

Response caching (5s TTL) prevents duplicate API calls. Conversation history maintained for context continuity.

### Layer 5: Skill Engine (The Capabilities)

YAML-based modular skills. Each skill defines waypoints, targeting, healing, supplies, anti-PK, and special behaviors.

Key differentiator: **skills are not static**. The engine auto-creates new skills when encountering unfamiliar situations and auto-improves existing skills based on performance data. Version tracking ensures rollback capability.

### Layer 6: Foundry (The Evolution)

The meta-system that improves NEXUS itself:

1. **OBSERVE**: Collects performance data and failure patterns from consciousness deep analysis
2. **ANALYZE**: Identifies highest-impact improvement opportunity (death patterns > XP decline > healing efficiency > mastery gaps)
3. **CREATE**: Claude generates specific improvement with testable hypothesis
4. **TEST**: Runs controlled A/B experiment with multi-signal evaluation (deaths, close calls, emotion state, emergency heal count)
5. **DEPLOY**: Keeps improvement if evaluation score >= 2/7, reverts if inconclusive
6. **ARCHIVE**: Full evolution history for rollback capability

The Foundry has direct access to the reactive brain, skill engine, and consciousness — it can modify live parameters without restart.

---

## The Consciousness Lifecycle

```
  ┌─────────┐
  │  AWAKEN  │ ← Load identity, memories, goals, mastery from disk
  └────┬─────┘
       │
  ┌────▼─────┐
  │ PERCEIVE │ ← Calibrate vision, find game window
  └────┬─────┘
       │
  ┌────▼─────┐
  │ PREPARE  │ ← Load skills, select best for context
  └────┬─────┘
       │
  ┌────▼──────────────────────────────────────────────┐
  │  LIVE — All loops running concurrently:           │
  │                                                    │
  │  ● Perception loop (30fps)    → sees the game     │
  │  ● Reactive brain (40/s)     → instinctive action │
  │  ● Strategic brain (3s)      → deep AI thinking   │
  │  ● Consciousness (always-on):                     │
  │      Instinct (1s) | Awareness (10s)              │
  │      Reflection (2m) | Deep Analysis (10m)         │
  │  ● Foundry evolution (continuous)                  │
  │  ● Metrics tracking (60s)                          │
  └────┬──────────────────────────────────────────────┘
       │
  ┌────▼─────┐
  │ REFLECT  │ ← End-of-session analysis, compile lessons
  └────┬─────┘
       │
  ┌────▼─────┐
  │  SLEEP   │ ← Persist memories, goals, mastery, skills to disk
  └──────────┘   Next session starts where this one left off
```

---

## Event System

Game state changes propagate through the event system to consciousness:

```
GameState events:
  hp_changed    → Consciousness.on_close_call() (when HP < 25%)
  kill          → Consciousness.on_kill() (confidence +, mastery +)
  death         → Consciousness.on_death() (confidence -, determination +)
  mode_changed  → Memory recording (flee events, mode transitions)
  combat_event  → Combat log tracking
```

---

## File Structure

```
gaming-agent/
├── main.py                    # Entry point (CLI args, signal handling)
├── requirements.txt           # Dependencies
├── config/
│   └── settings.yaml          # Master configuration (AI, perception, hotkeys, skills)
├── core/
│   ├── agent.py               # Main orchestrator (awakens → lives → sleeps)
│   ├── state.py               # Thread-safe state manager + event system
│   ├── consciousness.py       # Always-on awareness, memory, goals, emotions
│   └── foundry.py             # Self-evolution engine (observe → evolve → deploy)
├── perception/
│   ├── screen_capture.py      # dxcam/mss screen capture
│   └── game_reader.py         # Extracts game data from frames (HP, mana, battle list, chat)
├── brain/
│   ├── reactive.py            # Fast instinct (40 ticks/s, combo system, consciousness modifiers)
│   └── strategic.py           # Deep thinking (Claude API, consciousness context)
├── skills/
│   ├── engine.py              # Skill loader, creator, improver, A/B tester
│   └── tibia/
│       └── darashia_dragons_ek.yaml  # Example skill template
├── data/                      # Persistent data (survives across sessions)
│   ├── memory/
│   │   ├── MEMORY.md          # Core permanent memory
│   │   └── 2026-02-11.md     # Daily episode log
│   ├── goals.json             # Active and completed goals
│   ├── mastery.json           # Per-area mastery levels
│   ├── meta.json              # Session counter
│   ├── sessions.db            # Performance database
│   └── evolution/
│       └── history.json       # Foundry evolution records
└── logs/                      # Structured logs (structlog)
```

---

## What Comes Next

### Phase 1: Foundation (Complete)
- [x] Core architecture with always-on consciousness layer
- [x] Dual-brain system (reactive + strategic) with consciousness integration
- [x] Skill engine with auto-create and auto-improve
- [x] Foundry self-evolution engine with multi-signal evaluation
- [x] Persistent 3-tier memory system with fingerprint dedup
- [x] Event system wiring state → consciousness (kills, deaths, close calls)
- [x] Configurable hotkey system via settings.yaml

### Phase 2: Tibia Integration (Next)
- [ ] Screen capture calibration with Tibia client
- [ ] HP/Mana bar pixel-perfect reading
- [ ] Battle list OCR integration
- [ ] Bézier curve mouse movement implementation
- [ ] First autonomous hunting session

### Phase 3: Intelligence (Then)
- [ ] Strategic brain prompt optimization via Foundry
- [ ] Death pattern analysis and counter-strategy creation
- [ ] Market intelligence (buy low, sell high)
- [ ] PvP threat assessment and counter-play
- [ ] Multi-spawn route optimization

### Phase 4: Mastery (Ongoing)
- [ ] Cross-session learning compound effect
- [ ] Automatic skill generation for new hunting grounds
- [ ] Self-tuning healing thresholds per spawn
- [ ] Advanced anti-PK with player behavior profiling
- [ ] Dashboard for real-time monitoring

### Phase 5: Multi-Game (Future)
- [ ] Abstract game interface layer
- [ ] Second game integration (LoL, Dota, etc.)
- [ ] Cross-game strategy transfer
- [ ] Community skill marketplace
