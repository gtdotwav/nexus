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
├── reactive.py               # ReactiveBrain + HumanizedInput
├── strategic.py               # StrategicBrain + Claude API
└── reasoning.py               # ReasoningEngine

perception/
├── screen_capture.py
├── game_reader_v2.py          # Pixel-based (<2ms) — USAR ESTE
├── game_reader.py             # Legacy (EasyOCR) — NÃO USAR
├── spatial_memory_v2.py       # SQLite WAL — USAR ESTE
└── spatial_memory.py          # Legacy JSON — NÃO USAR

actions/
├── navigator.py               # A* pathfinding
├── looting.py                 # Loot engine
├── explorer.py                # Map exploration
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
├── server.py                  # WebSocket server
└── app.html                   # Real-time dashboard
```

## Ponto Crítico: GameState

`core/state/game_state.py` (GameState) é importado por **13 arquivos**. Qualquer mudança nele pode quebrar:

```
actions/behaviors.py, actions/explorer.py, actions/looting.py,
actions/navigator.py, actions/supply_manager.py,
brain/reactive.py, brain/reasoning.py,
perception/game_reader.py, perception/game_reader_v2.py,
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
- NÃO usar `game_reader.py` ou `spatial_memory.py` (legados, use v2)
- NÃO fazer `git push --force`
- NÃO editar o mesmo arquivo que outro dev está trabalhando

## Stack Técnica

- Perception: dxcam + OpenCV + pixel analysis (<2ms/frame)
- Reactive Brain: asyncio, 40 ticks/s, pynput singletons
- Strategic Brain: Claude API (Anthropic), state-diff skip (~30% savings)
- Spatial Memory: SQLite WAL mode, batched writes
- Event System: Typed async EventBus, thread-safe emission
- Input: pynput, Bézier curves, gaussian noise, anti-detection
- Dashboard: aiohttp + WebSocket
- CLI: Click + Rich

## Versão Atual

**v0.3.1** — Deep Analysis Bugfix

## Últimas Mudanças (v0.3.1)

- `core/consciousness.py` — Fix: 3 MAIS pontos de sync I/O que tinham escapado (session count + reflect)
- `core/event_bus.py` — Fix: `emit_threadsafe()` usava `ensure_future` errado → `run_coroutine_threadsafe()`
- `brain/reasoning.py` — Fix: crash ao acessar `floors[z]` sem verificar existência + null check em `get_reasoning_context()`
- `brain/strategic.py` — Fix: crash se API retorna response.content vazio
- `core/foundry.py` — Fix: 2 pontos de sync I/O em async (initialize + save_history)
- `core/recovery.py` — Fix: `_last_recovery_end` não inicializado (AttributeError na primeira morte)
- `core/state/game_state.py` — Fix: `_notify()` agora copia lista antes de iterar (thread safety)
- `core/loops/metrics.py` — Fix: crash se `navigator.active_route` é None
- `main.py` — Consolidado: era 174 linhas duplicando nexus_cli.py. Agora redirect fino
- `pyproject.toml` — Adicionado pydantic + sqlite-utils que faltavam nas deps core
- Versões alinhadas: main.py, nexus_cli.py, settings.yaml agora todos 0.3.1

## Mudanças Anteriores (v0.3.0)

- `core/event_bus.py` — Fix: errors in global handlers were silently swallowed. Now properly logged
- `core/consciousness.py` — Fix: 7 points of sync file I/O blocking the event loop. Now uses aiofiles
- `brain/strategic.py` — Fix: API calls without timeout/retry. Now has 15s timeout + 3x exponential backoff
- `core/agent.py` — Fix: loop crashes were silent. Now monitored with auto-restart (max 3x per loop)
- `core/loops/strategic.py` — Fix: single bad API decision could crash all decision application. Now individually wrapped
- `core/loops/__init__.py` — New: warns at startup if .py loop files exist but aren't registered in ALL_LOOPS
- `core/loops/reasoning.py`, `metrics.py` — Intervals now configurable via settings.yaml
- `core/loops/TEMPLATE.py` — Moved to `docs/LOOP_TEMPLATE.py` (was polluting production code)
- Legacy files `perception/game_reader.py` and `perception/spatial_memory.py` marked DEPRECATED
- CI: added ruff + mypy (warning-only)
- `aiofiles` added to dependencies

## Mudanças Anteriores (v0.2.0)

- `core/state/` — Splitado em package (enums.py, models.py, game_state.py)
- `core/loops/` — Loops extraídos de agent.py para arquivos individuais
- `CLAUDE.md` — Contexto compartilhado entre 3 Claudes
- GitHub Actions CI — Syntax + imports + secrets check
- Git hooks — Pre-push e pre-commit protections

## Known Issues & Limitations

### O que NÃO funciona ainda
- **Config validation**: Não existe validação do settings.yaml. Se faltam campos, crash sem mensagem clara
- **Testes**: Zero testes unitários/integração. Qualquer refatoração é "reza e push"
- **Dashboard**: Parcialmente implementado. Precisa de investigação do estado real
- **Humanização do mouse**: Usa noise gaussiano simples. Falta curvas Bézier para movimentos mais humanos
- **Creature database**: Tiers de criaturas inferidos pelo reasoning engine, não existe DB estático
- **Skill YAML schema**: Skills não são validadas antes de carregar. YAML inválido = crash
- **Anti-detection**: Nível básico. Análise comportamental mais avançada não implementada

### Pontos de atenção para devs
- `perception/game_reader.py` e `spatial_memory.py` são LEGACY. Use as versões v2
- Os loops têm auto-restart (max 3x). Se um loop morre 3 vezes, ele fica morto até restart do agent
- Strategic brain retorna `None` (manter estado) em caso de falha total da API — o agente não para
- EventBus `_dispatch_event()` é chamado via `call_soon_threadsafe` — handlers DEVEM ser thread-safe
