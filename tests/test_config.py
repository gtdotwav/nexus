"""
NEXUS — Config validation tests.

Validates: defaults, validation errors, YAML loading, and backward compatibility.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.config import NexusConfig, load_config, config_to_dict


class TestConfigDefaults:

    def test_default_config_is_valid(self):
        """Config with all defaults should pass validation."""
        config = NexusConfig()
        assert config.agent.name == "NEXUS"
        assert config.ai.max_tokens == 1024
        assert config.reactive.tick_rate_ms == 25

    def test_config_from_partial_dict(self):
        """Only override what you need, rest uses defaults."""
        config = NexusConfig(agent={"character_name": "TestChar", "game": "tibia"})
        assert config.agent.character_name == "TestChar"
        assert config.ai.temperature == 0.3  # Default preserved

    def test_unknown_keys_ignored(self):
        """Extra keys in YAML should be silently ignored (forward-compatible)."""
        config = NexusConfig(
            agent={"name": "NEXUS"},
            future_feature={"setting": "value"},  # Unknown top-level key
        )
        assert config.agent.name == "NEXUS"


class TestConfigValidation:

    def test_invalid_log_level(self):
        """Invalid log level should raise."""
        with pytest.raises(ValidationError, match="log_level"):
            NexusConfig(agent={"log_level": "SUPER_DEBUG"})

    def test_temperature_out_of_range(self):
        """Temperature > 1.0 should raise."""
        with pytest.raises(ValidationError):
            NexusConfig(ai={"temperature": 2.5})

    def test_negative_tick_rate(self):
        """Negative tick rate should raise."""
        with pytest.raises(ValidationError):
            NexusConfig(reactive={"tick_rate_ms": -1})

    def test_port_out_of_range(self):
        """Port below 1024 should raise."""
        with pytest.raises(ValidationError):
            NexusConfig(dashboard={"port": 80})

    def test_max_tokens_too_high(self):
        """max_tokens > 8192 should raise."""
        with pytest.raises(ValidationError):
            NexusConfig(ai={"max_tokens": 100000})


class TestConfigLoader:

    def test_load_nonexistent_file(self):
        """Missing file should return defaults, not crash."""
        config = load_config("/nonexistent/path/settings.yaml")
        assert config.agent.name == "NEXUS"

    def test_config_to_dict_roundtrip(self):
        """config_to_dict should produce a serializable dict."""
        config = NexusConfig(agent={"character_name": "Roundtrip"})
        d = config_to_dict(config)
        assert d["agent"]["character_name"] == "Roundtrip"
        assert isinstance(d["ai"]["max_tokens"], int)
