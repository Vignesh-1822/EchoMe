"""Load and scope a user's profile for the twin.

The profile (`profile.yaml`) is the structured source of truth about the person:
identity, facts, style, boundaries, and fact-visibility scoping. Nothing here is
hardcoded to a person — swap the file to swap whose twin it is.

Visibility is *deny-by-default*: a fact is shareable with a visitor only if its key
is explicitly listed under `visibility.public`. Anything else (including facts not
listed anywhere, and the `visibility.private` topics) is withheld from the public
view. This keeps the no-hallucination / privacy guardrail strict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PROFILE_PATH = "profile.yaml"


@dataclass(frozen=True)
class Profile:
    """A loaded, scoped profile."""

    name: str
    headline: str
    location: str
    pronouns: str
    facts: dict[str, Any]
    style: dict[str, Any]
    refuse_topics: list[str]
    disclosure: str
    public_keys: list[str] = field(default_factory=list)
    private_topics: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def public_facts(self) -> dict[str, Any]:
        """Facts a visitor may be told: only keys listed under visibility.public."""
        return {k: self.facts[k] for k in self.public_keys if k in self.facts}

    def withheld_fact_keys(self) -> list[str]:
        """Fact keys that exist but are NOT public (withheld by default)."""
        return [k for k in self.facts if k not in self.public_keys]


def load_profile(path: str | Path = DEFAULT_PROFILE_PATH) -> Profile:
    """Load `profile.yaml` into a Profile, raising a clear error if it's missing."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"No profile found at '{p}'. Copy profile.example.yaml to profile.yaml "
            "and fill in your details."
        )

    data: dict[str, Any] = yaml.safe_load(p.read_text()) or {}
    visibility = data.get("visibility", {}) or {}

    return Profile(
        name=data.get("name", ""),
        headline=data.get("headline", ""),
        location=data.get("location", ""),
        pronouns=data.get("pronouns", ""),
        facts=data.get("facts", {}) or {},
        style=data.get("style", {}) or {},
        refuse_topics=data.get("refuse_topics", []) or [],
        disclosure=data.get("disclosure", ""),
        public_keys=visibility.get("public", []) or [],
        private_topics=visibility.get("private", []) or [],
        raw=data,
    )
