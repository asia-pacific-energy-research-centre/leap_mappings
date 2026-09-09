# Considerations for creating ESTO Extended categories

**Status:** Maintainer workflow and design guide

**Editable authority:** `config/outlook_mappings_single_axis.xlsx`

**Source branch inventory:** `data/temp/new leap rows.xlsx`

**Review plans:** `data/temp/new demand branches remapping plan.xlsx`

This document records how new LEAP branches should become ESTO Extended
categories and how those categories should be connected to Ninth Outlook
categories. It is a review guide, not evidence that the present workbook,
generated candidates, subtotal flags, or synthetic ESTO Extended values are
correct.

## Current maintainer workflow

When adding a new ESTO Extended category, treat the category, its independent
axis mappings, and its valid exact pairs as one reviewed change:

1. Confirm that the LEAP branch represents meaningful detail not already
   represented by an ESTO category. Select an existing parent and review the
   complete sibling group. Category structure does not create historical
   values.
2. Edit only `config/outlook_mappings_single_axis.xlsx`. Add the flow relation
   to `leap_sector_to_esto` with `esto_dataset_scope = ESTO_EXTENDED`. Reuse an
   existing product-axis relation unless the fuel/product meaning is genuinely
   new. Add LEAP-to-Ninth or Ninth-to-ESTO relations only when those comparison
   directions have also been reviewed.
3. Complete exact-pair authority. First verify that the authoritative LEAP
   template or branch inventory contains a real new branch. Add source
   `(LEAP branch, fuel)` combinations to `extra_leap_key_pairs` only when that
   reviewed pair is not presently established by generated evidence. Add every
   defensible target `(ESTO Extended flow, product)` combination to
   `extra_esto_extended_pairs`. Add no other product merely because it exists
   elsewhere in ESTO.
4. Run the `generate` pipeline stage. Inspect
   `outputs/separate_axis_mapping_refresh/compiler/data/qa_axis_variables_without_pair_coverage.csv`,
   `outputs/separate_axis_mapping_refresh/workbooks/editable_duplicate_cleanup.json`,
   `outputs/separate_axis_mapping_refresh/compiler/data/qa_axis_components.csv`,
   `outputs/separate_axis_mapping_refresh/compiler/data/qa_many_to_many_axis_components.csv`,
   the regenerated workbooks, and
   `outlook_mappings_generation_manifest.json`. The coverage report names the
   exact `pair_sheet` to review. It proves that each axis variable occurs in at
   least one pair; it does not prove that every intended combination exists.
5. Rebuild `data/esto_extended_catalogue.csv` with
   `build_all_esto_extended_vintages()`. This is currently a separate step from
   `generate`. Verify that the intended pairs appear once and that no
   unintended products were introduced.
6. Run focused tests and Stages 1-3. Compare generated mappings, Common ESTO
   membership, and values with the prior baseline. Require source-once and
   value-preservation checks to pass, then commit the editable workbook and all
   regenerated tracked artifacts together.

From the repository root, the two structural build commands are:

```powershell
C:\Users\Work\miniconda3\python.exe codebase\run_mapping_pipeline.py --stages generate
C:\Users\Work\miniconda3\python.exe -c "from codebase.build_esto_extended_vintages import build_all_esto_extended_vintages; print(build_all_esto_extended_vintages())"
C:\Users\Work\miniconda3\python.exe codebase\run_mapping_pipeline.py --stages 1,2,3
```

The first command regenerates pair evidence and the compatibility master. The
second regenerates the consumer-facing structural catalogue. Until these are
combined in the pipeline, completing only the first command is incomplete for
an ESTO Extended category change.

### Worked example: PHEV medium and heavy trucks

The LEAP branches are:

```text
Freight road/Trucks/PHEV heavy
Freight road/Trucks/PHEV medium
```

Each branch has exactly four approved fuels: `Gas and diesel oil`,
`Biodiesel`, `Efuel`, and `Electricity`. Their ESTO Extended flows are:

```text
15.02.01.02.07 PHEV heavy truck
15.02.01.02.08 PHEV medium truck
```

The corresponding products are `07.07 Gas/diesel oil`, `16.06 Biodiesel`,
`16.11 E-fuel`, and `17 Electricity`. Therefore the reviewed change contains
eight LEAP source pairs and eight ESTO Extended target pairs: two flows times
four specifically approved products. It does not authorize either flow with
any other product. The independent axes describe the semantic translations;
the pair sheets constrain which combinations may actually compile. The eight
LEAP pairs are the intended source structure, not necessarily eight new
`extra_leap_key_pairs` rows: omit any extras already supplied by authoritative
generated LEAP evidence.

