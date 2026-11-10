# Input guide

Start with `python3 -m netarchitect preset campus` or an input in `examples/`. Unknown fields are rejected so typing errors do not silently change a design.

## Top-level fields

| Field | Meaning |
|---|---|
| `name` | Printable report title, 1-80 characters |
| `profile` | `campus`, `metro` or `global` |
| `root` | Aligned RFC 1918 IPv4 block; e.g. `10.40.0.0/16` |
| `resilient` | Boolean; adds a second HQ edge and an independent connection from every remote |
| `growth_percent` | Integer from 0 to 100; applied to every group and rounded up |
| `access_distance_m` | Endpoint-to-access-switch channel length; positive, at most 100 m |
| `sites` | 2-5 site objects; first site is HQ/hub |

All media rules are evaluated for 10 Gb/s, as in the assignment. This utility does not calculate reach for other Ethernet speeds.

## Site fields

| Field | Meaning |
|---|---|
| `name` | 1-24 letters, digits or hyphens; starts with a letter; unique ignoring case |
| `distance_m` | Campus/Metro: physical circuit length from hub to this site. Global: managed provider path length |
| `medium` | Optional `auto` (default), `copper`, `om4`, `os2`; Global requires `auto` |
| `fiber_attenuation_db_per_km` | Optional engineered assumption from 0.1 to 1 dB/km for OS2; defaults to 0.4 at 1310 nm and 0.3 at 1550 nm |
| `groups` | 1-16 VLAN group objects |

The first site's distance describes its local distribution-to-edge connection and is checked by the same media rules. Other in-rack equipment connections use a fixed 5 m rule. Global local WAN handoffs are modelled as 50 m. Secondary Metro/Campus paths use the same length as the primary; change the design outside this model if the diverse path is longer.

## Group fields

| Field | Meaning |
|---|---|
| `name` | Same identifier rules as site names; unique within its site |
| `hosts` | Positive integer endpoint count |
| `vlan` | Unique per site, 2-4093; 999 and 1002-1005 are reserved |
| `isolated` | Boolean; deny other private networks except CloudVPC services when present |
| `poe` | Boolean; request PoE+ access switches for this group |

One gateway is added **after** endpoint growth. A group with 254 endpoints and zero growth needs 255 usable IPs, so it gets a /23, not a /24. Each group uses dedicated 48-port access switches. One distribution switch supports at most 46 access uplinks and two routed edge uplinks; excessive density is rejected rather than silently oversubscribed.

`Finance` groups in a Metro profile are classified by source subnet for QoS. A group named `CloudVPC` is not special: the **site** named `CloudVPC` supplies the allowed service prefixes for isolated Global VLANs. Group names describe roles; VLAN IDs can repeat at different sites because the WAN is routed.

## Error examples

| Input | Result |
|---|---|
| `distance_m: 120`, `medium: "copper"` | `PhysicalDistanceViolationError` with attenuation warning |
| OM4 forced at 401 m | Distance violation |
| Direct OS2 span over 40 km | Reject; use separately engineered/managed transport |
| ER 35 km at default 0.30 dB/km | Reject: estimated loss exceeds available budget |
| ER 35 km at explicitly assumed 0.22 dB/km | 9.10 dB estimated loss, 2.00 dB remaining margin; still requires field verification |
| Root `10.1.0.1/16` | Reject unaligned network |
| Campus preset changed to a /29 root | `AddressSpaceExhaustionError` |

The included 35 km example uses 0.22 dB/km as a declared design assumption, not a claim about installed cable. Do not lower it simply to get a passing plan.
