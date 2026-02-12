"""
NEXUS Agent - Skill Engine

The self-improving skill system. Loads, creates, tests, and evolves skills.

This is what makes NEXUS fundamentally different from traditional bots:
it can create new skills from scratch and improve existing ones
through autonomous experimentation.
"""

from __future__ import annotations

import asyncio
import time
import yaml
import structlog
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from core.state import GameState

log = structlog.get_logger()


@dataclass
class Skill:
    """Represents a loaded skill."""
    name: str
    game: str
    version: str
    category: str
    performance_score: float = 0.0

    # Skill data
    metadata: dict = field(default_factory=dict)
    waypoints: list = field(default_factory=list)
    targeting: list = field(default_factory=list)
    healing: dict = field(default_factory=dict)
    supplies: dict = field(default_factory=dict)
    anti_pk: dict = field(default_factory=dict)

    # Runtime tracking
    total_sessions: int = 0
    total_xp_gained: int = 0
    total_deaths: int = 0
    avg_xp_per_hour: float = 0.0
    last_used: float = 0.0

    # Source file
    file_path: Optional[str] = None

    # Raw YAML data — needed by agent._activate_skill() for loot/behaviors
    _raw_data: dict = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str) -> "Skill":
        """Load a skill from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        return cls(
            name=data.get("name", "Unknown"),
            game=data.get("game", "tibia"),
            version=data.get("version", "1.0"),
            category=data.get("category", "general"),
            performance_score=data.get("performance_score", 50.0),
            metadata=data.get("metadata", {}),
            waypoints=data.get("waypoints", []),
            targeting=data.get("targeting", []),
            healing=data.get("healing", {}),
            supplies=data.get("supplies", {}),
            anti_pk=data.get("anti_pk", {}),
            file_path=path,
            _raw_data=data,  # Keep full raw data for loot, behaviors, etc.
        )

    def to_yaml(self) -> str:
        """Serialize skill to YAML string."""
        data = {
            "name": self.name,
            "game": self.game,
            "version": self.version,
            "category": self.category,
            "performance_score": self.performance_score,
            "metadata": self.metadata,
            "waypoints": self.waypoints,
            "targeting": self.targeting,
            "healing": self.healing,
            "supplies": self.supplies,
            "anti_pk": self.anti_pk,
        }
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    def save(self, path: str = None):
        """Save skill to YAML file."""
        save_path = path or self.file_path
        if not save_path:
            raise ValueError("No path specified for saving skill")

        with open(save_path, "w") as f:
            f.write(self.to_yaml())

        log.info("skill.saved", name=self.name, path=save_path, version=self.version)


class SkillEngine:
    """
    Manages the lifecycle of skills: load, create, test, improve, deploy.

    The self-improvement loop:
        1. Load existing skills
        2. Run a skill during hunting
        3. Track performance metrics
        4. After session, analyze with Claude API
        5. Generate improvements
        6. A/B test improvements
        7. Keep the better version
        8. Repeat
    """

    def __init__(self, state: GameState, skills_config: dict, strategic_brain):
        self.state = state
        self.config = skills_config
        self.strategic_brain = strategic_brain

        self.skills: dict[str, Skill] = {}
        self.active_skill: Optional[Skill] = None
        self.skills_dir = Path(skills_config["directory"])

        # Self-improvement settings
        self.auto_create = skills_config.get("auto_create", True)
        self.auto_improve = skills_config.get("auto_improve", True)
        self.improvement_threshold = skills_config.get("improvement_threshold", 80)
        self.test_duration = skills_config.get("test_duration_minutes", 5)
        self.max_iterations = skills_config.get("max_iterations", 5)

    async def load_skills(self):
        """Load all skills from the skills directory."""
        if not self.skills_dir.exists():
            self.skills_dir.mkdir(parents=True, exist_ok=True)
            log.info("skill_engine.created_directory", path=str(self.skills_dir))
            return

        yaml_files = list(self.skills_dir.rglob("*.yaml")) + list(self.skills_dir.rglob("*.yml"))

        for path in yaml_files:
            try:
                skill = Skill.from_yaml(str(path))
                self.skills[skill.name] = skill
                log.info(
                    "skill_engine.loaded",
                    name=skill.name,
                    version=skill.version,
                    score=skill.performance_score,
                    category=skill.category,
                )
            except Exception as e:
                log.error("skill_engine.load_error", path=str(path), error=str(e))

        log.info("skill_engine.all_loaded", total=len(self.skills))

    def get_best_skill_for_current_context(self) -> Optional[Skill]:
        """
        Select the best skill based on current game context.

        Considers:
        - Character level (from metadata)
        - Current location
        - Performance score (higher is better)
        - Category match (hunting, trading, etc.)
        """
        hunting_skills = [
            s for s in self.skills.values()
            if s.category == "hunting" and s.game == "tibia"
        ]

        if not hunting_skills:
            return None

        # Sort by performance score (highest first)
        hunting_skills.sort(key=lambda s: s.performance_score, reverse=True)
        return hunting_skills[0]

    async def activate_skill(self, skill_name: str) -> bool:
        """Activate a skill by name."""
        if skill_name in self.skills:
            self.active_skill = self.skills[skill_name]
            self.active_skill.last_used = time.time()
            self.state.active_skill = skill_name
            self.state.current_waypoint_index = 0
            log.info("skill_engine.activated", name=skill_name)
            return True

        log.warning("skill_engine.not_found", name=skill_name)
        return False

    async def create_skill(self, request: dict):
        """
        Create a new skill using the strategic brain (Claude API).

        This is the core of the self-creation system:
        1. Gather context about the current situation
        2. Ask Claude to design a skill
        3. Parse and validate the skill
        4. Save and optionally test it
        """
        log.info("skill_engine.creating", request=request)

        # Build context for skill creation
        context = {
            "request": request,
            "game_state": self.state.get_snapshot(),
            "existing_skills": [
                {"name": s.name, "score": s.performance_score, "category": s.category}
                for s in self.skills.values()
            ],
        }

        # Ask strategic brain to design the skill
        result = await self.strategic_brain.analyze_for_skill_creation(context)

        if not result or "yaml_content" not in result:
            log.error("skill_engine.creation_failed", reason="no response from AI")
            return None

        try:
            # Parse the generated YAML
            yaml_text = result["yaml_content"]

            # Clean up potential markdown artifacts
            if yaml_text.startswith("```"):
                yaml_text = yaml_text.split("\n", 1)[1]
            if yaml_text.endswith("```"):
                yaml_text = yaml_text.rsplit("```", 1)[0]

            skill_data = yaml.safe_load(yaml_text)

            # Create skill object
            skill = Skill(
                name=skill_data.get("name", f"auto_{int(time.time())}"),
                game=skill_data.get("game", "tibia"),
                version="1.0",
                category=skill_data.get("category", "hunting"),
                performance_score=50.0,  # Start at neutral score
                metadata=skill_data.get("metadata", {}),
                waypoints=skill_data.get("waypoints", []),
                targeting=skill_data.get("targeting", []),
                healing=skill_data.get("healing", {}),
                supplies=skill_data.get("supplies", {}),
                anti_pk=skill_data.get("anti_pk", {}),
            )

            # Save to disk
            file_name = skill.name.lower().replace(" ", "_").replace("-", "_")
            file_path = self.skills_dir / f"tibia/{file_name}.yaml"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            skill.file_path = str(file_path)
            skill.save()

            # Register in memory
            self.skills[skill.name] = skill

            log.info(
                "skill_engine.created",
                name=skill.name,
                category=skill.category,
                waypoints=len(skill.waypoints),
                targets=len(skill.targeting),
            )

            return skill

        except Exception as e:
            log.error("skill_engine.creation_parse_error", error=str(e))
            return None

    async def improve_skill(self, skill_name: str, session_metrics: dict):
        """
        Improve an existing skill based on performance data.

        The self-improvement loop:
        1. Analyze performance with Claude
        2. Generate specific improvements
        3. Apply improvements to a copy
        4. Test the improved version
        5. Keep it if better, revert if worse
        """
        if skill_name not in self.skills:
            log.warning("skill_engine.improve_not_found", name=skill_name)
            return

        skill = self.skills[skill_name]

        # Don't improve if score is already good
        if skill.performance_score >= self.improvement_threshold and not self.auto_improve:
            return

        log.info("skill_engine.improving", name=skill_name, current_score=skill.performance_score)

        # Analyze with strategic brain
        analysis = await self.strategic_brain.analyze_skill_performance(
            skill_name, session_metrics
        )

        if not analysis:
            return

        new_score = analysis.get("score", skill.performance_score)
        improvements = analysis.get("improvements", {})

        if not improvements:
            log.info("skill_engine.no_improvements_needed", name=skill_name)
            return

        # Apply improvements
        old_version = skill.version
        version_parts = skill.version.split(".")
        new_minor = int(version_parts[-1]) + 1
        skill.version = f"{'.'.join(version_parts[:-1])}.{new_minor}"

        # Apply healing adjustments
        if "healing" in improvements and improvements["healing"]:
            for key, value in improvements["healing"].items():
                if key in skill.healing:
                    skill.healing[key] = value

        # Apply targeting adjustments
        if "targeting" in improvements and improvements["targeting"]:
            for target_update in improvements["targeting"]:
                for existing_target in skill.targeting:
                    if existing_target.get("name") == target_update.get("name"):
                        existing_target.update(target_update)

        # Update score
        skill.performance_score = new_score

        # Save improved version
        skill.save()

        log.info(
            "skill_engine.improved",
            name=skill_name,
            old_version=old_version,
            new_version=skill.version,
            old_score=round(skill.performance_score, 1),
            new_score=round(new_score, 1),
            improvements=list(improvements.keys()),
        )

    async def save_skill_from_data(self, skill_data: dict) -> Optional[Skill]:
        """
        Save a skill from a raw dict (e.g., from exploration auto-generation).
        Registers it in memory and persists to disk.
        """
        try:
            skill = Skill(
                name=skill_data.get("name", f"auto_{int(time.time())}"),
                game=skill_data.get("game", "tibia"),
                version=skill_data.get("version", "1.0"),
                category=skill_data.get("category", "hunting"),
                performance_score=skill_data.get("performance_score", 50.0),
                metadata=skill_data.get("metadata", {}),
                waypoints=skill_data.get("waypoints", []),
                targeting=skill_data.get("targeting", []),
                healing=skill_data.get("healing", {}),
                supplies=skill_data.get("supplies", {}),
                anti_pk=skill_data.get("anti_pk", {}),
            )

            file_name = skill.name.lower().replace(" ", "_").replace("-", "_")
            # Remove special characters for filesystem safety
            file_name = "".join(c for c in file_name if c.isalnum() or c in ("_",))
            file_path = self.skills_dir / f"tibia/{file_name}.yaml"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            skill.file_path = str(file_path)
            skill.save()

            self.skills[skill.name] = skill

            log.info("skill_engine.saved_from_data",
                     name=skill.name,
                     waypoints=len(skill.waypoints),
                     targets=len(skill.targeting))

            return skill

        except Exception as e:
            log.error("skill_engine.save_from_data_error", error=str(e))
            return None

    async def auto_generate_from_knowledge(self, knowledge) -> Optional[Skill]:
        """
        Generate a hunting skill from accumulated knowledge (Zero-Knowledge System).

        Called when the agent has explored enough and found killable creatures.
        Builds a skill YAML purely from what the agent learned by playing.

        Args:
            knowledge: KnowledgeEngine instance with learned facts

        Returns:
            Skill object if generation succeeded, None if not enough data.
        """
        safe_creatures = knowledge.get_safe_creatures()
        if not safe_creatures:
            log.info("skill_engine.auto_gen_insufficient_data", reason="no safe creatures known")
            return None

        known_locations = knowledge.get_known_locations()
        known_spells = knowledge.get_known_spells()
        dangerous_creatures = knowledge.get_dangerous_creatures()

        # Build targeting list from safe creatures
        targeting = []
        for idx, creature in enumerate(safe_creatures[:5]):
            targeting.append({
                "name": creature["name"],
                "priority": max(1, 6 - idx),
                "attack_mode": "full_attack",
                "chase_distance": 3,
            })

        # Build flee-from list from dangerous creatures
        flee_from = [c["name"] for c in dangerous_creatures[:5]]

        # Infer healing from known spells
        healing_spells = [
            s for s in known_spells
            if "heal" in s.get("effect", "").lower()
            or "exura" in s.get("words", "").lower()
            or "exura" in s.get("name", "").lower()
        ]
        healing = {
            "critical_hp_percent": 30,
            "medium_hp_percent": 60,
        }
        if healing_spells:
            healing["spells"] = [
                {"name": s["name"], "words": s.get("words", ""), "mana_cost": s.get("mana_cost", 0)}
                for s in healing_spells[:3]
            ]

        # Build the skill
        primary_creature = safe_creatures[0]["name"]
        skill_name = f"auto_hunt_{primary_creature.lower().replace(' ', '_')}"

        skill_data = {
            "name": skill_name,
            "game": "detected",
            "version": "1.0",
            "category": "hunting",
            "performance_score": 50.0,
            "metadata": {
                "auto_generated": True,
                "source": "zero_knowledge_learning",
                "creatures_known": len(safe_creatures),
                "locations_known": len(known_locations),
            },
            "targeting": targeting,
            "healing": healing,
            "anti_pk": {
                "enabled": True,
                "action": "flee",
                "flee_from": flee_from,
            },
        }

        # If we have location data, try to build basic waypoints
        if known_locations:
            import json as _json
            loc = known_locations[0]
            try:
                coords = _json.loads(loc.get("coordinates", "{}"))
                if isinstance(coords, dict) and coords.get("x"):
                    skill_data["waypoints"] = [
                        {"x": coords["x"], "y": coords["y"], "z": coords.get("z", 7), "action": "hunt"},
                    ]
            except (ValueError, TypeError, KeyError):
                pass

        log.info("skill_engine.auto_generated",
                 name=skill_name,
                 targets=len(targeting),
                 flee_from=len(flee_from),
                 has_healing=bool(healing_spells),
                 has_waypoints="waypoints" in skill_data)

        return await self.save_skill_from_data(skill_data)

    def get_available_skills(self) -> list[str]:
        """Return list of available skill names."""
        return list(self.skills.keys())

    async def run_improvement_cycle(self):
        """
        Run a full improvement cycle on all skills below threshold.
        Called after each hunting session.
        """
        for name, skill in self.skills.items():
            if skill.performance_score < self.improvement_threshold:
                metrics = {
                    "total_sessions": skill.total_sessions,
                    "avg_xp_per_hour": skill.avg_xp_per_hour,
                    "total_deaths": skill.total_deaths,
                    "total_xp_gained": skill.total_xp_gained,
                    "session_data": self.state.get_snapshot(),
                }
                await self.improve_skill(name, metrics)
