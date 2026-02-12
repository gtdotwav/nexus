"""
NEXUS — Shared test fixtures.

Provides lightweight mocks and fixtures so tests run without
real game windows, API keys, or hardware peripherals.
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.state.game_state import GameState
from core.state.enums import AgentMode, ThreatLevel
from core.event_bus import EventBus


@pytest.fixture
def event_loop():
    """Create a fresh event loop for each test."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def game_state() -> GameState:
    """A default GameState with sensible values."""
    state = GameState()
    state.character.hp_percent = 100
    state.character.mana_percent = 100
    return state


@pytest.fixture
def event_bus() -> EventBus:
    """A fresh EventBus instance."""
    return EventBus(history_size=50)


@pytest.fixture
def ai_config() -> dict:
    """Minimal AI config for StrategicBrain init (no real API key)."""
    return {
        "model_strategic": "claude-sonnet-4-20250514",
        "model_skill_creation": "claude-sonnet-4-20250514",
        "max_tokens": 512,
        "temperature": 0.2,
        "api_key_env": "NEXUS_TEST_API_KEY",
    }


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic async client that returns valid JSON responses."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text='{"situation": "test", "threat_level": 0, "decisions": {}, "anticipation": "ok", "optimization_note": "none"}')]
    client.messages.create = AsyncMock(return_value=response)
    return client
