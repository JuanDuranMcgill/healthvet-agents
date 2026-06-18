"""
HospitalProfile: the quantified scoring model for one hospital.

A profile is stored as YAML under questionnaire/profiles/<slug>.yaml. It holds
the category weights, deal-breakers, verdict thresholds, the gap-resolution mode,
and an append-only log of assumptions added by the gap loop.
"""
from __future__ import annotations

import dataclasses
import pathlib
import re
from typing import Any

import yaml

from .categories import CATEGORY_KEYS, category_label

PROFILES_DIR = pathlib.Path(__file__).parent / "profiles"
VALID_MODES = ("ask", "auto")


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "hospital"


@dataclasses.dataclass
class HospitalProfile:
    hospital: str
    slug: str
    categories: dict[str, dict]               # key -> {weight, rank, source?}
    thresholds: dict[str, int]                # {approve, escalate}
    deal_breakers: list[dict] = dataclasses.field(default_factory=list)
    settings: dict[str, Any] = dataclasses.field(default_factory=lambda: {"gap_resolution_mode": "ask"})
    rationale: str = ""
    assumptions: list[dict] = dataclasses.field(default_factory=list)
    version: int = 1
    updated: str = ""

    # ---- construction ----
    @classmethod
    def from_fields(cls, hospital: str, fields: dict, *, rationale: str = "",
                    mode: str = "ask", updated: str = "") -> "HospitalProfile":
        return cls(
            hospital=hospital,
            slug=slugify(hospital),
            categories=fields["categories"],
            thresholds=fields["thresholds"],
            deal_breakers=fields.get("deal_breakers", []),
            settings={"gap_resolution_mode": mode},
            rationale=rationale,
            updated=updated,
        )

    # ---- persistence ----
    @classmethod
    def load(cls, slug: str, profiles_dir: pathlib.Path | None = None) -> "HospitalProfile":
        path = (profiles_dir or PROFILES_DIR) / f"{slug}.yaml"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def save(self, profiles_dir: pathlib.Path | None = None, updated: str | None = None) -> pathlib.Path:
        d = profiles_dir or PROFILES_DIR
        d.mkdir(parents=True, exist_ok=True)
        if updated is not None:
            self.updated = updated
        path = d / f"{self.slug}.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(dataclasses.asdict(self), f, sort_keys=False, allow_unicode=True)
        return path

    # ---- accessors ----
    @property
    def mode(self) -> str:
        return self.settings.get("gap_resolution_mode", "ask")

    def weight(self, key: str) -> float:
        return self.categories.get(key, {}).get("weight", 0.0)

    # ---- mutation (used by the gap loop / edits) ----
    def _renormalize(self) -> None:
        total = sum(c["weight"] for c in self.categories.values())
        if total <= 0:
            return
        for c in self.categories.values():
            c["weight"] = round(c["weight"] / total, 4)

    def add_category(self, key: str, weight: float, *, source: str,
                     label: str | None = None, assumed: bool = False) -> None:
        """
        Add (or bump) a category discovered by the gap loop, renormalize all
        weights, bump version, and log it in `assumptions`.

        `source` is free text (e.g. "gap:ask" or "gap:auto"); `assumed=True`
        marks an autonomous best-guess that must be disclosed to the hospital.
        """
        self.categories[key] = {
            "weight": float(weight),
            "rank": len(self.categories) + 1,
            "source": source,
        }
        self._renormalize()
        self.version += 1
        self.assumptions.append({
            "factor": key,
            "label": label or category_label(key),
            "weight": self.categories[key]["weight"],
            "source": source,
            "assumed": assumed,
        })

    # ---- display ----
    def to_summary(self) -> str:
        lines = [f"Profile: {self.hospital} (v{self.version}, mode={self.mode})"]
        for key, c in sorted(self.categories.items(), key=lambda kv: -kv[1]["weight"]):
            lines.append(f"  {category_label(key):<48} weight {c['weight']:.3f}")
        if self.deal_breakers:
            lines.append("  Deal-breakers: " + ", ".join(d["factor"] for d in self.deal_breakers))
        lines.append(f"  Thresholds: approve>={self.thresholds['approve']} escalate>={self.thresholds['escalate']}")
        return "\n".join(lines)


def list_profiles(profiles_dir: pathlib.Path | None = None) -> list[str]:
    d = profiles_dir or PROFILES_DIR
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.yaml"))


def known_category(key: str) -> bool:
    return key in CATEGORY_KEYS
