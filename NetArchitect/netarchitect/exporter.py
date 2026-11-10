import csv
import html
import json
from io import StringIO
from pathlib import Path

from .configs import generate_configs
from .diagram import topology_svg
from .errors import PlanningError
from .planner import address
from .verify import check_plan


REFERENCES = [
    ("RFC 1918 - private IPv4 space", "https://www.rfc-editor.org/rfc/rfc1918"),
    ("RFC 4632 - CIDR and aggregation", "https://www.rfc-editor.org/rfc/rfc4632"),
    ("RFC 2328 - OSPFv2", "https://www.rfc-editor.org/rfc/rfc2328"),
    ("RFC 4271 - BGP-4", "https://www.rfc-editor.org/rfc/rfc4271"),
    ("RFC 4301 - IPsec architecture", "https://www.rfc-editor.org/rfc/rfc4301"),
    ("Cisco 10GBASE SFP+ data sheet - reach and optical power", "https://www.cisco.com/c/en/us/products/collateral/interfaces-modules/transceiver-modules/data_sheet_c78-455693.html"),
    ("Cisco IOS XE IPsec configuration guide", "https://www.cisco.com/c/en/us/td/docs/routers/ios/config/17-x/sec-vpn/b-security-vpn/m_sec-cfg-vpn-ipsec-0.html"),
]


def report_sections(plan, verification, devices):
    rows = []
    rows.append(("Overview", [f"{plan['endpoint_count']} requested endpoints across {len(plan['sites'])} sites; "
        f"{plan['input']['growth_percent']}% endpoint growth reserved. "
        f"Root: {plan['root']}. All planned links use the assignment's 10 Gb/s media rules.",
        plan["topology_reason"], plan["routing"]["reason"], plan["address_summary"]["reason"],
        f"{plan['address_summary']['reserved_addresses']} of {plan['address_summary']['root_addresses']} "
        f"root addresses reserved ({plan['address_summary']['root_reserved_percent']}%). "
        "Per-subnet utilization includes endpoint growth and the SVI gateway; root reservation also "
        "includes alignment space inside site aggregates."]))
    media = []
    for m in plan["media"]:
        media.append(f"{m['name']}: {m['medium']} / {m['transceiver']}. {m['reason']} " + m.get("transport_reason", ""))
    rows.append(("Physical media decisions", media))
    rows.append(("Site capacity and summaries", [
        f"{s['name']}: {s['summary']}, {s['access_switch_count']} access switches, "
        f"{sum(g['hosts'] for g in s['groups'])} current endpoints, "
        f"{sum(g['planned_endpoints'] for g in s['groups'])} planned endpoints. "
        + (f"Private AS {s['asn']}. " if plan["profile"] == "global" else "")
        + "PoE groups: " + (", ".join(g['name'] for g in s['groups'] if g['poe']) or "none") + "."
        for s in plan["sites"]]))
    rows.append(("VLAN and access policy", [
        "Each VLAN's SVI is its default gateway. The first usable IP is reserved for the gateway; "
        "endpoints start at network + 2. An inbound ACL rejects sources outside the VLAN subnet.",
        "Isolated VLANs may ping their gateway and reach CloudVPC service subnets when present; "
        "they cannot reach other RFC 1918 destinations. Other destinations are permitted but this "
        "lab has no Internet route/NAT. ACLs are stateless, so return traffic from isolated VLANs "
        "to internal clients is also denied unless it matches the cloud exception.",
        "Access switches carry only their assigned data VLAN and native VLAN 999 on each trunk. "
        "End host ports use PortFast and BPDU Guard. Distribution switches are the local RSTP root.",
        "PoE access groups require a PoE+ switch model and a measured AP power budget. The planner "
        "counts Ethernet endpoints, not wireless clients behind each AP."]))
    if plan["profile"] == "metro":
        rows.append(("MAN transport and QoS", [
            ("Two separate EVPL E-Line circuits join each remote edge to two HQ routers. " if plan['input']['resilient']
             else "One EVPL E-Line circuit joins each remote edge to the HQ router. ") + "VLANs stay "
            "local; this is a routed design over the provider's Ethernet service.",
            "The router's egress policy classifies Finance source subnets directly and reserves "
            "30% of interface bandwidth during congestion. Other traffic uses the default queue. "
            "For a provider CIR below port speed, add shaping to the contracted CIR before using "
            "the policy in a physical deployment. This generated lab has no configured CIR.",
            "At 35 km, the preset explicitly assumes 0.22 dB/km at 1550 nm. With the default "
            "0.30 dB/km, the same ER span fails the loss test; changing this assumption requires "
            "a measured/provider loss figure, not merely a desired reach."]))
    if plan["profile"] == "global":
        rows.append(("WAN routing and encryption", [
            "The provider router carries only 198.18.0.0/15 lab underlay addresses. Edges use a "
            "static default toward it; these underlay links are excluded from OSPF and BGP.",
            "Point-to-point GRE tunnels are protected by IKEv2/IPsec using AES-256, SHA-256 and "
            "DH group 14. A fresh lab PSK is generated for each export and installed consistently "
            "in its edge configs. Treat the config directory as containing credentials.",
            "OSPF distributes local VLANs to the edge. Only exact local VLAN prefixes are imported "
            "into BGP, then summarized per site. Only remote site aggregates return to OSPF; "
            "this avoids redistribution feedback and avoids a permanently advertised Null0 route.",
            "The primary hub path gets BGP local preference 200; secondary gets 100. BGP timers "
            "are 3/9 seconds, so silent-failure detection can take about 9 seconds plus convergence. "
            "The tunnels use MTU 1400 and TCP MSS 1360; verify with DF pings on the chosen image."]))
    rows.append(("Offline validation", [verification["method"],
        f"{sum(c['passed'] for c in verification['checks'])}/{len(verification['checks'])} checks passed. "
        "See offline_checks.json for each packet ACL decision and hub-removal graph check. "
        "These results do not establish simulator interoperability, latency, or encryption counters."]))
    rows.append(("Assumptions and limits", plan["warnings"]))
    rows.append(("Lab inventory", [f"{len(devices)} devices total. device_inventory.csv lists every "
        "device and its active ports. A demo may use one access switch/host per VLAN; the exports "
        "retain the complete endpoint-capacity inventory. See cabling.csv for exact port pairs.",
        "Interface names are logical lab defaults: access Gi1/0/1-48 + Te1/1/1, distribution "
        "Te1/0/1-48, routers Gi1 onward. Remap names consistently for the installed simulator "
        "image. Virtual Gi labels do not represent physical 10 Gb/s transceiver compatibility."]))
    return rows


