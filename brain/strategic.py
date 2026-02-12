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
import hashlib
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

        # Circuit breaker: stop hammering API when it's down
        self._cb_state: str = "CLOSED"  # CLOSED (normal) | OPEN (fail fast) | HALF_OPEN (probe)
        self._cb_failures: int = 0
        self._cb_threshold: int = 5  # Failures in window to trip
        self._cb_timeout: float = 30.0  # Seconds before OPEN → HALF_OPEN
        self._cb_last_failure: float = 0.0
        self._cb_window: float = 60.0  # Failure counting window (seconds)

        # References (set by agent after init)
        self.consciousness = None
        self.spatial_memory = None       # SpatialMemory instance
        self.reasoning_engine = None     # ReasoningEngine instance
        self.knowledge = None            # KnowledgeEngine instance

        # Async lock for client initialization — prevents duplicate clients
        # when multiple think() calls race during startup
        self._client_lock = asyncio.Lock()

    async def _ensure_client(self) -> bool:
        if self.client:
            return True
        async with self._client_lock:
            # Double-check after acquiring lock (another coroutine may have initialized)
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

    def _cb_check(self) -> bool:
        """Check circuit breaker. Returns True if request is allowed."""
        now = time.time()

        if self._cb_state == "CLOSED":
            return True

        if self._cb_state == "OPEN":
            # Has timeout elapsed? → try HALF_OPEN
            if now - self._cb_last_failure >= self._cb_timeout:
                self._cb_state = "HALF_OPEN"
                log.info("strategic.circuit_breaker", state="HALF_OPEN",
                         msg="probing API health")
                return True
            return False

        # HALF_OPEN: allow one probe request
        return True

    def _cb_record_success(self):
        """Record successful API call — reset circuit breaker."""
        if self._cb_state != "CLOSED":
            log.info("strategic.circuit_breaker", state="CLOSED",
                     msg="API healthy, circuit reset")
        self._cb_state = "CLOSED"
        self._cb_failures = 0

    def _cb_record_failure(self):
        """Record API failure — may trip circuit breaker."""
        now = time.time()

        # Reset counter if gap between CONSECUTIVE failures exceeds window.
        # This correctly implements a sliding window: failures must be clustered
        # within _cb_window seconds to trip the breaker.
        if self._cb_last_failure > 0 and (now - self._cb_last_failure) > self._cb_window:
            self._cb_failures = 0

        self._cb_failures += 1
        self._cb_last_failure = now

        if self._cb_state == "HALF_OPEN":
            # Probe failed — go back to OPEN
            self._cb_state = "OPEN"
            log.warning("strategic.circuit_breaker", state="OPEN",
                        msg="probe failed, re-opening circuit",
                        timeout_s=self._cb_timeout)
        elif self._cb_failures >= self._cb_threshold:
            self._cb_state = "OPEN"
            log.warning("strategic.circuit_breaker", state="OPEN",
                        failures=self._cb_failures,
                        msg=f"threshold {self._cb_threshold} reached, failing fast",
                        timeout_s=self._cb_timeout)

    async def _call_api_with_retry(self, **kwargs) -> Optional[object]:
        """
        Call Claude API with exponential backoff retry + circuit breaker.

        Circuit breaker prevents hammering a dead API:
        - CLOSED: normal operation
        - OPEN: fail fast (return None immediately) for cb_timeout seconds
        - HALF_OPEN: allow one probe, trip back to OPEN on failure

        Retries on: timeout, connection error, rate limit (503/529).
        Does NOT retry on: auth error (401), bad request (400).
        Returns None after all retries exhausted or if circuit is OPEN.
        """
        # Circuit breaker gate
        if not self._cb_check():
            log.debug("strategic.circuit_open",
                      msg="API circuit breaker OPEN, failing fast")
            return None

        last_error = None

        for attempt in range(self._max_retries):
            try:
                result = await self.client.messages.create(**kwargs)
                self._cb_record_success()
                return result
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
                    self._cb_record_failure()
                    return None

                # Exponential backoff: 1s, 2s, 4s
                delay = self._base_delay * (2 ** attempt)
                log.warning("strategic.api_retry",
                            error=str(e)[:80], type=error_type,
                            attempt=attempt + 1, max_retries=self._max_retries,
                            next_delay_s=delay)
                await asyncio.sleep(delay)

        # All retries exhausted — record failure for circuit breaker
        self._cb_record_failure()
        log.error("strategic.api_exhausted",
                  error=str(last_error)[:100] if last_error else "unknown",
                  retries=self._max_retries,
                  cb_state=self._cb_state)
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
        context_hash = int(hashlib.md5(str(diff_key).encode()).hexdigest()[:16], 16)

        if context_hash == self._last_context_hash:
            # State hasn't materially changed — skip API call
            self._skipped_calls += 1
            return None

        self._last_context_hash = context_hash
        self._last_meaningful_change = time.time()

        # Check cache (avoid identical consecutive calls)
        cache_key = hashlib.sha256(context.encode()).hexdigest()[:32]
        now_ts = time.time()
        if cache_key in self._cache:
            cached_time, cached_result = self._cache[cache_key]
            if now_ts - cached_time < self._cache_ttl:
                return cached_result

        # Evict stale cache entries (prevent unbounded memory growth)
        if len(self._cache) > 50:
            stale_keys = [k for k, (t, _) in self._cache.items() if now_ts - t > self._cache_ttl * 10]
            for k in stale_keys:
                del self._cache[k]

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

            # Update conversation history (explicit trim prevents memory leak)
            self._conversation.append({"role": "user", "content": context})
            self._conversation.append({"role": "assistant", "content": text})
            self._conversation = self._conversation[-self._max_history * 2:]

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
        char = snapshot.get("character", {})
        combat = snapshot.get("combat", {})
        supplies = snapshot.get("supplies", {})
        session = snapshot.get("session", {})

        pos = char.get("position") or {}
        pos_str = f"({pos.get('x', '?')},{pos.get('y', '?')},{pos.get('z', '?')})" if pos else "(?,?,?)"
        lines = [
            f"[GAME STATE @ {time.strftime('%H:%M:%S')}]",
            f"HP:{char.get('hp_percent', 0)}% Mana:{char.get('mana_percent', 0)}% "
            f"Pos:{pos_str}",
            f"Mode:{combat.get('mode', '?')} Threat:{combat.get('threat_level', '?')} "
            f"Target:{combat.get('current_target') or '-'}",
        ]

        # Battle list (compact, safe access for malformed creature dicts)
        battle_list = combat.get("battle_list", [])
        if battle_list:
            bl = " ".join(
                f"{c.get('name', '?')}({c.get('hp', 0)}%)" for c in battle_list[:6]
            )
            lines.append(f"Battle: {bl}")

        # Players (safe access)
        nearby_players = combat.get("nearby_players", [])
        if nearby_players:
            pl = " ".join(
                f"{p.get('name', '?')}[{p.get('skull', 'none')}]" for p in nearby_players
            )
            lines.append(f"Players: {pl}")

        # Supplies
        lines.append(f"Pots: HP={supplies.get('health_potions', 0)} Mana={supplies.get('mana_potions', 0)}")

        # Session
        lines.append(
            f"Session: {session.get('duration_minutes', 0):.0f}min XP/hr:{session.get('xp_per_hour', 0):.0f} "
            f"Gold/hr:{session.get('profit_per_hour', 0):.0f} Deaths:{session.get('deaths', 0)} "
            f"Kills:{session.get('kills', 0)} Close:{session.get('close_calls', 0)}"
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

        # Knowledge Engine context (learned facts from vision)
        if self.knowledge:
            try:
                summary = self.knowledge.get_knowledge_summary(max_items=5)
                safe = summary.get("safe_creatures", [])
                dangerous = summary.get("dangerous_creatures", [])
                spells = summary.get("known_spells", [])
                stats = summary.get("stats", {})

                if stats.get("creatures", 0) > 0 or stats.get("spells", 0) > 0:
                    lines.append("")
                    lines.append("[KNOWLEDGE]")
                    lines.append(
                        f"Known: {stats.get('creatures', 0)} creatures, "
                        f"{stats.get('spells', 0)} spells, "
                        f"{stats.get('items', 0)} items, "
                        f"{stats.get('locations', 0)} locations"
                    )
                    if safe:
                        safe_str = " ".join(f"{c['name']}(hp≈{c['hp']},k={c['kills']})" for c in safe[:4])
                        lines.append(f"Safe: {safe_str}")
                    if dangerous:
                        dng_str = " ".join(f"{c['name']}(died={c['deaths_from']})" for c in dangerous[:3])
                        lines.append(f"Danger: {dng_str}")
                    if spells:
                        sp_str = " ".join(f"{s['name']}(mp={s['mana']})" for s in spells[:4])
                        lines.append(f"Spells: {sp_str}")
            except Exception:
                pass  # Knowledge context is optional, never block strategic thinking

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
        if response is None or not response.content:
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
        if response is None or not response.content:
            log.error("strategic.analysis_failed")
            return None
        return self._parse_json(response.content[0].text)

    # ─── Vision-Enhanced Analysis ─────────────────────────

    async def analyze_with_vision(self, frame, context: dict = None) -> Optional[dict]:
        """
        Strategic analysis using vision — for important decisions.
        Uses Sonnet (smarter) for situations where the agent needs deeper analysis.

        Args:
            frame: numpy array (BGR) from screen capture
            context: Optional dict with additional context (knowledge_summary, state)

        Returns:
            Dict with strategic decisions, or None on failure.
        """
        if not await self._ensure_client():
            return None

        import numpy as np
        if frame is None or not isinstance(frame, np.ndarray):
            return None

        from brain.vision_utils import frame_to_base64, build_vision_message

        b64 = frame_to_base64(frame, quality=70, max_width=1024)
        if not b64:
            return None

        knowledge_text = ""
        if context and "knowledge_summary" in context:
            knowledge_text = f"\nKnown facts: {json.dumps(context['knowledge_summary'], indent=1)}"

        state_text = ""
        if context and "state" in context:
            state_text = f"\nCurrent state: {json.dumps(context['state'])}"

        prompt = f"""You are NEXUS strategic brain analyzing a game screenshot for an important decision.
{knowledge_text}{state_text}

Analyze this screenshot and provide a strategic decision in JSON:
{{
    "situation": "brief assessment",
    "threat_level": 0-10,
    "decisions": {{}},
    "new_knowledge": [
        {{"type": "creature|spell|item|location|mechanic", "name": "...", "details": {{}}}}
    ],
    "recommendation": "what should the agent do and why"
}}"""

        content = build_vision_message(b64, prompt)

        start = time.perf_counter()
        try:
            response = await self._call_api_with_retry(
                model=self.config["model_strategic"],
                max_tokens=1024,
                temperature=0.2,
                messages=[{"role": "user", "content": content}],
            )

            latency = (time.perf_counter() - start) * 1000
            self._calls += 1
            self._total_latency_ms += latency

            if response is None or not response.content:
                self._errors += 1
                return None

            return self._parse_json(response.content[0].text)

        except Exception as e:
            self._errors += 1
            log.error("strategic.vision_analysis_error",
                      error=str(e), latency_ms=round((time.perf_counter() - start) * 1000))
            return None

    @property
    def calls(self) -> int:
        return self._calls

    @property
    def skipped_calls(self) -> int:
        return self._skipped_calls

    @property
    def avg_latency_ms(self) -> float:
        return self._total_latency_ms / max(1, self._calls)

    @property
    def error_rate(self) -> float:
        return self._errors / max(1, self._calls)

    @property
    def circuit_breaker_state(self) -> str:
        return self._cb_state
