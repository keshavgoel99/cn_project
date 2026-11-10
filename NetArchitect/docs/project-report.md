# NetArchitect project report

Course: CIC-307, Computer Networks mini-project.

## Problem and scope

Choosing a cable, dividing addresses and writing device configs by hand can introduce inconsistent assumptions. NetArchitect takes a small network description and produces a consistent plan with the reason for each decision. It supports the three scenarios in the assignment and custom inputs within the documented device limits.

A Python CLI was chosen because it is easy to run, test and explain during a lab demonstration. The program uses deterministic rules rather than asking an AI model to choose a design at runtime. The exported HTML is an offline report, not a web application.

## Processing flow

```text
Preset or custom JSON
        |
Input validation (types, ranges, VLANs, density, private root)
        |
Media and optical checks
        |
Site sizing -> bitwise VLSM -> VLAN and transit allocation
        |
Routing and topology selection
        |
IOS configurations + explanations + offline checks
        |
HTML / Markdown / JSON / CSV / CFG / SVG exports
```

`validation.py` rejects invalid requests before configuration generation. `subnetting.py` owns address arithmetic. `planner.py` joins site capacity, addresses, media and routing choices. `configs.py` turns the plan into individual device configs. `exporter.py` writes the human-readable report and lab files.

## Physical media

For a 10 Gb/s channel, the assignment's policy is Cat6a up to 100 m, OM4/SR above 100 m through 400 m, and OS2 above 400 m. Copper requests beyond 100 m raise the named distance exception. Fractional values are handled continuously: 100.1 m requires fibre.

SR uses an 850 nm optic. The OM4 limit involves modal dispersion as well as loss; 400 m is not a universal reach for every multimode cable or optic. OS2 selects LR at up to 10 km and ER above 10 km through 40 km, subject to its calculated budget.

The OS2 planning equation is:

```text
loss = distance_km * attenuation_db_per_km
     + 2 connectors * 0.5 dB
     + 4 splices * 0.1 dB
margin = optic_budget - loss
required margin >= 1 dB
```

The reference LR budget is 6.2 dB and ER budget is 11.1 dB, derived from minimum launch power minus receiver sensitivity for the reference modules in the Cisco data sheet. These are planning values, not a guarantee for all products sold as LR/ER. Check the exact module specification, overload threshold and installed loss.

The Metro 35 km example explicitly assumes 0.22 dB/km at 1550 nm. Its estimated loss is `35 * 0.22 + 1.4 = 9.1 dB`; the remaining ER budget is `11.1 - 9.1 = 2.0 dB`. At the default 0.30 dB/km it would lose 11.9 dB and is rejected. This distinction is deliberately visible in the input and report.

Global intercity distances exceed a direct ER span. They use a managed-WAN underlay with local 50 m Ethernet handoffs; the planner does not pretend one transceiver spans 1,400 km.

## VLSM algorithm

For each VLAN:

```text
planned_endpoints = ceil(current_endpoints * (100 + growth_percent) / 100)
required_usable = planned_endpoints + 1 gateway
find smallest h where 2^h - 2 >= required_usable
prefix = 32 - h
```

The implementation finds `h` with integer bit length. It computes subnet masks using shifts and a 32-bit mask; wildcard masks are the 32-bit inverse. Gateway is network + 1, last usable is broadcast - 1.

Requests are sorted largest-first. The allocation cursor is aligned using:

```text
size = 1 << (32 - prefix)
start = (cursor + size - 1) & ~(size - 1)
broadcast = start + size - 1
```

If broadcast exceeds the root's final address, allocation stops with `AddressSpaceExhaustionError`. No partial plan is exported. /31 and /32 are excluded because this lab uses the conventional network/broadcast model, including /30 point-to-point links.

Allocation has two levels. The root contains one aligned reservation per site and separate /30 transit networks. Each site's VLAN subnets are allocated within its reservation. This gives a real aligned site aggregate without accidentally summarizing another site's networks. Reservations are not counted again as active subnets in overlap tests.

For example, 254 endpoints with no growth need 255 usable addresses after reserving a gateway. /24 gives only 254, so /23 is required. Utilization is `required_usable / usable_capacity`; root reservation also includes spare addresses inside aligned site blocks. These two percentages describe different things.

Sorting costs O(n log n). Allocation after sorting is O(n). The independent validation checks every subnet pair for overlap, O(n^2), which is acceptable for the supported college-lab input size.

## Layer 2 and capacity

Each group has its own VLAN and dedicated 48-port access switches. The count is based on planned endpoint ports, not just current hosts. A distribution switch provides one SVI per VLAN and up to 46 access trunks, keeping two ports for routed edge uplinks.

