#!/usr/bin/env python3
"""
DEPRECATED — Use `nexus` CLI command or `python -m nexus_cli` instead.

This file redirects to the proper Click-based CLI in nexus_cli.py.
Kept only for backward compatibility with `python main.py` usage.
"""

from __future__ import annotations


def main():
    from nexus_cli import cli
    cli()


if __name__ == "__main__":
    main()
