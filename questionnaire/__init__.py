"""
Questionnaire & vendor-fit scoring for HealthVet Agents.

Turns a hospital's qualitative values into a weighted scoring model
(a HospitalProfile), then scores/ranks vendors against it from the agents'
findings. See docs/superpowers/specs/2026-06-17-questionnaire-vendor-fit-scoring-design.md
"""
from .categories import CATEGORIES, CATEGORY_KEYS, category_label
from .profile import HospitalProfile

__all__ = ["CATEGORIES", "CATEGORY_KEYS", "category_label", "HospitalProfile"]
