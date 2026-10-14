"""Versioned action contract for the evaluation's finite tool registry (ADR-008)."""

from dataclasses import dataclass

VERSION = 1
# Registry entries describe tool capability, not the caller's authorization.
TOOLS = {
    "cantonal_registry_query": ("read", "cantonal_registry"),
    "cantonal_registry_admin": ("admin", "cantonal_registry"),
    "db_readonly_query": ("read", "db-readonly", "db-write"),
    "db_write_query": ("write", "db-write"),
    "swiss_tax_lookup": ("read", "swiss-tax"),
}


@dataclass(frozen=True)
class Action:
    tool: str
    operation: str
    namespace: str
    resource_type: str
    identifier: str
    version: int = VERSION

    @property
    def resource(self) -> str:
        return f"{self.namespace}:{self.resource_type}:{self.identifier}"


def validate_action(tool: str, resource: str) -> Action:
    if not isinstance(tool, str) or tool not in TOOLS:
        raise ValueError("unknown tool")
    if not isinstance(resource, str):
        raise ValueError("resource must be a string")
    parts = resource.split(":", 2)
    if len(parts) != 3 or any(not part or part.strip() != part for part in parts):
        raise ValueError("resource must be namespace:type:identifier")
    namespace, kind, identifier = parts
    if namespace not in TOOLS[tool][1:]:
        raise ValueError("tool cannot address this resource namespace")
    if ":" in identifier or "*" in identifier or any(ord(c) < 32 for c in resource):
        raise ValueError("ambiguous resource identifier")
    return Action(tool, TOOLS[tool][0], namespace, kind, identifier)
