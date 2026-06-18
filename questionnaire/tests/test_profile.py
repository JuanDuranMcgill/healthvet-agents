import unittest
import os
from questionnaire.profile import HospitalProfile

class TestProfile(unittest.TestCase):
    def test_renormalize(self):
        p = HospitalProfile("test")
        p.add_category("a", 0.5, "test")
        self.assertEqual(p.categories["a"]["weight"], 1.0)
        
        p.add_category("b", 1.0, "test")
        # a=1.0, b=1.0 => sum 2.0 => each 0.5
        self.assertEqual(p.categories["a"]["weight"], 0.5)
        self.assertEqual(p.categories["b"]["weight"], 0.5)
        
        # Adding 'c' with weight 1.0 means total weight = 2.0
        # Renormalized: a=0.25, b=0.25, c=0.5
        p.add_category("c", 1.0, "test")
        self.assertEqual(p.categories["a"]["weight"], 0.25)
        self.assertEqual(p.categories["c"]["weight"], 0.5)
        
        self.assertEqual(p.version, 4) # 1 initial + 3 adds
        
    def test_save_load(self):
        p = HospitalProfile("save-test")
        p.rationale = "testing"
        p.save()
        
        p2 = HospitalProfile("save-test").load()
        self.assertEqual(p2.rationale, "testing")
        
        path = os.path.join(os.path.dirname(__file__), "..", "profiles", "save-test.yaml")
        if os.path.exists(path):
            os.remove(path)

if __name__ == "__main__":
    unittest.main()
