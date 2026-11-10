# Assignment checklist

Source: the supplied two-page CIC-307 NetArchitect specification. Submission deadline: 10 November 2026. The specification permits AI assistance and requires students to validate and defend the result.

| Requirement | Implementation / evidence |
|---|---|
| CLI, dashboard or API utility | Python CLI: `python3 -m netarchitect` |
| Three preset scenarios | `netarchitect/presets.py`; editable JSON in `examples/` |
| Custom parameters: distance, density, resiliency | Strict validation in `validation.py`; custom JSON CLI path |
| Input -> L1/L2 -> L3 -> explanations | `planner.py`, `media.py`, `subnetting.py`, `configs.py`, `exporter.py` |
| <=100 m Cat6a / 101-400 m OM4 / >400 m OS2 | `select_media()`; tests on both sides of the limits, including fractional distances |
| Explicit copper request >100 m raises named error | `PhysicalDistanceViolationError`, with attenuation message |
| Explain selected medium and optic | Distance, wavelength, reach and OS2 power calculation in each report |
| Bitwise VLSM, descending, zero overlap | Integer allocation and masks; two-stage site/VLAN reservations; independent `ipaddress` comparisons |
| Gateways, broadcasts, efficiency | `subnets.csv`, `plan.json` and report calculations |
| Single AS <50 subnets -> OSPF Area 0 | `routing_choice()`; 49/50 boundary test |
| Larger single domain -> multi-area OSPF | Separate area per site, backbone area 0, area ranges; 64-VLAN custom-input test |
| Multiple routing/cloud domains -> eBGP or multi-area | Global uses eBGP between private ASNs and OSPF within each site; the specification allows either interdomain choice |
| Campus VLANs, RSTP, PoE APs | 802.1Q trunks, Rapid-PVST, PoE+ inventory; 1,600 Ethernet endpoints |
| Metro OS2/EVPL, QoS, dual-homed failover | ER planning, independent E-Line circuit model, Finance QoS, two HQ routers |
| Metro sub-5 ms | Target analysed; no false guarantee of latency or convergence; must measure provider service |
| Global IPsec, routing and summaries | IKEv2/GRE/IPsec, eBGP per city/cloud, one aggregate per site |
| Cisco switch/router/SVI/ACL configs | `configs/*.cfg` in all three exports; device-specific lab remapping documented |
| Distance/exhaustion/wildcard tests | `tests/test_media.py`, `test_subnetting.py`; pytest and unittest compatible |
| AI audit log, >=2 flawed code examples | `ai_audit_log.md`; retained drafts and passing regression tests |
| Packet-flow audit analysis | Wildcard spoofed-source case, unauthorized trunk VLAN case and unmarked QoS case; offline evaluated; simulator procedure supplied |
| Three verification exports | `output/campus`, `output/metro`, `output/global` |
| Real simulator validation | Pending external execution; no compatible simulator or licensed IOS image was present on this machine |

The full source, tests and documentation are included. Add the student's name/roll number and actual simulator observations to the submission if the instructor requires them. Those personal details and unobserved test results are not invented here.
