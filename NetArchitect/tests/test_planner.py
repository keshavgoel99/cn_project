import unittest
from ipaddress import IPv4Network

from netarchitect.configs import generate_configs
from netarchitect.errors import PlanningError
from netarchitect.planner import build_plan, routing_choice
from netarchitect.presets import get_preset
from netarchitect.verify import check_plan, connected


class PlannerTests(unittest.TestCase):
    def test_three_complete_presets(self):
        for name, count, protocol in [("campus",1600,"OSPF Area 0"),
                                      ("metro",450,"OSPF Area 0"),("global",2020,"eBGP")]:
            with self.subTest(preset=name):
                plan = build_plan(get_preset(name))
                self.assertEqual(plan["endpoint_count"], count)
                self.assertEqual(plan["routing"]["protocol"], protocol)
                cfgs, cables, devices = generate_configs(plan)
                self.assertEqual(len(cfgs), len(devices))
                self.assertTrue(cables)
                checks = check_plan(plan, cfgs)
                self.assertTrue(checks["passed"], checks)
                for site in plan["sites"]:
                    summary = IPv4Network(site["summary"])
                    for g in site["groups"]:
                        self.assertTrue(IPv4Network(g["subnet"]["network"]).subnet_of(summary))
                        self.assertGreaterEqual(g["subnet"]["usable_capacity"], g["planned_endpoints"]+1)
                        self.assertEqual(len(g["distribution_ports"]),g["access_switches"])

    def test_routing_cutoff(self):
        self.assertEqual(routing_choice(49)["protocol"],"OSPF Area 0")
        self.assertEqual(routing_choice(50)["protocol"],"Multi-Area OSPF")
        self.assertEqual(routing_choice(2,True)["protocol"],"eBGP")

    def test_real_multi_area_custom_plan(self):
        data = get_preset("campus")
        data["sites"] = [dict(name=f"Site{i}", distance_m=200,
            groups=[dict(name=f"Group{j}",hosts=2,vlan=j+2,isolated=False,poe=False) for j in range(16)]) for i in range(4)]
        plan = build_plan(data)
        self.assertEqual(plan["routing"]["protocol"],"Multi-Area OSPF")
        configs, _, _ = generate_configs(plan)
        for site in plan["sites"]:
            edge = configs[site["name"]+"-R1.cfg"]
            self.assertIn(f"ip ospf 1 area {site['area']}", edge)
            self.assertIn("ip ospf 1 area 0", edge)
            self.assertIn(f"area {site['area']} range ", edge)

    def test_redundancy(self):
        plan = build_plan(get_preset("metro"))
        self.assertTrue(connected(plan, "HQ-R1"))
        self.assertTrue(connected(plan, "HQ-R2"))
        campus = build_plan(get_preset("campus"))
        self.assertFalse(connected(campus, "Admin-R1"))

    def test_growth_reserves_gateway(self):
        data = get_preset("campus")
        data["growth_percent"] = 0
        data["sites"][0]["groups"][0]["hosts"] = 254
        group = build_plan(data)["sites"][0]["groups"][0]
        self.assertEqual(group["subnet"]["prefix"],23)  # 254 endpoints + gateway won't fit /24.

    def test_bad_custom_inputs(self):
        mutations = [lambda d:d.update(resilient="yes"), lambda d:d.update(growth_percent=-1),
                     lambda d:d.update(root="10.0.0.1/16"),lambda d:d.update(root="8.8.0.0/16"),
                     lambda d:d.update(sites=[]),lambda d:d.update(unknown=1),
                     lambda d:d["sites"][0]["groups"][0].update(hosts=True),
                     lambda d:d["sites"][0]["groups"][0].update(vlan=999),
                     lambda d:d["sites"][0].update(name="x\nshutdown"),
                     lambda d:d["sites"][0]["groups"][0].update(hosts=1000000),
                     lambda d:d["sites"][1].update(name="ADMIN"),
                     lambda d:d["sites"][0]["groups"][1].update(vlan=10)]
        for mutate in mutations:
            data = get_preset("campus")
            mutate(data)
            with self.assertRaises(PlanningError):
                build_plan(data)

    def test_global_does_not_use_direct_intercity_optics(self):
        plan = build_plan(get_preset("global"))
        self.assertTrue(all(m["distance_m"] <= 100 for m in plan["media"]))
        self.assertTrue(any(m.get("provider_path_m",0)>40000 for m in plan["media"]))

    def test_hq_media_request_is_checked(self):
        data = get_preset("campus")
        data["sites"][0].update(distance_m=101,medium="copper")
        with self.assertRaisesRegex(PlanningError,"100 m"):
            build_plan(data)

    def test_bgp_filters_and_ipsec_both_ends(self):
        plan = build_plan(get_preset("global"))
        configs, _, _ = generate_configs(plan)
        for link in plan["links"]:
            for node in (link["a"],link["b"]):
                text = configs[node+".cfg"]
                self.assertIn("tunnel protection ipsec profile NA-IPSEC",text)
                self.assertIn("redistribute ospf 1 match internal route-map LOCAL-TO-BGP",text)
                self.assertIn("match ip address prefix-list REMOTE-SITES",text)
                self.assertNotIn("ip route 10.",text)  # no permanent Null0 local summary.
