"""
The nine fixed vendor-evaluation dimensions. This is the shared vocabulary:
the questionnaire assigns weights/deal-breakers over these, the extractor scores
vendors 0-10 on each, and the scorer combines them. Keep this list in sync with
the Gap agent's evidence categories.
"""

CATEGORIES = [
    {"key": "patient_safety",        "label": "Patient safety / clinical outcomes"},
    {"key": "security_breach",       "label": "Security & breach history"},
    {"key": "regulatory_compliance", "label": "Regulatory compliance (FDA / ONC / HIPAA / SOC 2)"},
    {"key": "deployment_speed",      "label": "Deployment speed / time-to-value"},
    {"key": "cost",                  "label": "Cost / total cost of ownership"},
    {"key": "integration_interop",   "label": "Integration & interoperability (EHR fit)"},
    {"key": "vendor_stability",      "label": "Vendor stability (litigation / financial)"},
    {"key": "support_service",       "label": "Support & service quality"},
    {"key": "data_transparency",     "label": "Data residency & subprocessor transparency"},
]

CATEGORY_KEYS = [c["key"] for c in CATEGORIES]
_LABELS = {c["key"]: c["label"] for c in CATEGORIES}


def category_label(key: str) -> str:
    """Human-readable label for a category key (falls back to the key itself)."""
    return _LABELS.get(key, key)
