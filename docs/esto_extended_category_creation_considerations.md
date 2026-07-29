# Considerations for creating ESTO Extended categories

**Status:** Working design and review guide

**Primary workbook base:** `config/outlook_mappings_master todo.xlsx`

**Source branch inventory:** `data/temp/new leap rows.xlsx`

**Review plans:** `data/temp/new demand branches remapping plan.xlsx`

This document records how new LEAP branches should become ESTO Extended
categories and how those categories should be connected to Ninth Outlook
categories. It is a review guide, not evidence that the present workbook,
generated candidates, subtotal flags, or synthetic ESTO Extended values are
correct.

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
| PHEV for buses, motorcycles, and medium/heavy trucks, which have no PHEV child | BEV |
| HEV | ICE |
| EREV | PHEV |
| Diesel engine | ICE |
| Gasoline engine | ICE |
| Compressed natural gas | ICE |
| Liquefied petroleum gas | ICE |
| LNG | ICE |

Both Ninth gasoline-PHEV and diesel-PHEV branches can map to the same
size-specific PHEV category where that category exists. The fuel/product axis
must preserve the gasoline, diesel, biodiesel, electricity, or other product
distinction.

The FCEV and PHEV fallback decisions apply only when the corresponding detailed
LEAP/ESTO Extended child does not exist. They do not replace a genuine FCEV or
PHEV child where one is present.

## 7. Stable category identifiers

Category codes must come from an explicit, persistent ESTO Extended registry.
Do not assign production identifiers by alphabetically sorting the current
sibling labels.

Rules:

- once assigned, a code is never renumbered;
- a new sibling receives the next unused identifier below its parent;
- renaming or correcting a display label does not create a new identifier;
- aliases point to the same identifier;
- adding an alphabetically earlier branch does not change existing identifiers;
- the registry records the source LEAP path, parent category, category code,
  canonical label, aliases, and review status.

The registry's final maintained location still needs to be chosen. A
configuration CSV is preferable to a generated results file because mappings
and category codes must remain stable across runs.

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

Use the todo workbook as the current base.

1. Add the reviewed exact LEAP-to-ESTO Extended relationships to
   `leap_combined_esto`.
2. Complete the coarse LEAP-to-Ninth crosswalk in `leap_combined_ninth`.
3. Add the matching complete Ninth-to-ESTO Extended crosswalk in
   `ninth_pairs_to_esto_pairs`.
4. Check that the three directions form a consistent triangle.

The planning workbook is evidence and a decision aid. Do not import it
automatically.

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

The equal-split behaviour in `build_esto_extended_test.py` is test scaffolding,
not an approved production rule.

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
- the maintained location and initial contents of the stable category registry;
- which new categories can receive defensible ESTO historical values and which
  should remain structural or LEAP/Ninth-only;
- all proposed subtotal flags, pending the separate workbook-wide review.

## 15. Mapping implementation checkpoint: 2026-07-28

The first reviewed implementation pass was applied to
`config/outlook_mappings_master todo.xlsx`.

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

The power-process identifier registry is currently explicit in
`codebase/mapping_tools/build_esto_extended_test.py`. This prevents
alphabetical renumbering and makes aliases share one identifier, but a later
cleanup may move the registry to maintained configuration without changing any
assigned identifiers.

The municipal-waste source-boundary decision is now explicit. The combined
`Municipal solid waste non and renewable` branch under
`Electricity Generation/Processes/Others` has been removed from
`data/temp/new leap rows.xlsx` and remains unmapped. The separately supplied
renewable and non-renewable branches remain and map to their corresponding
ESTO and Ninth products. This avoids both an arbitrary product choice and
double counting.
