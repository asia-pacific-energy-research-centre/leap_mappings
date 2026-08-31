from __future__ import annotations

import pandas as pd
import pytest

from codebase.utilities.leap_results_dashboard_utils import (
    _leap_sibling_allocation_shares,
)


def test_sibling_shares_conserve_parent_by_fuel_and_depth() -> None:
    rows = pd.DataFrame(
        [
            {
                "source": "leap",
                "scenario": "Target",
                "fuel_label": fuel,
                "year": 2022,
                "effective_parent_name": "15.02 Road",
                "min_sector_depth": depth,
                "sheet": sheet,
                "value": value,
            }
            for fuel, depth, sheet, value in [
                ("Motor gasoline", 3, "Passenger road", 60.0),
                ("Motor gasoline", 3, "Freight road", 40.0),
                ("Motor gasoline", 5, "LPV ICE", 45.0),
                ("Motor gasoline", 5, "LCV ICE", 30.0),
                ("Motor gasoline", 5, "Truck ICE", 25.0),
                ("Electricity", 3, "Passenger road", 8.0),
                ("Electricity", 3, "Freight road", 2.0),
                ("Electricity", 5, "LPV BEV", 7.0),
                ("Electricity", 5, "Truck BEV", 3.0),
            ]
        ]
    )
    shares = _leap_sibling_allocation_shares(
        rows,
        ["scenario", "fuel_label", "year", "effective_parent_name"],
    )

    totals = shares.groupby(
        ["scenario", "fuel_label", "year", "effective_parent_name", "min_sector_depth"]
    )["detail_share"].sum()
    assert list(totals) == pytest.approx([1.0, 1.0, 1.0, 1.0])
    assert shares.loc[shares["sheet"].eq("LPV ICE"), "detail_share"].item() == pytest.approx(0.45)
    assert shares.loc[shares["sheet"].eq("LPV BEV"), "detail_share"].item() == pytest.approx(0.70)

