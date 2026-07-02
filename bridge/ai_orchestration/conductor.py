"""
Conductor - Top-Level Orchestrator
====================================
Single entry point that chains all 6 stages of the supervisor/verifier pipeline.

  process_document(path, question, response_schema)
    → ingest_document            (intake.py)
    → build_bulletproof_prompt   (prompts.py)
    → correct_and_retry          (corrector.py - calls verifier.py internally)
    → proofread_output           (proofreader.py)
    → return verified result OR refusal

Provider selection uses the existing MODEL_ROUTES from bridge.api.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .intake     import ingest_document, FactsManifest
from .prompts    import build_bulletproof_prompt
from .corrector  import correct_and_retry, OrchestrationResult
from .proofreader import proofread_output, ProofreadReport


@dataclass
class ConductorResult:
    """The complete record of an orchestrated AI task - full audit trail."""
    status:       str        # APPROVED | UNVERIFIED | BLOCKED | ERROR
    answer:       dict | None
    manifest:     FactsManifest | None
    orchestration: OrchestrationResult | None
    proofread:    ProofreadReport | None
    summary:      str = ""

    def audit_trail(self) -> list[str]:
        """Human-readable record of what happened."""
        trail = []
        if self.manifest:
            trail.append(f"INTAKE: {self.manifest.page_count} pages, "
                         f"{len(self.manifest.facts)} facts extracted locally, "
                         f"AI vision needed: {self.manifest.needs_ai_vision}")
            for line in self.manifest.extraction_log:
                trail.append(f"  · {line}")
        if self.orchestration:
            trail.append(f"ORCHESTRATION: {self.orchestration.status}, "
                         f"{self.orchestration.attempts_count} attempt(s)")
            for a in self.orchestration.attempts:
                trail.append(f"  · attempt {a.attempt_no}: {a.provider}/{a.model} "
                             f"→ {a.verdict.status} (score {a.verdict.score:.2f})")
                for f in a.verdict.findings[:3]:
                    trail.append(f"      ⚠ {f}")
        if self.proofread:
            trail.append(f"PROOFREAD: {self.proofread.status} - {self.proofread.summary}")
            for f in self.proofread.issues[:3]:
                trail.append(f"  ⚠ {f}")
        return trail


def process_document(
    path:            str | Path,
    question:        str,
    response_schema: dict,
    call_provider:   Callable[[str, str, dict], dict],
    primary_provider: str = "claude",
    primary_model:    str = "claude-sonnet-4-6",
) -> ConductorResult:
    """Run a question against a document through the full supervisor/verifier pipeline.

    Args:
        path:        document to analyze
        question:    user's question (e.g. "What is the steel tonnage estimate?")
        response_schema: JSON schema the AI's response must satisfy
        call_provider: callable injected by caller - (provider, model, envelope) → dict
        primary_provider, primary_model: who to ask first

    Returns:
        ConductorResult with full audit trail.
    """
    result = ConductorResult(
        status="ERROR", answer=None, manifest=None,
        orchestration=None, proofread=None,
    )

    # ── Stage 1: INTAKE (local-first) ──
    try:
        manifest = ingest_document(path)
        result.manifest = manifest
    except FileNotFoundError as e:
        result.status = "ERROR"; result.summary = f"Document not found: {e}"
        return result
    except Exception as e:
        result.status = "ERROR"
        result.summary = f"Intake failed: {type(e).__name__}: {e}"
        return result

    # ── Stage 2/3: ROUTE + PROMPT ──
    envelope = build_bulletproof_prompt(question, manifest, response_schema)

    # ── Stage 4/5: VERIFY + CORRECT ──
    orch = correct_and_retry(
        initial_envelope=envelope,
        manifest=manifest,
        response_schema=response_schema,
        primary_provider=primary_provider,
        primary_model=primary_model,
        call_provider=call_provider,
    )
    result.orchestration = orch

    if orch.status != "APPROVED":
        result.status = "UNVERIFIED"
        result.summary = orch.refusal_reason
        return result

    # ── Stage 6: PROOFREAD output ──
    # Render the approved JSON answer to text for proofreading
    import json as _j
    answer_text = _j.dumps(orch.final_response, indent=2)
    # Pull verified derivations out of the verdict so the proofreader knows
    # which "novel" numbers in the rendered JSON are actually approved
    extra_verified: list[float] = []
    if orch.attempts and orch.attempts[-1].verdict.verified_facts:
        for vf in orch.attempts[-1].verdict.verified_facts:
            try:
                extra_verified.append(float(vf.get("value")))
            except (TypeError, ValueError):
                continue
    proof = proofread_output(answer_text, manifest, kind="text",
                              extra_verified_values=extra_verified)
    result.proofread = proof

    if proof.status == "BLOCKED":
        result.status = "BLOCKED"
        result.answer = None
        result.summary = (f"Final proofread blocked delivery: {proof.summary}. "
                          f"AI response was verified, but the rendered output contained "
                          f"unverified numbers. Refusing rather than deliver.")
        return result

    result.status = "APPROVED"
    result.answer = orch.final_response
    result.summary = (f"Verified through {orch.attempts_count} attempt(s); "
                      f"{len(proof.verified_numbers)} numbers proofread.")
    return result


def process_question(
    question:        str,
    facts:           dict,
    response_schema: dict,
    call_provider:   Callable[[str, str, dict], dict],
    primary_provider: str = "claude",
    primary_model:    str = "claude-sonnet-4-6",
) -> ConductorResult:
    """Variant for questions where facts are supplied directly (e.g. from
    a database query or KPI snapshot) rather than a document."""
    from .intake import Fact

    # Build a synthetic manifest from the supplied facts
    manifest = FactsManifest(
        document_path="(in-memory)", document_sha256="-", page_count=0,
        has_text_layer=False, has_tables=False, has_images=False,
        needs_ai_vision=False,
    )
    for key, value in facts.items():
        manifest.facts.append(Fact(
            key=key, value=value, source="programmatic",
            page=None, line=None, confidence=1.0,
            raw_text=f"{key}={value}",
        ))

    envelope = build_bulletproof_prompt(question, manifest, response_schema)
    orch = correct_and_retry(
        initial_envelope=envelope, manifest=manifest, response_schema=response_schema,
        primary_provider=primary_provider, primary_model=primary_model,
        call_provider=call_provider,
    )

    result = ConductorResult(
        status=("APPROVED" if orch.status == "APPROVED" else "UNVERIFIED"),
        answer=(orch.final_response if orch.status == "APPROVED" else None),
        manifest=manifest, orchestration=orch, proofread=None,
        summary=(orch.refusal_reason if orch.status != "APPROVED" else "verified"),
    )
    return result
