"""
NEXUS — [NOME DO LOOP] Loop

[Descrição: O que este loop faz e por que existe]
Runs every [X]ms / [X]s.

COMO USAR ESTE TEMPLATE:
    1. Copie este arquivo para core/loops/meu_loop.py
    2. Implemente a lógica dentro do try/except
    3. Registre em core/loops/__init__.py:
         from core.loops.meu_loop import run as meu_loop
         Adicione ("meu_loop", meu_loop) na lista ALL_LOOPS
    4. Commit e push — o loop roda automaticamente

ATRIBUTOS DISPONÍVEIS NO agent:
    agent.state            → GameState (HP, mana, position, mode, etc.)
    agent.running          → bool (False quando agent está parando)
    agent.config           → dict do config/settings.yaml
    agent.reactive_brain   → ReactiveBrain (healing, combat)
    agent.strategic_brain  → StrategicBrain (Claude API)
    agent.consciousness    → Consciousness (memories, goals, emotions)
    agent.navigator        → Navigator (pathfinding)
    agent.loot_engine      → LootEngine
    agent.supply_manager   → SupplyManager
    agent.behavior_engine  → BehaviorEngine
    agent.recovery         → DeathRecovery
    agent.spatial_memory   → SpatialMemoryV2 (SQLite world map)
    agent.reasoning_engine → ReasoningEngine
    agent.explorer         → Explorer
    agent.foundry          → Foundry (self-evolution)
    agent.event_bus        → EventBus
    agent.screen_capture   → ScreenCapture
    agent.game_reader      → GameReaderV2
    agent.skill_engine     → SkillEngine
"""

from __future__ import annotations

import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.agent import NexusAgent

log = structlog.get_logger()


async def run(agent: NexusAgent) -> None:
    """[Descrição curta do loop]."""
    import asyncio

    # Delay inicial (opcional — espera dados acumularem)
    # await asyncio.sleep(10)

    while agent.running:
        try:
            # ============================================
            # SUA LÓGICA AQUI
            # ============================================

            # Exemplo: checar estado
            # if agent.state.hp_percent < 50:
            #     log.info("meu_loop.hp_low", hp=agent.state.hp_percent)

            # Exemplo: usar consciência
            # agent.consciousness.remember(
            #     "categoria", "descrição do evento",
            #     importance=0.5, tags=["tag1", "tag2"],
            # )

            # Exemplo: emitir evento
            # await agent.event_bus.emit(EventType.CUSTOM, {"key": "value"})

            pass

        except Exception as e:
            log.error("meu_loop.error", error=str(e))

        # Intervalo entre ticks (ajuste conforme necessidade)
        await asyncio.sleep(1.0)
