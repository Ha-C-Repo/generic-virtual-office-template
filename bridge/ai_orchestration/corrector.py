"""
Cross-Correction Protocol
==========================
When the verifier flags a problem, this module orchestrates the recovery:

  Attempt 1: Original AI returns response → verifier rejects
  Attempt 2: Same AI gets a precise correction prompt with the verifier's
             findings - re-tries with explicit critique
  Attempt 3: If still rejected, escalate to alternate AI in the fallback chain
             (Claude → Gemini → OpenAI)
  Attempt 4: Try the third AI in the chain

If all four attempts fail to produce a verifier-approved response, the
function returns OrchestrationResult with status='UNVERIFIED' - the
caller (and ultimately the user) sees a clear refusal explaining what
could not be verified, never a fabricated answer.
"""

from dataclasses import dataclass, field
from typing import Any, Callable

from .intake import FactsManifest
from .prompts import build_correction_prompt
from .verifier import verify_response, VerifierVerdict


@dataclass
class AttemptRecord:
    attempt_no: int
    provider:   str
    model:      str
    response:   dict
    verdict:    VerifierVerdict


@dataclass
class OrchestrationResult:
    status:       str       # APPROVED | UNVERIFIED | ERROR
    final_response: dict | None
    attempts:     list[AttemptRecord] = field(default_factory=list)
    findings:     list[str] = field(default_factory=list)
    refusal_reason: str = ""

    @property
    def attempts_count(self) -> int:
        return len(self.attempts)


# Provider fallback chain - Claude is supervisor and primary
DEFAULT_FALLBACK_CHAIN = [
    ("claude",  "claude-sonnet-4-6"),
    ("gemini",  "gemini-2.5-flash"),
    ("openai",  "gpt-4o"),
]


def correct_and_retry(
    initial_envelope: dict,
    manifest:         FactsManifest,
    response_schema:  dict,
    primary_provider: str,
    primary_model:    str,
    call_provider:    Callable[[str, str, dict], dict],
    fallback_chain:   list[tuple[str, str]] | None = None,
    max_total_attempts: int = 4,
) -> OrchestrationResult:
    """Run the full retry+escalation loop.

    Args:
        initial_envelope: the bulletproof prompt envelope from build_bulletproof_prompt
        manifest: the FactsManifest the verifier checks against
        response_schema: schema for verification
        primary_provider, primary_model: who to call first
        call_provider: callable (provider, model, envelope) → response_json (a dict).
                       Tests inject a mock; production injects a real SDK wrapper.
        fallback_chain: ordered list of (provider, model) to try if primary fails.
                        Defaults to DEFAULT_FALLBACK_CHAIN with primary moved first.
        max_total_attempts: hard cap across all providers (default 4).
    """
    chain = fallback_chain or DEFAULT_FALLBACK_CHAIN
    # Move primary to front, keep rest in original order
    ordered_chain = [(primary_provider, primary_model)] + [
        (p, m) for p, m in chain if p != primary_provider
    ]

    result = OrchestrationResult(status="UNVERIFIED", final_response=None)
    envelope = initial_envelope
    last_response: dict | None = None
    attempt_no = 0

    for provider, model in ordered_chain:
        for retry_round in range(2):   # each provider gets 2 attempts (initial + 1 correction)
            if attempt_no >= max_total_attempts:
                break
            attempt_no += 1

            # Build envelope for this attempt
            if retry_round == 0:
                # First time on this provider - use either the initial envelope
                # OR a correction envelope if we have a previous response to critique
                if last_response is not None and result.attempts:
                    last_findings = result.attempts[-1].verdict.findings
                    envelope = build_correction_prompt(
                        initial_envelope, last_response, last_findings
                    )
                else:
                    envelope = initial_envelope
            else:
                # Second attempt on same provider - explicit correction
                if last_response is None:
                    continue
                last_findings = result.attempts[-1].verdict.findings
                envelope = build_correction_prompt(
                    initial_envelope, last_response, last_findings
                )

            # Call the provider
            try:
                response = call_provider(provider, model, envelope)
            except Exception as e:
                result.attempts.append(AttemptRecord(
                    attempt_no=attempt_no, provider=provider, model=model,
                    response={"error": str(e)},
                    verdict=VerifierVerdict(
                        status="REJECT", score=0.0,
                        findings=[f"Provider call failed: {type(e).__name__}: {e}"],
                    ),
                ))
                last_response = None
                break   # try next provider

            # Verify
            verdict = verify_response(response, manifest, response_schema)
            result.attempts.append(AttemptRecord(
                attempt_no=attempt_no, provider=provider, model=model,
                response=response, verdict=verdict,
            ))

            if verdict.status == "APPROVED":
                result.status = "APPROVED"
                result.final_response = response
                return result

            last_response = response

            if verdict.status == "REJECT":
                # Severe - skip this provider's second attempt, escalate
                break

        if result.status == "APPROVED":
            return result

    # Exhausted all attempts
    result.status = "UNVERIFIED"
    if result.attempts:
        last_findings = result.attempts[-1].verdict.findings
        result.findings = last_findings
        result.refusal_reason = (
            f"After {len(result.attempts)} attempts across "
            f"{len(set(a.provider for a in result.attempts))} providers, "
            f"no response passed verification. Refusing rather than guessing. "
            f"Last verifier findings: {'; '.join(last_findings[:3])}"
        )
    else:
        result.refusal_reason = "No providers were callable."
    return result
