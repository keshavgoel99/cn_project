"""Offline checks of generated plans and ACL packet decisions.

These checks do not run IOS or simulate packet timing.
"""
from ipaddress import IPv4Address, IPv4Network


def acl_decision(config, acl_name, source, destination, protocol="ip", icmp_type="echo"):
    """Evaluate the small extended-ACL grammar emitted by this project."""
    active = False
    src, dst = int(IPv4Address(source)), int(IPv4Address(destination))

    def operand(tokens, offset, ip):
        token = tokens[offset]
        if token == "any":
            return True, offset + 1
        if token == "host":
            return ip == int(IPv4Address(tokens[offset+1])), offset + 2
        base, wildcard = int(IPv4Address(token)), int(IPv4Address(tokens[offset+1]))
        mask = 0xffffffff ^ wildcard
        return (ip & mask) == (base & mask), offset + 2

    for line in config.splitlines():
        if line == f"ip access-list extended {acl_name}":
            active = True
            continue
        if not active:
            continue
        if not line.startswith(" "):
            break
        tokens = line.split()
        if not tokens or tokens[0] not in ("permit", "deny"):
            continue
        smatch, offset = operand(tokens, 2, src)
        dmatch, offset = operand(tokens, offset, dst)
        pmatch = tokens[1] == "ip" or tokens[1] == protocol
        if tokens[1] == "icmp" and len(tokens) > offset:
            pmatch = pmatch and tokens[offset] == icmp_type
        if smatch and dmatch and pmatch:
            return tokens[0]
    return "deny"


def connected(plan, removed=None):
    graph = {}
    def join(a, b):
        if removed in (a, b):
            return
        graph.setdefault(a, set()).add(b)
        graph.setdefault(b, set()).add(a)
    for edge in plan["edges"]:
        join(edge["site"]+"-DS", edge["name"])
    for link in plan["links"]:
        join(link["a"], link["b"])
    start = plan["sites"][0]["name"]+"-DS"
    visited, pending = set(), [start]
    while pending:
        node = pending.pop()
        if node not in visited:
            visited.add(node)
            pending.extend(graph.get(node, set()) - visited)
    return all(s["name"]+"-DS" in visited for s in plan["sites"])


def check_plan(plan, configs):
    checks = []
    def record(name, passed, detail):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})
    networks = [IPv4Network(a["network"]) for a in plan["allocations"]]
    root = IPv4Network(plan["root"])
    record("non_overlapping_subnets", all(not a.overlaps(b) for i, a in enumerate(networks) for b in networks[i+1:]),
           "Pairwise comparison of active VLAN, LAN transit and backbone/tunnel subnets.")
    record("inside_root", all(n.subnet_of(root) for n in networks), "Every active private subnet belongs to the input root.")
    record("normal_connectivity", connected(plan), "Logical topology graph reaches every distribution switch.")
    if plan["input"]["resilient"]:
        for edge in plan["edges"]:
            if edge["site_index"] == 0:
                record("hub_failure:"+edge["name"], connected(plan, edge["name"]),
                       "Logical alternate path remains after removing this hub. Convergence time is not modelled.")
    for site in plan["sites"]:
        config = configs[site["name"]+"-DS.cfg"]
        for group in site["groups"]:
            subnet = group["subnet"]
            n = IPv4Network(subnet["network"])
            source = str(n.network_address + 2)
            acl = f"VLAN-{group['vlan']}-IN"
            record(f"gateway:{site['name']}:{group['name']}",
                   acl_decision(config, acl, source, subnet["gateway"], "icmp") == "permit",
                   f"ICMP {source} -> {subnet['gateway']} permitted by the inbound SVI ACL.")
            other = next(s for s in plan["sites"] if s["name"] != site["name"] and s["name"] != "CloudVPC")
            dest = str(IPv4Network(other["groups"][0]["subnet"]["network"]).network_address + 2)
            wanted = "deny" if group["isolated"] else "permit"
            record(f"intersite_acl:{site['name']}:{group['name']}",
                   acl_decision(config, acl, source, dest, "icmp") == wanted,
                   f"ICMP {source} -> {dest}: expected {wanted}. This is an ACL check, not an end-to-end ping.")
            record(f"spoofed_source:{site['name']}:{group['name']}",
                   acl_decision(config, acl, "203.0.113.9", dest) == "deny",
                   "Source outside the VLAN subnet must hit deny ip any any.")
    return {"method": "Offline integer/IP, logical graph and generated-ACL evaluation; no IOS execution.",
            "passed": all(c["passed"] for c in checks), "checks": checks}