## 1. Keep four decisions separate

Creating an ESTO Extended row involves four different decisions:

1. **Category:** Does the LEAP branch represent a distinct semantic flow?
2. **Hierarchy:** Which ESTO or ESTO Extended parent contains that flow?
3. **Mappings:** Which LEAP and Ninth source pairs belong to that flow/product
   pair?
4. **Values:** Is there a defensible ESTO Extended historical value for the new
   category?

A valid category does not automatically justify a Ninth mapping or an
allocated historical value. Review each layer explicitly.

## 2. Create flows from semantic branches, not every workbook row

One semantic LEAP process, sector, vehicle, or technology branch creates one
candidate ESTO Extended flow. Its fuel leaves reuse that flow and map
independently to ESTO products.

For demand branches:

```text
Demand\Passenger road\LPVs\HEV small\Motor gasoline
```

the candidate flow is the semantic branch:

```text
Passenger road/LPVs/HEV small
```

and `Motor gasoline` maps separately to the ESTO product.

For transformation branches:

```text
Transformation\Electricity Generation\Processes\Coal_CCUS\
Feedstock Fuels\Sub bituminous coal
```

the candidate flow is:

```text
Electricity Generation/Processes/Coal_CCUS
```

`Processes`, `Feedstock Fuels`, `Auxiliary Fuels`, and `Output Fuels` are
structural containers. They do not create additional ESTO Extended flows.

## 3. Reuse existing ESTO categories where they are already exact

Before creating a new category, check whether the LEAP branch already has an
exact semantic home in the established ESTO hierarchy. If it does, add or
correct the mapping to that existing category.

Create a new ESTO Extended category only when the LEAP branch adds meaningful
detail below or beside the established ESTO category.

Imported electricity is a concrete example: it belongs to `02 Imports`, not to
a newly invented electricity-generation technology.

## 4. Every new category needs a reviewed parent

A new category must be placed below an existing ESTO or ESTO Extended parent.
Do not create detached top-level categories.

Examples:

- LPV drive/size categories belong below `Passenger road/LPVs`.
- Truck drive/weight categories belong below `Freight road/Trucks`.
- Detailed power processes belong below the reviewed power-process family.
- Detailed iron-and-steel routes belong below Iron and steel.

If the nearest mapped ancestor resolves to several possible parents or to a
rollup, stop and review the placement. Do not choose a parent from label
similarity alone.

## 5. Complete sibling groups

Do not map an arbitrary subset of the immediate children of a parent.

For each hierarchy boundary, use one of these complete treatments:

- map every immediate child using the reviewed detailed or coarse crosswalk;
- map only the parent where neither source can support a complete child
  crosswalk; or
- exclude the entire child group from a comparison axis when that source has no
  defensible counterpart.

This rule applies separately to LEAP-to-ESTO Extended, LEAP-to-Ninth, and
Ninth-to-ESTO Extended mappings.

Where the hierarchies differ, a blunt many-to-one classification is preferable
to leaving isolated siblings uncovered. Any one-to-many relationship still
needs an explicit review because it may duplicate source values or merge
otherwise distinct Common ESTO rows.

## 6. Confirmed transport crosswalk

### Vehicle classes

| Ninth category | LEAP / ESTO Extended category |
| --- | --- |
| Passenger car | LPV small |
| Passenger sports utility vehicle | LPV medium |
| Passenger light truck | LPV large |
| Passenger two-wheeler | Motorcycle |
| Freight two-wheeler | LCV |
| Freight light commercial vehicle | LCV |
| Medium truck | Truck medium |
| Heavy truck | Truck heavy |
| Bus | Bus |

### Drive types

| Ninth or LEAP drive type | Target treatment |
| --- | --- |
| BEV | BEV |
| FCEV where the target vehicle has an FCEV child | FCEV |
| FCEV where the target vehicle has no FCEV child | BEV |
| PHEV where the target vehicle has a PHEV child | PHEV |
| PHEV for buses and motorcycles, which have no PHEV child | BEV |
| PHEV for medium/heavy trucks | PHEV medium truck / PHEV heavy truck |
| HEV | ICE |
| EREV | PHEV |
| Diesel engine | ICE |
| Gasoline engine | ICE |
| Compressed natural gas | ICE |
| Liquefied petroleum gas | ICE |
| LNG | ICE |

