import math
import re
from ipaddress import IPv4Network
from .errors import PlanningError


def number(value, label, low, high, integer=False):
    allowed = (int,) if integer else (int, float)
    if type(value) not in allowed or not low <= value <= high or not math.isfinite(value):
        raise PlanningError(f"{label} must be {'an integer' if integer else 'a number'} from {low} to {high}.")


def keys(obj, required, optional, label):
    if not isinstance(obj, dict):
        raise PlanningError(f"{label} must be a JSON object.")
    missing = set(required) - obj.keys()
    extra = obj.keys() - set(required) - set(optional)
    if missing or extra:
        raise PlanningError(f"{label}: missing keys {sorted(missing)}; unknown keys {sorted(extra)}.")


def identifier(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{0,23}", value):
        raise PlanningError(f"{label} must start with a letter; use 1-24 letters, digits or hyphens.")


def validate(data):
    keys(data, ["name", "profile", "root", "resilient", "growth_percent", "access_distance_m", "sites"], [], "input")
    if not isinstance(data["name"], str) or not 1 <= len(data["name"]) <= 80 or any(ord(c) < 32 for c in data["name"]):
        raise PlanningError("name must be 1-80 printable characters.")
    if data["profile"] not in ("campus", "metro", "global"):
        raise PlanningError("profile must be campus, metro, or global.")
    if type(data["resilient"]) is not bool:
        raise PlanningError("resilient must be true or false.")
    number(data["growth_percent"], "growth_percent", 0, 100, integer=True)
    number(data["access_distance_m"], "access_distance_m", 0.1, 100)
    try:
        root = IPv4Network(data["root"], strict=True)
    except (TypeError, ValueError) as exc:
        raise PlanningError("root must be an aligned IPv4 CIDR network.") from exc
    private = [IPv4Network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]
    if not any(root.subnet_of(n) for n in private) or root.prefixlen > 29:
        raise PlanningError("root must be inside RFC 1918 space and have prefix /29 or larger block.")
    if not isinstance(data["sites"], list) or not 2 <= len(data["sites"]) <= 5:
        raise PlanningError("Provide 2-5 sites; the first is the hub/HQ.")
    site_names = set()
    for site in data["sites"]:
        keys(site, ["name", "distance_m", "groups"], ["medium", "fiber_attenuation_db_per_km"], "site")
        identifier(site["name"], "site name")
        if site["name"].lower() in site_names:
            raise PlanningError("Site names must be unique, ignoring case.")
        site_names.add(site["name"].lower())
        number(site["distance_m"], "site distance_m", 0.1, 40000000)
        if "fiber_attenuation_db_per_km" in site:
            number(site["fiber_attenuation_db_per_km"], "fiber_attenuation_db_per_km", 0.1, 1)
        if site.get("medium", "auto") not in ("auto", "copper", "om4", "os2"):
            raise PlanningError("medium must be auto, copper, om4, or os2.")
        if data["profile"] == "global" and site.get("medium", "auto") != "auto":
            raise PlanningError("Global uses a managed WAN with a 50 m local handoff; leave medium auto.")
        if not isinstance(site["groups"], list) or not 1 <= len(site["groups"]) <= 16:
            raise PlanningError("Each site requires 1-16 VLAN groups.")
        vlans, names = set(), set()
        for group in site["groups"]:
            keys(group, ["name", "hosts", "vlan", "isolated", "poe"], [], "group")
            identifier(group["name"], "group name")
            number(group["hosts"], "hosts", 1, 1000000, integer=True)
            number(group["vlan"], "vlan", 2, 4093, integer=True)
            if group["vlan"] in (999, 1002, 1003, 1004, 1005):
                raise PlanningError("VLAN 999 is the unused native VLAN; 1002-1005 are reserved.")
            if group["vlan"] in vlans or group["name"].lower() in names:
                raise PlanningError("Group names and VLAN IDs must be unique within each site.")
            vlans.add(group["vlan"])
            names.add(group["name"].lower())
            for field in ("isolated", "poe"):
                if type(group[field]) is not bool:
                    raise PlanningError(f"{field} must be true or false.")
    return data
