"""
Your Company AI Orchestration - Supervisor/Verifier Pattern
=========================================================

Architecture (all 6 stages run for any AI-touching task):

  1. INTAKE      - Extract everything possible LOCALLY first.
                   PDFs: pdfplumber (text+tables), PyMuPDF (images), tesseract (OCR fallback)
                   Build "facts manifest" with provenance (page#, line#) for every value.
                   Only escalate to AI vision if pages are scanned or no text layer.

  2. ROUTE       - Pick the right model for the task (existing MODEL_ROUTES).
                   Inject the facts manifest as the source of truth.

  3. PROMPT      - Wrap the request in a bulletproof template:
                   • forced JSON schema with confidence scores
                   • mandatory source citations (page/line) for every number
                   • "you may not guess; return null + reason if uncertain"
                   • domain rules injected (AISC tables, calibration constraints)

  4. VERIFY      - Claude (always Claude, regardless of who answered) reviews
                   the other AI's response:
                   • every numeric claim cross-referenced against facts manifest
                   • every derivation recomputed locally
                   • domain rules checked (e.g., W14X82 must weigh 82 lb/ft)
                   • verdict: APPROVE / NEEDS_CORRECTION / ESCALATE / REJECT

  5. CORRECT     - If NEEDS_CORRECTION: craft a precise correction prompt
                   citing exactly what was wrong, retry same AI (attempt 2).
                   If still wrong: escalate to alternate AI in fallback chain.
                   Hard limit: 3 distinct attempts across 2 providers, then refuse.

  6. PROOFREAD   - Before any output (text, DOCX, PDF, email) reaches the user,
                   parse it back, extract numeric claims, verify against the
                   approved facts manifest. Any unverified number → block delivery.

Hard guarantees:
  • No numeric value reaches the user without a provenance citation
  • No "guess" can pass - confidence < threshold means UNVERIFIED tag
  • Files generated are parsed back and verified before delivery
  • If all retry/escalation paths exhausted, the system refuses with a clear
    explanation rather than fabricating an answer
"""

from .intake import ingest_document, FactsManifest
from .prompts import build_bulletproof_prompt, SYSTEM_GUARDRAILS
from .verifier import verify_response, VerifierVerdict, auto_wrap_response
from .corrector import correct_and_retry, OrchestrationResult
from .proofreader import proofread_output, ProofreadReport
from .conductor import process_document, process_question

__all__ = [
    "ingest_document", "FactsManifest",
    "build_bulletproof_prompt", "SYSTEM_GUARDRAILS",
    "verify_response", "VerifierVerdict", "auto_wrap_response",
    "correct_and_retry", "OrchestrationResult",
    "proofread_output", "ProofreadReport",
    "process_document", "process_question",
]
