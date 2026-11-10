"""Integer/bitwise VLSM. ipaddress is used for parsing and display only."""

from ipaddress import IPv4Address, IPv4Network
from .errors import AddressSpaceExhaustionError, PlanningError

MAX_IP = (1 << 32) - 1


def mask_for(prefix):
    if type(prefix) is not int or not 0 <= prefix <= 32:
        raise PlanningError("IPv4 prefix must be an integer from 0 to 32.")
    return (MAX_IP << (32 - prefix)) & MAX_IP


def prefix_for_hosts(hosts):
    if type(hosts) is not int or hosts < 1 or hosts > (1 << 32) - 2:
        raise PlanningError("Host requests must be positive IPv4-sized integers.")
    # Reserve network + broadcast. /31 and /32 are deliberately excluded.
    return 32 - (hosts + 1).bit_length()


def allocate(root, requests):
    """requests: [(unique name, required usable addresses)]. Largest first."""
    try:
        block = IPv4Network(root, strict=True)
    except (ValueError, TypeError) as exc:
        raise PlanningError("Root must be an aligned IPv4 network, e.g. 10.0.0.0/16.") from exc
    names = [name for name, _ in requests]
    if len(names) != len(set(names)):
        raise PlanningError("Subnet request names must be unique.")
    sized = [(name, hosts, prefix_for_hosts(hosts)) for name, hosts in requests]
    sized.sort(key=lambda row: (row[2], row[0]))
    cursor = int(block.network_address)
    last = int(block.broadcast_address)
    result = []
    for name, hosts, prefix in sized:
        size = 1 << (32 - prefix)
        start = (cursor + size - 1) & ~(size - 1)
        end = start + size - 1
        if end > last or prefix < block.prefixlen:
            raise AddressSpaceExhaustionError(
                f"{name} needs /{prefix} ({size} addresses); {block} has no aligned space left.")
        mask = mask_for(prefix)
        result.append({
            "name": name, "network": f"{IPv4Address(start)}/{prefix}",
            "prefix": prefix, "mask": str(IPv4Address(mask)),
            "wildcard": str(IPv4Address(MAX_IP ^ mask)),
            "gateway": str(IPv4Address(start + 1)),
            "first_usable": str(IPv4Address(start + 1)),
            "last_usable": str(IPv4Address(end - 1)),
            "broadcast": str(IPv4Address(end)), "required_usable": hosts,
            "usable_capacity": size - 2, "total_addresses": size,
            "utilization_percent": round(hosts / (size - 2) * 100, 2),
            "reason": f"2^{32-prefix} - 2 = {size-2} usable addresses >= {hosts}; "
                      + ("/31 links are excluded by this lab's conventional network/broadcast model. "
                         if prefix == 30 else f"/{prefix+1} would not fit. ")
                      + "RFC 4632 CIDR alignment; "
                      "gateway is the first usable address.",
        })
        cursor = end + 1
    return result
