"""Brand profiles: a theme plus a default generation policy, loaded from JSON."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Optional

from .core import Policy

BUILTIN_PATH = Path(__file__).with_name("profiles.json")
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True)
class Theme:
    bg: str = "#f4f6f8"
    surface: str = "#ffffff"
    border: str = "#d5dbe1"
    text: str = "#1b2430"
    muted: str = "#667085"
    accent: str = "#0f766e"
    on_accent: str = "#ffffff"
    field: str = "#f1f4f7"


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    tagline: str
    action_label: str
    theme: Theme
    policy: Policy


def _build(cls, data: dict, where: str):
    allowed = {f.name for f in fields(cls)}
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"{where}: unknown field(s) {', '.join(sorted(unknown))}")
    return cls(**data)


def _parse_profile(raw: dict) -> Profile:
    pid = raw.get("id", "")
    if not re.fullmatch(r"[a-z0-9_-]+", pid):
        raise ValueError(f"Profile id {pid!r} must be lowercase letters, digits, '-' or '_'")
    theme = _build(Theme, raw.get("theme", {}), f"profile {pid} theme")
    for key, value in vars(theme).items():
        if not _HEX.match(value):
            raise ValueError(f"profile {pid}: theme.{key} must be a #rrggbb colour, got {value!r}")
    policy = _build(Policy, raw.get("policy", {}), f"profile {pid} policy")
    policy.validate()
    return Profile(
        id=pid,
        name=raw.get("name", pid.title()),
        tagline=raw.get("tagline", ""),
        action_label=raw.get("action_label", "Generate"),
        theme=theme,
        policy=policy,
    )


def load_profiles(extra: Optional[Path] = None) -> list[Profile]:
    """Load built-in profiles, then merge an optional user file (same id = override)."""
    profiles: dict[str, Profile] = {}
    paths = [BUILTIN_PATH] + ([Path(extra)] if extra else [])
    for path in paths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for raw in data.get("profiles", []):
            prof = _parse_profile(raw)
            profiles[prof.id] = prof
    if not profiles:
        raise ValueError("No profiles found")
    return list(profiles.values())


_ACTION_NOUN = {"password": "password", "passphrase": "passphrase", "pin": "PIN", "token": "token"}


def action_for(profile: Profile, mode: str) -> str:
    """Button text: the profile's own wording on its default type, generic otherwise."""
    if mode == profile.policy.mode:
        return profile.action_label
    return f"Generate {_ACTION_NOUN[mode]}"
