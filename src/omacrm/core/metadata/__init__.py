from omacrm.core.metadata.defs import EntityDef, FieldDef
from omacrm.core.metadata.registry import MetadataRegistry, registry

__all__ = ["EntityDef", "FieldDef", "MetadataRegistry", "registry"]

# Importing built-in definitions registers them with the registry.
from omacrm.core.metadata import entities  # noqa: E402,F401
