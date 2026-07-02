"""
Verifier - Claude as Supervisor
================================
After any AI (Gemini, OpenAI, or even Claude itself) returns an answer,
the verifier checks it against the locally-extracted FactsManifest before
it is allowed to leave the system.

The verifier does NOT call an AI by default - it runs deterministic checks:

  1. Every numeric claim → must match a Fact in the manifest (within tolerance)
                            OR have a derivation field with formula + inputs
                            we can recompute locally
  2. Every derivation     → recomputed in pure Python, must match within ±0.1%
  3. Domain rules         → checked against AISC tables, Houston calibration
  4. Schema compliance    → response must match the requested JSON schema
  5. Confidence floor     → any field with confidence < 0.7 → UNVERIFIED tag

If the deterministic checks pass, the verifier returns APPROVED.
If they fail, it produces precise findings the corrector can use.

Optionally, for ambiguous cases, the verifier can call Claude (the supervisor)
to make a judgment call - but Claude is constrained to only APPROVE / REJECT
based on evidence, never to invent a missing answer.
"""

from dataclasses import dataclass, field
from typing import Any

from .intake import FactsManifest


@dataclass
class VerifierVerdict:
    status:    str            # APPROVED | NEEDS_CORRECTION | ESCALATE | REJECT
    score:     float          # 0.0-1.0
    findings:  list[str] = field(default_factory=list)
    verified_facts:   list[dict] = field(default_factory=list)
    unverified_facts: list[dict] = field(default_factory=list)


# AISC canonical: weight per foot is the number after the X
def _aisc_weight_per_foot(designation: str) -> float | None:
    """W14X82 → 82.0, HSS6X4X1/4 → None (HSS uses different rule)."""
    import re
    m = re.match(r"^W\d+X(\d+(?:\.\d+)?)$", designation.upper().replace(" ", ""))
    if m:
        return float(m.group(1))
    return None


def _recompute_derivation(formula: str, inputs: dict) -> float | None:
    """Safely recompute a derivation. Returns None if formula uses anything
    other than basic arithmetic on the supplied inputs."""
    import re
    # Allow only: input names (a-zA-Z_), digits, operators, parens, decimal points
    if not re.match(r"^[a-zA-Z_0-9+\-*/().\s]+$", formula):
        return None
    safe_globals = {"__builtins__": {}}
    try:
        return float(eval(formula, safe_globals, {k: float(v) for k, v in inputs.items()}))
    except Exception:
        return None


