"""
NEXUS — Knowledge Engine

Persistent structured knowledge discovered by PLAYING, not by reading wikis.

This is the "Open Claw" principle: the agent creates its own knowledge base
by observing the game screen, experimenting with actions, and tracking outcomes.
Works on ANY game variant (official Tibia, OT servers, Pokemon Tibia, etc.)
because it starts with ZERO hardcoded knowledge.

SQLite backend consistent with SpatialMemoryV2. Single file, zero setup,
survives agent restarts, portable between machines.

Integration with Consciousness:
    - KnowledgeEngine = structured FACTS ("Dragon has ~400 HP, is dangerous")
    - Consciousness = experiential MEMORIES ("I died 3x to Dragon near cave")
    They are complementary, not competing.
"""

from __future__ import annotations

import json
import sqlite3
import time
import structlog
from pathlib import Path
from typing import Optional

log = structlog.get_logger()


class KnowledgeEngine:
    """
    Persistent knowledge store for everything the agent discovers by playing.

    Tables:
        learned_creatures  — Creatures encountered, with HP estimates, danger level, etc.
        learned_spells     — Spells/actions discovered (words, mana cost, hotkey, etc.)
        learned_items      — Items seen (type, effect, value, where found)
        learned_locations  — Places mapped (coordinates, connections, NPCs, danger)
        learned_mechanics  — Game mechanics understood (combat, UI, economy, etc.)
        confidence_history — How confidence scores evolve over time
    """

    def __init__(self, db_path: str = "data/knowledge.db"):
        self.db_path = db_path

        # Ensure parent directory exists
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")

        self._create_tables()

        stats = self.get_learning_stats()
        log.info("knowledge.initialized",
                 db=db_path,
                 creatures=stats["creatures"],
                 spells=stats["spells"],
                 items=stats["items"],
                 locations=stats["locations"],
                 mechanics=stats["mechanics"])

    def _create_tables(self):
        """Create all knowledge tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS learned_creatures (
                name TEXT PRIMARY KEY,
                hp_estimate INTEGER DEFAULT 0,
                damage_estimate INTEGER DEFAULT 0,
                loot_items TEXT DEFAULT '[]',
                location TEXT DEFAULT '',
                danger_level TEXT DEFAULT 'unknown',
                can_kill INTEGER DEFAULT 0,
                confidence REAL DEFAULT 0.1,
                encounters INTEGER DEFAULT 0,
                kills INTEGER DEFAULT 0,
                deaths_from INTEGER DEFAULT 0,
                first_seen TEXT,
                last_seen TEXT,
                notes TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS learned_spells (
                name TEXT PRIMARY KEY,
                words TEXT DEFAULT '',
                mana_cost INTEGER DEFAULT 0,
                effect TEXT DEFAULT '',
                hotkey TEXT DEFAULT '',
                cooldown_ms INTEGER DEFAULT 0,
                confidence REAL DEFAULT 0.1,
                times_used INTEGER DEFAULT 0,
                last_used TEXT
            );

            CREATE TABLE IF NOT EXISTS learned_items (
                name TEXT PRIMARY KEY,
                item_type TEXT DEFAULT 'unknown',
                effect TEXT DEFAULT '',
                value_estimate INTEGER DEFAULT 0,
                where_found TEXT DEFAULT '',
                confidence REAL DEFAULT 0.1,
                times_seen INTEGER DEFAULT 0,
                first_seen TEXT,
                last_seen TEXT
            );

            CREATE TABLE IF NOT EXISTS learned_locations (
                name TEXT PRIMARY KEY,
                description TEXT DEFAULT '',
                coordinates TEXT DEFAULT '{}',
                connections TEXT DEFAULT '[]',
                npcs TEXT DEFAULT '[]',
                creatures TEXT DEFAULT '[]',
                danger_level TEXT DEFAULT 'unknown',
                confidence REAL DEFAULT 0.1,
                visits INTEGER DEFAULT 0,
                last_visit TEXT
            );

            CREATE TABLE IF NOT EXISTS learned_mechanics (
                name TEXT PRIMARY KEY,
                category TEXT DEFAULT 'unknown',
                description TEXT DEFAULT '',
                how_to TEXT DEFAULT '',
                confidence REAL DEFAULT 0.1,
                verified INTEGER DEFAULT 0,
                discovered TEXT
            );

            CREATE TABLE IF NOT EXISTS confidence_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                old_confidence REAL,
                new_confidence REAL,
                reason TEXT DEFAULT '',
                timestamp TEXT
            );
        """)
        self.conn.commit()

    # ═══════════════════════════════════════════════════════
    #  LEARN — Upsert with intelligent merge
    # ═══════════════════════════════════════════════════════

    def learn_creature(self, name: str, **observations) -> dict:
        """
        Learn or update knowledge about a creature.
        Re-observations boost confidence. Conflicting data uses weighted merge.
        """
        now = _now()
        existing = self.get_creature(name)

        if existing:
            # Merge observations with existing knowledge
            updates = {}
            for key, value in observations.items():
                if key in ("encounters", "kills", "deaths_from"):
                    updates[key] = existing.get(key, 0) + value
                elif key == "loot_items" and value:
                    old_loot = json.loads(existing.get("loot_items", "[]"))
                    new_items = value if isinstance(value, list) else json.loads(value)
                    merged = list(set(old_loot + new_items))
                    updates["loot_items"] = json.dumps(merged)
                elif value is not None and value != "":
                    updates[key] = value

            # Boost confidence on re-observation
            old_conf = existing.get("confidence", 0.1)
            boost = min(0.15, 0.05 * updates.get("encounters", 0) + 0.03)
            new_conf = min(1.0, old_conf + boost)
            updates["confidence"] = new_conf
            updates["last_seen"] = now

            if old_conf != new_conf:
                self._log_confidence("creature", name, old_conf, new_conf, "re-observation")

            set_clause = ", ".join(f"{k}=?" for k in updates.keys())
            values = list(updates.values()) + [name]
            self.conn.execute(
                f"UPDATE learned_creatures SET {set_clause} WHERE name=?",
                values,
            )
        else:
            # New creature
            obs = {
                "name": name,
                "hp_estimate": observations.get("hp_estimate", 0),
                "damage_estimate": observations.get("damage_estimate", 0),
                "loot_items": json.dumps(observations.get("loot_items", [])) if isinstance(observations.get("loot_items"), list) else observations.get("loot_items", "[]"),
                "location": observations.get("location", ""),
                "danger_level": observations.get("danger_level", "unknown"),
                "can_kill": 1 if observations.get("can_kill") else 0,
                "confidence": observations.get("confidence", 0.1),
                "encounters": observations.get("encounters", 1),
                "kills": observations.get("kills", 0),
                "deaths_from": observations.get("deaths_from", 0),
                "first_seen": now,
                "last_seen": now,
                "notes": json.dumps(observations.get("notes", {})) if isinstance(observations.get("notes"), dict) else observations.get("notes", "{}"),
            }
            cols = ", ".join(obs.keys())
            placeholders = ", ".join("?" for _ in obs)
            self.conn.execute(
                f"INSERT INTO learned_creatures ({cols}) VALUES ({placeholders})",
                list(obs.values()),
            )
            self._log_confidence("creature", name, 0.0, obs["confidence"], "first_observation")

        self.conn.commit()
        return self.get_creature(name)

    def learn_spell(self, name: str, **observations) -> dict:
        """Learn or update knowledge about a spell/action."""
        now = _now()
        existing = self.get_spell(name)

        if existing:
            updates = {}
            for key, value in observations.items():
                if key == "times_used":
                    updates[key] = existing.get(key, 0) + value
                elif value is not None and value != "":
                    updates[key] = value

            old_conf = existing.get("confidence", 0.1)
            new_conf = min(1.0, old_conf + 0.1)
            updates["confidence"] = new_conf
            updates["last_used"] = now

            if old_conf != new_conf:
                self._log_confidence("spell", name, old_conf, new_conf, "re-observation")

            set_clause = ", ".join(f"{k}=?" for k in updates.keys())
            values = list(updates.values()) + [name]
            self.conn.execute(f"UPDATE learned_spells SET {set_clause} WHERE name=?", values)
        else:
            obs = {
                "name": name,
                "words": observations.get("words", ""),
                "mana_cost": observations.get("mana_cost", 0),
                "effect": observations.get("effect", ""),
                "hotkey": observations.get("hotkey", ""),
                "cooldown_ms": observations.get("cooldown_ms", 0),
                "confidence": observations.get("confidence", 0.1),
                "times_used": observations.get("times_used", 0),
                "last_used": now,
            }
            cols = ", ".join(obs.keys())
            placeholders = ", ".join("?" for _ in obs)
            self.conn.execute(f"INSERT INTO learned_spells ({cols}) VALUES ({placeholders})", list(obs.values()))

        self.conn.commit()
        return self.get_spell(name)

    def learn_item(self, name: str, **observations) -> dict:
        """Learn or update knowledge about an item."""
        now = _now()
        existing = self.get_item(name)

        if existing:
            updates = {}
            for key, value in observations.items():
                if key == "times_seen":
                    updates[key] = existing.get(key, 0) + value
                elif value is not None and value != "":
                    updates[key] = value

            old_conf = existing.get("confidence", 0.1)
            new_conf = min(1.0, old_conf + 0.08)
            updates["confidence"] = new_conf
            updates["last_seen"] = now

            set_clause = ", ".join(f"{k}=?" for k in updates.keys())
            values = list(updates.values()) + [name]
            self.conn.execute(f"UPDATE learned_items SET {set_clause} WHERE name=?", values)
        else:
            obs = {
                "name": name,
                "item_type": observations.get("item_type", "unknown"),
                "effect": observations.get("effect", ""),
                "value_estimate": observations.get("value_estimate", 0),
                "where_found": observations.get("where_found", ""),
                "confidence": observations.get("confidence", 0.1),
                "times_seen": observations.get("times_seen", 1),
                "first_seen": now,
                "last_seen": now,
            }
            cols = ", ".join(obs.keys())
            placeholders = ", ".join("?" for _ in obs)
            self.conn.execute(f"INSERT INTO learned_items ({cols}) VALUES ({placeholders})", list(obs.values()))

        self.conn.commit()
        return self.get_item(name)

    def learn_location(self, name: str, **observations) -> dict:
        """Learn or update knowledge about a location."""
        now = _now()
        existing = self.get_location(name)

        if existing:
            updates = {}
            for key, value in observations.items():
                if key == "visits":
                    updates[key] = existing.get(key, 0) + value
                elif key in ("connections", "npcs", "creatures") and value:
                    # Merge lists
                    old_list = json.loads(existing.get(key, "[]"))
                    new_list = value if isinstance(value, list) else json.loads(value)
                    merged = list(set(old_list + new_list))
                    updates[key] = json.dumps(merged)
                elif value is not None and value != "":
                    updates[key] = value

            old_conf = existing.get("confidence", 0.1)
            new_conf = min(1.0, old_conf + 0.1)
            updates["confidence"] = new_conf
            updates["last_visit"] = now

            set_clause = ", ".join(f"{k}=?" for k in updates.keys())
            values = list(updates.values()) + [name]
            self.conn.execute(f"UPDATE learned_locations SET {set_clause} WHERE name=?", values)
        else:
            obs = {
                "name": name,
                "description": observations.get("description", ""),
                "coordinates": json.dumps(observations.get("coordinates", {})) if isinstance(observations.get("coordinates"), dict) else observations.get("coordinates", "{}"),
                "connections": json.dumps(observations.get("connections", [])) if isinstance(observations.get("connections"), list) else observations.get("connections", "[]"),
                "npcs": json.dumps(observations.get("npcs", [])) if isinstance(observations.get("npcs"), list) else observations.get("npcs", "[]"),
                "creatures": json.dumps(observations.get("creatures", [])) if isinstance(observations.get("creatures"), list) else observations.get("creatures", "[]"),
                "danger_level": observations.get("danger_level", "unknown"),
                "confidence": observations.get("confidence", 0.1),
                "visits": observations.get("visits", 1),
                "last_visit": now,
            }
            cols = ", ".join(obs.keys())
            placeholders = ", ".join("?" for _ in obs)
            self.conn.execute(f"INSERT INTO learned_locations ({cols}) VALUES ({placeholders})", list(obs.values()))

        self.conn.commit()
        return self.get_location(name)

    def learn_mechanic(self, name: str, **observations) -> dict:
        """Learn or update knowledge about a game mechanic."""
        now = _now()
        existing = self.get_mechanic(name)

        if existing:
            updates = {}
            for key, value in observations.items():
                if value is not None and value != "":
                    updates[key] = value

            old_conf = existing.get("confidence", 0.1)
            new_conf = min(1.0, old_conf + 0.15)
            updates["confidence"] = new_conf

            set_clause = ", ".join(f"{k}=?" for k in updates.keys())
            values = list(updates.values()) + [name]
            self.conn.execute(f"UPDATE learned_mechanics SET {set_clause} WHERE name=?", values)
        else:
            obs = {
                "name": name,
                "category": observations.get("category", "unknown"),
                "description": observations.get("description", ""),
                "how_to": observations.get("how_to", ""),
                "confidence": observations.get("confidence", 0.2),
                "verified": 1 if observations.get("verified") else 0,
                "discovered": now,
            }
            cols = ", ".join(obs.keys())
            placeholders = ", ".join("?" for _ in obs)
            self.conn.execute(f"INSERT INTO learned_mechanics ({cols}) VALUES ({placeholders})", list(obs.values()))

        self.conn.commit()
        return self.get_mechanic(name)

    # ═══════════════════════════════════════════════════════
    #  QUERY — Get knowledge back
    # ═══════════════════════════════════════════════════════

    def get_creature(self, name: str) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM learned_creatures WHERE name=?", (name,)).fetchone()
        return dict(row) if row else None

    def get_spell(self, name: str) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM learned_spells WHERE name=?", (name,)).fetchone()
        return dict(row) if row else None

    def get_item(self, name: str) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM learned_items WHERE name=?", (name,)).fetchone()
        return dict(row) if row else None

    def get_location(self, name: str) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM learned_locations WHERE name=?", (name,)).fetchone()
        return dict(row) if row else None

    def get_mechanic(self, name: str) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM learned_mechanics WHERE name=?", (name,)).fetchone()
        return dict(row) if row else None

    def get_known_creatures(self) -> list[dict]:
        """All known creatures sorted by confidence descending."""
        rows = self.conn.execute(
            "SELECT * FROM learned_creatures ORDER BY confidence DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_safe_creatures(self) -> list[dict]:
        """Creatures the agent can reliably kill (danger_level safe/moderate, can_kill=1)."""
        rows = self.conn.execute(
            "SELECT * FROM learned_creatures WHERE can_kill=1 AND danger_level IN ('safe', 'moderate') AND confidence >= 0.3 ORDER BY confidence DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_dangerous_creatures(self) -> list[dict]:
        """Creatures that are dangerous or have killed the agent."""
        rows = self.conn.execute(
            "SELECT * FROM learned_creatures WHERE danger_level IN ('dangerous', 'deadly') OR deaths_from > 0 ORDER BY deaths_from DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_known_spells(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM learned_spells ORDER BY confidence DESC").fetchall()
        return [dict(r) for r in rows]

    def get_known_items(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM learned_items ORDER BY confidence DESC").fetchall()
        return [dict(r) for r in rows]

    def get_known_locations(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM learned_locations ORDER BY confidence DESC").fetchall()
        return [dict(r) for r in rows]

    def get_nearby_knowledge(self, x: int, y: int, z: int, radius: int = 10) -> dict:
        """Get all knowledge relevant to a position."""
        # Find locations near coordinates
        locations = []
        for loc in self.get_known_locations():
            try:
                coords = json.loads(loc.get("coordinates", "{}"))
                if isinstance(coords, dict):
                    lx = coords.get("x", 0)
                    ly = coords.get("y", 0)
                    lz = coords.get("z", 0)
                    if lz == z and abs(lx - x) <= radius and abs(ly - y) <= radius:
                        locations.append(loc)
            except (json.JSONDecodeError, TypeError):
                continue

        # Aggregate creatures from nearby locations
        nearby_creatures = set()
        for loc in locations:
            try:
                creatures = json.loads(loc.get("creatures", "[]"))
                nearby_creatures.update(creatures)
            except (json.JSONDecodeError, TypeError):
                continue

        creature_details = []
        for name in nearby_creatures:
            c = self.get_creature(name)
            if c:
                creature_details.append(c)

        return {
            "locations": locations,
            "creatures": creature_details,
            "position": {"x": x, "y": y, "z": z},
        }

    # ═══════════════════════════════════════════════════════
    #  CONFIDENCE
    # ═══════════════════════════════════════════════════════

    def boost_confidence(self, entity_type: str, name: str, amount: float = 0.1, reason: str = ""):
        """Manually boost confidence for an entity."""
        table = self._table_for_type(entity_type)
        if not table:
            return

        row = self.conn.execute(f"SELECT confidence FROM {table} WHERE name=?", (name,)).fetchone()
        if not row:
            return

        old_conf = row["confidence"]
        new_conf = min(1.0, old_conf + amount)
        self.conn.execute(f"UPDATE {table} SET confidence=? WHERE name=?", (new_conf, name))
        self.conn.commit()
        self._log_confidence(entity_type, name, old_conf, new_conf, reason)

    def decay_confidence(self, max_age_days: int = 30):
        """Decay confidence for old knowledge that hasn't been re-observed."""
        cutoff = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - max_age_days * 86400))

        for table, time_col in [
            ("learned_creatures", "last_seen"),
            ("learned_spells", "last_used"),
            ("learned_items", "last_seen"),
            ("learned_locations", "last_visit"),
        ]:
            self.conn.execute(
                f"UPDATE {table} SET confidence = MAX(0.05, confidence * 0.95) WHERE {time_col} < ? AND confidence > 0.05",
                (cutoff,),
            )
        self.conn.commit()

    # ═══════════════════════════════════════════════════════
    #  STATS & EXPORT
    # ═══════════════════════════════════════════════════════

    def get_learning_stats(self) -> dict:
        """Summary statistics for TUI/dashboard display."""
        def count(table):
            return self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        def avg_conf(table):
            row = self.conn.execute(f"SELECT AVG(confidence) FROM {table}").fetchone()
            return round(row[0] or 0, 2)

        return {
            "creatures": count("learned_creatures"),
            "spells": count("learned_spells"),
            "items": count("learned_items"),
            "locations": count("learned_locations"),
            "mechanics": count("learned_mechanics"),
            "avg_confidence": {
                "creatures": avg_conf("learned_creatures"),
                "spells": avg_conf("learned_spells"),
                "items": avg_conf("learned_items"),
                "locations": avg_conf("learned_locations"),
            },
            "total_kills": self.conn.execute("SELECT COALESCE(SUM(kills), 0) FROM learned_creatures").fetchone()[0],
            "total_deaths_from": self.conn.execute("SELECT COALESCE(SUM(deaths_from), 0) FROM learned_creatures").fetchone()[0],
        }

    def get_knowledge_summary(self, max_items: int = 10) -> dict:
        """
        Compact summary for strategic brain context.
        Designed to be token-efficient in API calls.
        """
        safe = self.get_safe_creatures()[:max_items]
        dangerous = self.get_dangerous_creatures()[:5]
        spells = self.get_known_spells()[:max_items]
        locations = self.get_known_locations()[:5]

        return {
            "safe_creatures": [
                {"name": c["name"], "hp": c["hp_estimate"], "kills": c["kills"]}
                for c in safe
            ],
            "dangerous_creatures": [
                {"name": c["name"], "deaths_from": c["deaths_from"]}
                for c in dangerous
            ],
            "known_spells": [
                {"name": s["name"], "effect": s["effect"][:30], "mana": s["mana_cost"]}
                for s in spells
            ],
            "known_locations": [
                {"name": l["name"], "danger": l["danger_level"]}
                for l in locations
            ],
            "stats": self.get_learning_stats(),
        }

    def export_knowledge(self) -> dict:
        """Full dump for debug/sharing."""
        return {
            "creatures": self.get_known_creatures(),
            "spells": self.get_known_spells(),
            "items": self.get_known_items(),
            "locations": self.get_known_locations(),
            "stats": self.get_learning_stats(),
        }

    # ═══════════════════════════════════════════════════════
    #  INTERNAL
    # ═══════════════════════════════════════════════════════

    def _table_for_type(self, entity_type: str) -> Optional[str]:
        mapping = {
            "creature": "learned_creatures",
            "spell": "learned_spells",
            "item": "learned_items",
            "location": "learned_locations",
            "mechanic": "learned_mechanics",
        }
        return mapping.get(entity_type)

    def _log_confidence(self, entity_type: str, name: str, old: float, new: float, reason: str):
        self.conn.execute(
            "INSERT INTO confidence_history (entity_type, entity_name, old_confidence, new_confidence, reason, timestamp) VALUES (?,?,?,?,?,?)",
            (entity_type, name, old, new, reason, _now()),
        )

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()


def _now() -> str:
    """ISO 8601 timestamp."""
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
