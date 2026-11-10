import unittest
from netarchitect.media import select_media
from netarchitect.errors import PhysicalDistanceViolationError, PlanningError


class MediaTests(unittest.TestCase):
    def test_distance_boundaries(self):
        for distance, medium in [(0.1,"Cat6a"),(100,"Cat6a"),(100.01,"OM4 MMF"),
                                 (101,"OM4 MMF"),(400,"OM4 MMF"),(400.01,"OS2 SMF")]:
            with self.subTest(distance=distance):
                self.assertEqual(select_media(distance)["medium"], medium)
        self.assertEqual(select_media(10000, fiber_attenuation=0.35)["transceiver"], "10GBASE-LR")
        self.assertEqual(select_media(10001)["transceiver"], "10GBASE-ER")

    def test_explicit_copper_and_fibre_violations(self):
        for distance, medium in [(100.1,"copper"),(400.1,"om4"),(40001,"os2")]:
            with self.assertRaises(PhysicalDistanceViolationError):
                select_media(distance, medium)

    def test_optical_budget_not_just_reach(self):
        with self.assertRaisesRegex(PhysicalDistanceViolationError, "estimated loss"):
            select_media(35000, "os2")
        result = select_media(35000, "os2", fiber_attenuation=0.22)
        self.assertEqual(result["estimated_loss_db"], 9.1)
        self.assertEqual(result["margin_db"], 2.0)
        self.assertEqual(select_media(40000,"os2",0.2)["transceiver"], "10GBASE-ER")

    def test_invalid_distance(self):
        for value in [0,-1,True,"100",None,float("nan"),float("inf")]:
            with self.assertRaises(PlanningError):
                select_media(value)
        with self.assertRaises(PlanningError):
            select_media(5,"wireless")
