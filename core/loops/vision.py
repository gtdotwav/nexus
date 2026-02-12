"""
NEXUS — Vision Loop (Loop #10)

The agent's EYES connected to INTELLIGENCE. Sends game screenshots to
Claude Vision (Haiku) for scene understanding and knowledge extraction.

This is the core of the Zero-Knowledge Learning System:
    1. Capture screenshot from screen_capture.last_frame
    2. Compress to 768px JPEG (~50KB)
    3. Send to Claude Haiku with structured prompt
    4. Parse JSON response
    5. Route observations to Knowledge Engine

Cost: ~$0.30/hr at 5-second intervals with Haiku.
The agent learns by SEEING, not by reading wikis.

Frequency: configurable via config.vision.cycle_seconds (default 5s)
Model: claude-haiku (cheap + fast enough for passive observation)
"""

from __future__ import annotations

import asyncio
import json
import time
import structlog
from typing import TYPE_CHECKING

from brain.vision_utils import frame_to_base64, build_vision_message

if TYPE_CHECKING:
    from core.agent import NexusAgent

log = structlog.get_logger()

# ═══════════════════════════════════════════════════════
#  VISION PROMPT
# ═══════════════════════════════════════════════════════

VISION_PROMPT = """You are NEXUS, an autonomous gaming agent observing a game screen.
You have NO prior knowledge of this game. Everything you report must come from what you SEE.

Analyze this screenshot and report ALL observations in strict JSON:

{
    "scene_type": "combat|town|dialogue|tutorial|death|loading|inventory|map|unknown",
    "creatures": [
        {"name": "visible name", "hp_pct": 0-100, "distance": "close|medium|far", "threatening": true}
    ],
    "npcs": [
        {"name": "visible name", "interaction": "talk|trade|quest|unknown"}
    ],
    "items_ground": [
        {"name": "description of item"}
    ],
    "location": {
        "type": "town|dungeon|surface|underground|building|unknown",
        "description": "brief description of the area"
    },
    "chat_messages": ["any visible text in chat area"],
    "tutorials": ["any tutorial text, popup instructions, or hints visible"],
    "player_status": {
        "hp_pct": 0-100,
        "mana_pct": 0-100,
        "condition": "normal|poisoned|burning|electrified|cursed|unknown"
    },
    "ui_elements": ["list any UI elements you can identify: minimap, inventory, spells, etc."],
    "suggested_action": {
        "action": "what the agent should do next",
        "reason": "why this action makes sense",
        "priority": "urgent|normal|low"
    },
    "new_knowledge": [
        {
            "type": "creature|spell|item|location|mechanic",
            "name": "what was learned",
            "details": {"key": "value pairs of what was discovered"}
        }
    ]
}

CRITICAL RULES:
- Only report what you can ACTUALLY SEE in the screenshot
- If you can't read text clearly, say "unclear" not a guess
- HP/mana bars: estimate percentage from the bar fill level
- Creatures: report their visible name and health bar color (green=high, red=low)
- If this looks like a tutorial or first-time experience, capture ALL instructions
- Report ANY text visible on screen — it could be important game mechanics
- If the screen is loading or transitioning, just report scene_type as "loading"
"""

# ═══════════════════════════════════════════════════════
#  VISION LOOP
# ═══════════════════════════════════════════════════════

