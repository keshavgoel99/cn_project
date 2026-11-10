# AI code audit log

Project: NetArchitect, CIC-307.

AI assistance was used to write the Python project, tests and documentation. No AI API is called by the finished program. The student must review the code and be able to defend its decisions.

This log separates reproducible draft errors from observed simulator results. The QoS error came from the first implementation draft in this build. The wildcard and trunk snippets are controlled faulty AI draft samples generated for this audit and retained in `docs/audit_candidates.py`. They are not represented as earlier production incidents or separate model conversation transcripts. No packet capture or simulator result is invented.

## 1. Wildcard helper assumes every subnet is /24

Audit prompt for the controlled draft: "Draft a helper that returns the wildcard mask for a VLAN's IPv4 prefix. Check it on a /25."

Rejected AI code:

```python
def bad_wildcard(prefix):
    return "0.0.0.255"
```

**Diagnosis.** A /25 has mask 255.255.255.128 and wildcard 0.0.0.127. The constant draft ignores the prefix and allows an entire /24. This is a bitmask error with a real packet policy consequence.

**Packet-flow analysis.** Consider a source-validation ACL on VLAN 10.0.0.0/25:

```text
permit ip 10.0.0.0 0.0.0.255 any
deny ip any any
```

A packet claiming source 10.0.0.200 enters the SVI. That address is outside 10.0.0.0/25, but the incorrect wildcard ignores all eight last-octet bits. The first line permits it instead of reaching the final deny. With wildcard 0.0.0.127, bit 7 must match; .200 fails and is denied. A valid source .126 remains permitted.

**Fix.** Compute a 32-bit mask using shifts and XOR it with 0xffffffff. The production allocator uses this calculation for every prefix.

```python
mask = (0xffffffff << (32 - prefix)) & 0xffffffff
wildcard = 0xffffffff ^ mask
```

**Evidence.** `test_bad_wildcard_permits_out_of_subnet_source` evaluates both ACLs; `test_all_masks_against_independent_library` checks all prefixes against `ipaddress`. `audit_demo.py` prints the draft permit and corrected deny.

## 2. Trunk config omits its allowed VLAN list

Audit prompt for the controlled draft: "Draft the uplink config for a Staff access switch assigned to VLAN 10, with native VLAN 999. Check whether VLAN 20 could cross it."

Rejected AI code:

```text
interface TenGigabitEthernet1/1/1
 switchport mode trunk
 switchport trunk native vlan 999
 no shutdown
```

**Diagnosis.** Setting a native VLAN does not restrict tagged VLANs. An IOS trunk without an allowed list defaults to allowing all VLANs. The draft has not enforced the stated one-group-per-access-switch design.

**Packet-flow analysis.** If a VLAN 20 port or tagged frame is introduced on the access switch, the unrestricted uplink admits VLAN 20 to the distribution switch when that VLAN exists. This expands Layer 2 reach beyond the intended Staff VLAN. Whether a subsequent IP flow is permitted still depends on SVIs/ACLs; the error does not automatically bypass every Layer 3 control.

**Fix.** On both sides of every trunk, emit:

```text
 switchport trunk native vlan 999
 switchport trunk allowed vlan 10,999
 switchport nonegotiate
```

User ports remain static access ports with PortFast/BPDU Guard. The fix blocks unassigned VLAN 20 at the trunk membership check and continues to admit VLAN 10. Native VLAN 999 is unused by hosts.

**Evidence.** `test_trunk_admits_unassigned_vlan_in_draft` checks the rejected snippet and the actual generated `Admin-Staff-AS1.cfg`. For IOS confirmation, add a VLAN 20 test port in the lab and inspect `show interfaces trunk`; do not claim that external check has already been run.

## 3. Initial MAN QoS draft depends on marks nobody supplies

Development task: generate a simple QoS policy for the Metro Finance users.

The initial implementation classified only AF31:

```text
class-map match-any FINANCE
 match dscp af31
!
policy-map MAN-QOS
 class FINANCE
  bandwidth percent 30
```

**Diagnosis.** The project did not configure a trusted endpoint marking scheme or an ingress remarking policy. Ordinary Finance packets may have DSCP 0. Naming a class FINANCE does not make it recognize Finance traffic.

**Packet-flow analysis.** A Finance host sends an unmarked packet through its access switch and SVI. At the WAN egress router, DSCP 0 does not match AF31 (26), so it enters class-default and misses the intended Finance reservation. An unrelated marked packet could enter that class instead.

**Fix.** Build `FINANCE-SOURCES` from the actual VLSM Finance subnets and use `match access-group name FINANCE-SOURCES`. Attach the policy on both ends of the Metro backbone links. This makes classification depend on the assigned source network, with SVI source validation. Physical deployment still needs CIR shaping and measured QoS behaviour.

**Evidence.** `test_unmarked_finance_would_miss_draft_qos` evaluates the final source ACL and confirms the class and interface attachment. The simulator guide includes the required `show policy-map interface` counter check with DSCP 0 traffic.

## 4. Initial Metro preset omitted its optical-loss assumption

The first generated preset requested the specified 35 km Metro link without a fibre-loss field. The default ER attenuation was 0.30 dB/km, so the generated preset failed its own planning rules:

```text
PhysicalDistanceViolationError: 10GBASE-ER reach alone is insufficient:
estimated loss 11.90 dB, budget 11.1 dB leaves -0.80 dB (<1 dB reserve).
```

**Diagnosis.** The draft input treated the ER reach label as enough to make the scenario feasible. Its planning code correctly refused the link; the missing assumption was in the generated scenario definition.

**Packet-flow consequence.** If deployed without a valid optical budget, the receiver may not recover frames reliably. OSPF adjacency and ordinary IP traffic could fail before any routing or ACL decision matters. That is a physical-layer analysis, not a measured optical test on this machine.

**Correction.** Keep the rejection at 0.30 dB/km. Add an explicit attenuation input and declare 0.22 dB/km in the illustrative preset, yielding 9.10 dB estimated loss and 2.00 dB margin. This describes a conditional engineered design; it does not repair installed fibre. A real site must supply a measured/provider-approved loss value or choose different transport. `test_optical_budget_not_just_reach` checks both cases.

## Reproduce the audit

```sh
python3 audit_demo.py
python3 -m unittest tests.test_audit -v
```

The observed offline output is saved in `docs/audit-results.txt`. The checker evaluates generated ACLs and allowed VLAN sets. It does not execute IOS or measure packet timing. `docs/simulation-results-template.csv` intentionally marks external checks NOT RUN.

## Additional review findings

- A gateway must be counted in addition to requested endpoints; the 254-endpoint test prevents an undersized /24.
- The initial optical test incorrectly expected 10 km LR to pass with every loss assumption. At 0.4 dB/km plus connectors/splices, only 0.8 dB reserve remains, below this planner's 1 dB rule. The test now supplies its explicit 0.35 dB/km assumption. The engine's rejection was retained.
- A 35 km ER label alone is insufficient. Default attenuation fails; the preset's lower attenuation is an explicit assumption requiring field/provider verification.
- Global intercity links cannot be represented as one long ER span; the design uses managed transport and protected tunnels.
- Mutual routing redistribution is restricted by exact local prefixes and remote aggregates. A permanently installed local summary is not used as evidence of live LAN reachability.
- The generated /30 explanation originally said a /31 "would not fit" without stating the address model. /31 is valid for suitable point-to-point links. The explanation now explicitly states that this lab excludes /31 under its conventional network/broadcast reservation model.