Both Ninth gasoline-PHEV and diesel-PHEV branches can map to the same
size-specific or truck-size PHEV category where that category exists. The
fuel/product axis must preserve the reviewed product distinction. For the LEAP
truck example, the exact canonical targets are Gas/diesel oil, Biodiesel,
E-fuel, and Electricity.

The FCEV and PHEV fallback decisions apply only when the corresponding detailed
LEAP/ESTO Extended child does not exist. They do not replace a genuine FCEV or
PHEV child where one is present.

## 7. Stable category identifiers

Category codes and labels must remain stable in the maintained mapping
contract. Do not assign production identifiers by alphabetically sorting the
current sibling labels.

Rules:

- once assigned, a code is never renumbered;
- a new sibling receives the next unused identifier below its parent;
- renaming or correcting a display label does not create a new identifier;
- aliases point to the same identifier;
- adding an alphabetically earlier branch does not change existing identifiers;
- the maintained flow-axis relation records the source LEAP path and canonical
  ESTO Extended code/label;
- exact-pair authority is recorded separately in the applicable `extra_*`
  pair sheets; and
- parentage must be supported by the established coded hierarchy or an
  explicit reviewed hierarchy/rollup rule. An exact pair alone does not define
  a parent.

`data/esto_extended_catalogue.csv` is a generated, numeric-free consumer view
of the promoted mapping authority. It is not an editable identifier registry
and must not be used as the source from which mappings are maintained.

## 8. Aliases and legacy branches

Alternative names for the same process do not create separate additive
categories. Examples under review include:

- `Battery`, `Batteries`, and `Distributed storage`;
- `Solar_rooftop` and `Solar rooftop`.

Branches ending in `_do not use` are legacy or alternative structures and do
not create categories.

Where aliases may coexist in source data, add a reviewed source-selection or
fallback rule before treating them as one category.

## 9. Product mapping stays independent

The semantic branch determines the flow. The LEAP or Ninth fuel determines the
ESTO product.

Use the reviewed fuel/product crosswalk and repeated existing mappings as
evidence. Do not create a new product because of spelling, case, or punctuation
differences. Normalize or review differences such as:

- `Black liqour` versus `Black liquor`;
- `Petroleum Coke` versus `Petroleum coke`;
- `Natural Gas` versus `Natural gas`.

The source-side mapping label must match the normalized output of the LEAP
balance parser. The parser currently converts `Black liqour` to `Black liquor`,
`Fuelwood and woodwaste` to `Fuelwood & woodwaste`, and
`of which Photovoltaics` to `Solar photovoltaics`. It leaves the literal
`Solar` label unchanged.

Literal `Solar` is a reviewed exception: map it to ESTO
`12.99 Solar nonspecified` and to the sector-appropriate Ninth
nonspecified-solar category. This allocation is intentionally different from
assuming photovoltaics. The source inventory retains a `FOLLOW-UP` note asking
modellers to rename the branch to `Solar nonspecified` when practical.
`Black liqour` also retains a source follow-up even though the parser and
mapping workbook already use the corrected `Black liquor` spelling.

If a fuel has no reviewed ESTO product, leave that source pair unresolved for
human review rather than inventing a product.

## 10. Build the mapping directions in a controlled order

Use `config/outlook_mappings_single_axis.xlsx`; never edit
`leap_combined_esto`, `leap_combined_ninth`, or
`ninth_pairs_to_esto_pairs` in the generated compatibility master.

1. Add the reviewed LEAP-to-ESTO Extended flow-axis relation and reuse or add
   the necessary product-axis relations.
2. Add only the defensible exact LEAP and ESTO Extended pairs to their
   applicable `extra_*` sheets when generated evidence does not already supply
   them.
3. Complete the independent LEAP-to-Ninth axes when that comparison is in
   scope.
4. Complete the independent Ninth-to-ESTO axes and Ninth exact pairs when that
   comparison is in scope.
5. Run generation and check that the three compiled directions form a
   consistent triangle without fan-out or unintended combinations.

Planning workbooks are evidence and decision aids. Do not import them
automatically or treat them as maintained authority.

Rejected mappings are removed from the maintained mapping sheets. Do not retain
known-wrong rows with `duplicate_to_remove = True`.

## 11. Subtotal status follows the completed hierarchy

Structurally, a category with children is a subtotal and a leaf is not.
However, the existing mapping-sheet subtotal flags contain historical
assumptions and mistakes and are not authority for new rows.

For the present ESTO Extended work:

- derive the proposed structural status from the completed category tree;
- review whole sibling groups together;
- record proposed mapping-sheet flags for review;
- do not use an empty subtotal-mismatch QA file as proof that the flags are
  semantically correct.

