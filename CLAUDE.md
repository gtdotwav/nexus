# NEXUS — Claude Context File

> Este arquivo é lido automaticamente pelo Claude no início de cada sessão.
> Ele garante que os 3 Claudes (GTzen, cbrviny13, dev3) tenham o mesmo contexto.
> **ATUALIZE ESTE ARQUIVO** toda vez que fizer uma mudança arquitetural.

## O que é o NEXUS

Agente autônomo de gaming para Tibia (MMORPG). Dual-brain: reactive (<25ms, 40 ticks/s) + strategic (Claude API, 3s). Consciousness layer com memória persistente, emoções, auto-evolução via Foundry.

## Regra #1 para trabalhar neste repo

```
ANTES DE QUALQUER COISA:
  git pull --rebase origin main
  git log --oneline -10
```

Leia os últimos commits para entender o que os outros devs/Claudes fizeram.

## Arquitetura de Módulos

```
core/
├── state/                    # ← PACKAGE (não arquivo único)
│   ├── __init__.py           # Re-exporta tudo (backward compatible)
│   ├── enums.py              # AgentMode, ThreatLevel
│   ├── models.py             # Position, CreatureState, SupplyCount, etc.
│   └── game_state.py         # GameState class
├── config.py                 # Pydantic config validation (NexusConfig)
├── agent.py                  # Orquestrador fino — registra loops, não implementa
├── loops/                    # ← Cada loop em arquivo separado
│   ├── __init__.py
│   ├── perception.py         # 30fps screen capture + spatial feed
│   ├── reactive.py           # 40 ticks/s survival
│   ├── action.py             # 10 ticks/s navigation, loot, supply
│   ├── strategic.py          # 3s Claude API + apply decisions
│   ├── consciousness.py      # Multi-frequency awareness
│   ├── evolution.py          # Foundry cycle
│   ├── recovery.py           # Death recovery
│   ├── reasoning.py          # Local real-time inference
│   └── metrics.py            # 60s performance tracking
├── consciousness.py
├── event_bus.py
├── foundry.py
└── recovery.py

brain/
├── reactive.py               # ReactiveBrain + HumanizedInput (asyncio.Lock no keyboard)
├── strategic.py               # StrategicBrain + Claude API (hash determinístico no cache)
└── reasoning.py               # ReasoningEngine

perception/
├── screen_capture.py
├── game_reader_v2.py          # Pixel-based (<2ms) — CANÔNICO
└── spatial_memory_v2.py       # SQLite WAL — CANÔNICO

actions/
├── navigator.py               # A* pathfinding
├── looting.py                 # Loot engine
├── explorer.py                # Map exploration (diagonais corrigidas)
├── supply_manager.py          # Supply tracking
└── behaviors.py               # Behavior patterns

skills/
├── engine.py                  # Skill loader + A/B testing
└── tibia/                     # Game-specific YAML skills

games/
├── base.py                    # Abstract game interface
├── registry.py
└── tibia/adapter.py

dashboard/
├── server.py                  # WebSocket server (null-safe agora)
└── app.html                   # Real-time dashboard
```

**NOTA**: `perception/game_reader.py` e `perception/spatial_memory.py` foram REMOVIDOS em v0.4.0.
`perception/__init__.py` exporta v2 como nomes canônicos (`GameReader`, `SpatialMemory`).

## Ponto Crítico: GameState

`core/state/game_state.py` (GameState) é importado por **13 arquivos**. Qualquer mudança nele pode quebrar:

```
actions/behaviors.py, actions/explorer.py, actions/looting.py,
actions/navigator.py, actions/supply_manager.py,
brain/reactive.py, brain/reasoning.py,
perception/game_reader_v2.py,
core/agent.py, core/recovery.py,
skills/engine.py, games/tibia/adapter.py
```

**ANTES de mudar GameState**: `grep -r "from core.state" --include="*.py" .`

## Como adicionar funcionalidades (SEM conflito)

### Novo loop no agent
1. Crie `core/loops/meu_loop.py` com uma função `async def run(agent)`
2. Registre em `core/agent.py` no array `self._tasks`
3. Commit + push

