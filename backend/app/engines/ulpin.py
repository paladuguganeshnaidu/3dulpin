"""3D ULPIN engine (project-specific, deterministic, non-authoritative).

IMPORTANT: The identifier produced here is a *project-specific demonstration*
extension. It is NOT claimed to be the officially adopted national ULPIN
format. See docs/ULPIN.md for the full conceptual model.

Architecture of the identifier:

    <BASE IDENTITY>  +  <3D EXTENSION>  +  <STABLE SEQUENCE/TYPE>  +  <VERSION>  +  <CHECKSUM>

Example:
    IN3D-KA-BLR-P00042-B-0012-V1-7F

Base parcel identity is a stable, surveyor-supplied parcel key
(state + district + parcel number). No personal data is embedded. The checksum
is derived deterministically (SHA-256 over a stable secret + inputs), so the
same stable inputs always produce the same 3D ULPIN.

Identity is stored separately from geometry, ownership, provenance and approval
state -- see docs/DATA_MODEL.md.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from ..core.enums import PropertyType

# Default development salt. Override via env ULPIN_SALT in production so that
# identifiers cannot be reproduced externally. Determinism is per-deployment.
DEFAULT_ULPIN_SALT = "3dulpin-dev-salt-do-not-use-in-prod"

# kind codes mapped from PropertyType
KIND_CODES: dict[PropertyType, str] = {
    PropertyType.PARCEL: "P",
    PropertyType.BUILDING: "B",
    PropertyType.FLOOR: "F",
    PropertyType.UNIT: "U",
    PropertyType.BASEMENT: "M",  # M for "middle/below" marker
    PropertyType.PARKING: "K",
    PropertyType.UNDERGROUND_ASSET: "G",
    PropertyType.VOLUME: "V",
}

VALID_TYPE_CODES = set(KIND_CODES.values())

# parcel codes are 5-6 alnum, kind 1 char, seq 4 digits, version int, checksum 2
ULPIN_RE = re.compile(r"^IN3D-([A-Z0-9]{2})-([A-Z0-9]{2,6})-([A-Z0-9]{2,12})-([A-Z])-(\d{4})-V(\d+)-([0-9A-Z]{2})$")


@dataclass(frozen=True)
class UlpinInputs:
    state_code: str  # e.g. "KA"
    district_code: str  # e.g. "BLR"
    parcel_no: str  # stable surveyor parcel key e.g. "P00042"
    kind: PropertyType | str  # PropertyType or its one-letter code
    sequence: int  # stable per-kind sequence on this parcel (>=0)
    version: int = 1


def _norm_parcel_no(parcel_no: str) -> str:
    """Normalize parcel keys: upper + keep [A-Z0-9] only, cap length 12."""
    cleaned = re.sub(r"[^A-Z0-9]", "", parcel_no.upper())
    if not cleaned:
        raise ValueError("parcel_no must contain at least one letter/digit.")
    return cleaned[:12]


def _norm_area_code(code: str, length: int) -> str:
    cleaned = re.sub(r"[^A-Z0-9]", "", (code or "").upper())
    if not cleaned:
        raise ValueError("state/district code is required.")
    return cleaned[:length]


def _kind_code(kind: PropertyType | str) -> str:
    if isinstance(kind, PropertyType):
        return KIND_CODES[kind]
    c = str(kind).upper().strip()
    if c in VALID_TYPE_CODES:
        return c
    for pt, code in KIND_CODES.items():
        if pt.value.lower() == c.lower():
            return code
    raise ValueError(f"Unknown property kind: {kind!r}")


def _base_key(parcel_no: str, state_code: str, district_code: str) -> str:
    return f"{_norm_area_code(state_code, 2)}-{_norm_area_code(district_code, 6)}-{_norm_parcel_no(parcel_no)}"


def _checksum(base: str, kind: str, sequence: int, version: int, salt: str) -> str:
    payload = f"{base}|{kind}|{sequence:04d}|V{version}|{salt}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()
    # map hex to [0-9A-Z] alphabet for a compact 2-char checksum
    table = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ints = [int(digest[i : i + 2], 16) for i in (0, 2)]
    return "".join(table[v % 36] for v in ints)


def generate_3d_ulpin(
    parcel_no: str,
    kind: PropertyType | str,
    sequence: int,
    *,
    state_code: str = "KA",
    district_code: str = "BLR",
    version: int = 1,
    salt: str | None = None,
) -> str:
    """Deterministically generate a 3D ULPIN for the given stable inputs.

    Same inputs (parcel, kind, sequence, version, area codes, salt) always
    yield the same identifier.
    """
    if sequence < 0 or sequence > 9999:
        raise ValueError("sequence must be in [0, 9999].")
    if version < 1:
        raise ValueError("version must be >= 1.")
    if not salt:
        salt = DEFAULT_ULPIN_SALT
    base = _base_key(parcel_no, state_code, district_code)
    kind_c = _kind_code(kind)
    cs = _checksum(base, kind_c, sequence, version, salt)
    return f"IN3D-{base}-{kind_c}-{sequence:04d}-V{version}-{cs}"


def validate_3d_ulpin(value: str) -> bool:
    """Structural validation of a project 3D ULPIN string."""
    if not isinstance(value, str):
        return False
    return bool(ULPIN_RE.match(value.strip().upper()))


def checksum_valid(ulpin: str, *, salt: str | None = None) -> bool:
    """Verify the checksum portion of a 3D ULPIN (format + determinism)."""
    if not validate_3d_ulpin(ulpin):
        return False
    state, district, parcel, kind, seq_s, ver_s, cs = _split(ulpin)
    if not salt:
        salt = DEFAULT_ULPIN_SALT
    expected = _checksum(
        _base_key(parcel, state, district), kind, int(seq_s), int(ver_s), salt
    )
    return expected == cs.upper()


def _split(ulpin: str) -> tuple[str, str, str, str, str, str, str]:
    body = ulpin.strip().upper()
    m = ULPIN_RE.match(body)
    if not m:
        raise ValueError(f"Not a valid 3D ULPIN: {ulpin}")
    return m.groups()  # state, district, parcel, kind, seq, ver, checksum


def parse_3d_ulpin(ulpin: str) -> dict:
    """Parse a valid 3D ULPIN into its components (non-authoritative)."""
    state, district, parcel, kind, seq, ver, cs = _split(ulpin)
    return {
        "ulpin": ulpin.strip().upper(),
        "state_code": state,
        "district_code": district,
        "parcel_no": parcel,
        "kind_code": kind,
        "sequence": int(seq),
        "version": int(ver),
        "checksum": cs,
    }


def version_3d_ulpin(ulpin: str, new_version: int, *, salt: str | None = None) -> str:
    """Produce the same identity at a new version number."""
    parsed = parse_3d_ulpin(ulpin)
    return generate_3d_ulpin(
        parsed["parcel_no"],
        parsed["kind_code"],
        parsed["sequence"],
        state_code=parsed["state_code"],
        district_code=parsed["district_code"],
        version=new_version,
        salt=salt,
    )


def kind_from_type(property_type: PropertyType) -> str:
    return _kind_code(property_type)
