# ML / AI

## Model registry

`backend/app/ml/registry.py` exposes metadata for each component
(name, version, source, license, input, output, confidence semantics,
availability). Deterministic heuristics are always available; the heavy
`building_extraction` adapter is disabled unless
`ML_BUILDING_MODEL_ENABLED=true` and is **lazy-loaded** (never downloaded at
startup).

## Assistive analysis (AI Analyse)

`backend/app/ml/analysis.py` runs over the current dataset and reports:

- counts (objects/buildings/ai-candidates/anomalies),
- existing `ai_derived` candidates + confidence + verification state,
- height & floor estimates with explicit **method** and **confidence**,
- rule-based anomalies with plain-language messages.

Everything returned is explicitly non-authoritative and recommends human
verification.

## Building extraction (optional path)

Image/orthophoto → pretrained segmentation → masks → polygon extraction →
geometry cleanup → candidate footprints with confidence → **human verification**.
This mirrors the SIH intent while keeping the MVP honest: it is optional and
never implied to be a legal boundary.

## Floor segmentation

- PATH A: explicit floors from surveyor/import (confidence 1.0).
- PATH B: estimated levels from height/floor-count (confidence 0.5, marked
  estimated, requires verification). We do not claim to recover apartment
  boundaries from a photograph.

## Height estimation

metadata > DSM/DEM (roof − ground) > floor-count estimate; method + confidence
are always returned. No invented precision.

## Anomaly detection

Deterministic GIS rules first (extreme height, impossible z, tiny footprint,
overlap via topology engine, child outside parent). ML only where it adds value.
