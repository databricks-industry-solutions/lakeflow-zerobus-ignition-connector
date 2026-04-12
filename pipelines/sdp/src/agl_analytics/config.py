"""Pipeline catalog/schema configuration.

Hardcoded to match pipeline settings: catalog=ot_demo, schema=ot.
"""

# Pipeline target catalog and schema (from pipeline settings)
CATALOG = "ot_demo"
SCHEMA = "ot"


def catalog() -> str:
    """Return the pipeline target catalog."""
    return CATALOG


def schema() -> str:
    """Return the pipeline target schema."""
    return SCHEMA


def table(name: str) -> str:
    """Fully qualified table name in pipeline catalog.schema."""
    return f"{CATALOG}.{SCHEMA}.{name}"
