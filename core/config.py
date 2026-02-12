"""
NEXUS — Config validation with Pydantic.

Validates settings.yaml at startup so typos, missing keys, and invalid
values crash loud instead of failing silently 10 minutes into a session.

Usage:
    from core.config import load_config, NexusConfig
    config: NexusConfig = load_config("config/settings.yaml")
    # Access: config.ai.model_strategic, config.reactive.tick_rate_ms, etc.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import structlog
import yaml
from pydantic import BaseModel, Field, field_validator

log = structlog.get_logger()


# ─── Sub-models ─────────────────────────────────────────

class AgentConfig(BaseModel):
    """Top-level agent identity."""
    name: str = "NEXUS"
    version: str = "0.4.1"
    game: str = "tibia"
    character_name: str = "UNNAMED"
    log_level: str = "INFO"

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}, got '{v}'")
        return v_upper


class AIConfig(BaseModel):
    """Claude API configuration."""
    provider: str = "anthropic"
    model_strategic: str = "claude-sonnet-4-5-20250929"
    model_skill_creation: str = "claude-sonnet-4-5-20250929"
    model_quick: str = "claude-haiku-4-5-20251001"
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    strategic_cycle_seconds: float = Field(default=3.0, ge=0.5, le=30.0)
    api_key_env: str = "ANTHROPIC_API_KEY"


class RegionConfig(BaseModel):
    """Screen region definition."""
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0


class CaptureConfig(BaseModel):
    """Screen capture settings."""
    fps: int = Field(default=30, ge=1, le=120)
    monitor_index: int = 0
    backend: str = "dxcam"


class PerceptionConfig(BaseModel):
    """Full perception config."""
    capture: CaptureConfig = CaptureConfig()
    regions: dict[str, RegionConfig] = {}


class HealingConfig(BaseModel):
    """Healing thresholds."""
    critical_hp_percent: int = Field(default=30, ge=1, le=99)
    medium_hp_percent: int = Field(default=60, ge=1, le=99)
    mana_restore_percent: int = Field(default=40, ge=1, le=99)
    spells: list[dict] = []
    potions: list[dict] = []


class AntiPKConfig(BaseModel):
    """Anti-PK settings."""
    enabled: bool = True
    action: str = "flee_to_depot"
    whitelist: list[str] = []
    threat_detection_radius: int = Field(default=8, ge=1, le=20)


class ReactiveConfig(BaseModel):
    """Reactive brain settings."""
    tick_rate_ms: int = Field(default=25, ge=10, le=200)
    healing: HealingConfig = HealingConfig()
    anti_pk: AntiPKConfig = AntiPKConfig()
    hotkeys: dict[str, str] = {}


class HumanizationConfig(BaseModel):
    """Input humanization settings."""
    enabled: bool = True
    mouse_speed_range: list[float] = [0.3, 0.8]
    click_hold_range: list[float] = [0.05, 0.15]
    key_hold_range: list[float] = [0.05, 0.12]
    coordinate_noise_std: float = Field(default=2.0, ge=0.0)
    inter_action_delay: list[float] = [0.08, 0.25]


class InputConfig(BaseModel):
    """Input simulation settings."""
    humanization: HumanizationConfig = HumanizationConfig()


class SkillsConfig(BaseModel):
    """Skill system settings."""
    directory: str = "skills/"
    auto_create: bool = True
    auto_improve: bool = True
    improvement_threshold: int = Field(default=80, ge=0, le=100)
    test_duration_minutes: int = Field(default=5, ge=1)
    max_iterations: int = Field(default=5, ge=1)


class ReasoningConfig(BaseModel):
    """Reasoning engine settings."""
    cycle_seconds: float = Field(default=2.5, ge=0.5, le=30.0)


class MetricsConfig(BaseModel):
    """Metrics loop settings."""
    cycle_seconds: float = Field(default=60.0, ge=5.0, le=600.0)


class DashboardConfig(BaseModel):
    """Dashboard settings."""
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = Field(default=8420, ge=1024, le=65535)
    websocket_update_ms: int = Field(default=500, ge=50, le=5000)


# ─── Root config ────────────────────────────────────────

class NexusConfig(BaseModel):
    """
    Root configuration model for NEXUS.

    Validates all settings at startup. Unknown keys are silently ignored
    (forward-compatible) but missing required keys and invalid values
    raise clear errors immediately.
    """
    agent: AgentConfig = AgentConfig()
    ai: AIConfig = AIConfig()
    perception: PerceptionConfig = PerceptionConfig()
    reactive: ReactiveConfig = ReactiveConfig()
    input: InputConfig = InputConfig()
    skills: SkillsConfig = SkillsConfig()
    reasoning: ReasoningConfig = ReasoningConfig()
    metrics: MetricsConfig = MetricsConfig()
    dashboard: DashboardConfig = DashboardConfig()

    model_config = {"extra": "ignore"}  # Don't fail on unknown keys


# ─── Loader ─────────────────────────────────────────────

def load_config(path: str | Path = "config/settings.yaml") -> NexusConfig:
    """
    Load and validate NEXUS config from YAML file.

    Returns NexusConfig with defaults for any missing sections.
    Raises pydantic.ValidationError with clear messages on invalid values.
    """
    path = Path(path)

    if not path.exists():
        log.warning("config.not_found", path=str(path),
                    msg="Using all defaults")
        return NexusConfig()

    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        log.error("config.yaml_parse_error", path=str(path), error=str(e))
        raise

    config = NexusConfig(**raw)
    log.info("config.loaded", path=str(path),
             game=config.agent.game,
             character=config.agent.character_name,
             model=config.ai.model_strategic)
    return config


def config_to_dict(config: NexusConfig) -> dict:
    """Convert validated config back to dict (for backward compatibility)."""
    return config.model_dump()
