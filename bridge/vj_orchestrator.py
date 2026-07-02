"""Virtual Joseph Orchestrator - AI routing, tool selection, and feature design.

This module makes VJ an autonomous agent that:
  1. Chooses the best AI model or tool for any given task
  2. Designs and deploys new features when capabilities don't exist
  3. Informs the user when designing new solutions

The orchestrator sits between the user request and the Bridge, routing
to the optimal execution path. When no path exists, it designs one.

Usage:
    from bridge.vj_orchestrator import get_orchestrator

    orch = get_orchestrator()
    result = orch.route(request="generate a Gantt chart for this project")
    # If capability exists: result.tool = "project_timeline", result.ready = True
    # If not: result.designing = True, result.user_message = "The software is..."
"""

import json
import logging
import os
import re
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("vj_orchestrator")

# ---- Data persistence ----
_DATA_DIR = Path(__file__).parent.parent / "data" / "virtual_joseph"
_DESIGNED_FEATURES_FILE = _DATA_DIR / "designed_features.json"
_ROUTING_LOG_FILE = _DATA_DIR / "routing_log.json"


# ---- AI Model Registry ----
# Each model's strengths, costs, and when to use it.

AI_MODELS = {
    "claude": {
        "provider": "anthropic",
        "models": [
            "claude-opus-4-7",                   # Pass 8: max accuracy tier
            "claude-opus-4-6",                   # Pass 8: accurate tier
            "claude-sonnet-4-6",                 # default workhorse
            "claude-haiku-4-5-20251001",         # Pass 8: fast tier
        ],
        "default_tier_module": "bridge.ai_model_router",
        "strengths": [
            "code generation", "code review", "complex reasoning",
            "long document analysis", "bid writing", "voice calibration",
            "compliance checking", "governance rules", "structured output",
            "system prompts", "multi-step planning", "debugging",
        ],
        "cost_tier": "primary",
        "env_key": "ANTHROPIC_API_KEY",
        "best_for": "Rules-heavy tasks, code, compliance, voice-calibrated output. "
                    "Use Sonnet by default; escalate to Opus 4.7 for max accuracy.",
    },
    "gemini": {
        "provider": "google",
        "models": ["gemini-2.5-pro", "gemini-2.5-flash"],
        "strengths": [
            "multimodal vision", "drawing reading", "PDF image extraction",
            "grounding with search", "large context window",
            "architectural review", "competitive analysis",
            "image understanding", "blueprint reading",
        ],
        "cost_tier": "primary",
        "env_key": "GOOGLE_API_KEY",
        "best_for": "Vision tasks, drawing analysis, research with grounding.",
    },
    "gpt": {
        "provider": "openai",
        "models": ["gpt-4o", "gpt-4o-mini"],
        "strengths": [
            "structured JSON output", "Monte Carlo simulation",
            "PDF generation", "function calling", "data extraction",
            "spreadsheet analysis", "statistical analysis",
        ],
        "cost_tier": "primary",
        "env_key": "OPENAI_API_KEY",
        "best_for": "Structured output, Monte Carlo, statistical analysis.",
    },
}


# ---- Tool Registry ----
# Maps capability domains to Bridge methods and their descriptions.