def export_plan(plan, output, force=False):
    out = Path(output).expanduser().resolve()
    configs, cables, devices = generate_configs(plan)
    verification = check_plan(plan, configs)
    if not verification["passed"]:
        raise PlanningError("Generated plan failed offline validation; no export written.")
    if out.exists() and any(out.iterdir()):
        marker = out / "netarchitect-export.json"
        if not force or not marker.is_file():
            raise PlanningError(f"{out} is not empty. Choose another folder, or use --force for an existing NetArchitect export.")
        try:
            old = json.loads(marker.read_text())
            old_files = old["files"]
        except (ValueError, KeyError) as exc:
            raise PlanningError("Export marker is invalid; choose another output folder.") from exc
        # Only remove files recorded by this exporter; preserve unrelated user files.
        for filename in old_files:
            target = out / filename
            if target.resolve().is_relative_to(out) and target.is_file():
                target.unlink()
    out.mkdir(parents=True, exist_ok=True)
    cfgdir = out / "configs"
    cfgdir.mkdir(exist_ok=True)
    files = []
    def write(name, content):
        target = out/name
        target.write_text(content, encoding="utf-8")
        if plan["profile"] == "global" and name.startswith("configs/"):
            target.chmod(0o600)
        files.append(name)
    for filename, content in configs.items():
        write("configs/"+filename, content)
    write("plan.json", json.dumps(plan, indent=2)+"\n")
    write("input.json", json.dumps(plan["input"], indent=2)+"\n")
    write("offline_checks.json", json.dumps(verification, indent=2)+"\n")
    def csv_text(header, rows):
        stream = StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)
        return stream.getvalue()
    write("cabling.csv", csv_text(["device_a", "port_a", "device_b", "port_b", "purpose", "subnet"], cables))
    write("device_inventory.csv", csv_text(["device", "role", "active_ports", "vlan"],
        [(d["name"], d["role"], d["active_ports"], d.get("vlan", "")) for d in devices]))
    write("host_examples.csv", csv_text(["site", "group", "vlan", "host_ip", "mask", "gateway", "isolated"],
        [(s["name"], g["name"], g["vlan"], address(g["subnet"]["network"],2), g["subnet"]["mask"],
          g["subnet"]["gateway"], g["isolated"]) for s in plan["sites"] for g in s["groups"]]))
    subnet_headers = ["name", "network", "mask", "wildcard", "gateway", "last_usable", "broadcast", "required_usable", "usable_capacity", "utilization_percent"]
    write("subnets.csv", csv_text(subnet_headers, [[a[h] for h in subnet_headers] for a in plan["allocations"]]))
    write("topology.svg", topology_svg(plan))
    sections = report_sections(plan, verification, devices)
    md = ["# "+plan["name"], "", "CIC-307 - NetArchitect generated plan", "", "![Logical topology](topology.svg)", ""]
    body = [f"<h1>{html.escape(plan['name'])}</h1><p class='subtitle'>CIC-307 · NetArchitect generated plan</p>",
            "<img src='topology.svg' alt='Logical hub and spoke topology' style='width:100%;height:auto'>"]
    for title, paragraphs in sections:
        md += ["## "+title, ""]
        body += ["<h2>"+html.escape(title)+"</h2>"]
        for p in paragraphs:
            md += [p, ""]
            body += ["<p>"+html.escape(p)+"</p>"]
    md += ["## Active subnet allocation", "", "| Name | Network | Gateway | Broadcast | Usable needed / capacity |", "|---|---|---|---|---|"]
    body += ["<h2>Active subnet allocation</h2><div class='table-wrap'><table><thead><tr><th>Name</th><th>Network</th><th>Gateway</th><th>Broadcast</th><th>Needed / usable</th></tr></thead><tbody>"]
    for a in plan["allocations"]:
        cells = [a["name"], a["network"], a["gateway"], a["broadcast"], f"{a['required_usable']} / {a['usable_capacity']}"]
        md += ["| " + " | ".join(cells) + " |"]
        body += ["<tr>"+"".join("<td>"+html.escape(c)+"</td>" for c in cells)+"</tr>",
                 "<tr><td class='rationale' colspan='5'>"+html.escape(a["reason"])+"</td></tr>"]
    body += ["</tbody></table></div><h2>References</h2><ul>"]
    md += ["", "## Subnet calculations", ""]
    for a in plan["allocations"]:
        md += [a["name"]+": "+a["reason"], ""]
    md += ["", "## References", ""]
    for title, url in REFERENCES:
        md += [f"- [{title}]({url})"]
        body += [f"<li><a href='{url}'>{html.escape(title)}</a></li>"]
    body += ["</ul><footer>Generated by a deterministic rule engine. Confirm the lab behaviour using docs/verification.md.</footer>"]
    write("report.md", "\n".join(md)+"\n")
    style = """body{font:16px/1.65 system-ui,sans-serif;color:#17252d;background:#f3f5f6;margin:0}main{max-width:1050px;margin:36px auto;background:white;padding:40px 48px;border:1px solid #d9e1e5;border-radius:8px}h1{font-size:36px;line-height:1.2;margin:0}h2{font-size:22px;margin-top:36px;border-bottom:2px solid #dfe9ed;padding-bottom:8px}.subtitle,footer{color:#536874}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;border:1px solid #d9e1e5;padding:8px;vertical-align:top}th{background:#eaf1f4}.rationale{color:#52646c;background:#fafcfc}a{color:#13617e}footer{font-size:13px;margin-top:32px}@media(max-width:700px){main{padding:24px 18px;margin:0;border:0}h1{font-size:28px}}@media print{body{background:white}main{margin:0;padding:0;border:0}h2{break-after:avoid}tr{break-inside:avoid}}"""
    write("report.html", "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><link rel='icon' href='data:,'>"
        + "<title>"+html.escape(plan["name"])+" - NetArchitect</title><style>"+style+"</style></head><body><main>"+"".join(body)+"</main></body></html>")
    write("netarchitect-export.json", json.dumps({"format": 1, "files": files.copy()}, indent=2)+"\n")
    return {"directory": str(out), "config_count": len(configs), "check_count": len(verification["checks"])}
