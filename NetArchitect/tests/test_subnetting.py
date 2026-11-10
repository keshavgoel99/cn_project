import random
import unittest
from ipaddress import IPv4Address, IPv4Network

from netarchitect.errors import AddressSpaceExhaustionError, PlanningError
from netarchitect.subnetting import allocate, mask_for, prefix_for_hosts


class SubnetTests(unittest.TestCase):
    def test_host_boundaries(self):
        for hosts, prefix in [(1,30), (2,30), (3,29), (6,29), (7,28),
                              (126,25), (127,24), (254,24), (255,23), (510,23), (511,22)]:
            with self.subTest(hosts=hosts):
                self.assertEqual(prefix_for_hosts(hosts), prefix)

    def test_all_masks_against_independent_library(self):
        for prefix in range(33):
            network = IPv4Network(f"0.0.0.0/{prefix}")
            mask = mask_for(prefix)
            self.assertEqual(str(IPv4Address(mask)), str(network.netmask))
            self.assertEqual(str(IPv4Address(0xffffffff ^ mask)), str(network.hostmask))

    def test_sort_alignment_and_broadcast(self):
        result = allocate("10.0.0.0/24", [("tiny",2), ("large",100), ("medium",40)])
        self.assertEqual([n["name"] for n in result], ["large","medium","tiny"])
        self.assertEqual([n["network"] for n in result], ["10.0.0.0/25","10.0.0.128/26","10.0.0.192/30"])
        self.assertEqual(result[1]["gateway"], "10.0.0.129")
        self.assertEqual(result[1]["broadcast"], "10.0.0.191")
        self.assertEqual(result[1]["wildcard"], "0.0.0.63")

    def test_exact_fit(self):
        rows = allocate("192.168.1.0/29", [("a",2),("b",2)])
        self.assertEqual(rows[-1]["broadcast"], "192.168.1.7")

    def test_exhaustion_and_invalid_inputs(self):
        for root, requests in [("10.0.0.0/30", [("a",3)]),
                               ("10.0.0.0/29", [("a",2),("b",2),("c",2)])]:
            with self.assertRaises(AddressSpaceExhaustionError):
                allocate(root, requests)
        for hosts in (0,-1,True,2.5,"100",2**32):
            with self.assertRaises(PlanningError):
                prefix_for_hosts(hosts)
        with self.assertRaises(PlanningError):
            allocate("10.0.0.1/24", [("a",1)])
        with self.assertRaises(PlanningError):
            allocate("10.0.0.0/24", [("a",1),("a",2)])

    def test_random_allocations_against_ipaddress(self):
        randomizer = random.Random(307)
        for _ in range(100):
            requests = [(str(i), randomizer.randint(1,500)) for i in range(20)]
            result = allocate("10.0.0.0/16", requests)
            networks = [IPv4Network(r["network"]) for r in result]
            for i, row in enumerate(result):
                network = networks[i]
                self.assertEqual(row["broadcast"], str(network.broadcast_address))
                self.assertEqual(row["wildcard"], str(network.hostmask))
                self.assertGreaterEqual(network.num_addresses-2, row["required_usable"])
                self.assertTrue(all(not network.overlaps(n) for n in networks[i+1:]))
