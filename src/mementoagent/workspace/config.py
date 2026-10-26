"""Workspace configuration helpers (secrets are deliberately excluded)."""

from __future__ import annotations

import json
import math
import re
import tomllib
from pathlib import Path
from typing import Any

from .paths import WorkspacePaths


def load_workspace_config(root: Path | str) -> dict[str, Any]:
    """Load non-secret TOML configuration from a workspace.

    Args:
        root: Workspace root directory.

    Returns:
        Parsed configuration, or an empty mapping when no config exists.
    """
    paths = WorkspacePaths(Path(root))
    if not paths.workspace_config.exists():
        return {}
    with paths.workspace_config.open("rb") as handle:
        return tomllib.load(handle)


def _toml_value(value: Any) -> str:
    """Serialize a scalar value supported by the workspace TOML writer.

    Args:
        value: Boolean, finite number, or string to serialize.

    Returns:
        A TOML representation of the scalar.

    Raises:
        TypeError: If the value is not a supported scalar.
        ValueError: If a floating-point value is not finite.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Workspace configuration requires finite numbers")
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise TypeError(f"Unsupported TOML value: {type(value).__name__}")


def write_workspace_config(root: Path | str, config: dict[str, Any]) -> Path:
    """Write a deterministic TOML document for workspace settings.

    Args:
        root: Workspace root directory.
        config: Nested mapping of TOML tables and supported scalar values.

    Returns:
        Path to the written workspace configuration.
    """
    paths = WorkspacePaths(Path(root))
    lines: list[str] = []

    def key_name(key: str) -> str:
        """Quote a TOML key when it contains special characters."""
        return (
            key
            if re.fullmatch(r"[A-Za-z0-9_-]+", key)
            else json.dumps(key, ensure_ascii=False)
        )

    def write_table(values: dict[str, Any], prefix: tuple[str, ...]) -> None:
        """Append a table and its child tables to the output lines."""
        if prefix:
            lines.append("[" + ".".join(key_name(key) for key in prefix) + "]")
        for key in sorted(values):
            if not isinstance(values[key], dict):
                lines.append(f"{key_name(key)} = {_toml_value(values[key])}")
        for key in sorted(values):
            if isinstance(values[key], dict):
                if lines:
                    lines.append("")
                write_table(values[key], (*prefix, key))

    write_table(config, ())
    paths.memento.mkdir(parents=True, exist_ok=True)
    paths.workspace_config.write_text(
        "\n".join(lines).rstrip() + "\n", encoding="utf-8"
    )
    return paths.workspace_config