async def run(agent: "NexusAgent") -> None:
    """
    Vision loop — 10th async loop. Sends screenshots to Claude Vision.

    Follows the standard loop pattern: async def run(agent) -> None
    Registered in core/loops/__init__.py.
    """
    # Get config
    vision_config = agent.config.get("vision", {})
    enabled = vision_config.get("enabled", True)
    cycle_seconds = vision_config.get("cycle_seconds", 5)
    model = vision_config.get("model", "claude-haiku-4-5-20251001")
    max_width = vision_config.get("max_width", 768)
    jpeg_quality = vision_config.get("jpeg_quality", 60)

    if not enabled:
        log.info("vision_loop.disabled")
        return

    # Check if knowledge engine is available
    if not hasattr(agent, "knowledge") or agent.knowledge is None:
        log.warning("vision_loop.no_knowledge_engine",
                    msg="Knowledge engine not initialized, vision loop disabled")
        return

    # Ensure strategic brain client is ready (we share it)
    if not await agent.strategic_brain._ensure_client():
        log.warning("vision_loop.no_api_client",
                    msg="No Anthropic API client available, vision loop disabled")
        return

    log.info("vision_loop.started",
             cycle_s=cycle_seconds, model=model,
             max_width=max_width, quality=jpeg_quality)

    # Stats
    calls = 0
    errors = 0
    total_latency_ms = 0.0
    last_scene_type = "unknown"

    # Initial delay — let other loops stabilize first
    await asyncio.sleep(3.0)

    while agent.running:
        try:
            # 1. Get latest frame
            frame = getattr(agent.screen_capture, "last_frame", None)
            if frame is None:
                await asyncio.sleep(cycle_seconds)
                continue

            # 2. Compress frame
            b64 = frame_to_base64(frame, quality=jpeg_quality, max_width=max_width)
            if not b64:
                await asyncio.sleep(cycle_seconds)
                continue

            # 3. Build vision message
            content = build_vision_message(b64, VISION_PROMPT)

            # 4. Call Claude Vision (reuse strategic brain's client)
            start = time.perf_counter()

            try:
                response = await agent.strategic_brain._call_api_with_retry(
                    model=model,
                    max_tokens=1024,
                    temperature=0.1,  # Low temp for consistent observation
                    messages=[{"role": "user", "content": content}],
                )
            except Exception as api_err:
                errors += 1
                log.warning("vision_loop.api_error", error=str(api_err)[:100])
                await asyncio.sleep(cycle_seconds)
                continue

            latency_ms = (time.perf_counter() - start) * 1000
            total_latency_ms += latency_ms
            calls += 1

            if response is None or not response.content:
                errors += 1
                await asyncio.sleep(cycle_seconds)
                continue

            # 5. Parse response — safe access to content[0]
            first_block = response.content[0] if response.content else None
            if not first_block or not hasattr(first_block, "text"):
                errors += 1
                log.warning("vision_loop.invalid_response_format",
                            content_type=type(first_block).__name__ if first_block else "None")
                await asyncio.sleep(cycle_seconds)
                continue

            text = first_block.text
            scene = _parse_vision_response(text)

            if not scene:
                errors += 1
                await asyncio.sleep(cycle_seconds)
                continue

            last_scene_type = scene.get("scene_type", "unknown")

            # 6. Route observations to Knowledge Engine
            await _process_scene(agent, scene)

            # Log progress
            if calls % 10 == 0:
                avg_latency = total_latency_ms / max(1, calls)
                stats = agent.knowledge.get_learning_stats()
                log.info("vision_loop.progress",
                         calls=calls, errors=errors,
                         avg_latency_ms=round(avg_latency),
                         scene=last_scene_type,
                         known_creatures=stats["creatures"],
                         known_spells=stats["spells"],
                         known_items=stats["items"])

        except asyncio.CancelledError:
            raise
        except Exception as e:
            errors += 1
            log.error("vision_loop.error", error=str(e), type=type(e).__name__)

        await asyncio.sleep(cycle_seconds)

    log.info("vision_loop.stopped", total_calls=calls, total_errors=errors)


# ═══════════════════════════════════════════════════════
#  SCENE PROCESSING
# ═══════════════════════════════════════════════════════

