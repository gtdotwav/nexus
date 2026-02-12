"""
NEXUS — Vision Utilities

Shared helpers for converting game frames to Claude Vision API format.
Used by both the vision loop (Haiku, passive observation) and
strategic brain (Sonnet, important decisions).
"""

from __future__ import annotations

import base64
import cv2
import numpy as np
from typing import Optional


def frame_to_base64(
    frame: np.ndarray,
    quality: int = 70,
    max_width: int = 768,
) -> str:
    """
    Compress a BGR numpy frame to JPEG base64 for Claude Vision API.

    Args:
        frame: BGR numpy array from screen capture
        quality: JPEG quality (0-100). Lower = smaller, cheaper API calls
        max_width: Maximum width in pixels. Frame is downscaled if wider.

    Returns:
        Base64-encoded JPEG string ready for API content blocks.

    Cost note:
        768px JPEG q60 ≈ 40-60KB ≈ ~$0.001/call with Haiku
    """
    if frame is None:
        return ""

    h, w = frame.shape[:2]

    # Downscale if wider than max_width
    if w > max_width:
        scale = max_width / w
        new_w = max_width
        new_h = int(h * scale)
        frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # Encode as JPEG
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    success, jpg_buffer = cv2.imencode(".jpg", frame, encode_params)

    if not success:
        return ""

    return base64.b64encode(jpg_buffer.tobytes()).decode("ascii")


def build_vision_message(b64_image: str, prompt: str) -> list[dict]:
    """
    Build a multimodal message content array for Claude Vision API.

    Args:
        b64_image: Base64-encoded JPEG from frame_to_base64()
        prompt: Text prompt to send alongside the image

    Returns:
        List of content blocks for messages.create() content parameter.

    Usage:
        content = build_vision_message(b64, "What creatures do you see?")
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            messages=[{"role": "user", "content": content}],
        )
    """
    return [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": b64_image,
            },
        },
        {
            "type": "text",
            "text": prompt,
        },
    ]
