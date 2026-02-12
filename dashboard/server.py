"""
NEXUS — Dashboard Server

Real-time web dashboard powered by aiohttp + WebSocket.
Serves a single-page app that displays:
    - Agent state (HP, mana, position, mode)
    - Session metrics (XP/hr, gold/hr, deaths, kills)
    - Spatial memory minimap visualization
    - Consciousness state (emotion, goals, mastery)
    - Reasoning engine inferences
    - Exploration progress
    - Structured log stream
    - Agent controls (start/stop, skills, exploration)

Architecture:
    - aiohttp serves the static HTML + handles WebSocket
    - Agent pushes state updates every 500ms via WebSocket
    - Dashboard sends control commands back via WebSocket
    - Zero external dependencies beyond aiohttp
"""

from __future__ import annotations

import asyncio
import json
import time
import structlog
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from core.agent import NexusAgent

log = structlog.get_logger()

DASHBOARD_HTML = Path(__file__).parent / "app.html"


class DashboardServer:
    """
    Lightweight dashboard server for NEXUS.

    Runs alongside the agent, pushing real-time state
    updates to connected browsers via WebSocket.
    """

    def __init__(self, agent: "NexusAgent", host: str = "127.0.0.1", port: int = 8420):
        self.agent = agent
        self.host = host
        self.port = port
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._ws_clients: list[web.WebSocketResponse] = []
        self._broadcast_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the dashboard web server."""
        self._app = web.Application()
        self._app.router.add_get("/", self._serve_dashboard)
        self._app.router.add_get("/ws", self._handle_websocket)
        self._app.router.add_get("/api/state", self._api_state)
        self._app.router.add_get("/api/skills", self._api_skills)
        self._app.router.add_get("/api/map", self._api_map)
        self._app.router.add_post("/api/command", self._api_command)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()

        # Start broadcast loop
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())

        log.info("dashboard.started", url=f"http://{self.host}:{self.port}")

    async def stop(self):
        """Stop the dashboard server."""
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass

        # Close all WebSocket connections
        for ws in self._ws_clients:
            await ws.close()
        self._ws_clients.clear()

        if self._runner:
            await self._runner.cleanup()

        log.info("dashboard.stopped")

    # ═══════════════════════════════════════════════════════
    #  HTTP Handlers
    # ═══════════════════════════════════════════════════════

    async def _serve_dashboard(self, request: web.Request) -> web.Response:
        """Serve the single-page dashboard app."""
        if DASHBOARD_HTML.exists():
            return web.Response(
                text=DASHBOARD_HTML.read_text(),
                content_type="text/html",
            )
        return web.Response(text="Dashboard not found", status=404)

    async def _api_state(self, request: web.Request) -> web.Response:
        """Return current agent state as JSON."""
        state = self._build_state_payload()
        return web.json_response(state)

    async def _api_skills(self, request: web.Request) -> web.Response:
        """Return all skills."""
        skills = []
        for name, skill in self.agent.skill_engine.skills.items():
            skills.append({
                "name": name,
                "category": skill.category,
                "score": skill.performance_score,
                "version": skill.version,
                "waypoints": len(skill.waypoints),
                "active": name == self.agent.state.active_skill,
            })
        return web.json_response({"skills": skills})

    async def _api_map(self, request: web.Request) -> web.Response:
        """Return spatial memory map data for visualization."""
        pos = self.agent.state.position
        if not pos:
            return web.json_response({"cells": [], "landmarks": {}})

        z = pos.z
        memory = self.agent.spatial_memory
        cells = []

        if z in memory.floors:
            floor = memory.floors[z]
            for (x, y), cell in floor.cells.items():
                if cell.explored:
                    cells.append({
                        "x": x, "y": y,
                        "w": cell.walkable,
                        "d": round(cell.danger_score, 2),
                        "v": round(cell.value_score, 2),
                        "t": cell.cell_type,
                        "c": sum(cell.creature_types.values()),
                        "lm": cell.landmark,
                    })

        return web.json_response({
            "cells": cells,
            "player": {"x": pos.x, "y": pos.y, "z": pos.z},
            "landmarks": {k: v for k, v in memory.landmarks.items() if v[2] == z},
            "frontiers": [f for f in memory.frontiers if f[2] == z],
        })

    async def _api_command(self, request: web.Request) -> web.Response:
        """Handle control commands from the dashboard."""
        try:
            data = await request.json()
            cmd = data.get("command", "")
            params = data.get("params", {})

            result = await self._execute_command(cmd, params)
            return web.json_response({"ok": True, "result": result})

        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=400)

    # ═══════════════════════════════════════════════════════
    #  WebSocket
    # ═══════════════════════════════════════════════════════

    async def _handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connection for real-time updates."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self._ws_clients.append(ws)
        log.info("dashboard.ws_connected", clients=len(self._ws_clients))

        # Send initial state
        await ws.send_json({"type": "state", "data": self._build_state_payload()})

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        if data.get("type") == "command":
                            result = await self._execute_command(
                                data.get("command", ""),
                                data.get("params", {}),
                            )
                            await ws.send_json({"type": "command_result", "data": result})
                    except json.JSONDecodeError:
                        pass
                elif msg.type == web.WSMsgType.ERROR:
                    log.error("dashboard.ws_error", error=ws.exception())
        finally:
            self._ws_clients.remove(ws)
            log.info("dashboard.ws_disconnected", clients=len(self._ws_clients))

        return ws

    async def _broadcast_loop(self):
        """Push state updates to all connected clients every 500ms."""
        while True:
            try:
                if self._ws_clients:
                    payload = {"type": "state", "data": self._build_state_payload()}
                    payload_json = json.dumps(payload)

                    dead = []
                    for ws in self._ws_clients:
                        try:
                            await ws.send_str(payload_json)
                        except Exception:
                            dead.append(ws)

                    for ws in dead:
                        self._ws_clients.remove(ws)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("dashboard.broadcast_error", error=str(e))

            await asyncio.sleep(0.5)

    # ═══════════════════════════════════════════════════════
    #  State Builder
    # ═══════════════════════════════════════════════════════

    def _build_state_payload(self) -> dict:
        """Build the complete state payload for the dashboard."""
        agent = self.agent
        snapshot = agent.state.get_snapshot()
        char = snapshot.get("character", {})
        combat = snapshot.get("combat", {})
        session = snapshot.get("session", {})

        # Consciousness
        consciousness = {}
        if agent.consciousness:
            consciousness = {
                "emotion": agent.consciousness.emotional_state,
                "mastery": {k: round(v, 2) for k, v in agent.consciousness.mastery.items()},
                "goals": [
                    {"text": g.text, "type": g.type, "priority": g.priority}
                    for g in agent.consciousness.active_goals[:5]
                ],
                "recent_memories": [
                    {"type": m.category, "text": m.content[:100], "importance": m.importance}
                    for m in list(agent.consciousness.working_memory)[-5:]
                ],
            }

        # Reasoning
        reasoning = {}
        if agent.reasoning_engine:
            p = agent.reasoning_engine.current_profile
            reasoning = {
                "danger_trend": p.danger_trend,
                "creature_difficulty": p.creature_difficulty,
                "topology": p.topology,
                "efficiency": p.resource_efficiency,
                "recommendation": p.recommended_action,
                "warnings": p.warnings[:3],
                "opportunities": p.opportunities[:2],
                "recent_inferences": [
                    {"category": i.category, "text": i.description[:80],
                     "confidence": i.confidence, "hint": i.action_hint}
                    for i in agent.reasoning_engine.get_recent_inferences(max_age_s=30)[-5:]
                ],
            }

        # Explorer
        explorer = {
            "active": agent.explorer.active,
            "strategy": agent.explorer.strategy.name if agent.explorer.active else None,
        }
        if hasattr(agent.explorer, "stats"):
            explorer.update(agent.explorer.stats)

        # Spatial memory
        spatial = agent.spatial_memory.stats

        return {
            "timestamp": time.time(),
            "character": {
                "hp": char.get("hp_percent", 100),
                "mana": char.get("mana_percent", 100),
                "position": char.get("position", {}),
            },
            "combat": {
                "mode": agent.state.mode.name,
                "threat": combat.get("threat_level", "NONE"),
                "target": combat.get("current_target"),
                "battle_list": combat.get("battle_list", [])[:8],
                "nearby_players": combat.get("nearby_players", []),
            },
            "session": {
                "duration_min": round(session.get("duration_minutes", 0), 1),
                "xp_hr": round(session.get("xp_per_hour", 0)),
                "gold_hr": round(session.get("profit_per_hour", 0)),
                "deaths": session.get("deaths", 0),
                "kills": session.get("kills", 0),
                "close_calls": session.get("close_calls", 0),
            },
            "active_skill": snapshot.get("active_skill", "None"),
            "consciousness": consciousness,
            "reasoning": reasoning,
            "explorer": explorer,
            "spatial_memory": spatial,
            "foundry": {
                "evolutions": agent.foundry.total_evolutions,
            },
            "recovery": {
                "active": agent.recovery.recovery_active,
                "total": agent.recovery.total_recoveries,
            },
            "navigation": {
                "waypoint": f"{agent.navigator.current_index}/{len(agent.navigator.active_route)}",
            },
            "strategic_brain": {
                "calls": agent.strategic_brain._calls,
                "avg_latency_ms": round(agent.strategic_brain.avg_latency_ms),
                "error_rate": round(agent.strategic_brain.error_rate, 3),
            },
        }

    # ═══════════════════════════════════════════════════════
    #  Command Execution
    # ═══════════════════════════════════════════════════════

    async def _execute_command(self, cmd: str, params: dict) -> dict:
        """Execute a dashboard command."""
        agent = self.agent

        if cmd == "change_mode":
            from core.state import AgentMode
            mode_name = params.get("mode", "HUNTING")
            try:
                agent.state.set_mode(AgentMode[mode_name])
                return {"mode": mode_name}
            except KeyError:
                return {"error": f"Unknown mode: {mode_name}"}

        elif cmd == "change_skill":
            skill_name = params.get("skill", "")
            success = await agent.skill_engine.activate_skill(skill_name)
            if success:
                skill = agent.skill_engine.skills[skill_name]
                agent._activate_skill(skill)
            return {"success": success, "skill": skill_name}

        elif cmd == "start_explore":
            from actions.explorer import ExploreStrategy
            strategy_name = params.get("strategy", "FRONTIER")
            try:
                strategy = ExploreStrategy[strategy_name]
            except KeyError:
                strategy = ExploreStrategy.FRONTIER
            agent.explorer.start_exploration(strategy, reason="dashboard_command")
            from core.state import AgentMode
            agent.state.set_mode(AgentMode.EXPLORING)
            return {"exploring": True, "strategy": strategy.name}

        elif cmd == "stop_explore":
            if agent.explorer.active:
                findings = agent.explorer.stop_exploration()
                from core.state import AgentMode
                agent.state.set_mode(AgentMode.HUNTING)
                return {"exploring": False, "findings": findings}
            return {"exploring": False}

        elif cmd == "save_map":
            await agent.spatial_memory.save()
            return {"saved": True}

        elif cmd == "get_inferences":
            inferences = agent.reasoning_engine.get_recent_inferences(max_age_s=120)
            return {
                "inferences": [
                    {"cat": i.category, "conf": i.confidence,
                     "desc": i.description, "hint": i.action_hint}
                    for i in inferences
                ]
            }

        return {"error": f"Unknown command: {cmd}"}
