# NetArchitect

CIC-307 Computer Networks mini-project: a rule-based network recommendation and configuration utility.

The program reads a preset or custom JSON, checks the inputs, allocates IPv4 subnets, explains the design, and writes Cisco IOS lab configurations. It is a command-line project using Python's standard library. There is no AI API, database or web server to set up.

## Run

Requires Python 3.9 or later. From the project folder:

```sh
python3 -m netarchitect presets
python3 -m netarchitect plan --preset campus --out output/my-campus
python3 -m unittest discover -s tests -v
```

Open `output/my-campus/report.html` in a browser. It works offline. Three complete exports are already included:

| Preset | Report | Current endpoints | Main choices |
|---|---|---:|---|
| Campus LAN | [Campus report](output/campus/report.html) | 1,600 | Cat6a / OM4, VLANs, RSTP, OSPF Area 0 |
| Metro MAN | [Metro report](output/metro/report.html) | 450 | OS2 ER, EVPL model, dual HQ edges, source-based QoS |
| Global WAN | [Global report](output/global/report.html) | 2,000 IoT/scanners + 20 cloud service hosts | Managed WAN, GRE/IPsec, eBGP, site summaries |

For the other presets:

```sh
python3 -m netarchitect plan --preset metro --out output/my-metro
python3 -m netarchitect plan --preset global --out output/my-global
```

Use `--force` to regenerate an existing NetArchitect export. It replaces previously generated files and keeps unrelated files. A fresh global export also generates a fresh lab VPN key; paste matching configs from the same export.

`python3 run_demo.py` regenerates all three included exports together.

## Custom input

```sh
python3 -m netarchitect preset campus > examples/my-network.json
python3 -m netarchitect plan --input examples/my-network.json --out output/custom
```

Edit the JSON before the second command. [Input guide](docs/input-guide.md) explains each field. The three original inputs are in `examples/`.

Examples of rejected inputs include copper beyond 100 m, negative host counts, duplicate VLANs, invalid CIDR boundaries, insufficient root space and unsupported switch density. The CLI prints a short error and returns exit code 2.

## Export contents

| File | Purpose |
|---|---|
| `report.html`, `report.md` | Explained engineering decisions and calculations |
| `topology.svg` | Logical topology sketch |
| `plan.json`, `input.json` | Structured plan and original parameters |
| `subnets.csv` | Network, mask, wildcard, gateway, broadcast and utilization |
| `configs/*.cfg` | Individual access switch, distribution switch and router configs |
| `device_inventory.csv` | Complete device count and active ports |
| `cabling.csv` | Port-to-port connections; logical tunnels are labelled |
| `host_examples.csv` | One sample host per VLAN with mask and gateway |
| `offline_checks.json` | Address, topology and ACL checks with their exact scope |

## Project files

- `netarchitect/`: validation, media rules, bitwise VLSM, topology, IOS generation and CLI.
- `tests/`: unit and end-to-end CLI tests, including 100 seeded randomized allocation cases.
- [Assignment checklist](docs/assignment-checklist.md): requirements mapped to implementation.
- [Project report](docs/project-report.md): design, algorithms, calculations and limitations.
- [Verification guide](docs/verification.md): simulator setup and expected packet flows.
- [AI audit log](ai_audit_log.md): faulty AI drafts, diagnosis, fixes and reproducible checks.
- [Viva notes](docs/viva-notes.md): short answers about the design.

## Verification status

The Python tests and exported offline checks are executable without network hardware. IOS configurations have **not** been run in Packet Tracer, GNS3 or CML on this machine. The complete port map, configs and simulator checklist are provided for that final check; no simulator screenshots, timing results or `.pkt` file are fabricated.

Use a licensed IOS XE image with IKEv2/IPsec support for Global WAN. Packet Tracer can be used for basic VLAN/OSPF/ACL work, with interface names remapped to its device models. Physical optics, AP power budgets and a provider's EVPL SLA require actual hardware/provider data. See the verification guide for the precise limits.

## Optional install and pytest

Running from this folder needs no installation. To install the command or use pytest:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install .
netarchitect presets
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
```

The tests also work with the standard-library command shown at the top.