TOOL_REGISTRY = {
    # Steel engineering
    "aisc_lookup": {
        "method": "get_aisc_member_info",
        "domain": "engineering",
        "keywords": ["weight", "shape", "W14", "HSS", "AISC", "steel", "lb/ft", "tons", "member info"],
        "description": "AISC shape property lookup and weight calculation.",
    },
    "tonnage_calc": {
        "method": "run_takeoff",
        "domain": "engineering",
        "keywords": ["tonnage", "takeoff", "total weight", "member list", "extract members"],
        "description": "Tonnage calculation from member list or PDF.",
    },
    "labor_hours": {
        "method": "get_calibrated_estimate",
        "domain": "engineering",
        "keywords": ["labor", "hours", "fab hours", "erection hours", "crew", "calibrated"],
        "description": "Labor hour and cost estimate from tonnage (Q2 2026 calibrated).",
    },
    "cost_estimate": {
        "method": "get_calibrated_estimate",
        "domain": "engineering",
        "keywords": ["cost", "estimate", "price", "total cost", "budget", "rough draft"],
        "description": "Full cost estimate from tonnage and labor.",
    },
    "stl_model": {
        "method": "generate_3d_view",
        "domain": "cad",
        "keywords": ["3D", "STL", "model", "wireframe", "visualization", "3d model"],
        "description": "3D STL model generation from AISC shapes.",
    },
    "dxf_drawing": {
        "method": "generate_dxf",
        "domain": "cad",
        "keywords": ["DXF", "cross-section", "AutoCAD", "CNC", "drawing"],
        "description": "DXF cross-section generation.",
    },
    # Compliance
    "compliance_check": {
        "method": "check_bid_compliance",
        "domain": "compliance",
        "keywords": ["ISNetworld", "RAVS", "safety", "compliance", "Avetta", "ISN"],
        "description": "ISNetworld/Avetta compliance checking.",
    },
    "governance_check": {
        "method": "get_governance_status",
        "domain": "governance",
        "keywords": ["governance", "rule", "violation", "Tier 1", "supplier", "governance check", "governance status"],
        "description": "Governance rule enforcement.",
    },
    # Documents
    "bid_proposal": {
        "method": "generate_proposal",
        "domain": "bid",
        "keywords": ["proposal", "bid document", "PDF", "bid package", "generate proposal"],
        "description": "Full bid proposal PDF generation.",
    },
    "change_order": {
        "method": "generate_change_order",
        "domain": "documents",
        "keywords": ["change order", "AIA G701", "scope change", "addendum"],
        "description": "AIA G701 change order generation.",
    },
    # Communications
    "cold_email": {
        "method": "draft_refinery_outreach",
        "domain": "outreach",
        "keywords": ["cold email", "outreach", "GC", "general contractor", "email", "draft email", "prospect"],
        "description": "Personalized cold email generation.",
    },
    "linkedin_post": {
        "method": "draft_email_outlook",
        "domain": "content",
        "keywords": ["LinkedIn", "post", "social media", "content", "article"],
        "description": "Content drafting (LinkedIn, social).",
    },
    # Research
    "competitor_research": {
        "method": "get_steel_research",
        "domain": "research",
        "keywords": ["competitor", "research", "market", "analysis", "compare", "steel research"],
        "description": "Competitor and market research from free sources.",
    },
    # VJ itself
    "vj_scan": {
        "method": "vj_scan",
        "domain": "quality",
        "keywords": ["scan", "check", "health", "diagnostic", "Virtual Joseph", "codebase", "issues", "bugs"],
        "description": "Full codebase health scan.",
    },
    "vj_deps": {
        "method": "vj_check_deps",
        "domain": "quality",
        "keywords": ["install", "dependency", "missing", "pip", "package"],
        "description": "Dependency audit with install instructions.",
    },
}


# ---- Result types ----

@dataclass
class RouteResult:
    """Result of routing a request to the best tool/AI."""
    ready: bool = False
    designing: bool = False
    tool: str = ""
    method: str = ""
    ai_model: str = ""
    ai_reason: str = ""
    user_message: str = ""
    confidence: float = 0.0
    alternatives: list[str] = field(default_factory=list)
    # Pass 10g: AI prompt-route match. Populated when route() resolved via
    # the api.py _INTENT_PATTERNS table instead of TOOL_REGISTRY. Caller
    # can dispatch this template directly to Claude with the user's
    # original request as additional context.
    prompt_template: str = ""


@dataclass
class DesignResult:
    """Result of designing a new feature."""
    success: bool = False
    feature_name: str = ""
    method_name: str = ""
    code: str = ""
    description: str = ""
    user_message: str = ""
    error: str = ""