The workbook-wide subtotal rebuild is tracked separately as MAPQ-030.

## 12. Do not invent ESTO Extended historical values

Category creation and value creation are separate.

- LEAP values may map directly into the new category.
- Ninth values may map through the reviewed coarse crosswalk.
- Do not use automatic equal splitting of an ESTO parent as a production
  allocation rule.
- Parent-minus-known-children is acceptable only when the contributor set is
  complete and the calculation is explicitly defined.
- Otherwise the category may exist structurally without fabricated ESTO
  historical values.

`build_esto_extended_test.py` is historical/test scaffolding, not category,
pair, or value authority. Do not add production mappings there.

## 13. Validation before adoption

Before editing the maintained workbook:

- freeze the reviewed source inventories;
- generate an exact row-level proposed change set;
- perform the required lossless workbook round-trip proof;
- back up the workbook;
- review additions, replacements, and removals by domain.
- require new Boolean cells to contain actual `TRUE` or `FALSE` values, retain
  the ordinary unfilled surrounding style, and add no checkbox controls or
  other special formatting.

After each reviewed domain:

- check registry code uniqueness and parent existence;
- check complete immediate-sibling coverage;
- check for orphaned or duplicated categories;
- check the LEAP/Ninth/ESTO Extended triangle;
- check raw and rollup-aware mapping cardinality;
- check parent-versus-child and source-total preservation;
- confirm no rejected rows remain in the maintained mapping sheets.
- reopen and inspect every edited Boolean column; require actual Boolean values
  displayed as ordinary `TRUE` or `FALSE`, with no checkbox controls,
  black/solid fills, masked values, text substitutes, or required blanks.

Only after the structural review is clean should the full value pipeline and
downstream `leap_initialisation` and dashboard checks be run.

## 14. Open considerations

The following still need explicit review:

- how parent-only Electricity, CHP, and Heat output rows should relate to
  detailed process children;
- whether the coded hierarchy needs a dedicated maintained parent/alias
  registry beyond the current flow-axis and rollup authorities;
- which new categories can receive defensible ESTO historical values and which
  should remain structural or LEAP/Ninth-only;
- all proposed subtotal flags, pending the separate workbook-wide review.

## 15. Mapping implementation checkpoint: 2026-07-28

This is historical context, not the current editing procedure. The first
reviewed implementation pass was applied to the now-retired
`config/outlook_mappings_master todo.xlsx`; subsequent maintenance was moved to
`config/outlook_mappings_single_axis.xlsx` and generated outputs.

Completed treatments:

- split the new `Agriculture` and `Fishing` branches to their exact ESTO and
  Ninth children;
- mapped the renamed `Non energy use` and `Non specified others` branches;
- completed the new Buildings branches;
- repaired the shifted Buildings product block and physically removed the one
  wrong row that would otherwise duplicate the correct Bagasse row;
- completed the LEAP transport mappings and the non-zero, non-subtotal
  Ninth-to-ESTO Extended transport bridge using the confirmed vehicle and drive
  rules;
- removed the rejected CHP/heat direct fan-out rows;
- replaced them with one combined main-activity/autoproducer target per
  process;
- implemented explicit non-expanding Other + solid-biomass boundaries:
  `09_02_04_biomass + 09_02_05_others` for CHP,
  `09_x_04_biomass + 09_x_05_others` for heat, and
  `09_01_06_biomass + 09_01_10_otherrenewable +
  09_01_11_otherfuel` for electricity generation;
- left the three detailed iron-and-steel routes absent from the Ninth axes, as
  decided;
- treated `_do not use` power branches as legacy and left them unmapped.
- aligned mapping keys with the parser's normalized fuel spellings, mapped the
  literal `Solar` label to Solar nonspecified, and retained source-inventory
  follow-up warnings for modeller cleanup;

The historical power-process identifier constants in
`codebase/mapping_tools/build_esto_extended_test.py` remain technical debt and
test compatibility only. New production categories and exact pairs belong in
the single-axis workbook, and the structural catalogue is regenerated from the
promoted mapping master.

The municipal-waste source-boundary decision is now explicit. The combined
`Municipal solid waste non and renewable` branch under
`Electricity Generation/Processes/Others` has been removed from
`data/temp/new leap rows.xlsx` and remains unmapped. The separately supplied
renewable and non-renewable branches remain and map to their corresponding
ESTO and Ninth products. This avoids both an arbitrary product choice and
double counting.
