"""Cisco lab configurations and explicit cable/port inventory."""

import secrets
from ipaddress import IPv4Network
from .planner import address


def header(name):
    return ["! NetArchitect generated lab configuration", "enable", "configure terminal",
            f"hostname {name}", "no ip domain-lookup", "!"]


def finish(lines):
    return "\n".join(lines + ["end", "! Save after checking: copy running-config startup-config", ""])


def net_parts(cidr):
    n = IPv4Network(cidr)
    return str(n.network_address), str(n.netmask)


def vlan_acl(group, plan):
    n = group["subnet"]
    source = f"{n['network'].split('/')[0]} {n['wildcard']}"
    result = [f"ip access-list extended VLAN-{group['vlan']}-IN"]
    if group["isolated"]:
        result += [f" permit icmp {source} host {n['gateway']} echo"]
        if plan["profile"] == "global":
            cloud = next((s for s in plan["sites"] if s["name"] == "CloudVPC"), None)
            if cloud:
                for g in cloud["groups"]:
                    c = g["subnet"]
                    result += [f" permit ip {source} {c['network'].split('/')[0]} {c['wildcard']}"]
        for dest, wild in [("10.0.0.0", "0.255.255.255"), ("172.16.0.0", "0.15.255.255"),
                           ("192.168.0.0", "0.0.255.255")]:
            result += [f" deny ip {source} {dest} {wild}"]
    return result + [f" permit ip {source} any", " deny ip any any log", "!"]


def qos(plan):
    lines = ["ip access-list extended FINANCE-SOURCES"]
    for site in plan["sites"]:
        for group in site["groups"]:
            if group["name"].lower() == "finance":
                n = group["subnet"]
                lines += [f" permit ip {n['network'].split('/')[0]} {n['wildcard']} any"]
    return lines + ["!", "class-map match-any FINANCE", " match access-group name FINANCE-SOURCES", "!",
            "policy-map MAN-QOS", " class FINANCE", "  bandwidth percent 30",
            " class class-default", "  fair-queue", "!"]


def crypto(edge, peers, psk):
    lines = ["crypto ikev2 proposal NA-PROP", " encryption aes-cbc-256", " integrity sha256",
             " prf sha256", " group 14", "!", "crypto ikev2 policy NA-POLICY",
             " proposal NA-PROP", "!", "crypto ikev2 keyring NA-KEYS"]
    for peer in peers:
        lines += [f" peer {peer['name']}", f"  address {address(peer['underlay'], 2)}",
                  f"  pre-shared-key local {psk}", f"  pre-shared-key remote {psk}"]
    lines += ["!", "crypto ikev2 profile NA-IKE", " match identity remote any",
              f" identity local address {address(edge['underlay'], 2)}",
              " authentication remote pre-share", " authentication local pre-share",
              " keyring local NA-KEYS", " dpd 10 2 periodic", "!",
              "crypto ipsec transform-set NA-TRANSFORM esp-aes 256 esp-sha256-hmac",
              " mode transport", "!", "crypto ipsec profile NA-IPSEC",
              " set transform-set NA-TRANSFORM", " set ikev2-profile NA-IKE", "!"]
    return lines