Every trunk explicitly allows only its group's VLAN and unused native VLAN 999. End-user ports run PortFast with BPDU Guard. Rapid-PVST implements RSTP independently per VLAN, and the distribution switch has the preferred root priority. Routed backbone links do not extend a broadcast domain across sites.

PoE groups require PoE+ capable access hardware. AP model/wattage is not provided by the assignment, so total PoE watts are not fabricated. In the presets, a WiFi group's host count means Ethernet-connected AP/endpoints, not users behind one AP.

## Routing and resilience

Campus and Metro have one administrative routing domain. Below 50 active subnets they use OSPF Area 0. With 50 or more, backbone links remain in area 0 and each site's local links and VLANs use a separate area, with the site edge as ABR. The threshold comes from the assignment; RFC 2328 does not set a hard limit of 50.

The Global profile selects eBGP for separate city/cloud routing domains, as allowed by the specification. Each site has a private ASN and one LAN aggregate. Local VLANs reach the site edge through OSPF Area 0. Only exact local VLAN prefixes are redistributed into BGP; only remote site aggregates are redistributed back into OSPF. That restricts feedback between protocols. Aggregation depends on live component routes, rather than an unconditional Null0 static route.

With resilience enabled, each remote router has independent links/tunnels to two HQ edges. Metro uses higher OSPF cost for secondary paths. Global uses BGP local preference 200 for the primary path and 100 for the backup. The logical graph is tested with either hub removed. This proves the existence of another path; actual routing reconvergence must be tested on IOS.

The Metro sub-5 ms requirement is treated as a service-latency target. Light in fibre takes roughly 5 microseconds per kilometre, so a 35 km round trip has about 0.35 ms propagation delay before equipment and queueing. This calculation does not guarantee a carrier SLA or sub-5 ms failover. Finance source subnets receive a 30% egress bandwidth reservation under congestion. Real EVPL CIR shaping must be configured from the provider contract.

Global GRE carries routed IP over an IKEv2/IPsec protected path. AES-256, SHA-256 and DH group 14 are configured. MTU 1400 / MSS 1360 leave room for encapsulation. A generated lab key is shared across that export; a physical deployment should use its own credential policy.

## ACL policy and packet flow

All SVIs reject sources outside their own subnet. Isolated groups can ping their gateway and reach the Global cloud services when that site exists; other private destinations are denied. Other groups can route between sites. This is a stateless ACL, so it is not a substitute for a session-aware firewall.

A permitted intersite packet follows: endpoint -> access switch -> VLAN trunk -> distribution SVI -> site router -> backbone or encrypted tunnel -> remote router -> remote distribution SVI -> destination VLAN. The destination uses its own SVI for the return path.

An isolated guest's private-destination packet reaches its local SVI and is denied before the WAN. A spoofed source does not match the source subnet permit and reaches the final deny. These decisions are evaluated against the generated ACL text in the offline checker and audit tests.

## Validation and limits

The test suite covers media boundaries, explicit copper violations, optical budget rejection, host-prefix boundaries, wildcard masks for all 33 prefixes, exact fits, exhaustion, overlap, gateway reservation, invalid input, both routing choices, hub removal and complete CLI exports. A seeded randomized check compares 2,000 allocated subnets against Python's independent `ipaddress` implementation.

The three exports also include their own offline checks. Those checks inspect addresses, logical connectivity and ACL decisions. They do not execute Cisco IOS, measure latency or prove that encryption counters increase. No compatible simulator or licensed IOS image was installed on this machine. Follow `verification.md` for the required device-level checks and record actual results before claiming simulator validation.

The CloudVPC node is a routed cloud-gateway emulator, not a provisioned AWS/Azure/GCP environment. DHCP, DNS, NAT, actual provider provisioning and full hardware/device redundancy are outside this mini-project.

## References

- [RFC 1918: Private address allocation](https://www.rfc-editor.org/rfc/rfc1918)
- [RFC 4632: CIDR](https://www.rfc-editor.org/rfc/rfc4632)
- [RFC 2328: OSPFv2](https://www.rfc-editor.org/rfc/rfc2328)
- [RFC 4271: BGP-4](https://www.rfc-editor.org/rfc/rfc4271)
- [RFC 4301: IPsec architecture](https://www.rfc-editor.org/rfc/rfc4301)
- [Cisco SFP+ data sheet](https://www.cisco.com/c/en/us/products/collateral/interfaces-modules/transceiver-modules/data_sheet_c78-455693.html)
- [Cisco IOS XE IPsec guide](https://www.cisco.com/c/en/us/td/docs/routers/ios/config/17-x/sec-vpn/b-security-vpn/m_sec-cfg-vpn-ipsec-0.html)
