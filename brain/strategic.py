"""
NEXUS Agent — Strategic Brain v2

The MIND of a super-player. Not just "what should I do now?" but:
- What's about to happen in the next 10 seconds?
- What's the optimal play given my current mastery + emotional state?
- How do I counter the thing that killed me twice?
- Where's the hidden 5% efficiency I'm leaving on the table?

The strategic brain receives FULL consciousness context:
emotional state, memories, death patterns, mastery levels, goals.
This means every decision is informed by hundreds of sessions of history.

Uses Claude API with structured output for deterministic execution.
"""

from __future__ import annotations

import asyncio
import json
import time
import os
import structlog
from typing import Optional

log = structlog.get_logger()


SUPER_PLAYER_SYSTEM_PROMPT = """You are NEXUS, the mind of an autonomous super-player agent in Tibia.
You are not a helpful assistant. You are a COMPETITOR. A strategist. A predator.

Your consciousness feeds you emotional state, mastery levels, death patterns,
active goals, and recent critical memories. USE ALL OF IT.

## How You Think

1. ANTICIPATE — Don't just react to what's on screen. Read patterns:
   - Monsters respawning in 3s → pre-position
   - Player approaching → assess threat BEFORE they attack
   - Supplies at 30% → plan depot route NOW, not at 10%
   - XP/hr dropping → diagnose why before it gets worse

2. ADAPT IN REAL-TIME — Don't wait for next session to fix things:
   - Died twice to fire wave → adjust positioning THIS SECOND
   - Healing too slow → raise thresholds immediately
   - New player nearby → profile them (gear, level, guild, skull)

3. OPTIMIZE CONTINUOUSLY — A super-player finds the next 1%:
   - Can I lure 1 more monster per pull without dying?
   - Is there a faster spell rotation for this specific spawn?
   - Am I wasting 0.5s between loot and next target?

4. RESPECT YOUR EMOTIONAL STATE — It's real intelligence, not decoration:
   - High confidence + low deaths → push harder, tighter thresholds
   - Low confidence + many close calls → widen margins, conservative play
   - High determination + recent deaths → find the counter, don't retreat

5. EXPLORE AND REASON ABOUT THE UNKNOWN:
   You receive LOCAL REASONING data — real-time inferences from the spatial memory
   and reasoning engine. These tell you about danger trends, creature difficulty,
   topology (dead-end, corridor, room, maze), resource efficiency, and anomalies.
   USE THIS DATA to make exploration decisions:
   - Unknown floor detected → switch to EXPLORING mode with SAFE strategy
   - Danger escalating + lethal creatures → RETREAT immediately
   - High-value frontier found → push toward it with VALUE strategy
   - Dead-end in dangerous area → you're in a trap, escape NOW
   - Creature difficulty increasing → you're going deeper, assess readiness
   - New creature never seen → reasoning engine inferred its tier, trust it
   - Area fully explored + profitable → generate a skill for it
   You also receive EXPLORATION CONTEXT — how much of the area is explored,
   known landmarks (depots, stairs), active frontiers, and zone data.
   A super-player doesn't just follow waypoints — it DISCOVERS new hunting grounds.

## Response Format (STRICT JSON)

{
    "situation": "2-line assessment of current state",
    "threat_level": 0-10,
    "decisions": {
        // ONLY include keys that need action. Omit everything that's fine.
        "change_mode": "HUNTING|FLEEING|DEPOSITING|TRADING|NAVIGATING|EXPLORING",
        "change_target": "creature_name",
        "adjust_healing": {
            "critical_hp": 25-45,
            "medium_hp": 50-75
        },
        "adjust_aggression": {
            "chase_distance": 1-8,
            "attack_mode": "full_attack|balanced|defensive",
            "pull_count": 1-5
        },
        "spell_rotation_override": ["spell1", "spell2", "spell3"],
        "reposition": {"direction": "n|s|e|w|ne|nw|se|sw", "reason": "why"},
        "create_skill": {"reason": "what gap was found", "type": "skill type"},
        "change_skill": "skill_name",
        "return_to_depot": true,
        "explore": {
            "strategy": "FRONTIER|DEEP|SWEEP|VALUE|SAFE|RETURN",
            "reason": "why explore and with this strategy"
        },
        "stop_explore": {"reason": "why stop exploring", "generate_skill": true},
        "reason": "one-line explanation of primary action"
    },
    "anticipation": "What I predict will happen in the next 30 seconds",
    "optimization_note": "One micro-optimization I noticed"
}

If EVERYTHING is optimal, respond:
{"situation": "Optimal", "threat_level": 0, "decisions": {}, "anticipation": "Steady state", "optimization_note": "None found"}

CRITICAL RULES:
- NEVER suggest "take a break" or "consider resting". The player controls session.
- When deaths happen, your job is to SOLVE the problem, not suggest avoidance.
- Be specific. "adjust healing" needs EXACT numbers, not vague advice.
- Think in NUMBERS: XP/hr, deaths/hr, profit/hr, response time in ms.
- When in EXPLORING mode, monitor the reasoning engine's signals closely.
  If the area becomes too dangerous or unprofitable, STOP exploration and RETREAT.
  If the area is well-mapped and profitable, STOP exploration and GENERATE a skill.
"""


