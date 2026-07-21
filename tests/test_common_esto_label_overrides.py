"""Tests for config-owned common ESTO display-label overrides."""

import pandas as pd
import pytest

from codebase.mapping_tools.build_common_esto_structure import apply_configured_axis_label_overrides


def test_flow_label_override_relabels_only_the_matching_component_partition() -> None:
    lookup_df = pd.DataFrame(
        [
            {
                "partition_label": "10.01.13,10.01.17 Losses and own use",
                "partition_components": "10.01.13 Pump storage plants|10.01.17 Non-specified own uses",
                "partition_created_by": "axis_partition_closure",
            }
        ]
    )
    overrides_df = pd.DataFrame(
        [
            {
                "enabled": True,
                "comparison_scope": "",
                "auto_common_flow_label": "10.01.13,10.01.17 Losses and own use",
                "component_esto_flows": "10.01.13 Pump storage plants|10.01.17 Non-specified own uses",
                "preferred_common_flow_label": "10.01.13,10.01.17 Pump storage and non-specified own uses",
            }
        ]
    )

    result = apply_configured_axis_label_overrides(
        lookup_df,
        overrides_df,
        axis="flow",
        comparison_scope="esto_leap",
    )

    assert result.loc[0, "partition_label"] == "10.01.13,10.01.17 Pump storage and non-specified own uses"
    assert result.loc[0, "partition_created_by"] == "config_label_override"


def test_enabled_override_warns_when_the_expected_partition_is_not_present() -> None:
    lookup_df = pd.DataFrame(
        [{"partition_label": "10.01.17 Non-specified own uses", "partition_components": "10.01.17 Non-specified own uses"}]
    )
    overrides_df = pd.DataFrame(
        [{"enabled": "true", "comparison_scope": "", "auto_common_flow_label": "missing label", "preferred_common_flow_label": "replacement"}]
    )

    with pytest.warns(RuntimeWarning, match="did not match a final partition"):
        result = apply_configured_axis_label_overrides(
            lookup_df,
            overrides_df,
            axis="flow",
            comparison_scope="esto_leap",
        )

    assert result.loc[0, "partition_label"] == "10.01.17 Non-specified own uses"
