"""Unit tests for SQL query builder parameter binding."""

from __future__ import annotations

import re

from backend.services import query as query_service


def test_asset_attr_values_update_parameter_alignment() -> None:
    """assetAttrValuesUpdate binds values to placeholders in the right order."""
    sql, params = query_service.build_query(
        "assetAttrValuesUpdate",
        asset_id="asset_1",
        attribute_id="attr_1",
        value="42",
    )

    names = re.findall(r":(\w+)", sql)
    assert names == [
        "p_asset",
        "p_attr",
        "p_value",
        "p_asset2",
        "p_attr2",
        "p_value2",
    ]
    assert list(zip(names, params)) == [
        ("p_asset", "asset_1"),
        ("p_attr", "attr_1"),
        ("p_value", "42"),
        ("p_asset2", "asset_1"),
        ("p_attr2", "attr_1"),
        ("p_value2", "42"),
    ]


def test_hierarchy_asset_tags_parameter_alignment() -> None:
    """hierarchyAssetTags binds placeholders in the expected order."""
    sql, params = query_service.build_query(
        "hierarchyAssetTags",
        asset_id="tomago_bess01",
        minutes=30,
        include_unmapped=True,
    )

    names = re.findall(r":(\w+)", sql)
    assert names == [
        "p_asset_id",
        "p_minutes",
        "p_asset_id2",
        "p_include_unmapped",
    ]
    assert list(zip(names, params)) == [
        ("p_asset_id", "tomago_bess01"),
        ("p_minutes", 30),
        ("p_asset_id2", "tomago_bess01"),
        ("p_include_unmapped", True),
    ]


def test_hierarchy_asset_tag_summary_parameter_alignment() -> None:
    """hierarchyAssetTagSummary binds lookback minutes correctly."""
    sql, params = query_service.build_query(
        "hierarchyAssetTagSummary",
        minutes=45,
    )

    names = re.findall(r":(\w+)", sql)
    assert names == ["p_minutes"]
    assert list(zip(names, params)) == [("p_minutes", 45)]