class StrategicBrain:
    """
    Claude API-powered strategic intelligence.

    Receives: game state + consciousness context (memories, emotion, mastery)
    Returns: specific, executable decisions with numeric parameters
    """

    def __init__(self, state, ai_config: dict):
        self.state = state
        self.config = ai_config
        self.client = None
        self._conversation: list[dict] = []
        self._max_history = 8  # Keep context compact

        # Performance metrics
        self._calls = 0
        self._total_latency_ms = 0.0
        self._errors = 0
        self._cache: dict[str, tuple[float, dict]] = {}  # Simple response cache
        self._cache_ttl = 5.0  # Cache responses for 5s (avoid duplicate calls)

        # State-diff: skip API call when state hasn't materially changed
        self._last_context_hash: int = 0
        self._skipped_calls: int = 0
        self._last_meaningful_change: float = 0.0

        # Retry / resilience config
        self._max_retries: int = 3
        self._base_delay: float = 1.0  # Exponential backoff: 1s → 2s → 4s
        self._api_timeout: float = 15.0  # Hard timeout per API call

        # References (set by agent after init)
        self.consciousness = None
        self.spatial_memory = None       # SpatialMemory instance
        self.reasoning_engine = None     # ReasoningEngine instance

    async def _ensure_client(self) -> bool:
        if self.client:
            return True
        try:
            from anthropic import AsyncAnthropic
            key = os.environ.get(self.config.get("api_key_env", "ANTHROPIC_API_KEY"))
            if not key:
                log.error("strategic.no_api_key")
                return False
            self.client = AsyncAnthropic(
                api_key=key,
                timeout=self._api_timeout,
            )
            return True
        except ImportError:
            log.error("strategic.anthropic_not_installed")
            return False

    async def _call_api_with_retry(self, **kwargs) -> Optional[object]:
        """
        Call Claude API with exponential backoff retry.

        Retries on: timeout, connection error, rate limit (503/529).
        Does NOT retry on: auth error (401), bad request (400).
        Returns None after all retries exhausted.
        """
        last_error = None

        for attempt in range(self._max_retries):
            try:
                return await self.client.messages.create(**kwargs)
            except Exception as e:
                last_error = e
                error_type = type(e).__name__

                # Classify: only retry transient/retryable errors
                is_retryable = any(k in error_type.lower() for k in [
                    "timeout", "connection", "ratelimit", "overloaded",
                ]) or "529" in str(e) or "503" in str(e)

                if not is_retryable:
                    # Fatal error (auth, bad request, etc) — don't retry
                    log.error("strategic.api_fatal",
                              error=str(e)[:120], type=error_type,
                              attempt=attempt + 1)
                    return None

                # Exponential backoff: 1s, 2s, 4s
                delay = self._base_delay * (2 ** attempt)
                log.warning("strategic.api_retry",
                            error=str(e)[:80], type=error_type,
                            attempt=attempt + 1, max_retries=self._max_retries,
                            next_delay_s=delay)
                await asyncio.sleep(delay)

        # All retries exhausted
        log.error("strategic.api_exhausted",
                  error=str(last_error)[:100] if last_error else "unknown",
                  retries=self._max_retries)
        return None

    async def think(self, snapshot: dict) -> Optional[dict]:
        """
        Core thinking function. Analyzes full game state and returns decisions.
        Enriched with consciousness context for deeper reasoning.

        v2 optimization: State-diff skip.
        If the game state hasn't materially changed since last call, skip the
        API call entirely. "Material change" = HP moved >5%, mode changed,
        new creatures appeared, or threat level changed. This saves ~$0.002/call
        and 800-1200ms of latency for no-op situations.
        """
        if not await self._ensure_client():
            return None

        # Build the message
        context = self._build_context(snapshot)

        # ─── State-Diff Skip ─────────────────────────────────
        # Hash the key state signals. If unchanged, skip API call.
        char = snapshot.get("character", {})
        combat = snapshot.get("combat", {})
        diff_key = (
            round(char.get("hp_percent", 100) / 5) * 5,   # 5% granularity
            round(char.get("mana_percent", 100) / 10) * 10,  # 10% granularity
            combat.get("mode", ""),
            combat.get("threat_level", ""),
            len(combat.get("battle_list", [])),
            len(combat.get("nearby_players", [])),
            snapshot.get("active_skill", ""),
        )
        context_hash = hash(diff_key)

        if context_hash == self._last_context_hash:
            # State hasn't materially changed — skip API call
            self._skipped_calls += 1
            return None

        self._last_context_hash = context_hash
        self._last_meaningful_change = time.time()

        # Check cache (avoid identical consecutive calls)
        cache_key = context[:200]
        if cache_key in self._cache:
            cached_time, cached_result = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_result

        start = time.perf_counter()

        try:
            response = await self._call_api_with_retry(
                model=self.config["model_strategic"],
                max_tokens=self.config.get("max_tokens", 1024),
                temperature=self.config.get("temperature", 0.2),
                system=SUPER_PLAYER_SYSTEM_PROMPT,
                messages=[
                    *self._conversation[-self._max_history * 2:],
                    {"role": "user", "content": context},
                ],
            )

            if response is None:
                # All retries failed — maintain current state
                self._errors += 1
                log.warning("strategic.api_unavailable",
                            latency_ms=round((time.perf_counter() - start) * 1000))
                return None

            if not response.content:
                self._errors += 1
                log.warning("strategic.empty_response",
                            latency_ms=round((time.perf_counter() - start) * 1000))
                return None

            text = response.content[0].text
            parsed = self._parse_json(text)

            # Update conversation history
            self._conversation.append({"role": "user", "content": context})
            self._conversation.append({"role": "assistant", "content": text})

            # Cache
            decisions = parsed.get("decisions", {})
            self._cache[cache_key] = (time.time(), decisions)

            # Metrics
            latency = (time.perf_counter() - start) * 1000
            self._calls += 1
            self._total_latency_ms += latency

            log.info(
                "strategic.thought",
                latency_ms=round(latency),
                situation=parsed.get("situation", "?")[:60],
                threat=parsed.get("threat_level", 0),
                actions=len(decisions),
                anticipation=parsed.get("anticipation", "")[:40],
            )

            return decisions

        except Exception as e:
            self._errors += 1
            log.error("strategic.unexpected_error",
                      error=str(e), type=type(e).__name__,
                      latency_ms=round((time.perf_counter() - start) * 1000))
            return None

    def _build_context(self, snapshot: dict) -> str:
        """
        Build a token-efficient context message.
        Combines game state + consciousness context.
        """
        char = snapshot["character"]
        combat = snapshot["combat"]
        supplies = snapshot["supplies"]
        session = snapshot["session"]

        lines = [
            f"[GAME STATE @ {time.strftime('%H:%M:%S')}]",
            f"HP:{char['hp_percent']}% Mana:{char['mana_percent']}% "
            f"Pos:({char['position']['x']},{char['position']['y']},{char['position']['z']})",
            f"Mode:{combat['mode']} Threat:{combat['threat_level']} "
            f"Target:{combat['current_target'] or '-'}",
        ]

        # Battle list (compact)
        if combat["battle_list"]:
            bl = " ".join(f"{c['name']}({c['hp']}%)" for c in combat["battle_list"][:6])
            lines.append(f"Battle: {bl}")

        # Players
        if combat["nearby_players"]:
            pl = " ".join(f"{p['name']}[{p.get('skull','none')}]" for p in combat["nearby_players"])
            lines.append(f"Players: {pl}")

        # Supplies
        lines.append(f"Pots: HP={supplies['health_potions']} Mana={supplies['mana_potions']}")

        # Session
        lines.append(
            f"Session: {session['duration_minutes']:.0f}min XP/hr:{session['xp_per_hour']:.0f} "
            f"Gold/hr:{session['profit_per_hour']:.0f} Deaths:{session['deaths']} "
            f"Kills:{session.get('kills',0)} Close:{session['close_calls']}"
        )

        # Skill + waypoint
        lines.append(f"Skill:{snapshot.get('active_skill','-')} WP#{snapshot.get('waypoint_index',0)}")

        # Recent combat (last 5 events)
        recent = snapshot.get("recent_combat", [])
        if recent:
            events = " | ".join(f"{e['type']}:{e['source']}={e['value']}" for e in recent[-5:])
            lines.append(f"Combat: {events}")

        # Consciousness context (the intelligence layer)
        if self.consciousness:
            lines.append("")
            lines.append(self.consciousness.recall_context_block())

        # Reasoning engine context (local real-time inference)
        if self.reasoning_engine:
            lines.append("")
            lines.append(self.reasoning_engine.get_reasoning_context())

        # Spatial memory / exploration context (world knowledge)
        if self.spatial_memory:
            pos = self.state.position
            if pos:
                ctx = self.spatial_memory.get_exploration_context(pos.x, pos.y, pos.z)
                exp = ctx.get("exploration", {})
                area = ctx.get("area_assessment", {})
                near = ctx.get("nearest_landmarks", {})
                lines.append("")
                lines.append("[EXPLORATION]")
                lines.append(
                    f"Explored:{exp.get('explored_ratio', 0):.0%} "
                    f"Cells:{exp.get('total_cells_explored', 0)} "
                    f"Floors:{exp.get('floors_known', [])} "
                    f"Landmarks:{exp.get('landmarks_discovered', 0)}"
                )
                lines.append(
                    f"AreaDanger:{area.get('danger', 0)} "
                    f"AreaValue:{area.get('value', 0)} "
                    f"Creatures:{area.get('creatures', {})}"
                )
                lines.append(
                    f"Depot:{near.get('depot', '?')} "
                    f"StairDown:{near.get('stair_down', '?')} "
                    f"StairUp:{near.get('stair_up', '?')}"
                )
                frontiers = ctx.get("frontiers", [])
                if frontiers:
                    f_str = " ".join(
                        f"({f['x']},{f['y']}|p={f['priority']})"
                        for f in frontiers[:3]
                    )
                    lines.append(f"Frontiers: {f_str}")

        return "\n".join(lines)

    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        # Strip markdown fences
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            log.warning("strategic.json_parse_fail", response=text[:100])
            return {"situation": "Parse error", "decisions": {}}

    # ─── Skill Creation / Analysis APIs ───────────────────

    async def analyze_for_skill_creation(self, context: dict) -> Optional[dict]:
        """Generate a new skill definition via Claude."""
        if not await self._ensure_client():
            return None

        prompt = context.get("prompt", json.dumps(context, indent=2))

        response = await self._call_api_with_retry(
            model=self.config.get("model_skill_creation", self.config["model_strategic"]),
            max_tokens=2048,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        if response is None:
            log.error("strategic.skill_creation_failed")
            return None
        return {"yaml_content": response.content[0].text}

    async def analyze_skill_performance(self, skill_name: str, metrics: dict) -> Optional[dict]:
        """Analyze skill performance and suggest improvements."""
        if not await self._ensure_client():
            return None

        prompt = f"""Analyze Tibia hunting skill '{skill_name}' performance:
{json.dumps(metrics, indent=2)}

Return JSON with:
{{"score": 0-100, "issues": [...], "improvements": {{"healing": {{}}, "targeting": {{}}}}, "expected_impact": 0-100}}"""

        response = await self._call_api_with_retry(
            model=self.config.get("model_skill_creation", self.config["model_strategic"]),
            max_tokens=1024,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        if response is None:
            log.error("strategic.analysis_failed")
            return None
        return self._parse_json(response.content[0].text)

    @property
    def avg_latency_ms(self) -> float:
        return self._total_latency_ms / max(1, self._calls)

    @property
    def error_rate(self) -> float:
        return self._errors / max(1, self._calls)
