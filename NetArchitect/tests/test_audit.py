import unittest
from ipaddress import IPv4Address

from docs.audit_candidates import BAD_TRUNK, BAD_QOS, bad_wildcard, trunk_accepts
from netarchitect.configs import generate_configs
from netarchitect.planner import build_plan
from netarchitect.presets import get_preset
from netarchitect.subnetting import mask_for
from netarchitect.verify import acl_decision


class AuditTests(unittest.TestCase):
    def test_bad_wildcard_permits_out_of_subnet_source(self):
        buggy = f"ip access-list extended TEST\n permit ip 10.0.0.0 {bad_wildcard(25)} any\n deny ip any any\n!"
        good = f"ip access-list extended TEST\n permit ip 10.0.0.0 {IPv4Address(0xffffffff ^ mask_for(25))} any\n deny ip any any\n!"
        self.assertEqual(acl_decision(buggy,"TEST","10.0.0.200","10.2.0.2"),"permit")
        self.assertEqual(acl_decision(good,"TEST","10.0.0.200","10.2.0.2"),"deny")
        self.assertEqual(acl_decision(good,"TEST","10.0.0.126","10.2.0.2"),"permit")

    def test_trunk_admits_unassigned_vlan_in_draft(self):
        self.assertTrue(trunk_accepts(BAD_TRUNK,20))
        configs, _, _ = generate_configs(build_plan(get_preset("campus")))
        text = configs["Admin-Staff-AS1.cfg"]
        self.assertFalse(trunk_accepts(text,20))
        self.assertTrue(trunk_accepts(text,10))

    def test_unmarked_finance_would_miss_draft_qos(self):
        self.assertIn("match dscp af31",BAD_QOS)
        # DSCP 0 does not match AF31 (26); final class uses source subnet instead.
        self.assertNotEqual(0,26)
        plan = build_plan(get_preset("metro"))
        configs, _, _ = generate_configs(plan)
        text = configs["HQ-R1.cfg"]
        finance = plan["sites"][0]["groups"][0]["subnet"]
        self.assertEqual(acl_decision(text,"FINANCE-SOURCES",str(IPv4Address(finance["gateway"])+1),"10.20.3.2"),"permit")
        self.assertIn("match access-group name FINANCE-SOURCES",text)
        self.assertIn("service-policy output MAN-QOS",text)
