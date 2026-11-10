# Metro MAN

CIC-307 - NetArchitect generated plan

![Logical topology](topology.svg)

## Overview

450 requested endpoints across 3 sites; 10% endpoint growth reserved. Root: 10.20.0.0/16. All planned links use the assignment's 10 Gb/s media rules.

Two HQ edge routers connect 2 remote sites. Routed links keep broadcasts local; 802.1Q trunks are limited to each access switch's VLAN and unused native VLAN 999. Rapid-PVST (RSTP per VLAN) protects local L2 wiring. Independent spoke links to both hubs provide dual-homed path failover. 48-port access switches are counted from planned endpoints, with one VLAN per switch.

One administrative domain and 14 active subnets (<50) fit the assignment's single-area rule. OSPF (RFC 2328) computes shortest paths and recalculates after failure. The 50-subnet cutoff is an assignment policy, not an RFC protocol limit.

Each site's VLAN blocks are placed largest-first inside an aligned site aggregate. Site aggregates and /30 transit blocks are then placed largest-first in the root. Aggregates are reservations, not extra active subnets.

1056 of 65536 root addresses reserved (1.61%). Per-subnet utilization includes endpoint growth and the SVI gateway; root reservation also includes alignment space inside site aggregates.

## Physical media decisions

Endpoint access: Cat6a / 10GBASE-T. 80 m <= 100 m: Cat6a supports the assignment's 10GBASE-T access channel (IEEE 802.3an). The channel includes patch leads. 

In-rack links: Cat6a / 10GBASE-T. 5 m <= 100 m: Cat6a supports the assignment's 10GBASE-T access channel (IEEE 802.3an). The channel includes patch leads. 

HQ local routed uplink: Cat6a / 10GBASE-T. 50 m <= 100 m: Cat6a supports the assignment's 10GBASE-T access channel (IEEE 802.3an). The channel includes patch leads. 

HQ to Remote1: OS2 SMF / 10GBASE-ER. OS2 10GBASE-ER (1550 nm) chosen for 15000 m. Estimated loss = 15 km x 0.3 dB/km + 2 connectors x 0.5 + 4 splices x 0.1 = 5.90 dB; budget 11.1 dB leaves 5.20 dB. Minimum reserve is 1 dB. Attenuation is a planning input, not a measured result. Check actual optics, receiver overload/attenuator needs and measured loss. 

HQ to Remote2: OS2 SMF / 10GBASE-ER. OS2 10GBASE-ER (1550 nm) chosen for 35000 m. Estimated loss = 35 km x 0.22 dB/km + 2 connectors x 0.5 + 4 splices x 0.1 = 9.10 dB; budget 11.1 dB leaves 2.00 dB. Minimum reserve is 1 dB. Attenuation is a planning input, not a measured result. Check actual optics, receiver overload/attenuator needs and measured loss. 

## Site capacity and summaries

HQ: 10.20.0.0/23, 7 access switches, 250 current endpoints, 275 planned endpoints. PoE groups: none.

Remote1: 10.20.2.0/24, 3 access switches, 100 current endpoints, 110 planned endpoints. PoE groups: none.

Remote2: 10.20.3.0/24, 3 access switches, 100 current endpoints, 110 planned endpoints. PoE groups: none.

## VLAN and access policy

Each VLAN's SVI is its default gateway. The first usable IP is reserved for the gateway; endpoints start at network + 2. An inbound ACL rejects sources outside the VLAN subnet.

Isolated VLANs may ping their gateway and reach CloudVPC service subnets when present; they cannot reach other RFC 1918 destinations. Other destinations are permitted but this lab has no Internet route/NAT. ACLs are stateless, so return traffic from isolated VLANs to internal clients is also denied unless it matches the cloud exception.

Access switches carry only their assigned data VLAN and native VLAN 999 on each trunk. End host ports use PortFast and BPDU Guard. Distribution switches are the local RSTP root.

PoE access groups require a PoE+ switch model and a measured AP power budget. The planner counts Ethernet endpoints, not wireless clients behind each AP.

