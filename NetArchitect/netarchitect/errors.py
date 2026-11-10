class PlanningError(ValueError):
    """An input cannot produce a valid supported plan."""


class PhysicalDistanceViolationError(PlanningError):
    """The selected medium cannot carry this link over its stated distance."""


class AddressSpaceExhaustionError(PlanningError):
    """The root address block cannot hold the requested subnets."""
