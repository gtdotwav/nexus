"""
NEXUS Agent — Foundry (Self-Evolution Engine)

Inspired by OpenClaw's Foundry: a meta-system that writes its own capabilities.

Traditional bots break when the game changes. NEXUS EVOLVES.

The Foundry:
1. OBSERVES — Watches what works and what doesn't across sessions
2. ANALYZES — Uses Claude to deep-analyze patterns, failures, inefficiencies
3. CREATES — Generates new skills, strategies, and even new code
4. TESTS — Runs controlled experiments to validate improvements
5. DEPLOYS — Integrates improvements into the live agent
6. ARCHIVES — Keeps history of all evolution steps for rollback

This is what makes NEXUS a "super player" — it doesn't just play,
it continuously engineers a better version of itself.
"""

from __future__ import annotations

import asyncio
import json
import time
import yaml
import aiofiles
import structlog
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum, auto

log = structlog.get_logger()


class EvolutionType(Enum):
    SKILL_CREATE = auto()      # Create a new skill from scratch
    SKILL_IMPROVE = auto()     # Improve an existing skill
    STRATEGY_EVOLVE = auto()   # Evolve a high-level strategy
    BEHAVIOR_ADAPT = auto()    # Adapt a behavioral parameter
    PATTERN_LEARN = auto()     # Learn a new pattern (e.g., monster behavior)
    COUNTER_DEVELOP = auto()   # Develop counter-strategy (e.g., anti-PK technique)


@dataclass
class EvolutionRecord:
    """Tracks a single evolution event."""
    id: str
    type: EvolutionType
    timestamp: float
    description: str
    trigger: str             # What triggered this evolution
    before_state: dict       # State before evolution
    after_state: dict        # State after evolution
    performance_before: float
    performance_after: float
    success: bool = False
    rolled_back: bool = False
    notes: str = ""


@dataclass
class Experiment:
    """An A/B test between current and evolved behavior."""
    id: str
    name: str
    hypothesis: str          # "Increasing critical HP to 35% will reduce deaths"
    variable: str            # What's being changed
    control_value: any       # Current value
    test_value: any          # New value
    duration_minutes: int
    metrics_to_track: list
    started: float = 0.0
    control_results: dict = field(default_factory=dict)
    test_results: dict = field(default_factory=dict)
    conclusion: str = ""
    winner: str = ""         # "control" or "test"


