"""Rejected AI draft samples retained for the assignment's audit exercise.

These deliberately flawed samples were generated during this project, not
copied from production incidents. Never use them as device configurations.
"""


def bad_wildcard(prefix):
    # Faulty draft assumes every VLAN is /24.
    return "0.0.0.255"


BAD_TRUNK = """interface TenGigabitEthernet1/1/1
 switchport mode trunk
 switchport trunk native vlan 999
 no shutdown
!
"""

BAD_QOS = """class-map match-any FINANCE
 match dscp af31
!
policy-map MAN-QOS
 class FINANCE
  bandwidth percent 30
!
"""


def trunk_accepts(config, vlan):
    """Model allowed VLAN membership, excluding physical/STP link state."""
    for line in config.splitlines():
        if line.strip().startswith("switchport trunk allowed vlan "):
            values = line.strip().split()[-1].split(",")
            return str(vlan) in values
    return True  # IOS trunk default allows all VLANs.
