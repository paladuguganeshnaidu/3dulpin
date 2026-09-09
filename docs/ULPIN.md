# 3D ULPIN (project-specific)

> **Not the officially adopted national ULPIN format.** This is this project's
> deterministic demonstration identifier. Do not present it as legal identity.

## Format

```
IN3D-<STATE>-<DISTRICT>-<PARCEL>-<KIND>-<SEQ:4>-V<VER>-<CHECK:2>
```

Example: `IN3D-KA-BLR-P00042-U-0012-V1-7F`

- STATE/DISTRICT: fixed-area codes (e.g. `KA`, `BLR` — project demo codes).
- PARCEL: stable surveyor parcel key (base identity). No personal data.
- KIND: one-letter type code (P parcel, B building, F floor, U unit, M basement,
  K parking, G underground, V volume).
- SEQ: stable per-(parcel,kind) sequence.
- V<VER>: identity version.
- CHECK: 2-char SHA-256 checksum over stable inputs + salt.

## Properties

- **Deterministic**: identical inputs ⇒ identical identifier.
- **Unique** for distinct (parcel, kind, sequence, version).
- **No embedded personal/ownership data.**
- **Checksummed** and structurally validated.
- Identity lives in `ulpin_records`, separate from geometry, ownership,
  provenance and approval state; geometry edits bump `version` (V1→V2…) without
  inventing new identity.

## Engine functions

- `generate_3d_ulpin(parcel_no, kind, sequence, state_code, district_code, version, salt)`
- `validate_3d_ulpin(ulpin)`
- `parse_3d_ulpin(ulpin)`
- `version_3d_ulpin(ulpin, new_version)`
- registry `lookup` via `GET /api/v1/ulpin/{ulpin}`

Salt is configurable (default dev salt); production should set a per-deployment
secret so external parties cannot reproduce identifiers.