class Foundry:
    """
    The self-evolution engine of NEXUS.

    Operates in cycles:
    1. Collect performance data and failure patterns
    2. Identify the highest-impact improvement opportunity
    3. Generate an improvement hypothesis
    4. Create or modify the relevant component
    5. Run an A/B experiment
    6. Deploy or rollback based on results
    """

    def __init__(self, consciousness, strategic_brain, skill_engine,
                 reactive_brain=None, data_dir: str = "data"):
        self.consciousness = consciousness
        self.strategic_brain = strategic_brain
        self.skill_engine = skill_engine
        self.reactive_brain = reactive_brain  # Set by agent after init
        self.data_dir = Path(data_dir)
        self.evolution_dir = self.data_dir / "evolution"
        self.evolution_dir.mkdir(parents=True, exist_ok=True)

        # Evolution history
        self.history: list[EvolutionRecord] = []
        self.active_experiment: Optional[Experiment] = None

        # Analysis state
        self._last_analysis = 0.0
        self._analysis_interval = 900  # Every 15 minutes

        # Evolution metrics
        self.total_evolutions = 0
        self.successful_evolutions = 0
        self.total_experiments = 0

    async def initialize(self):
        """Load evolution history."""
        history_file = self.evolution_dir / "history.json"
        if history_file.exists():
            async with aiofiles.open(history_file) as f:
                raw = await f.read()
                data = json.loads(raw)
                self.total_evolutions = data.get("total", 0)
                self.successful_evolutions = data.get("successful", 0)
                self.total_experiments = data.get("experiments", 0)
        log.info(
            "foundry.initialized",
            evolutions=self.total_evolutions,
            success_rate=f"{self.success_rate:.0%}",
        )

    @property
    def success_rate(self) -> float:
        if self.total_evolutions == 0:
            return 0
        return self.successful_evolutions / self.total_evolutions

    # ─── Core Evolution Cycle ─────────────────────────────

    async def evolution_cycle(self, game_state_snapshot: dict):
        """
        Main evolution cycle. Called periodically by the agent.

        Analyzes current performance and identifies the highest-impact
        improvement opportunity, then acts on it.
        """
        now = time.time()
        if now - self._last_analysis < self._analysis_interval:
            return
        self._last_analysis = now

        # If there's an active experiment, check results
        if self.active_experiment:
            await self._check_experiment()
            return

        # Identify the biggest opportunity for improvement
        opportunity = await self._identify_opportunity(game_state_snapshot)

        if not opportunity:
            log.debug("foundry.no_opportunity", msg="Everything looks optimized")
            return

        log.info(
            "foundry.opportunity_found",
            type=opportunity["type"],
            description=opportunity["description"],
            estimated_impact=opportunity.get("estimated_impact", "unknown"),
        )

        # Generate improvement
        improvement = await self._generate_improvement(opportunity)

        if improvement:
            # Start experiment if possible, otherwise deploy directly
            if improvement.get("testable", True):
                await self._start_experiment(improvement)
            else:
                await self._deploy_improvement(improvement)

    async def _identify_opportunity(self, snapshot: dict) -> Optional[dict]:
        """
        Analyze performance data to find the highest-impact improvement.

        Priority order:
        1. Death patterns (dying = maximum inefficiency)
        2. XP/hr below potential (leaving performance on the table)
        3. Supply waste (burning money unnecessarily)
        4. Skill gaps (areas with no coverage)
        5. Stale strategies (haven't improved in a long time)
        """
        opportunities = []

        # 1. Analyze death patterns
        death_memories = self.consciousness.recall(category="death", limit=20)
        if len(death_memories) >= 2:
            # Look for repeated causes
            causes = [m.content for m in death_memories]
            cause_counts = {}
            for cause in causes:
                # Simple similarity — check if same words appear
                key_words = set(cause.lower().split())
                for existing_key in cause_counts:
                    overlap = len(key_words & set(existing_key.split()))
                    if overlap > 3:
                        cause_counts[existing_key] += 1
                        break
                else:
                    cause_counts[cause.lower()] = 1

            repeated = {k: v for k, v in cause_counts.items() if v >= 2}
            if repeated:
                top_cause = max(repeated, key=repeated.get)
                opportunities.append({
                    "type": "death_pattern",
                    "description": f"Repeated deaths: {top_cause} ({repeated[top_cause]} times)",
                    "estimated_impact": "high",
                    "data": {"cause": top_cause, "count": repeated[top_cause]},
                    "priority": 0,
                })

        # 2. XP/hr analysis
        session = snapshot.get("session", {})
        xp_hr = session.get("xp_per_hour", 0)
        active_skill = snapshot.get("active_skill")
        # Compare against known benchmarks per skill
        if active_skill and active_skill in self.skill_engine.skills:
            skill = self.skill_engine.skills[active_skill]
            if skill.avg_xp_per_hour > 0 and xp_hr < skill.avg_xp_per_hour * 0.85:
                opportunities.append({
                    "type": "xp_optimization",
                    "description": f"XP/hr ({xp_hr:.0f}) is {((1 - xp_hr / skill.avg_xp_per_hour) * 100):.0f}% below skill average ({skill.avg_xp_per_hour:.0f})",
                    "estimated_impact": "medium",
                    "data": {"current_xp_hr": xp_hr, "avg_xp_hr": skill.avg_xp_per_hour, "skill": active_skill},
                    "priority": 2,
                })

        # 3. Mastery stagnation
        weak_areas = self.consciousness.get_weakest_areas(3)
        for area in weak_areas:
            if area.level < 30 and area.practice_hours > 1:
                opportunities.append({
                    "type": "mastery_gap",
                    "description": f"Low mastery in {area.name} ({area.level:.0f}/100) despite {area.practice_hours:.1f}h practice",
                    "estimated_impact": "medium",
                    "data": {"area": area.name, "level": area.level},
                    "priority": 3,
                })

        # 4. Healing efficiency
        close_calls = self.consciousness.recall(tags=["close_call"], limit=20)
        if len(close_calls) > 5:
            opportunities.append({
                "type": "healing_optimization",
                "description": f"{len(close_calls)} close calls — healing may be too slow or thresholds too low",
                "estimated_impact": "high",
                "data": {"close_calls": len(close_calls)},
                "priority": 1,
            })

        # Sort by priority
        opportunities.sort(key=lambda x: x["priority"])

        return opportunities[0] if opportunities else None

    async def _generate_improvement(self, opportunity: dict) -> Optional[dict]:
        """
        Use Claude API to generate a specific improvement.

        The AI doesn't just identify the problem — it designs the solution.
        """
        prompt = f"""You are NEXUS Foundry, the self-evolution engine of an autonomous Tibia gaming agent.

An opportunity for improvement has been identified:

Type: {opportunity['type']}
Description: {opportunity['description']}
Impact: {opportunity['estimated_impact']}
Data: {json.dumps(opportunity.get('data', {}), indent=2)}

Current agent memories about this topic:
{self._get_relevant_memories(opportunity)}

Design a specific, measurable improvement. Respond in JSON:
{{
    "improvement_type": "skill_modify|behavior_adjust|strategy_change|new_skill",
    "description": "What specifically to change",
    "testable": true/false,
    "hypothesis": "If we change X, then Y should improve by Z",
    "changes": {{
        "parameter": "value",
        ...
    }},
    "expected_impact": {{
        "metric": "xp_per_hour|deaths_per_hour|profit_per_hour|survival_rate",
        "expected_change_percent": 0-100
    }},
    "risk_level": "low|medium|high",
    "rollback_plan": "How to revert if it fails"
}}"""

        result = await self.strategic_brain.analyze_for_skill_creation({
            "type": "improvement",
            "prompt": prompt,
        })

        if result and "yaml_content" in result:
            try:
                # The response might be JSON despite asking for YAML
                text = result["yaml_content"]
                if text.startswith("{"):
                    return json.loads(text)
                else:
                    return yaml.safe_load(text)
            except Exception as e:
                log.error("foundry.parse_improvement_error", error=str(e))

        return None

    async def _start_experiment(self, improvement: dict):
        """
        Start an A/B experiment to validate the improvement.

        Runs the current behavior (control) vs improved behavior (test)
        for a set duration and compares metrics.
        """
        experiment = Experiment(
            id=f"exp_{int(time.time())}",
            name=improvement.get("description", "Unknown improvement")[:50],
            hypothesis=improvement.get("hypothesis", ""),
            variable=improvement.get("improvement_type", "unknown"),
            control_value=improvement.get("current_value"),
            test_value=improvement.get("changes"),
            duration_minutes=self._analysis_interval // 60,  # Match analysis interval
            metrics_to_track=["xp_per_hour", "deaths", "close_calls", "profit_per_hour"],
            started=time.time(),
        )

        self.active_experiment = experiment
        self.total_experiments += 1

        # Apply the test changes
        if improvement.get("changes"):
            await self._apply_changes(improvement["changes"])

        log.info(
            "foundry.experiment_started",
            id=experiment.id,
            hypothesis=experiment.hypothesis[:80],
            duration_min=experiment.duration_minutes,
        )

        self.consciousness.remember(
            "strategy",
            f"Experiment started: {experiment.hypothesis}",
            importance=0.6,
            tags=["experiment", "foundry"],
        )

    async def _check_experiment(self):
        """Check if the active experiment has completed and evaluate results."""
        if not self.active_experiment:
            return

        exp = self.active_experiment
        elapsed = (time.time() - exp.started) / 60

        if elapsed < exp.duration_minutes:
            return  # Still running

        # Experiment complete — evaluate using multiple signals
        log.info("foundry.experiment_complete", id=exp.id, elapsed_min=elapsed)

        # Collect evaluation metrics
        emotion = self.consciousness.emotion.copy()
        score = 0
        reasons = []

        # Signal 1: Emotional state (confidence up = good, caution down = good)
        if emotion.get("confidence", 0.5) > 0.55:
            score += 1
            reasons.append("confidence_improved")
        if emotion.get("caution", 0.5) < 0.45:
            score += 1
            reasons.append("caution_reduced")

        # Signal 2: Death rate during experiment period
        recent_deaths = sum(
            1 for m in self.consciousness.recall(category="death", max_age_seconds=elapsed * 60, limit=50)
            if m.timestamp >= exp.started
        )
        if recent_deaths == 0:
            score += 2
            reasons.append("zero_deaths")
        elif recent_deaths <= 1:
            score += 1
            reasons.append("low_deaths")
        else:
            score -= 1
            reasons.append(f"deaths={recent_deaths}")

        # Signal 3: Close calls during experiment
        recent_close_calls = sum(
            1 for m in self.consciousness.recall(tags=["close_call"], max_age_seconds=elapsed * 60, limit=50)
            if m.timestamp >= exp.started
        )
        if recent_close_calls <= 2:
            score += 1
            reasons.append("few_close_calls")
        else:
            score -= 1
            reasons.append(f"close_calls={recent_close_calls}")

        # Signal 4: Reactive brain stats (if available)
        if self.reactive_brain:
            stats = self.reactive_brain.stats
            if stats.get("emergency_heals", 0) == 0:
                score += 1
                reasons.append("no_emergency_heals")

        # Decision: need score >= 2 to keep (out of max ~7)
        if score >= 2:
            exp.winner = "test"
            exp.conclusion = f"Improvement positive (score={score}): {', '.join(reasons)}"
            self.successful_evolutions += 1
        else:
            exp.winner = "control"
            exp.conclusion = f"Improvement inconclusive (score={score}): {', '.join(reasons)}"
            # Revert changes by re-applying control values
            if exp.control_value and self.reactive_brain:
                await self._apply_changes({"revert": True, **(exp.control_value if isinstance(exp.control_value, dict) else {})})

        self.total_evolutions += 1

        self.consciousness.remember(
            "strategy",
            f"Experiment result: {exp.conclusion} (winner: {exp.winner})",
            importance=0.7,
            tags=["experiment", "result"],
        )

        log.info(
            "foundry.experiment_result",
            id=exp.id,
            winner=exp.winner,
            conclusion=exp.conclusion[:80],
        )

        # Save evolution record
        record = EvolutionRecord(
            id=exp.id,
            type=EvolutionType.BEHAVIOR_ADAPT,
            timestamp=time.time(),
            description=exp.name,
            trigger=exp.hypothesis,
            before_state=exp.control_results,
            after_state=exp.test_results,
            performance_before=0,
            performance_after=0,
            success=exp.winner == "test",
        )
        self.history.append(record)

        self.active_experiment = None
        await self._save_history()

    async def _deploy_improvement(self, improvement: dict):
        """Deploy an improvement directly (without A/B testing)."""
        log.info("foundry.deploying", description=improvement.get("description", ""))

        if improvement.get("changes"):
            await self._apply_changes(improvement["changes"])

        self.total_evolutions += 1
        self.successful_evolutions += 1  # Assume success for non-testable changes

        self.consciousness.remember(
            "strategy",
            f"Improvement deployed: {improvement.get('description', 'Unknown')}",
            importance=0.7,
            tags=["evolution", "deployed"],
        )

    async def _apply_changes(self, changes: dict):
        """
        Apply parameter changes to the active agent systems.
        Bridges Foundry intelligence → live agent components.
        """
        applied = []

        # Healing threshold changes → reactive brain
        healing_changes = {}
        if "critical_hp" in changes:
            healing_changes["critical_hp"] = changes["critical_hp"]
        if "medium_hp" in changes:
            healing_changes["medium_hp"] = changes["medium_hp"]
        if "mana_threshold" in changes:
            healing_changes["mana_threshold"] = changes["mana_threshold"]

        if healing_changes and self.reactive_brain:
            self.reactive_brain.update_healing_thresholds(healing_changes)
            applied.append("healing")
            log.info("foundry.applied_healing", changes=healing_changes)

        # Aggression changes → reactive brain
        aggression_changes = {}
        if "chase_distance" in changes:
            aggression_changes["chase_distance"] = changes["chase_distance"]
        if "attack_mode" in changes:
            aggression_changes["attack_mode"] = changes["attack_mode"]
        if "pull_count" in changes:
            aggression_changes["pull_count"] = changes["pull_count"]

        if aggression_changes and self.reactive_brain:
            self.reactive_brain.update_aggression(aggression_changes)
            applied.append("aggression")
            log.info("foundry.applied_aggression", changes=aggression_changes)

        # Spell rotation changes → reactive brain
        if "spell_rotation" in changes and self.reactive_brain:
            self.reactive_brain.set_spell_rotation(changes["spell_rotation"])
            applied.append("spell_rotation")

        # Targeting changes → active skill
        if "targeting" in changes and self.skill_engine.active_skill:
            skill = self.skill_engine.active_skill
            for target_update in changes["targeting"]:
                for existing in skill.targeting:
                    if existing.get("name") == target_update.get("name"):
                        existing.update(target_update)
            skill.save()
            applied.append("targeting")
            log.info("foundry.applied_targeting")

        # Waypoint changes → active skill
        if "waypoints" in changes and self.skill_engine.active_skill:
            skill = self.skill_engine.active_skill
            skill.waypoints = changes["waypoints"]
            skill.save()
            applied.append("waypoints")
            log.info("foundry.applied_waypoints")

        if applied:
            log.info("foundry.changes_applied", components=applied)
        else:
            log.warning("foundry.no_changes_applied", changes=list(changes.keys()))

    def _get_relevant_memories(self, opportunity: dict) -> str:
        """Get memories relevant to the opportunity."""
        category = {
            "death_pattern": "death",
            "healing_optimization": "combat",
            "mastery_gap": "mastery",
            "xp_optimization": "strategy",
        }.get(opportunity["type"], "combat")

        memories = self.consciousness.recall(category=category, limit=10)
        return "\n".join(f"- {m.content}" for m in memories)

    # ─── Autonomous Skill Creation ────────────────────────

    async def process_consciousness_findings(self, findings: dict, snapshot: dict):
        """
        Receive findings from the Consciousness deep analysis layer.
        Act on them immediately — no waiting for the next evolution cycle.
        """
        if "death_pattern" in findings:
            dp = findings["death_pattern"]
            log.info("foundry.death_pattern_received", cause=dp["top_cause"], count=dp["count"])
            # Create an immediate opportunity from the death pattern
            opportunity = {
                "type": "death_pattern",
                "description": f"Repeated death: {dp['top_cause']} ({dp['count']} times)",
                "estimated_impact": "critical",
                "data": dp,
                "priority": 0,
            }
            improvement = await self._generate_improvement(opportunity)
            if improvement:
                await self._deploy_improvement(improvement)

        if "risk_pattern" in findings:
            rp = findings["risk_pattern"]
            log.info("foundry.risk_pattern", risk=rp["top_risk"], count=rp["count"])

        if "efficiency_decline" in findings:
            ed = findings["efficiency_decline"]
            log.warning("foundry.efficiency_decline", drop=f"{ed['drop_percent']}%")

    async def auto_create_skill_for_situation(self, situation: dict):
        """
        Autonomously create a new skill when the agent encounters
        an unfamiliar situation.

        This is the gaming equivalent of OpenClaw's Foundry:
        observe → research → write → deploy.
        """
        log.info("foundry.auto_creating_skill", situation=situation.get("description", ""))

        # Step 1: Analyze what's needed
        analysis_prompt = f"""The gaming agent is in an unfamiliar situation:
{json.dumps(situation, indent=2)}

Research what's needed:
1. What type of skill would handle this?
2. What are the key challenges?
3. What parameters should be conservative vs aggressive?
4. What's the safest approach to start with?

Then create a complete Tibia skill YAML definition."""

        result = await self.strategic_brain.analyze_for_skill_creation({
            "type": "auto_create",
            "prompt": analysis_prompt,
            "game_state": situation.get("game_state", {}),
        })

        if result:
            # Create the skill through the skill engine
            skill = await self.skill_engine.create_skill({
                "reason": situation.get("description", "auto-detected need"),
                "type": result.get("skill_type", "hunting"),
                "yaml_content": result.get("yaml_content", ""),
            })

            if skill:
                self.consciousness.remember(
                    "skill",
                    f"Auto-created skill: {skill.name} for situation: {situation.get('description', '')}",
                    importance=0.8,
                    tags=["skill_created", "foundry"],
                )
                return skill

        return None

    # ─── Persistence ──────────────────────────────────────

    async def _save_history(self):
        """Save evolution history."""
        history_file = self.evolution_dir / "history.json"
        data = {
            "total": self.total_evolutions,
            "successful": self.successful_evolutions,
            "experiments": self.total_experiments,
            "recent": [
                {
                    "id": r.id,
                    "type": r.type.name,
                    "timestamp": r.timestamp,
                    "description": r.description,
                    "success": r.success,
                }
                for r in self.history[-100:]
            ],
        }
        async with aiofiles.open(history_file, "w") as f:
            await f.write(json.dumps(data, indent=2))