def generate_configs(plan):
    files, cables, devices = {}, [], []
    edges = {e["name"]: e for e in plan["edges"]}
    multi = plan["routing"]["protocol"] == "Multi-Area OSPF"
    global_wan = plan["profile"] == "global"
    psk = secrets.token_hex(24) if global_wan else None
    for site in plan["sites"]:
        ds = site["name"] + "-DS"
        local_edges = [e for e in plan["edges"] if e["site"] == site["name"]]
        area = site["area"] if multi else 0
        lines = header(ds) + ["ip routing", "spanning-tree mode rapid-pvst",
                              "vlan 999", " name UNUSED-NATIVE", "!"]
        for group in site["groups"]:
            n, v = group["subnet"], group["vlan"]
            lines += [f"vlan {v}", f" name {group['name']}", "!"]
            lines += vlan_acl(group, plan)
            lines += [f"spanning-tree vlan {v} priority 4096", f"interface Vlan{v}",
                      f" ip address {n['gateway']} {n['mask']}", f" ip access-group VLAN-{v}-IN in",
                      f" ip ospf 1 area {area}", " no shutdown", "!"]
            for j, port in enumerate(group["distribution_ports"]):
                access_name = f"{site['name']}-{group['name']}-AS{j+1}"
                lines += [f"interface TenGigabitEthernet1/0/{port}", f" description TO-{access_name}",
                          " switchport mode trunk", " switchport trunk native vlan 999",
                          f" switchport trunk allowed vlan {v},999", " switchport nonegotiate",
                          " no shutdown", "!"]
                active = min(48, group["planned_endpoints"] - j*48)
                aclines = header(access_name) + ["spanning-tree mode rapid-pvst", f"vlan {v}",
                          f" name {group['name']}", "vlan 999", " name UNUSED-NATIVE", "!",
                          f"interface range GigabitEthernet1/0/1 - {active}",
                          " switchport mode access", f" switchport access vlan {v}",
                          " spanning-tree portfast", " spanning-tree bpduguard enable", " no shutdown", "!"]
                if group["poe"]:
                    # Capability is inventory-dependent; auto is normal on PoE platforms.
                    aclines += ["! Select a PoE+ model. Verify AP wattage against switch budget."]
                if active < 48:
                    aclines += [f"interface range GigabitEthernet1/0/{active+1} - 48", " shutdown", "!"]
                aclines += ["interface TenGigabitEthernet1/1/1", f" description TO-{ds}",
                            " switchport mode trunk", " switchport trunk native vlan 999",
                            f" switchport trunk allowed vlan {v},999", " switchport nonegotiate",
                            " no shutdown", "!"]
                files[access_name+".cfg"] = finish(aclines)
                devices.append({"name": access_name, "role": "48-port PoE+ access" if group["poe"] else "48-port access",
                                "active_ports": active + 1, "vlan": v})
                cables.append([ds, f"Te1/0/{port}", access_name, "Te1/1/1", "802.1Q trunk", "-"])
        for j, edge in enumerate(local_edges):
            n = edge["lan"]
            lines += [f"interface TenGigabitEthernet1/0/{47+j}", f" description TO-{edge['name']}",
                      " no switchport", f" ip address {address(n['network'],1)} {n['mask']}",
                      f" ip ospf 1 area {area}", " ip ospf network point-to-point",
                      f" ip ospf cost {100 if j else 10}", " no shutdown", "!"]
            cables.append([ds, f"Te1/0/{47+j}", edge["name"], "Gi1", "routed LAN uplink", n["network"]])
        unused_start = site["access_switch_count"] + 1
        if unused_start <= 46:
            lines += [f"interface range TenGigabitEthernet1/0/{unused_start} - 46", " shutdown", "!"]
        if len(local_edges) == 1:
            lines += ["interface TenGigabitEthernet1/0/48", " shutdown", "!"]
        lines += ["router ospf 1", f" router-id 192.0.2.{100+site['index']}", " passive-interface default"]
        for j in range(len(local_edges)):
            lines += [f" no passive-interface TenGigabitEthernet1/0/{47+j}"]
        files[ds+".cfg"] = finish(lines)
        devices.append({"name": ds, "role": "48-port multilayer distribution", "active_ports": site["access_switch_count"]+len(local_edges)})
    for edge in plan["edges"]:
        site = plan["sites"][edge["site_index"]]
        area = site["area"] if multi else 0
        n = edge["lan"]
        lines = header(edge["name"])
        if plan["profile"] == "metro":
            lines += qos(plan)
        attached = [(idx, link) for idx, link in enumerate(plan["links"]) if edge["name"] in (link["a"], link["b"])]
        if global_wan:
            peers = [edges[link["b"] if edge["name"] == link["a"] else link["a"]] for _, link in attached]
            lines += crypto(edge, peers, psk)
        lines += ["interface GigabitEthernet1", f" description TO-{site['name']}-DS",
                  f" ip address {address(n['network'],2)} {n['mask']}",
                  f" ip ospf 1 area {area}", " ip ospf network point-to-point",
                  f" ip ospf cost {100 if edge['hub_copy'] else 10}", " no shutdown", "!"]
        ospf_ports = ["GigabitEthernet1"]
        if global_wan:
            lines += ["interface GigabitEthernet2", " description MANAGED-WAN-HANDOFF",
                      f" ip address {address(edge['underlay'],2)} 255.255.255.252",
                      " no shutdown", "!", f"ip route 0.0.0.0 0.0.0.0 {address(edge['underlay'],1)}", "!"]
            cables.append([edge["name"], "Gi2", "PROVIDER", f"Gi{edge['provider_port']}", "WAN underlay", edge["underlay"]])
        bgp_neighbors = []
        for idx, link in attached:
            is_a = edge["name"] == link["a"]
            peer = edges[link["b"] if is_a else link["a"]]
            subnet = link["subnet"]
            port = "Tunnel" + str(idx+1) if global_wan else "GigabitEthernet" + str(link["a_port"] if is_a else link["b_port"])
            local_ip = address(subnet["network"], 1 if is_a else 2)
            remote_ip = address(subnet["network"], 2 if is_a else 1)
            lines += [f"interface {port}", f" description TO-{peer['name']}",
                      f" ip address {local_ip} {subnet['mask']}"]
            if global_wan:
                lines += [" ip mtu 1400", " ip tcp adjust-mss 1360", " tunnel source GigabitEthernet2",
                          f" tunnel destination {address(peer['underlay'],2)}", " tunnel mode gre ip",
                          " tunnel protection ipsec profile NA-IPSEC"]
                bgp_neighbors.append((remote_ip, plan["sites"][peer["site_index"]]["asn"], link["secondary"]))
            else:
                lines += [" ip ospf 1 area 0", " ip ospf network point-to-point",
                          f" ip ospf cost {100 if link['secondary'] else 10}"]
                if plan["profile"] == "metro":
                    lines += [" service-policy output MAN-QOS"]
                ospf_ports.append(port)
            lines += [" no shutdown", "!"]
            if is_a:
                cables.append([edge["name"], port, peer["name"],
                               "Tunnel"+str(idx+1) if global_wan else "Gi"+str(link["b_port"]),
                               "encrypted overlay (logical)" if global_wan else "backbone / EVPL E-Line",
                               subnet["network"]])
        lines += ["router ospf 1", f" router-id {edge['router_id']}", " passive-interface default"]
        lines += [f" no passive-interface {p}" for p in ospf_ports]
        if multi:
            net, mask = net_parts(site["summary"])
            lines += [f" area {area} range {net} {mask}"]
        if global_wan:
            lines += [f" redistribute bgp {site['asn']} subnets route-map REMOTE-TO-OSPF", "!"]
            for group in site["groups"]:
                lines += [f"ip prefix-list LOCAL-LANS permit {group['subnet']['network']}"]
            for other in plan["sites"]:
                lines += [f"ip prefix-list ALL-SITES permit {other['summary']}"]
                if other["name"] != site["name"]:
                    lines += [f"ip prefix-list REMOTE-SITES permit {other['summary']}"]
            lines += ["!", "route-map LOCAL-TO-BGP permit 10", " match ip address prefix-list LOCAL-LANS",
                      "!", "route-map REMOTE-TO-OSPF permit 10", " match ip address prefix-list REMOTE-SITES",
                      "!", "route-map PRIMARY permit 10", " set local-preference 200", "!",
                      "route-map SECONDARY permit 10", " set local-preference 100", "!",
                      f"router bgp {site['asn']}", " bgp log-neighbor-changes",
                      f" bgp router-id {edge['router_id']}",
                      " redistribute ospf 1 match internal route-map LOCAL-TO-BGP"]
            net, mask = net_parts(site["summary"])
            lines += [f" aggregate-address {net} {mask} summary-only"]
            for ip, asn, secondary in bgp_neighbors:
                lines += [f" neighbor {ip} remote-as {asn}", f" neighbor {ip} timers 3 9",
                          f" neighbor {ip} prefix-list REMOTE-SITES in",
                          f" neighbor {ip} prefix-list ALL-SITES out",
                          f" neighbor {ip} route-map {'SECONDARY' if secondary else 'PRIMARY'} in"]
        files[edge["name"]+".cfg"] = finish(lines)
        devices.append({"name": edge["name"], "role": "IOS XE WAN edge" if global_wan else "IOS router",
                        "active_ports": 2 if global_wan else edge["ports"]})
    if global_wan:
        lines = header("PROVIDER")
        for edge in plan["edges"]:
            lines += [f"interface GigabitEthernet{edge['provider_port']}", f" description TO-{edge['name']}",
                      f" ip address {address(edge['underlay'],1)} 255.255.255.252", " no shutdown", "!"]
        files["PROVIDER.cfg"] = finish(lines)
        devices.append({"name": "PROVIDER", "role": "simulated managed-WAN router", "active_ports": len(plan["edges"])})
    return files, cables, devices
