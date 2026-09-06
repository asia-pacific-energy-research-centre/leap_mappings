# AUS Buildings ESTO child preservation

Status: implementation verified; end-to-end dashboard regeneration pending.

## Problem

Published AUS ESTO Residential values for gas/diesel oil and gas works gas
were present in earlier historical years but zero at the latest endpoint. The
Common ESTO relevance step treated the endpoint as authority for the entire
time series and removed those valid historical observations. Separately, a
portable run could extract Extended rows without access to the matching native
ESTO table and inherit a synthetic subtotal classification for Residential.

## Permanent contract

- Any nonzero published source fact remains relevant in its observed year.
- Relevance-only vintage files keep their latest-endpoint semantics and cannot
  delete facts from the selected source issue.
- Extended exact-row extraction receives the matching native ESTO table
  explicitly and restores native subtotal status before leaf selection.
- AUS Buildings history must reconcile as 16.01 Services plus 16.02
  Residential without a retained 16.01-16.02 parent segment.

## Verification

- Focused relevance, native-classification, and portable-wiring regressions.
- Contained 2026 AUS exact-row reproduction confirms both affected Residential
  product pairs remain relevant after the change.