def _walk_claims(obj: Any, path: str = "$") -> list[tuple[str, Any]]:
    """Walk a JSON response and yield (path, claim_dict) for every numeric
    claim - defined as any dict with a 'value' key."""
    out = []
    if isinstance(obj, dict):
        if "value" in obj:
            out.append((path, obj))
        for k, v in obj.items():
            out.extend(_walk_claims(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(_walk_claims(v, f"{path}[{i}]"))
    return out


# Metadata keys that legitimately hold raw numeric values (not claims).
# Anything else MUST be wrapped in a claim object {value, confidence, derivation?}.
# These are STRUCTURAL keys (response shape), not factual claims. "weight" is
# explicitly NOT here because every weight in a structural steel system is a
# factual claim that needs verification.
_CLAIM_METADATA_KEYS: frozenset[str] = frozenset({
    "confidence", "score", "probability",  # claim metadata
    "page", "line", "row", "col",          # document position
    "count", "index", "rank",              # structural counters
})


def _find_naked_numerics(obj: Any, path: str = "$",
                         inside_claim: bool = False) -> list[tuple[str, Any]]:
    """Find numeric leaf values that are NOT inside a claim wrapper and NOT
    in the metadata-key whitelist. Used to catch the v3.5.2 regression where
    flat {tonnage: 9999} responses bypassed verification entirely."""
    out = []
    if isinstance(obj, dict):
        if "value" in obj:
            # This dict IS a claim. Descend, but mark inside_claim for nested fields.
            for k, v in obj.items():
                if k == "value":
                    continue  # the claim's own value is handled by _walk_claims
                out.extend(_find_naked_numerics(v, f"{path}.{k}", inside_claim=True))
            return out
        for k, v in obj.items():
            if k in _CLAIM_METADATA_KEYS:
                continue
            out.extend(_find_naked_numerics(v, f"{path}.{k}", inside_claim))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(_find_naked_numerics(v, f"{path}[{i}]", inside_claim))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        if not inside_claim:
            out.append((path, obj))
    return out


def auto_wrap_response(
    obj: Any,
    default_confidence: float = 0.5,
    default_source: str = "auto_wrap_migration",
) -> Any:
    """Recursively convert a flat-value response into a claim-wrapped one.

    Use this from bridge-internal callers that synthesize responses outside
    the AI provider path (e.g., calculator output, fixture data, programmatic
    Bridge methods). It walks the structure and wraps any naked numeric leaf
    in a {value, confidence, source} object so the verifier engages on it.

    Numerics under metadata keys (page, line, count, confidence, etc.) are
    left as-is - they are structural, not factual claims.

    Already-wrapped claims (dicts containing a "value" key) are passed through
    unchanged. This makes the helper idempotent - running it on a partially
    migrated response is safe.

    Default confidence is 0.5 because an auto-wrap with no provenance is by
    definition unverified; the verifier will flag it as no_provenance unless
    the caller also supplies a matching FactsManifest entry.
    """
    return _auto_wrap_walk(obj, default_confidence, default_source, inside_claim=False)


def _auto_wrap_walk(obj: Any, conf: float, src: str, inside_claim: bool) -> Any:
    if isinstance(obj, dict):
        if "value" in obj:
            # Already wrapped - pass through, but recurse into siblings to
            # wrap any nested leaves they might contain.
            return {k: (_auto_wrap_walk(v, conf, src, inside_claim=True)
                        if k != "value" else v)
                    for k, v in obj.items()}
        return {
            k: (v if k in _CLAIM_METADATA_KEYS
                else _auto_wrap_walk(v, conf, src, inside_claim))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_auto_wrap_walk(v, conf, src, inside_claim) for v in obj]
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        if inside_claim:
            return obj
        return {"value": obj, "confidence": conf, "source": src}
    return obj


def verify_response(
    response: dict,
    manifest: FactsManifest,
    schema:   dict | None = None,
    confidence_floor: float = 0.7,
    strict_claim_wrapping: bool = True,
) -> VerifierVerdict:
    """Run all deterministic verification checks against the AI response.

    strict_claim_wrapping (default True): every numeric leaf in the response
    must be inside a claim object {value, confidence, derivation?} or in the
    metadata-key whitelist (confidence, page, line, etc.). Naked numerics
    bypass verification and are treated as unverified guesses. Set False
    only for backward-compat callers that have not yet migrated.
    """
    findings: list[str] = []
    verified: list[dict] = []
    unverified: list[dict] = []

    # 1. Schema compliance - minimal check (key presence)
    if schema and isinstance(schema.get("properties"), dict):
        for key in schema.get("required", []):
            if key not in response:
                findings.append(f"Schema violation: missing required key '{key}'")

    # 2. Walk every claim
    claims = _walk_claims(response)
    for path, claim in claims:
        value = claim.get("value")

        # 2a. Null with reason - acceptable, mark unverified
        if value is None:
            reason = claim.get("reason", "(no reason given)")
            unverified.append({"path": path, "reason": reason, "kind": "null_acceptable"})
            continue

        # 2b. Confidence floor
        conf = claim.get("confidence", 1.0)
        if conf < confidence_floor:
            findings.append(f"{path}: confidence {conf} below floor {confidence_floor}")
            unverified.append({"path": path, "value": value, "confidence": conf})
            continue

        # 2c. Derivation - recompute and check
        if "derivation" in claim:
            d = claim["derivation"]
            # Guard: AI may return a string instead of a dict
            if isinstance(d, str):
                findings.append(f"{path}: derivation is a string, not a dict - skipping recompute")
                unverified.append({"path": path, "value": value, "kind": "string_derivation"})
                continue
            if not isinstance(d, dict):
                continue
            recomputed = _recompute_derivation(d.get("formula", ""), d.get("inputs", {}))
            if recomputed is None:
                findings.append(f"{path}: derivation formula failed to recompute "
                                f"(formula='{d.get('formula','')}')")
                unverified.append({"path": path, "value": value, "kind": "bad_derivation"})
                continue
            try:
                claimed = float(value)
                if abs(claimed - recomputed) > 0.001 * max(1.0, abs(claimed)):
                    findings.append(f"{path}: derivation mismatch - "
                                    f"AI claimed {claimed}, recomputed {recomputed}")
                    unverified.append({"path": path, "value": value,
                                       "kind": "derivation_mismatch", "recomputed": recomputed})
                    continue
            except (TypeError, ValueError):
                findings.append(f"{path}: derivation present but value not numeric: {value}")
                unverified.append({"path": path, "value": value, "kind": "non_numeric"})
                continue
            # Inputs of the derivation MUST themselves be cited Facts
            inputs_ok = True
            for input_key, input_val in d.get("inputs", {}).items():
                if manifest.has_provenance(input_val) is None:
                    findings.append(f"{path}: derivation input '{input_key}'={input_val} "
                                    f"has no provenance in facts_manifest")
                    inputs_ok = False
            if inputs_ok:
                verified.append({"path": path, "value": value, "kind": "derived"})
            continue

        # 2d. Direct citation - value must match a Fact
        cited_fact = manifest.has_provenance(value)
        if cited_fact is None:
            # Check domain rules (AISC) - value might be derivable from canonical rule
            designation = claim.get("aisc_designation")
            if designation:
                expected = _aisc_weight_per_foot(designation)
                if expected is not None:
                    try:
                        if abs(float(value) - expected) < 0.001:
                            verified.append({"path": path, "value": value,
                                             "kind": "aisc_canonical", "designation": designation})
                            continue
                        else:
                            findings.append(f"{path}: AISC designation {designation} should weigh "
                                            f"{expected} lb/ft, but AI claimed {value}")
                            unverified.append({"path": path, "value": value, "kind": "aisc_mismatch"})
                            continue
                    except (TypeError, ValueError):
                        pass
            findings.append(f"{path}: numeric value {value} has no provenance in facts_manifest "
                            f"and no derivation - would be a guess")
            unverified.append({"path": path, "value": value, "kind": "no_provenance"})
            continue

        verified.append({
            "path": path, "value": value,
            "matched_fact": cited_fact.key,
            "page": cited_fact.page, "line": cited_fact.line,
        })

    # 3. Defensive check: catch naked numeric values that should have been
    #    claim-wrapped. Closes the v3.5.2 regression where flat {tonnage: 9999}
    #    responses produced zero claims and silently APPROVED with score 1.0.
    naked: list[tuple[str, Any]] = []
    if strict_claim_wrapping:
        naked = _find_naked_numerics(response)
        for nk_path, nk_val in naked:
            findings.append(
                f"{nk_path}: naked numeric value {nk_val} is not claim-wrapped - "
                f"flat values bypass verification. Wrap as "
                f"{{value: ..., confidence: ..., derivation?: ...}}"
            )
            unverified.append({"path": nk_path, "value": nk_val,
                               "kind": "unwrapped_numeric"})

    # Score = fraction verified of all numeric claims AND naked numerics.
    # Naked numerics count against the score so flat-value responses can't
    # silently approve (score = 0/N = 0.0 → REJECT).
    total_claims = len(claims) + len(naked)
    if total_claims == 0:
        score = 1.0   # no numeric claims to verify, no naked numerics either
    else:
        score = len(verified) / total_claims

    # Verdict
    if not findings and score >= 0.95:
        status = "APPROVED"
    elif score >= 0.5:
        status = "NEEDS_CORRECTION"
    elif score >= 0.2:
        status = "ESCALATE"
    else:
        status = "REJECT"

    return VerifierVerdict(
        status=status, score=score, findings=findings,
        verified_facts=verified, unverified_facts=unverified,
    )
