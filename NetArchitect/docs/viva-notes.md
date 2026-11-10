# Viva notes

**Why Python and a CLI?** The assignment accepts a CLI. Python makes the arithmetic and tests readable and runs without a framework or service account.

**Is AI choosing routes when the program runs?** No. All choices come from explicit rules and supplied input. AI helped create the project; the program itself is deterministic except for freshly generated VPN keys.

**Why is a 100.1 m copper link rejected?** The policy is a 100 m channel limit. It includes patch leads. Fibre is chosen above that boundary.

**Why OM4 rather than any multimode fibre?** The 400 m SR reach depends on OM4's modal bandwidth. OM1/OM2 do not inherit that reach.

**Why not use LR for a 35 km path?** LR's reference reach is 10 km. ER has longer reach, but its loss budget still needs checking. The 35 km example only passes under its explicit attenuation assumption.

**Why does 254 hosts need /23?** Those are endpoints, and the SVI gateway needs one more usable address. /24 has only 254 usable addresses.

**How is overlap prevented?** Requests are sorted largest-first and allocated at aligned boundaries, with the cursor moved past each broadcast address. Site reservations and transit networks are disjoint. Pairwise independent checks verify the result.

**What is a wildcard mask?** It tells an ACL which bits to ignore. It is `0xffffffff XOR subnet_mask`. A /25 uses 0.0.0.127; using 0.0.0.255 admits an extra half of the /24.

**Why /30 for routed links?** It gives two usable addresses using the same network/broadcast model as the rest of the project. /31 is valid in suitable real links but is outside this lab's chosen model.

**Does RFC 2328 say OSPF supports only 49 subnets per area?** No. The <50 threshold is the assignment's design policy. OSPF's actual limits depend on resources and design.

**Why eBGP in Global?** Cities/cloud are separate routing domains. The assignment allows multi-area OSPF or eBGP. This implementation uses eBGP between domains and local OSPF inside each site.

**Why site summaries?** They reduce interdomain routes. Each site owns an aligned block; the summary does not include another site's allocations.

**Could OSPF/BGP redistribution loop?** Unrestricted mutual redistribution can. Here only local VLAN specifics enter BGP, and only remote site aggregates return to OSPF. Prefix filters restrict both directions.

**What does resilience protect?** Either HQ edge or one spoke-to-hub path can fail. Remote routers, distribution switches and shared carrier infrastructure can still fail. The graph test proves an alternate logical path, not a convergence deadline.

**What is the difference between latency and convergence?** Latency measures how long a working path takes to carry a packet. Convergence measures how long routing takes to settle after change. A sub-5 ms latency target is not a sub-5 ms failover promise.

**What happens to DSCP 0 Finance traffic?** The final Metro policy classifies its source subnet, so it still enters the Finance class. The rejected DSCP-only draft would miss it.

**What does the ACL allow?** All valid local sources may use their gateway. Isolated groups are denied other private networks, except the named CloudVPC service subnets. These are stateless ACLs; reverse traffic needs consideration too.

**Is the cloud actually deployed?** No. CloudVPC is an IOS gateway/service-network emulator. There are no cloud credentials or actual cloud resources in this project.

**What has been tested?** The Python engine, CLI exports, mask arithmetic, boundary errors, topology graph and generated ACL decisions. Actual IOS forwarding, feature support, SAs and timing must be tested using the provided simulator guide.
