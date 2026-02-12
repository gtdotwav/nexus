"""
NEXUS — StrategicBrain tests.

Validates: circuit breaker, cache hashing, state-diff skip,
JSON parsing, conversation trim, and error handling.
No real API calls — everything is mocked.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from brain.strategic import StrategicBrain


@pytest.fixture
def brain(ai_config):
    """StrategicBrain with mock client."""
    from core.state.game_state import GameState
    state = GameState()
    b = StrategicBrain(state, ai_config)
    return b


@pytest.fixture
def brain_with_client(brain, mock_anthropic_client):
    """StrategicBrain with pre-attached mock client."""
    brain.client = mock_anthropic_client
    return brain


def _snapshot(hp=100, mana=100, mode="HUNTING", battle_list=None):
    """Helper to build a minimal snapshot dict."""
    return {
        "character": {
            "hp_percent": hp,
            "mana_percent": mana,
            "position": {"x": 100, "y": 200, "z": 7},
        },
        "combat": {
            "mode": mode,
            "threat_level": "LOW",
            "battle_list": battle_list or [],
            "nearby_players": [],
            "current_target": None,
        },
        "supplies": {"health_potions": 50, "mana_potions": 100},
        "session": {
            "duration_minutes": 30,
            "xp_per_hour": 500000,
            "profit_per_hour": 100000,
            "deaths": 0,
            "kills": 25,
            "close_calls": 1,
        },
        "active_skill": "darashia_dragons_ek",
        "waypoint_index": 3,
    }


# ─── Circuit Breaker Tests ──────────────────────────────

class TestCircuitBreaker:

    def test_initial_state_closed(self, brain):
        """Circuit breaker should start in CLOSED state."""
        assert brain._cb_state == "CLOSED"
        assert brain._cb_failures == 0

    def test_check_allows_when_closed(self, brain):
        """Requests should be allowed when circuit is CLOSED."""
        assert brain._cb_check() is True

    def test_trips_after_threshold(self, brain):
        """Circuit should OPEN after threshold failures."""
        for _ in range(brain._cb_threshold):
            brain._cb_record_failure()
        assert brain._cb_state == "OPEN"

    def test_open_blocks_requests(self, brain):
        """Requests should be blocked when circuit is OPEN."""
        for _ in range(brain._cb_threshold):
            brain._cb_record_failure()
        assert brain._cb_check() is False

    def test_half_open_after_timeout(self, brain):
        """After timeout, OPEN → HALF_OPEN to allow probe."""
        for _ in range(brain._cb_threshold):
            brain._cb_record_failure()
        assert brain._cb_state == "OPEN"

        # Simulate timeout elapsed
        brain._cb_last_failure = time.time() - brain._cb_timeout - 1
        assert brain._cb_check() is True
        assert brain._cb_state == "HALF_OPEN"

    def test_success_resets_to_closed(self, brain):
        """Successful probe should reset circuit to CLOSED."""
        brain._cb_state = "HALF_OPEN"
        brain._cb_failures = 5
        brain._cb_record_success()
        assert brain._cb_state == "CLOSED"
        assert brain._cb_failures == 0

    def test_half_open_failure_reopens(self, brain):
        """Failed probe in HALF_OPEN should revert to OPEN."""
        brain._cb_state = "HALF_OPEN"
        brain._cb_record_failure()
        assert brain._cb_state == "OPEN"

    @pytest.mark.asyncio
    async def test_api_call_blocked_when_open(self, brain_with_client):
        """API calls should return None immediately when circuit is OPEN."""
        brain_with_client._cb_state = "OPEN"
        brain_with_client._cb_last_failure = time.time()  # Recent failure

        result = await brain_with_client._call_api_with_retry(
            model="test", messages=[], max_tokens=10
        )
        assert result is None
        # Client should NOT have been called
        brain_with_client.client.messages.create.assert_not_called()


# ─── Cache & State-Diff Tests ───────────────────────────

class TestCacheAndStateDiff:

    def test_cache_key_is_deterministic(self):
        """Same context should always produce the same cache key."""
        context = "HP:100% Mana:80% Mode:HUNTING"
        key1 = hashlib.sha256(context.encode()).hexdigest()[:32]
        key2 = hashlib.sha256(context.encode()).hexdigest()[:32]
        assert key1 == key2

    def test_state_diff_hash_is_deterministic(self):
        """Same diff_key should always produce the same hash."""
        diff_key = (100, 80, "HUNTING", "LOW", 3, 0, "skill1")
        h1 = int(hashlib.md5(str(diff_key).encode()).hexdigest()[:16], 16)
        h2 = int(hashlib.md5(str(diff_key).encode()).hexdigest()[:16], 16)
        assert h1 == h2

    def test_different_states_produce_different_hashes(self):
        """Different game states should hash differently."""
        key1 = (100, 80, "HUNTING", "LOW", 3, 0, "skill1")
        key2 = (50, 80, "FLEEING", "HIGH", 5, 1, "skill1")
        h1 = int(hashlib.md5(str(key1).encode()).hexdigest()[:16], 16)
        h2 = int(hashlib.md5(str(key2).encode()).hexdigest()[:16], 16)
        assert h1 != h2

    @pytest.mark.asyncio
    async def test_state_diff_skips_unchanged(self, brain_with_client):
        """Identical snapshots should be skipped on second call."""
        snap = _snapshot()

        # First call — should hit API
        result1 = await brain_with_client.think(snap)
        assert brain_with_client.client.messages.create.call_count == 1

        # Second call with same snapshot — should skip
        result2 = await brain_with_client.think(snap)
        assert brain_with_client.client.messages.create.call_count == 1
        assert result2 is None
        assert brain_with_client._skipped_calls == 1

    @pytest.mark.asyncio
    async def test_state_diff_detects_changes(self, brain_with_client):
        """Changed HP should trigger a new API call."""
        snap1 = _snapshot(hp=100)
        snap2 = _snapshot(hp=50)  # HP changed significantly

        await brain_with_client.think(snap1)
        assert brain_with_client.client.messages.create.call_count == 1

        await brain_with_client.think(snap2)
        assert brain_with_client.client.messages.create.call_count == 2


# ─── JSON Parsing Tests ─────────────────────────────────

class TestJSONParsing:

    def test_parse_clean_json(self, brain):
        """Should parse clean JSON correctly."""
        result = brain._parse_json('{"situation": "ok", "decisions": {}}')
        assert result["situation"] == "ok"

    def test_parse_markdown_fenced_json(self, brain):
        """Should handle markdown code fences."""
        text = '```json\n{"situation": "fenced", "decisions": {}}\n```'
        result = brain._parse_json(text)
        assert result["situation"] == "fenced"

    def test_parse_invalid_json(self, brain):
        """Should return fallback on invalid JSON."""
        result = brain._parse_json("this is not json at all")
        assert result["situation"] == "Parse error"
        assert result["decisions"] == {}


# ─── Conversation Trim Tests ─────────────────────────────

class TestConversationTrim:

    @pytest.mark.asyncio
    async def test_conversation_trimmed(self, brain_with_client):
        """Conversation should be trimmed to max_history * 2 entries."""
        brain_with_client._max_history = 3  # Keep 6 messages (3 pairs)

        # Make many unique calls to build up conversation
        for hp in range(100, 40, -10):
            await brain_with_client.think(_snapshot(hp=hp))

        # Should be trimmed to 6 (3 user + 3 assistant)
        assert len(brain_with_client._conversation) <= 6


# ─── Build Context Safety Tests ──────────────────────────

class TestBuildContext:

    def test_empty_snapshot(self, brain):
        """_build_context should handle completely empty snapshot."""
        result = brain._build_context({})
        assert "HP:0% Mana:0%" in result
        assert "Mode:?" in result

    def test_malformed_battle_list(self, brain):
        """_build_context should handle creatures with missing fields."""
        snap = _snapshot(battle_list=[
            {"name": "Dragon", "hp": 80},
            {},  # Completely empty creature
            {"hp": 50},  # Missing name
        ])
        result = brain._build_context(snap)
        assert "Dragon" in result
        assert "?" in result  # Fallback for missing name
