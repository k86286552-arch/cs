from __future__ import annotations

import os
from pathlib import Path

import yaml


def get_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists() and (parent / "config").is_dir():
            return parent
    return Path.cwd()


def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def load_yaml(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_absolute():
        p = get_project_root() / p
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}