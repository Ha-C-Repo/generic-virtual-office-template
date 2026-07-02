"""
Bulletproof Prompt Templates
=============================
Every AI call from Virtual Office goes through a wrapper that injects:

  1. The system guardrails (no guessing, mandatory JSON schema, citations)
  2. Domain rules (AISC tables, Houston calibration, no LLM math)
  3. The facts manifest (locally-extracted source of truth)
  4. The user's actual question - only after all of the above

This means even if the wrapped AI tries to be helpful and guess, it cannot
produce output that passes the verifier without citing a real Fact.
"""

import json
from .intake import FactsManifest


SYSTEM_GUARDRAILS = """\
You are a specialized analysis assistant for Your Company, a Houston structural
steel fabricator. You operate under STRICT RULES:

1. NO GUESSING. If you do not have information sufficient to answer a numeric
   question, return {"value": null, "confidence": 0.0, "reason": "..."}. Do
   NOT estimate, infer, or fill in plausible numbers.

2. EVERY NUMERIC VALUE IN YOUR RESPONSE MUST BE A CLAIM OBJECT.
   A claim object has this exact shape:

     {"value": 320, "confidence": 0.97,
      "source": {"page": 3, "line": 42, "raw": "..."}}

   OR, if the value is computed from inputs, include a derivation:

     {"value": 320, "confidence": 0.95,
      "derivation": {"formula": "tons * 2000", "inputs": {"tons": 0.16}}}

   FLAT VALUES WILL BE REJECTED. The verifier walks your JSON looking for
   {value: ...} objects. A flat number like {"tonnage": 9999} produces zero
   claims and the verifier rejects it as an unverified guess. Always wrap.

   Exception (safe to leave as raw numbers): pure schema metadata such as
   page numbers, line numbers, item counts, confidence scores, and array
   indices. These are structural, not factual claims.

3. NO MATH IN YOUR HEAD. If a calculation is required, write the formula
   explicitly and the inputs explicitly inside a derivation block. The
   verifier will recompute locally. You are forbidden from outputting a
   final numeric result without showing formula + inputs.

4. DOMAIN RULES (always apply):
   - AISC weight per foot is canonical. W14X82 = 82 lb/ft. W18X35 = 35 lb/ft.
     The number after the X IS the weight. Do not look this up - just use it.
   - Houston labor rates come from SAM.gov WD-2026, never from your training data.
   - Steel costs use Q2 2026 calibration: A992 W-section ≈ $1,150/ton typ.
   - FLSA OT at 40 hours × 1.5 multiplier. NO double-time in Texas.

5. RESPONSE FORMAT: Strict JSON matching the schema provided. No prose
   outside the JSON. No markdown code fences. Just the raw JSON object.

6. UNCERTAINTY IS BETTER THAN INVENTION. A "I don't know" with reasoning is
   worth more than a confident wrong answer. The user is a structural
   engineer - they can handle uncertainty. They cannot handle being misled.
"""


def build_bulletproof_prompt(
    user_request:    str,
    manifest:        FactsManifest,
    response_schema: dict,
    extra_rules:     list[str] | None = None,
) -> dict:
    """Build a complete prompt envelope ready to send to any AI provider.

    Returns a dict with 'system' + 'messages' + 'response_schema' keys, ready
    to drop into the Anthropic, OpenAI, or Gemini SDK call.
    """
    rules = list(extra_rules or [])

    # Render the manifest in a form the AI can use as source of truth
    facts_for_prompt = []
    for f in manifest.facts:
        if isinstance(f.value, list):   # tables
            facts_for_prompt.append({
                "key": f.key, "type": "table",
                "rows": len(f.value), "cols": len(f.value[0]) if f.value else 0,
                "page": f.page, "source": f.source, "confidence": f.confidence,
            })
        else:
            facts_for_prompt.append({
                "key": f.key, "value": f.value,
                "page": f.page, "line": f.line,
                "source": f.source, "confidence": f.confidence,
                "raw_text": f.raw_text[:120],
            })

    user_payload = {
        "user_request": user_request,
        "facts_manifest": {
            "document_sha256": manifest.document_sha256,
            "page_count":      manifest.page_count,
            "has_text_layer":  manifest.has_text_layer,
            "has_tables":      manifest.has_tables,
            "has_images":      manifest.has_images,
            "needs_ai_vision": manifest.needs_ai_vision,
            "facts":           facts_for_prompt,
        },
        "response_schema": response_schema,
        "answering_rules": [
            "Wrap every numeric value as {value, confidence, source|derivation} - flat numbers are rejected",
            "Show formula + inputs for any calculation (no math in your head)",
            "Return null + reason if uncertain - DO NOT guess",
            *rules,
        ],
    }

    return {
        "system": SYSTEM_GUARDRAILS,
        "messages": [
            {"role": "user", "content": json.dumps(user_payload, indent=2)},
        ],
        "response_schema": response_schema,
    }


def build_correction_prompt(
    original_envelope: dict,
    failed_response:   dict,
    verifier_feedback: list[str],
) -> dict:
    """Build a follow-up prompt explaining exactly what was wrong.

    Used when the verifier catches an issue - we re-call the same AI with
    a precise critique rather than just retrying blindly.
    """
    correction_msg = {
        "role": "user",
        "content": json.dumps({
            "previous_response_was_rejected": True,
            "your_previous_response":         failed_response,
            "verifier_findings":              verifier_feedback,
            "instruction": (
                "The verifier found problems with your previous response listed above. "
                "Please reconsider and provide a corrected response. If the verifier "
                "found that you cited a fact incorrectly, look again at the facts_manifest "
                "in the original request. If the verifier found a math error, recompute "
                "showing your work. If you cannot answer correctly without guessing, "
                "return null with an explanation - that is acceptable and preferred over "
                "a confident wrong answer."
            ),
        }, indent=2),
    }

    return {
        "system":          original_envelope["system"],
        "messages":        list(original_envelope["messages"]) + [
            {"role": "assistant", "content": json.dumps(failed_response)},
            correction_msg,
        ],
        "response_schema": original_envelope["response_schema"],
    }
