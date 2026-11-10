"""Reproduce the rejected AI draft behaviours without a simulator."""
from ipaddress import IPv4Address

from docs.audit_candidates import BAD_TRUNK, bad_wildcard, trunk_accepts
from netarchitect.configs import generate_configs
from netarchitect.planner import build_plan
from netarchitect.presets import get_preset
from netarchitect.subnetting import mask_for
from netarchitect.verify import acl_decision


def main():
    wrong = bad_wildcard(25)
    correct = str(IPv4Address(0xffffffff ^ mask_for(25)))
    template = "ip access-list extended TEST\n permit ip 10.0.0.0 {} any\n deny ip any any\n!"
    for label, wildcard in [("DRAFT",wrong),("FIXED",correct)]:
        decision = acl_decision(template.format(wildcard),"TEST","10.0.0.200","10.2.0.2")
        print(f"Wildcard {label}: /25 wildcard={wildcard}; source 10.0.0.200 -> {decision}")
    campus, _, _ = generate_configs(build_plan(get_preset("campus")))
    fixed_trunk = campus["Admin-Staff-AS1.cfg"]
    print(f"Trunk DRAFT: unassigned VLAN 20 allowed={trunk_accepts(BAD_TRUNK,20)}")
    print(f"Trunk FIXED: unassigned VLAN 20 allowed={trunk_accepts(fixed_trunk,20)}")
    metro = build_plan(get_preset("metro"))
    configs, _, _ = generate_configs(metro)
    source = str(IPv4Address(metro["sites"][0]["groups"][0]["subnet"]["gateway"])+1)
    decision = acl_decision(configs["HQ-R1.cfg"],"FINANCE-SOURCES",source,"10.20.2.2")
    print("QoS DRAFT: DSCP 0 equals AF31 (26)=False; Finance packet misses class")
    print(f"QoS FIXED: unmarked Finance source {source} classifier decision={decision}")
    print("Scope: offline ACL/VLAN/classifier evaluation, not captured IOS traffic.")


if __name__ == "__main__":
    main()
