import yaml
import os
import datetime
from typing import Dict, Any, List

class HospitalProfile:
    def __init__(self, slug: str):
        self.slug = slug
        self.version = 1
        self.hospital = slug.replace('-', ' ').title()
        self.updated = ""
        self.settings = {"gap_resolution_mode": "ask"}
        self.categories = {}
        self.deal_breakers = []
        self.thresholds = {"approve": 75, "escalate": 50}
        self.rationale = ""
        self.assumptions = []

    def load(self):
        path = os.path.join(os.path.dirname(__file__), "profiles", f"{self.slug}.yaml")
        if os.path.exists(path):
            with open(path, "r") as f:
                data = yaml.safe_load(f)
                if data:
                    self.__dict__.update(data)
        return self

    def save(self):
        self.updated = datetime.datetime.now().strftime("%Y-%m-%d")
        path = os.path.join(os.path.dirname(__file__), "profiles", f"{self.slug}.yaml")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Avoid saving methods or internal states if any
        data = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        with open(path, "w") as f:
            yaml.dump(data, f, sort_keys=False)

    def add_category(self, key: str, weight: float, source: str):
        if key not in self.categories:
            self.categories[key] = {"weight": weight, "rank": len(self.categories) + 1}
        else:
            self.categories[key]["weight"] = weight
            
        self._renormalize()
        self.version += 1
        self.assumptions.append({"action": "updated_category", "category": key, "source": source, "timestamp": datetime.datetime.now().isoformat()})

    def _renormalize(self):
        total_weight = sum(c.get("weight", 0) for c in self.categories.values())
        if total_weight > 0:
            for c in self.categories.values():
                c["weight"] = round(c["weight"] / total_weight, 4)

    def to_summary(self):
        return f"{self.hospital} Profile (v{self.version}) - {len(self.categories)} categories, {len(self.deal_breakers)} deal-breakers."