# ---- Orchestrator ----

class Orchestrator:
    """Routes requests to the best AI/tool combo and designs new features."""

    DESIGN_MESSAGE = (
        "The software is designing a solution for your request as those "
        "capabilities do not currently exist. One moment while I design "
        "a solution for your request."
    )

    def __init__(self):
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._designed_features = self._load_designed_features()
        self._routing_log: list[dict] = []

    # ---- Public API ----

    def route(self, request: str) -> RouteResult:
        """Route a request to the best tool and AI model.

        Returns a RouteResult indicating:
          - ready=True: existing tool found, use result.method
          - designing=True: no tool exists, VJ will design one
        """
        request_lower = request.lower()
        result = RouteResult()

        # Step 1: Check existing tools
        best_tool, best_score = self._match_tool(request_lower)
        if best_tool and best_score >= 2:
            tool_def = TOOL_REGISTRY[best_tool]
            result.ready = True
            result.tool = best_tool
            result.method = tool_def["method"]
            result.confidence = min(best_score / 5.0, 1.0)
            result.ai_model = self._pick_ai_for_domain(tool_def["domain"])
            result.ai_reason = AI_MODELS.get(
                result.ai_model, {}
            ).get("best_for", "")
            # Log the routing decision
            self._log_route(request, best_tool, result.ai_model, "existing_tool")
            return result

        # Step 2: Check designed features (previously built on-the-fly)
        designed = self._match_designed_feature(request_lower)
        if designed:
            result.ready = True
            result.tool = designed["feature_name"]
            result.method = designed["method_name"]
            result.confidence = 0.7
            result.ai_model = "claude"
            result.ai_reason = "Using previously designed feature."
            self._log_route(request, designed["feature_name"], "claude", "designed_feature")
            return result

        # Step 2.5 (pass 10g): Check api.py _INTENT_PATTERNS for AI prompt routes.
        # These are not Bridge tools but pre-defined prompt templates that
        # rewrite the Owner's casual phrasing into a structured prompt for Claude.
        # bid_followup, cold_email, compliance_status, etc. all live there.
        prompt = self._match_intent_pattern(request_lower)
        if prompt:
            result.ready = True
            result.tool = "ai_prompt_route"
            result.method = "ai_ask"
            result.prompt_template = prompt
            result.confidence = 0.8
            result.ai_model = "claude"
            result.ai_reason = (
                "AI prompt route matched. Dispatch the prompt_template via "
                "Bridge.ai_ask() with the user's original message as context."
            )
            self._log_route(request, "ai_prompt_route", "claude", "intent_pattern")
            return result

        # Step 3: No match. Enter design mode.
        result.designing = True
        result.user_message = self.DESIGN_MESSAGE
        result.ai_model = "claude"
        result.ai_reason = "Claude is best for code generation and new feature design."
        self._log_route(request, "NONE", "claude", "design_mode")
        return result

    def pick_best_ai(self, task_description: str) -> dict:
        """Choose the best AI model for a task description.

        Returns dict with model, reason, and alternatives.
        """
        task_lower = task_description.lower()
        scores: dict[str, int] = {}

        for model_name, model_def in AI_MODELS.items():
            score = 0
            for strength in model_def["strengths"]:
                # Check if any word in the strength appears in the task
                strength_words = strength.lower().split()
                for word in strength_words:
                    if len(word) > 3 and word in task_lower:
                        score += 1
            scores[model_name] = score

        # Sort by score descending
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_name = ranked[0][0] if ranked[0][1] > 0 else "claude"
        best_def = AI_MODELS[best_name]

        # Check if the best model's API key is available
        env_key = best_def.get("env_key", "")
        available = bool(os.environ.get(env_key, "")) if env_key else False

        # If best isn't available, fall back
        if not available and best_name != "claude":
            for name, score in ranked[1:]:
                alt_key = AI_MODELS[name].get("env_key", "")
                if os.environ.get(alt_key, ""):
                    best_name = name
                    best_def = AI_MODELS[name]
                    break

        return {
            "model": best_name,
            "provider": best_def["provider"],
            "reason": best_def["best_for"],
            "available": available,
            "scores": {k: v for k, v in ranked},
            "alternatives": [
                {"model": k, "score": v}
                for k, v in ranked[1:]
                if v > 0
            ],
        }

    def design_feature(self, request: str, context: str = "") -> DesignResult:
        """Design a new feature to handle a request that has no existing tool.

        This generates a feature specification. The actual code generation
        happens via the AI model (Claude), not hardcoded templates.

        Returns DesignResult with the feature spec and suggested method name.
        """
        result = DesignResult()

        # Generate a method name from the request
        method_name = self._request_to_method_name(request)
        result.feature_name = method_name.replace("_", " ").title()
        result.method_name = method_name

        # Build a feature specification
        spec = {
            "request": request,
            "method_name": method_name,
            "feature_name": result.feature_name,
            "context": context,
            "designed_at": datetime.now(timezone.utc).isoformat(),
            "status": "designed",
            "ai_model": "claude",
        }

        # Generate a description of what the feature should do
        result.description = (
            f"New feature '{result.feature_name}' designed to handle: "
            f"{request[:200]}"
        )

        # Build skeleton code for the feature
        result.code = self._generate_feature_skeleton(method_name, request)
        result.success = True
        result.user_message = self.DESIGN_MESSAGE

        # Save the designed feature for future routing
        spec["code"] = result.code
        spec["description"] = result.description
        self._designed_features.append(spec)
        self._save_designed_features()

        log.info("Designed new feature: %s for request: %s", method_name, request[:80])
        return result

    def get_designed_features(self) -> list[dict]:
        """Return all features that VJ has designed."""
        return list(self._designed_features)

    def get_routing_stats(self) -> dict:
        """Return routing statistics."""
        total = len(self._routing_log)
        by_type = {}
        by_model = {}
        for entry in self._routing_log:
            t = entry.get("route_type", "unknown")
            m = entry.get("ai_model", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
            by_model[m] = by_model.get(m, 0) + 1
        return {
            "total_routes": total,
            "by_type": by_type,
            "by_model": by_model,
            "designed_features": len(self._designed_features),
        }

    # ---- Internal methods ----

    def _match_tool(self, request_lower: str) -> tuple[str, int]:
        """Find the best matching tool for a request. Returns (tool_name, score).

        Multi-word keyword phrases (like 'cold email') count as 2 points
        since they are more specific than single-word matches.
        """
        best_tool = ""
        best_score = 0
        for tool_name, tool_def in TOOL_REGISTRY.items():
            score = 0
            for kw in tool_def["keywords"]:
                if kw.lower() in request_lower:
                    # Multi-word phrases are more specific, count double
                    score += 2 if " " in kw else 1
            if score > best_score:
                best_score = score
                best_tool = tool_name
        return best_tool, best_score

    def _match_intent_pattern(self, request_lower: str) -> str:
        """Consult api.py's _INTENT_PATTERNS for an AI prompt template match.

        Returns the matched prompt template string, or empty if no match.
        Lazy-imports api so vj_orchestrator stays decoupled from import order.
        """
        try:
            import re as _re
            from bridge.api import _INTENT_PATTERNS as _IP
            for keys_any, keys_none, prompt in _IP:
                # Word-boundary match (same logic as _translate_intent)
                if any(
                    _re.search(rf"\b{_re.escape(k.strip())}\b", request_lower)
                    for k in keys_any
                ):
                    if keys_none and any(
                        _re.search(rf"\b{_re.escape(k.strip())}\b", request_lower)
                        for k in keys_none
                    ):
                        continue
                    return prompt
        except Exception:
            pass
        return ""

    def _match_designed_feature(self, request_lower: str) -> Optional[dict]:
        """Check if a previously designed feature matches this request."""
        for feature in self._designed_features:
            # Simple keyword overlap check
            original_words = set(feature.get("request", "").lower().split())
            request_words = set(request_lower.split())
            overlap = original_words & request_words
            # Need at least 3 meaningful word matches
            meaningful = [w for w in overlap if len(w) > 3]
            if len(meaningful) >= 3:
                return feature
        return None

    def _pick_ai_for_domain(self, domain: str) -> str:
        """Pick the best AI model for a given domain."""
        domain_to_ai = {
            "engineering": "claude",
            "cad": "claude",
            "compliance": "claude",
            "governance": "claude",
            "bid": "claude",
            "documents": "claude",
            "outreach": "claude",
            "content": "claude",
            "research": "gemini",
            "vision": "gemini",
            "drawing": "gemini",
            "statistics": "gpt",
            "monte_carlo": "gpt",
            "quality": "claude",
        }
        return domain_to_ai.get(domain, "claude")

    def _request_to_method_name(self, request: str) -> str:
        """Convert a natural language request to a snake_case method name."""
        # Extract key action words
        words = re.findall(r"[a-zA-Z]+", request.lower())
        # Remove common filler words
        filler = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "can", "shall",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "above",
            "below", "between", "out", "off", "over", "under", "again",
            "further", "then", "once", "here", "there", "when", "where",
            "why", "how", "all", "each", "every", "both", "few", "more",
            "most", "other", "some", "such", "no", "nor", "not", "only",
            "own", "same", "so", "than", "too", "very", "just", "because",
            "but", "and", "or", "if", "while", "about", "up", "this",
            "that", "these", "those", "me", "my", "i", "we", "our",
            "you", "your", "it", "its", "please", "want", "need", "like",
            "make", "get", "give", "let", "help",
        }
        key_words = [w for w in words if w not in filler and len(w) > 2][:5]
        if not key_words:
            key_words = ["custom", "feature"]
        return "_".join(key_words)

    def _generate_feature_skeleton(self, method_name: str, request: str) -> str:
        """Generate skeleton code for a new feature."""
        safe_request = request.replace('"', '\\"').replace("\n", " ")[:200]
        return textwrap.dedent(f'''\
            def {method_name}(self, **kwargs) -> dict:
                """Auto-designed feature: {safe_request}

                Designed by Virtual Joseph when no existing capability matched.
                Generated: {datetime.now(timezone.utc).isoformat()}
                """
                try:
                    # TODO: Implement feature logic
                    # This skeleton was generated by VJ Orchestrator.
                    # The AI model (Claude) should fill in the implementation
                    # based on the request context.
                    return {{
                        "ok": True,
                        "data": {{
                            "feature": "{method_name}",
                            "status": "designed",
                            "request": "{safe_request}",
                            "message": "Feature designed. Implementation pending.",
                        }},
                    }}
                except Exception as e:
                    return {{"ok": False, "error": f"{method_name} failed: {{e}}"}}
        ''')

    def _log_route(self, request: str, tool: str, ai_model: str, route_type: str):
        """Log a routing decision."""
        self._routing_log.append({
            "request": request[:200],
            "tool": tool,
            "ai_model": ai_model,
            "route_type": route_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _load_designed_features(self) -> list[dict]:
        """Load previously designed features from disk."""
        if _DESIGNED_FEATURES_FILE.exists():
            try:
                return json.loads(_DESIGNED_FEATURES_FILE.read_text())
            except Exception:
                return []
        return []

    def _save_designed_features(self):
        """Save designed features to disk."""
        try:
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            _DESIGNED_FEATURES_FILE.write_text(
                json.dumps(self._designed_features, indent=2, default=str)
            )
        except Exception as e:
            log.warning("Failed to save designed features: %s", e)


# ---- Singleton ----

_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    """Get the singleton Orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
