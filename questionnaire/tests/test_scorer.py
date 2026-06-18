import unittest
from questionnaire.profile import HospitalProfile
from questionnaire.scorer import score_vendor, rank_vendors

class TestScorer(unittest.TestCase):
    def setUp(self):
        self.profile = HospitalProfile("test")
        self.profile.categories = {
            "a": {"weight": 0.5, "rank": 1},
            "b": {"weight": 0.5, "rank": 2}
        }
        self.profile.thresholds = {"approve": 80, "escalate": 50}
        
    def test_score_basic(self):
        extracted = {
            "scores": {
                "a": {"score": 10}, # 10/10 * 0.5 = 0.50
                "b": {"score": 8}   # 8/10 * 0.5 = 0.40
            }
        }
        res = score_vendor(self.profile, extracted)
        self.assertEqual(res["fit"], 90)
        self.assertEqual(res["verdict"], "APPROVE")
        
    def test_score_missing(self):
        extracted = {
            "scores": {
                "a": {"score": 10}
            }
        }
        res = score_vendor(self.profile, extracted)
        # b defaults to 5. 10/10*0.5 + 5/10*0.5 = 0.5 + 0.25 = 0.75
        self.assertEqual(res["fit"], 75)
        self.assertEqual(res["verdict"], "ESCALATE")

    def test_deal_breaker(self):
        self.profile.deal_breakers = [{
            "factor": "bad_thing",
            "category": "a",
            "rule": "terrible"
        }]
        extracted = {
            "scores": {
                "a": {"score": 10, "evidence": "this is terrible"}
            }
        }
        res = score_vendor(self.profile, extracted)
        # Without DB, fit is 75. But DB caps at escalate-1 = 49
        self.assertTrue(res["fit"] <= 49)
        self.assertEqual(res["verdict"], "REJECT")
        self.assertEqual(len(res["triggered_deal_breakers"]), 1)

if __name__ == "__main__":
    unittest.main()
