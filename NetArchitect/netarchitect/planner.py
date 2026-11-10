import math
from ipaddress import IPv4Address, IPv4Network

from .errors import PlanningError
from .media import select_media
from .subnetting import allocate, prefix_for_hosts
from .validation import validate


def address(network, offset):
    return str(IPv4Address(int(IPv4Network(network).network_address) + offset))


def routing_choice(subnets, domain_boundary=False):
    if domain_boundary:
        return {"protocol": "eBGP", "reason": "Separate city/cloud routing domains use private ASNs "
                "and eBGP (RFC 4271). Each site advertises one aligned LAN aggregate (RFC 4632); "
                "OSPF Area 0 stays inside each site. GRE over IPsec carries intersite BGP."}
    if subnets < 50:
        return {"protocol": "OSPF Area 0", "reason": f"One administrative domain and {subnets} active "
                "subnets (<50) fit the assignment's single-area rule. OSPF (RFC 2328) computes "
                "shortest paths and recalculates after failure. The 50-subnet cutoff is an "
                "assignment policy, not an RFC protocol limit."}
    return {"protocol": "Multi-Area OSPF", "reason": f"{subnets} active subnets reach the assignment's "
            "50-subnet threshold. Backbone links stay in Area 0; each site's LAN and distribution "
            "uplinks use one local area. Edge routers are ABRs; area ranges summarize LANs (RFC 2328)."}


def plan_media(data):
    media = [{"name": "Endpoint access", **select_media(data["access_distance_m"], "copper")}]
    media.append({"name": "In-rack links", **select_media(5)})
    for idx, raw in enumerate(data["sites"]):
        if data["profile"] == "global":
            media.append({"name": raw["name"] + " managed-WAN handoff", **select_media(50),
                          "provider_path_m": raw["distance_m"],
                          "transport_reason": f"The {raw['distance_m']/1000:g} km provider path "
                          "is a managed service, not one Ethernet optical span. The 50 m "
                          "local handoff uses Cat6a; IPsec protects traffic across the service."})
        else:
            choice = select_media(raw["distance_m"], raw.get("medium", "auto"),
                                  raw.get("fiber_attenuation_db_per_km"))
            media.append({"name": ("HQ local routed uplink" if idx == 0 else "HQ to " + raw["name"]), **choice})
    return media