## MAN transport and QoS

Two separate EVPL E-Line circuits join each remote edge to two HQ routers. VLANs stay local; this is a routed design over the provider's Ethernet service.

The router's egress policy classifies Finance source subnets directly and reserves 30% of interface bandwidth during congestion. Other traffic uses the default queue. For a provider CIR below port speed, add shaping to the contracted CIR before using the policy in a physical deployment. This generated lab has no configured CIR.

At 35 km, the preset explicitly assumes 0.22 dB/km at 1550 nm. With the default 0.30 dB/km, the same ER span fails the loss test; changing this assumption requires a measured/provider loss figure, not merely a desired reach.

## Offline validation

Offline integer/IP, logical graph and generated-ACL evaluation; no IOS execution.

23/23 checks passed. See offline_checks.json for each packet ACL decision and hub-removal graph check. These results do not establish simulator interoperability, latency, or encryption counters.

## Assumptions and limits

Configurations target a lab IOS/IOS XE feature set. Match interface names and supported commands to the chosen image before pasting.

End hosts use static addresses; DHCP, DNS, Internet access and NAT are outside this lab.

One distribution switch and one router at each remote site remain single points of failure.

The MAN is a routed hub-and-spoke design carried by two independent EVPL E-Line services to different HQ edge routers. Provider EVC/VLAN mapping is external.

Sub-5 ms is a latency target, not an OSPF convergence promise. Fibre propagation RTT at 35 km is about 0.35 ms; provider queuing and equipment delays must be measured.

OS2 ER at 35 km needs a measured optical budget. If loss exceeds the stated assumption, use engineered optics or a managed service.

## Lab inventory

20 devices total. device_inventory.csv lists every device and its active ports. A demo may use one access switch/host per VLAN; the exports retain the complete endpoint-capacity inventory. See cabling.csv for exact port pairs.

Interface names are logical lab defaults: access Gi1/0/1-48 + Te1/1/1, distribution Te1/0/1-48, routers Gi1 onward. Remap names consistently for the installed simulator image. Virtual Gi labels do not represent physical 10 Gb/s transceiver compatibility.

## Active subnet allocation

| Name | Network | Gateway | Broadcast | Usable needed / capacity |
|---|---|---|---|---|
| HQ:Finance | 10.20.0.0/24 | 10.20.0.1 | 10.20.0.255 | 243 / 254 |
| HQ:Guest | 10.20.1.0/26 | 10.20.1.1 | 10.20.1.63 | 34 / 62 |
| Remote1:Finance | 10.20.2.0/25 | 10.20.2.1 | 10.20.2.127 | 89 / 126 |
| Remote1:Guest | 10.20.2.128/27 | 10.20.2.129 | 10.20.2.159 | 23 / 30 |
| Remote2:Finance | 10.20.3.0/25 | 10.20.3.1 | 10.20.3.127 | 89 / 126 |
| Remote2:Guest | 10.20.3.128/27 | 10.20.3.129 | 10.20.3.159 | 23 / 30 |
| lan:HQ-R1 | 10.20.4.16/30 | 10.20.4.17 | 10.20.4.19 | 2 / 2 |
| lan:HQ-R2 | 10.20.4.20/30 | 10.20.4.21 | 10.20.4.23 | 2 / 2 |
| lan:Remote1-R1 | 10.20.4.24/30 | 10.20.4.25 | 10.20.4.27 | 2 / 2 |
| lan:Remote2-R1 | 10.20.4.28/30 | 10.20.4.29 | 10.20.4.31 | 2 / 2 |
| backbone:HQ-R1:Remote1-R1 | 10.20.4.0/30 | 10.20.4.1 | 10.20.4.3 | 2 / 2 |
| backbone:HQ-R1:Remote2-R1 | 10.20.4.4/30 | 10.20.4.5 | 10.20.4.7 | 2 / 2 |
| backbone:HQ-R2:Remote1-R1 | 10.20.4.8/30 | 10.20.4.9 | 10.20.4.11 | 2 / 2 |
| backbone:HQ-R2:Remote2-R1 | 10.20.4.12/30 | 10.20.4.13 | 10.20.4.15 | 2 / 2 |

