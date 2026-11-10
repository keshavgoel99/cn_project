from copy import deepcopy


def group(name, hosts, vlan, isolated=False, poe=False):
    return dict(name=name, hosts=hosts, vlan=vlan, isolated=isolated, poe=poe)


PRESETS = {
    "campus": {
        "name": "Campus LAN", "profile": "campus", "root": "10.10.0.0/16",
        "resilient": False, "growth_percent": 10, "access_distance_m": 70,
        "sites": [
            {"name": "Admin", "distance_m": 50, "groups": [group("Staff", 300, 10), group("WiFi", 100, 20, poe=True)]},
            {"name": "Teaching", "distance_m": 220, "groups": [group("Students", 600, 10), group("WiFi", 100, 20, poe=True)]},
            {"name": "Library", "distance_m": 380, "groups": [group("Readers", 400, 10), group("WiFi", 100, 20, poe=True)]},
        ],
    },
    "metro": {
        "name": "Metro MAN", "profile": "metro", "root": "10.20.0.0/16",
        "resilient": True, "growth_percent": 10, "access_distance_m": 80,
        "sites": [
            {"name": "HQ", "distance_m": 50, "groups": [group("Finance", 220, 10), group("Guest", 30, 20, isolated=True)]},
            {"name": "Remote1", "distance_m": 15000, "groups": [group("Finance", 80, 10), group("Guest", 20, 20, isolated=True)]},
            {"name": "Remote2", "distance_m": 35000, "fiber_attenuation_db_per_km": 0.22,
             "groups": [group("Finance", 80, 10), group("Guest", 20, 20, isolated=True)]},
        ],
    },
    "global": {
        "name": "Global WAN", "profile": "global", "root": "10.30.0.0/16",
        "resilient": True, "growth_percent": 10, "access_distance_m": 60,
        "sites": [
            {"name": "Delhi", "distance_m": 50, "groups": [group("IoT", 400, 10, isolated=True), group("Scanners", 100, 20)]},
            {"name": "Mumbai", "distance_m": 1400000, "groups": [group("IoT", 400, 10, isolated=True), group("Scanners", 100, 20)]},
            {"name": "Chennai", "distance_m": 2200000, "groups": [group("IoT", 400, 10, isolated=True), group("Scanners", 100, 20)]},
            {"name": "Kolkata", "distance_m": 1500000, "groups": [group("IoT", 400, 10, isolated=True), group("Scanners", 100, 20)]},
            {"name": "CloudVPC", "distance_m": 1000000, "groups": [group("Services", 20, 10)]},
        ],
    },
}


def get_preset(name):
    return deepcopy(PRESETS[name])
