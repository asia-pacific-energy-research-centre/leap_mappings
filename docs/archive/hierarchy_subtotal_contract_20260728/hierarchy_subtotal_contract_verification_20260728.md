# Hierarchy/subtotal contract verification — 2026-07-28

## Inputs

| Input | SHA-256 |
| --- | --- |
| `config/outlook_mappings_master.xlsx` (pre-existing dirty canonical workbook; not written) | `833CBA8E40D343AB2A21637933FB49FFBDECD5B36FC0021DD776E1EE66369BD6` |
| `config/outlook_mappings_master todo.xlsx` (MAPQ-030 review base) | `61352BB53910F65738A075497965CAF15C4B40FF5021AA5E6A31DB3B1903EE6E` |
| `config/mapping_issue_exception_sets.xlsx` | `49ED0859CEF5A0140CFE1C0CCE120645C1B2222D50867643174E9A7A41877ED6` |
| `data/00APEC_2025_low_with_subtotals.csv` | `B8685B566F348A90D3D8FA8279DECB909F04ABFB5140FCB9563E04CDEC54E8C3` |
| `data/merged_file_energy_ALL_20251106.csv` | `B99869AD28EDF8EA8D08EC0738D6EEB007EB0FD7527C2B27F6948589C818CC8D` |
| `data/temp/new leap rows.xlsx` | `0BF3D9D569C45C6DFF00E75B0B8D32FAEA4155C38E5810AA398187520DB4F520` |

Selected structural build ID:
`268ceec95fe1ff4cd0264b82fb4ae7db7d9cb1d349e1a0e01f2d02bd7f1dae5e`.

## Commands and results

```powershell
C:\Users\Work\miniconda3\python.exe -m pytest `
  tests\test_hierarchy_subtotal_contract.py `
  tests\test_build_dataset_tree_structure.py::test_ninth_structural_parenthood_does_not_depend_on_subtotal_results -q
```

Result: `8 passed`.

The pre-change focused baseline was `63 passed, 1 failed`. The known failure is
`test_leap_validation_excludes_base_year_and_uses_full_paths`: the validator
reports `leaf_only_unambiguous` where the test expects `full_path`. This
failure pre-dated MAPQ-030 and was not changed.

The real contract build strictly reloaded its own manifest and all member
hashes. The review summary is:

| Metric | Count |
| --- | ---: |
| Canonical pairs | 9,121 |
| Workbook cells inspected | 17,668 |
| Proposed cell changes | 3,410 |
| Pairs with conflicting current cross-sheet flags | 520 |
| Unresolved canonical pairs | 1,055 |
| Enabled subtotal exception rows audited | 2,960 |

The review workbook was formula-error scanned and visually rendered sheet by
sheet. It is a proposal artifact only. No mapping or exception workbook was
modified.

## Known limitations and decisions still required

1. The full 21-economy LEAP template/model-tree policy is MAPQ-032 and remains
   unresolved. Current LEAP nodes are explicitly partial.
2. No authoritative LEAP fuel hierarchy is available. Contract review rows
   do not guess aggregate fuel parenthood.
3. Real Ninth conformance evidence is bounded to 2022, 2023, 2050, and 2070
   to keep the published diagnostic narrow. The function accepts `years=None`
   for a full-year diagnostic run.
4. The canonical mapping workbook and exception workbook require human review
   before any proposed values or exception dispositions are applied.
5. The dirty dashboard Mapping diagnostics changes were preserved. The new
   loader and structural/additivity helper are ready to be wired into that
   surface after its owner reconciles the active diff.
6. Stages 1–3 and workbook exact-cell verification cannot be meaningful until
   the reviewed changes are approved and applied.