## Subnet calculations

HQ:Finance: 2^8 - 2 = 254 usable addresses >= 243; /25 would not fit. RFC 4632 CIDR alignment; gateway is the first usable address.

HQ:Guest: 2^6 - 2 = 62 usable addresses >= 34; /27 would not fit. RFC 4632 CIDR alignment; gateway is the first usable address.

Remote1:Finance: 2^7 - 2 = 126 usable addresses >= 89; /26 would not fit. RFC 4632 CIDR alignment; gateway is the first usable address.

Remote1:Guest: 2^5 - 2 = 30 usable addresses >= 23; /28 would not fit. RFC 4632 CIDR alignment; gateway is the first usable address.

Remote2:Finance: 2^7 - 2 = 126 usable addresses >= 89; /26 would not fit. RFC 4632 CIDR alignment; gateway is the first usable address.

Remote2:Guest: 2^5 - 2 = 30 usable addresses >= 23; /28 would not fit. RFC 4632 CIDR alignment; gateway is the first usable address.

lan:HQ-R1: 2^2 - 2 = 2 usable addresses >= 2; /31 links are excluded by this lab's conventional network/broadcast model. RFC 4632 CIDR alignment; gateway is the first usable address.

lan:HQ-R2: 2^2 - 2 = 2 usable addresses >= 2; /31 links are excluded by this lab's conventional network/broadcast model. RFC 4632 CIDR alignment; gateway is the first usable address.

lan:Remote1-R1: 2^2 - 2 = 2 usable addresses >= 2; /31 links are excluded by this lab's conventional network/broadcast model. RFC 4632 CIDR alignment; gateway is the first usable address.

lan:Remote2-R1: 2^2 - 2 = 2 usable addresses >= 2; /31 links are excluded by this lab's conventional network/broadcast model. RFC 4632 CIDR alignment; gateway is the first usable address.

backbone:HQ-R1:Remote1-R1: 2^2 - 2 = 2 usable addresses >= 2; /31 links are excluded by this lab's conventional network/broadcast model. RFC 4632 CIDR alignment; gateway is the first usable address.

backbone:HQ-R1:Remote2-R1: 2^2 - 2 = 2 usable addresses >= 2; /31 links are excluded by this lab's conventional network/broadcast model. RFC 4632 CIDR alignment; gateway is the first usable address.

backbone:HQ-R2:Remote1-R1: 2^2 - 2 = 2 usable addresses >= 2; /31 links are excluded by this lab's conventional network/broadcast model. RFC 4632 CIDR alignment; gateway is the first usable address.

backbone:HQ-R2:Remote2-R1: 2^2 - 2 = 2 usable addresses >= 2; /31 links are excluded by this lab's conventional network/broadcast model. RFC 4632 CIDR alignment; gateway is the first usable address.


## References

- [RFC 1918 - private IPv4 space](https://www.rfc-editor.org/rfc/rfc1918)
- [RFC 4632 - CIDR and aggregation](https://www.rfc-editor.org/rfc/rfc4632)
- [RFC 2328 - OSPFv2](https://www.rfc-editor.org/rfc/rfc2328)
- [RFC 4271 - BGP-4](https://www.rfc-editor.org/rfc/rfc4271)
- [RFC 4301 - IPsec architecture](https://www.rfc-editor.org/rfc/rfc4301)
- [Cisco 10GBASE SFP+ data sheet - reach and optical power](https://www.cisco.com/c/en/us/products/collateral/interfaces-modules/transceiver-modules/data_sheet_c78-455693.html)
- [Cisco IOS XE IPsec configuration guide](https://www.cisco.com/c/en/us/td/docs/routers/ios/config/17-x/sec-vpn/b-security-vpn/m_sec-cfg-vpn-ipsec-0.html)
