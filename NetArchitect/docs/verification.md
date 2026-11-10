# Simulator verification

## Status

The generated plans pass Python/offline checks. No Packet Tracer, GNS3/CML installation or licensed IOS image was available on the build machine. The observations below are **expected results to verify**, not measured results. Record actual observations in a copy of `simulation-results-template.csv`.

## Choose a lab platform

Campus basic VLAN/ACL/OSPF behaviour can be built in Packet Tracer using suitable multilayer switches and routers. Global needs GNS3/CML with a licensed IOS XE image supporting IKEv2, GRE, IPsec and BGP. A minimal IOSv image may not implement the selected crypto suite. Check support before building the full topology.

The configs use these logical interface names:

| Role | Generated names | Adaptation |
|---|---|---|
| Access switch | `Gi1/0/1-48`, trunk `Te1/1/1` | Map to your access ports and uplink, e.g. a 2960's Fa0/x and Gi0/1 |
| Distribution | `Te1/0/1-46` for trunks; `Te1/0/47-48` routed | Use a multilayer switch with enough interfaces; map ports consistently |
| Site router | `Gi1` to distribution; `Gi2` onward to circuits | CSR/C8000v-style logical names; map to model's Gi0/x or Gi0/0/x if needed |
| Global provider | `Gi1` through `Gi6` | Provide one routed port per edge |
| Global overlays | `Tunnel1` onward | Logical connections; do not add physical cables for them |

Virtual interface speed does not validate the 10 Gb/s physical design. The cable/optic recommendation is a separate engineering result.

Some fixed-802.1Q switches do not accept an encapsulation command, so the generator deliberately omits `switchport trunk encapsulation dot1q`. If the chosen distribution platform defaults to ISL, set dot1q before trunk mode. Check support for Rapid-PVST, MQC and `switchport nonegotiate` on the image.

## Build a preset

1. Pick one complete export folder, e.g. `output/campus/`.
2. Create all routers and distribution switches listed in `device_inventory.csv`. To keep the simulator small, use one access switch and one host per VLAN for a functional demo. This reduced demo does not prove full physical port capacity; the complete inventory is still exported.
3. Wire the devices using `cabling.csv`. In Metro, each backbone row represents a separate EVPL E-Line; direct lab cables emulate those services. In Global, cable every edge's Gi2 to the provider. Tunnel rows are logical only.
4. Start with empty configurations. Remap every interface reference consistently, including `no passive-interface`, tunnel source, descriptions and the cable sheet.
5. Paste each device's matching `.cfg` into its console. Stop and resolve rejected commands. Do not claim the config loaded successfully if IOS reports syntax/feature errors.
6. Configure a test host from each row in `host_examples.csv`. Use its static address, mask and SVI gateway. No DHCP is configured.
7. Keep at least one access port active in every test VLAN; an SVI may stay down until that VLAN has an up port/trunk.
8. Run the checks below. Save the simulator project and console evidence after recording actual results.

## Common checks

```text
show ip interface brief
show vlan brief
show interfaces trunk
show spanning-tree summary
show spanning-tree vlan 10
show ip ospf neighbor
show ip route
show access-lists
```

Expected:

- Used physical interfaces and test SVIs are up/up.
- Access trunks carry only their data VLAN and native 999. VLAN 1/other groups are not allowed.
- Rapid-PVST is enabled and each site's distribution switch is its local root.
- OSPF neighbors form on routed links, never on endpoint-facing SVIs. Use point-to-point links; neighbor count depends on hub/spoke role.
- Every host can ping its own gateway.
- Ordinary groups can ping ordinary groups at another site. Test both directions.
- Isolated guests/IoT cannot ping other private VLANs, except Global CloudVPC services. These ACLs are stateless: an internal host's ping to an isolated host also fails when its reply is denied.
- ACL counters increment on the expected permit/deny line.

## Campus example packet flow

Use the current addresses from `host_examples.csv`, since custom inputs change allocation order.

```text
Admin Staff host
 -> Admin-Staff-AS1 data VLAN 10
 -> Admin-DS SVI Vlan10 (inbound source validation)
 -> Admin-R1
 -> Teaching-R1
 -> Teaching-DS
 -> Teaching Students host
```

Expected: successful ICMP in both directions. OSPF-learned subnets should appear on the distribution switches. Students should not share a Layer 2 broadcast domain with the Admin VLAN even if both use VLAN ID 10.

## Metro failover and QoS

```text
show ip ospf neighbor
show ip route <remote-host-ip>
show policy-map interface
```

1. Confirm an ordinary Finance-to-Finance ping across sites succeeds. Record the primary next hop.
2. Shut a primary backbone interface on `HQ-R1`, or stop that router completely.
3. Repeat route lookup and ping. The route should move to the path through `HQ-R2`; record packet loss and actual convergence time. Do not label convergence as sub-5 ms.
4. Restore it with `no shutdown` and verify the lower-cost primary route returns.
5. Send Finance traffic with DSCP 0. Its source-subnet match should increment the FINANCE class counter. Send Guest traffic and verify it uses class-default.
6. For a real EVPL service, apply shaping at the contracted CIR and measure latency under load. The generated lab policy reserves 30% of interface bandwidth under congestion; it does not enforce an external carrier SLA.

The exported logical graph remains connected after either hub is removed. A shared remote router/distribution switch, site outage or shared carrier failure is not protected by this topology.

## Global VPN and routing

```text
show ip route 198.18.0.10
ping 198.18.0.10 source GigabitEthernet2
show crypto ikev2 sa
show crypto ipsec sa
show interfaces tunnel 1
show ip bgp summary
show ip bgp
show ip route bgp
show ip ospf database external
```

1. Verify provider-connected underlay IPs before troubleshooting the overlay. `198.18.0.0/15` is lab benchmarking space, not Internet addressing.
2. Generate ordinary intersite traffic to start IKE/IPsec negotiation. Peers must use the same key from the same export.
3. Expect IKEv2 established SAs and growing IPsec encapsulation/decapsulation counters on both ends.
4. Expect established eBGP neighbors on tunnel /30s. Only the aligned site LAN aggregates should cross BGP; the underlay and individual VLANs should not leak.
5. Check remote LAN aggregates appear as external OSPF routes on each distribution switch.
6. Ping a CloudVPC service host from an IoT host: expected permit. Ping a remote Scanner/private host from that IoT host: expected deny.
7. Stop `Delhi-R1`. The lower-preference path through `Delhi-R2` should remain; BGP's 3/9-second timers mean a silent failure may take about 9 seconds plus routing convergence. Verify both forward and return paths.
8. Test maximum packet size/DF pings against the 1400 tunnel MTU. A small ping alone does not prove MTU correctness.
9. Capture on a provider link: encrypted data should appear as ESP (or UDP 4500 if NAT-T applies), rather than clear inner LAN packets. The simulated provider has no NAT.

## Boundary demonstrations

Use a copied custom JSON, not the original preset files:

- Force `medium` to `copper` on a 101 m link: error with `PhysicalDistanceViolationError`.
- Change the Campus root to `10.0.0.0/29`: `AddressSpaceExhaustionError` and no new output.
- Use 254 endpoints with zero growth: verify /23 allocation for the VLAN after the gateway is added.
- Change the Metro 35 km attenuation to 0.30: optical budget rejection.

## Evidence to submit after the lab run

Save the actual `.pkt` or `.gns3` project, command output/screenshots for VLANs/OSPF/BGP/IPsec, a positive and negative ACL flow, a hub failure, and the filled results CSV. The repository's exports are configuration inputs and offline evidence, not a substitute for observations from IOS.