def build_plan(data):
    validate(data)
    media = plan_media(data)
    sites = []
    for idx, raw in enumerate(data["sites"]):
        groups = []
        for raw_group in raw["groups"]:
            g = dict(raw_group)
            g["planned_endpoints"] = math.ceil(g["hosts"] * (100 + data["growth_percent"]) / 100)
            g["required_usable"] = g["planned_endpoints"] + 1
            g["access_switches"] = math.ceil(g["planned_endpoints"] / 48)
            groups.append(g)
        count = sum(g["access_switches"] for g in groups)
        if count > 46:
            raise PlanningError(f"{raw['name']} needs {count} access uplinks; one distribution "
                                "switch supports at most 46. Split the site or reduce density.")
        total = sum(1 << (32-prefix_for_hosts(g["required_usable"])) for g in groups)
        site_prefix = 32 - (total - 1).bit_length()
        # Root-level allocator reserves a complete aligned site block.
        sites.append({"name": raw["name"], "index": idx, "groups": groups,
                      "block_hosts": (1 << (32-site_prefix)) - 2,
                      "access_switch_count": count, "asn": 65100 + idx,
                      "area": idx + 1, "distance_m": raw["distance_m"]})
    copies = 2 if data["resilient"] else 1
    requests = [("site:" + s["name"], s["block_hosts"]) for s in sites]
    edges, links = [], []
    for s in sites:
        for n in range(copies if s["index"] == 0 else 1):
            edge = {"name": s["name"] + f"-R{n+1}", "site": s["name"],
                    "site_index": s["index"], "hub_copy": n, "ports": 1,
                    "router_id": f"192.0.2.{len(edges)+1}"}
            edges.append(edge)
            requests.append(("lan:" + edge["name"], 2))
    hubs = [e for e in edges if e["site_index"] == 0]
    spokes = [e for e in edges if e["site_index"] != 0]
    for h in hubs:
        for spoke in spokes:
            key = f"backbone:{h['name']}:{spoke['name']}"
            requests.append((key, 2))
            h["ports"] += 1
            spoke["ports"] += 1
            links.append({"name": key, "a": h["name"], "b": spoke["name"],
                          "a_port": h["ports"], "b_port": spoke["ports"],
                          "secondary": h["hub_copy"] == 1})
    blocks = {r["name"]: r for r in allocate(data["root"], requests)}
    allocations = []
    for s in sites:
        s["summary"] = blocks["site:" + s["name"]]["network"]
        vlans = {v["name"]: v for v in allocate(s["summary"], [(g["name"], g["required_usable"]) for g in s["groups"]])}
        next_port = 1
        for g in s["groups"]:
            g["subnet"] = vlans[g["name"]]
            g["distribution_ports"] = list(range(next_port, next_port + g["access_switches"]))
            next_port += g["access_switches"]
            allocations.append(dict(vlans[g["name"]], name=s["name"]+":"+g["name"], site=s["name"], vlan=g["vlan"]))
    for edge in edges:
        edge["lan"] = blocks["lan:" + edge["name"]]
        allocations.append(edge["lan"])
    for link in links:
        link["subnet"] = blocks[link["name"]]
        allocations.append(link["subnet"])
    routing = routing_choice(len(allocations), data["profile"] == "global")
    # Global /30 underlay space is separate from all RFC1918 LAN/tunnel addresses.
    if data["profile"] == "global":
        for i, edge in enumerate(edges):
            edge["underlay"] = f"198.18.0.{i*4}/30"
            edge["provider_port"] = i + 1
    warnings = ["Configurations target a lab IOS/IOS XE feature set. Match interface names and "
                "supported commands to the chosen image before pasting.",
                "End hosts use static addresses; DHCP, DNS, Internet access and NAT are outside this lab.",
                "One distribution switch and one router at each remote site remain single points of failure."]
    if data["profile"] == "metro":
        warnings += [("The MAN is a routed hub-and-spoke design carried by two independent EVPL "
                     "E-Line services to different HQ edge routers. " if copies == 2 else
                     "The MAN is a routed hub-and-spoke design using one EVPL E-Line per remote. ")
                     + "Provider EVC/VLAN mapping is external.",
                     "Sub-5 ms is a latency target, not an OSPF convergence promise. Fibre propagation "
                     "RTT at 35 km is about 0.35 ms; provider queuing and equipment delays must be measured.",
                     "OS2 ER at 35 km needs a measured optical budget. If loss exceeds the stated "
                     "assumption, use engineered optics or a managed service."]
    if data["profile"] == "global":
        warnings += ["CloudVPC is an IOS cloud-gateway emulator, not an actual provisioned cloud VPC.",
                     "Both hub routers share one simulated provider. Separate carrier fault domains "
                     "must be provisioned to protect against provider failure.",
                     "WAN IPsec/IKEv2 and BGP require GNS3/CML with a suitable licensed IOS XE image. "
                     "Packet Tracer support is incomplete."]
    if not data["resilient"]:
        warnings.append("Single hub selected: a hub or backbone failure disconnects the affected site.")
    used = sum(IPv4Network(s["summary"]).num_addresses for s in sites) + (len(edges)+len(links))*4
    endpoints = sum(g["hosts"] for s in sites for g in s["groups"])
    return {"name": data["name"], "profile": data["profile"], "root": data["root"],
            "input": data, "endpoint_count": endpoints, "sites": sites, "edges": edges,
            "links": links, "allocations": allocations, "routing": routing, "media": media,
            "topology_reason": (f"{'Two HQ edge routers' if copies == 2 else 'One HQ edge router'} "
                f"{'connect' if copies == 2 else 'connects'} {len(sites)-1} remote sites. Routed links keep broadcasts local; "
                "802.1Q trunks are limited to each access switch's VLAN and unused native VLAN 999. "
                "Rapid-PVST (RSTP per VLAN) protects local L2 wiring. "
                + ("Independent spoke links to both hubs provide dual-homed path failover. " if copies == 2 else "")
                + "48-port access switches are counted from planned endpoints, with one VLAN per switch."),
            "address_summary": {"reserved_addresses": used,
                "root_addresses": IPv4Network(data["root"]).num_addresses,
                "root_reserved_percent": round(used/IPv4Network(data["root"]).num_addresses*100, 2),
                "reason": "Each site's VLAN blocks are placed largest-first inside an aligned "
                          "site aggregate. Site aggregates and /30 transit blocks are then placed "
                          "largest-first in the root. Aggregates are reservations, not extra active subnets."},
            "warnings": warnings}