async def _process_scene(agent: "NexusAgent", scene: dict):
    """Route vision observations to the Knowledge Engine."""
    knowledge = agent.knowledge

    # Learn about creatures
    for creature in scene.get("creatures", []):
        name = creature.get("name", "").strip()
        if not name or name.lower() in ("unclear", "unknown", ""):
            continue

        threatening = creature.get("threatening", False)
        danger = "dangerous" if threatening else "moderate"

        knowledge.learn_creature(
            name,
            encounters=1,
            danger_level=danger,
        )

    # Learn about NPCs
    for npc in scene.get("npcs", []):
        name = npc.get("name", "").strip()
        if not name or name.lower() in ("unclear", "unknown", ""):
            continue

        knowledge.learn_mechanic(
            f"npc_{name}",
            category="social",
            description=f"NPC named {name}, interaction: {npc.get('interaction', 'unknown')}",
        )

    # Learn about items
    for item in scene.get("items_ground", []):
        name = item.get("name", "").strip()
        if not name or name.lower() in ("unclear", "unknown", ""):
            continue

        knowledge.learn_item(
            name,
            times_seen=1,
            item_type="ground_loot",
        )

    # Learn about location
    location = scene.get("location", {})
    loc_type = location.get("type", "unknown")
    loc_desc = location.get("description", "")
    if loc_desc and loc_desc.lower() != "unknown":
        # Use description as location name (deduplicate similar descriptions)
        loc_name = loc_desc[:50].strip()
        knowledge.learn_location(
            loc_name,
            description=loc_desc,
            danger_level="unknown",
            visits=1,
        )

    # Learn from tutorials — HIGH VALUE
    for tutorial in scene.get("tutorials", []):
        if tutorial and tutorial.lower() not in ("unclear", "unknown", ""):
            knowledge.learn_mechanic(
                f"tutorial_{hash(tutorial) % 10000}",
                category="tutorial",
                description=tutorial[:200],
                how_to=tutorial[:200],
                confidence=0.5,  # Tutorials are high-confidence knowledge
            )

    # Process explicit new_knowledge entries
    for entry in scene.get("new_knowledge", []):
        ktype = entry.get("type", "")
        kname = entry.get("name", "").strip()
        details = entry.get("details", {})

        if not kname or kname.lower() in ("unclear", "unknown", ""):
            continue

        if ktype == "creature":
            knowledge.learn_creature(kname, **details)
        elif ktype == "spell":
            knowledge.learn_spell(kname, **details)
        elif ktype == "item":
            knowledge.learn_item(kname, **details)
        elif ktype == "location":
            knowledge.learn_location(kname, **details)
        elif ktype == "mechanic":
            knowledge.learn_mechanic(kname, **details)

    # Check if we should auto-generate a skill
    await _check_auto_skill_generation(agent)


async def _check_auto_skill_generation(agent: "NexusAgent"):
    """
    Check if we have enough knowledge to auto-generate a hunting skill.
    Triggered when: agent is exploring + has enough safe creatures + locations.
    """
    from core.state import AgentMode

    # Guard: skill engine must be ready
    if not hasattr(agent, "skill_engine") or agent.skill_engine is None:
        return

    # Only auto-generate if we're in EXPLORING mode with no active skill
    if agent.state.mode != AgentMode.EXPLORING:
        return

    if getattr(agent.skill_engine, "active_skill", None) is not None:
        return

    threshold = agent.config.get("knowledge", {}).get("auto_skill_threshold", 3)
    safe_creatures = agent.knowledge.get_safe_creatures()

    if len(safe_creatures) >= threshold:
        log.info("vision_loop.auto_skill_trigger",
                 safe_creatures=len(safe_creatures),
                 threshold=threshold,
                 msg="Enough knowledge to generate a skill!")

        try:
            skill = await agent.skill_engine.auto_generate_from_knowledge(agent.knowledge)
            if skill:
                agent._activate_skill(skill)
                agent.state.set_mode(AgentMode.HUNTING)
                log.info("vision_loop.auto_skill_created",
                         skill=skill.name,
                         targets=len(skill.targeting))

                if hasattr(agent, "consciousness"):
                    agent.consciousness.remember(
                        "strategy",
                        f"Auto-generated hunting skill '{skill.name}' from {len(safe_creatures)} known creatures",
                        importance=0.8,
                        tags=["zero_knowledge", "auto_skill", "milestone"],
                    )
        except Exception as e:
            log.error("vision_loop.auto_skill_error", error=str(e))


# ═══════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════

def _parse_vision_response(text: str) -> dict:
    """Parse JSON response from Claude Vision, handling markdown fences."""
    text = text.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()
    if text.startswith("json"):
        text = text[4:].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        log.warning("vision_loop.json_parse_fail",
                    error=str(e),
                    response_len=len(text),
                    head=text[:200],
                    tail=text[-100:] if len(text) > 200 else "")
        return {}