### Novo handler reativo
1. Adicione o método em `brain/reactive.py` na seção apropriada
2. Chame-o no `tick()` com a prioridade correta
3. Commit + push

### Novo modelo de dados
1. Adicione em `core/state/models.py` (NÃO em game_state.py)
2. Re-exporte em `core/state/__init__.py`
3. Commit + push

### Novo game adapter
1. Crie `games/nome_do_jogo/` com `__init__.py` e `adapter.py`
2. Registre em `games/registry.py`
3. Commit + push

### Nova skill YAML
1. Crie em `skills/nome_do_jogo/nome_da_skill.yaml`
2. Segue o formato de `skills/tibia/darashia_dragons_ek.yaml`
3. Commit + push

## Convenções de Código

- Python 3.11+, asyncio everywhere
- `structlog` para logging (não print)
- Type hints em todas as funções públicas
- Docstring em toda classe e método público
- Nomes em inglês, commits em inglês
- `from __future__ import annotations` em todo arquivo
- **I/O em funções async**: SEMPRE usar `aiofiles`, NUNCA `open()` bloqueante
- **Imports circulares**: `from __future__ import annotations` + `if TYPE_CHECKING:`
- **Keyboard**: SEMPRE usar `async with self._input_lock:` ao acessar pynput

## Padrão de Commits

```
feat: nova funcionalidade
fix: correção de bug
perf: melhoria de performance
refactor: refatoração sem mudar comportamento
docs: documentação
chore: manutenção
```

## O que NÃO fazer

- NÃO editar `core/state/game_state.py` sem verificar os 13 dependentes
- NÃO criar imports circulares
- NÃO usar `print()` — sempre `structlog`
- NÃO commitar `config/settings.yaml` (tem API keys)
- NÃO fazer `git push --force`
- NÃO editar o mesmo arquivo que outro dev está trabalhando
- NÃO usar `hash()` para cache keys (é randomizado por sessão) — usar `hashlib`

## Stack Técnica

- Perception: dxcam + OpenCV + pixel analysis (<2ms/frame)
- Reactive Brain: asyncio, 40 ticks/s, pynput singletons com asyncio.Lock
- Strategic Brain: Claude API (Anthropic), state-diff skip com hash determinístico
- Spatial Memory: SQLite WAL mode, batched writes
- Event System: Typed async EventBus, `run_coroutine_threadsafe` para thread-safety
- Input: pynput, gaussian noise, anti-detection, asyncio.Lock
- Dashboard: aiohttp + WebSocket
- CLI: Click + Rich
- Version: Single source of truth em `pyproject.toml` via `importlib.metadata`

## Versão Atual

**v0.4.1** — Circuit Breaker + Tests + Config Validation

## Últimas Mudanças (v0.4.1)

### Novas Features
- **Circuit breaker** em `brain/strategic.py`: 3-state (CLOSED/OPEN/HALF_OPEN). Após 5 falhas em 60s, para de chamar API e retorna None instantaneamente. Probe a cada 30s
- **Test suite**: 46 testes em `tests/` — EventBus, GameState, StrategicBrain (circuit breaker, cache, state-diff, JSON parse), Config validation. CI roda `pytest` automaticamente
- **Config validation**: `core/config.py` com Pydantic. `NexusConfig` valida settings.yaml no startup. Typos crasham imediato com mensagem clara
- **EventBus parallel handlers**: Async handlers agora rodam via `asyncio.gather` em paralelo. Handler lento não bloqueia healing

### Fixes
- `games/tibia/adapter.py` — Import de `game_reader.py` (deletado!) → `game_reader_v2.py`
- `core/consciousness.py` — Fingerprints: set (sem ordem) → deque(maxlen=500) (FIFO, auto-evict)
- `brain/strategic.py` — Conversation history memory leak → explicit trim
- `brain/strategic.py` — `c['name']` → `c.get('name', '?')` para creature dicts malformados
- `actions/explorer.py` — Diagonal move sem asyncio.Lock → com lock
- `brain/reasoning.py` — Unused Counter import removido
- TYPE_CHECKING imports atualizados para spatial_memory_v2

## Mudanças Anteriores (v0.4.0)

### Remoções (stack cleanup)
- `perception/game_reader.py` — REMOVIDO (legacy v1, ninguém usa)
- `perception/spatial_memory.py` — REMOVIDO (legacy v1, substituído por v2 SQLite)
- `perception/__init__.py` — Reescrito: exporta v2 como nomes canônicos

### Fixes Críticos
- `brain/strategic.py` — Cache key usava `hash()` (randomizado por sessão = cache NUNCA acertava) → `hashlib.sha256`
- `brain/strategic.py` — State-diff hash usava `hash()` também → `hashlib.md5` determinístico
- `brain/strategic.py` — `_build_context()` crashava se snapshot tivesse campos faltando → safe `.get()`
- `brain/strategic.py` — `analyze_for_skill_creation()` e `analyze_skill_performance()` sem null check em response.content
- `brain/reactive.py` — Keyboard race condition: múltiplas tasks async acessavam pynput sem lock → `asyncio.Lock`
- `brain/reactive.py` — `_press_diagonal()` também sem lock → adicionado
- `brain/reactive.py` — `press_key()` / `click()` sem null check em `_keyboard` / `_mouse`
- `brain/reasoning.py` — `Inference.timestamp` usava `default_factory=time.time` (errado) → `lambda: time.time()`
- `brain/reasoning.py` — `_analyze_topology()` acessava `floor.get()` que cria cells vazias → `floor.cells.get()` com None check
- `core/recovery.py` — `_last_recovery_end` definido 2x (duplicata) → removido duplicado
- `core/loops/metrics.py` — Acessava `agent.strategic_brain._skipped_calls` (privado) → public property
- `core/loops/metrics.py` — `reasoning_engine.current_profile.recommended_action` sem null check → guard
- `dashboard/server.py` — `agent.navigator.active_route` sem null guard → `or []`
- `dashboard/server.py` — Acessava `._calls` (privado) → public properties `calls`, `skipped_calls`
- `actions/explorer.py` — `_move()` mapeava diagonais para uma tecla só → 2 teclas simultâneas

### Infraestrutura
- CI: Instala dependências via `pip install -e ".[dev]"` (não hardcoded)
- CI: Removidos imports de game_reader.py e spatial_memory.py (deletados)
- `pyproject.toml` — `[tool.setuptools.package-data]` para dashboard HTML
- Version single source of truth: `pyproject.toml` via `importlib.metadata`
- Versão 0.4.0 em todos os pontos

## Mudanças Anteriores (v0.3.1)

- 16 arquivos corrigidos — deep analysis bugfix sweep
- consciousness.py sync I/O, event_bus threadsafe, foundry async, recovery init

## Mudanças Anteriores (v0.3.0)

- Resilience overhaul: retry/timeout/monitored loops/decision validation/aiofiles

## Known Issues & Limitations

### O que NÃO funciona ainda
- **Dashboard**: Parcialmente implementado
- **Humanização do mouse**: Falta curvas Bézier
- **Creature database**: Tiers inferidos pelo reasoning engine, não existe DB estático
- **Skill YAML schema**: Skills não são validadas antes de carregar
- **Consciousness god object**: 800+ linhas, deveria ser quebrado em MemoryStore/EmotionTracker/GoalManager
- **Foundry experiment threshold**: Score ≥ 2 de max 7 é muito baixo (28%)
- **Navigator hunt patrol**: Random walk puro, deveria usar spatial memory
- **Looting**: `modifiers=["shift"]` no click() não implementado

### Resolvido em v0.4.1
- ~~Config validation~~ → `core/config.py` com Pydantic
- ~~Zero testes~~ → 46 testes em `tests/`
- ~~EventBus handlers sequenciais~~ → Parallel via `asyncio.gather`
- ~~No circuit breaker~~ → 3-state circuit breaker no StrategicBrain

### Pontos de atenção para devs
- Os loops têm auto-restart (max 3x). Se um loop morre 3 vezes, ele fica morto até restart do agent
- Strategic brain retorna `None` (manter estado) em caso de falha total da API
- Keyboard operations protegidas por `asyncio.Lock` — respeitar o padrão
