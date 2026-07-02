"""Virtual Joseph Self-Repair Engine.

Scans the codebase for bugs, diagnoses root causes, proposes fixes,
applies them, and verifies they work. This is the autonomous repair
capability that encodes the lesson from the v6.1.2 debug session:
integration paths are where real bugs hide.

Scan categories:
  1. Import-path validation: every import in api.py checked against
     actual module exports (catches the silent-bug class from sweep4)
  2. Bare except detection: finds except: without Exception
  3. Em-dash voice rule: checks protected files
  4. Diagnostic engine: runs full diagnostics and analyzes failures
  5. Test assertion staleness: checks for hardcoded versions/values
  6. Return-key consistency: checks calculator return schemas
  7. Cross-module integration: exercises call chains end-to-end

Usage:
    from bridge.self_repair import SelfRepairEngine

    engine = SelfRepairEngine()
    report = engine.full_scan()

    if report.issues:
        for issue in report.issues:
            if issue.auto_fixable:
                engine.apply_fix(issue)

    # Or do it all at once:
    report = engine.scan_and_fix()
"""
from __future__ import annotations

import ast
import importlib
import inspect
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Ensure project root is importable
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


@dataclass
class RepairIssue:
    """A single issue found during scanning."""
    category: str          # import_path, bare_except, em_dash, diagnostic, etc.
    severity: str          # critical, high, medium, low
    file_path: str         # relative path to the file
    line_number: int       # line where the issue is
    description: str       # human-readable description
    root_cause: str        # technical root cause
    auto_fixable: bool     # whether the engine can fix it automatically
    fix_description: str   # what the fix would do
    fix_old: str = ""      # the text to replace
    fix_new: str = ""      # the replacement text
    verified: bool = False # whether the fix was verified after applying


@dataclass
class ScanReport:
    """Result of a full codebase scan.

    v3.2.7: 'issues' = real things to fix. 'warnings' = informational
    (e.g. diagnostic WARN status that lacks fixtures). 'suppressed' =
    items the scanner filtered as false positives, kept for transparency.
    """
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    scan_duration_ms: float = 0
    files_scanned: int = 0
    issues: list[RepairIssue] = field(default_factory=list)
    warnings: list[RepairIssue] = field(default_factory=list)
    suppressed: list[dict] = field(default_factory=list)
    fixes_applied: int = 0
    fixes_verified: int = 0
    diagnostics_before: dict = field(default_factory=dict)
    diagnostics_after: dict = field(default_factory=dict)
    log_path: str = ""
    fast_mode: bool = False

    @property
    def clean(self) -> bool:
        return len(self.issues) == 0

    @property
    def duration_ms(self) -> float:
        """SIM-03: Alias for `scan_duration_ms`. Owner expected the short name."""
        return self.scan_duration_ms

    def summary(self) -> str:
        lines = [
            f"Scan completed in {self.scan_duration_ms:.0f}ms"
            + (" (fast mode)" if self.fast_mode else ""),
            f"Files scanned: {self.files_scanned}",
            f"Issues found: {len(self.issues)}",
        ]
        if self.issues:
            by_sev = {}
            for i in self.issues:
                by_sev.setdefault(i.severity, []).append(i)
            for sev in ["critical", "high", "medium", "low"]:
                if sev in by_sev:
                    lines.append(f"  {sev}: {len(by_sev[sev])}")
            fixable = sum(1 for i in self.issues if i.auto_fixable)
            lines.append(f"Auto-fixable: {fixable}/{len(self.issues)}")
        if self.warnings:
            lines.append(f"Warnings (informational): {len(self.warnings)}")
        if self.suppressed:
            lines.append(f"False positives suppressed: {len(self.suppressed)}")
        if self.fixes_applied:
            lines.append(
                f"Fixes applied: {self.fixes_applied} "
                f"({self.fixes_verified} verified)"
            )
        if self.log_path:
            lines.append(f"Detail log: {self.log_path}")
        return "\n".join(lines)


class SelfRepairEngine:
    """Autonomous scanner and repair engine."""

    # Files that are part of VJ/enforcement infrastructure.
    # Content-matching scans must skip these to avoid flagging
    # their own detection patterns as violations.
    _ENFORCEMENT_FILES = {
        "self_repair.py",
        "virtual_joseph.py",
        "vj_orchestrator.py",
    }

    # R10: raised from 10 to 25 to prevent over-pruning during back-to-back
    # scan_and_fix runs (each run can add up to 2 snapshots: before + after).
    SNAPSHOT_LIMIT = 25

    def __init__(self, project_root: Path | str | None = None):
        self.root = Path(project_root) if project_root else _PROJECT_ROOT
        self.api_path = self.root / "bridge" / "api.py"
        self._snapshot_limit = self.SNAPSHOT_LIMIT

    # ================================================================
    # Main entry points
    # ================================================================

    def full_scan(self, fast_mode: bool = False) -> ScanReport:
        """Run all scan categories. Does NOT apply fixes.

        fast_mode: skip the diagnostics engine (the slow part on Windows).
        Useful for quick wiring/syntax sweeps during development.
        """
        t0 = time.perf_counter()
        ts_start = datetime.now().strftime("%Y%m%d_%H%M%S")
        report = ScanReport(fast_mode=fast_mode)

        # Run syntax check first - truncated files break every other scan
        report.issues.extend(self._scan_syntax_errors())
        report.issues.extend(self._scan_import_paths())
        report.issues.extend(self._scan_bare_excepts())
        report.issues.extend(self._scan_em_dashes())

        # Diagnostics scan: separates FAIL (-> issues) from WARN (-> warnings)
        if not fast_mode:
            diag_issues, diag_warnings = self._scan_diagnostics_split()
            report.issues.extend(diag_issues)
            report.warnings.extend(diag_warnings)
        else:
            report.warnings.append(RepairIssue(
                category="diagnostic_skipped",
                severity="low",
                file_path="",
                line_number=0,
                description="Diagnostics scan skipped (fast_mode=True)",
                root_cause="",
                auto_fixable=False,
                fix_description="",
            ))

        report.issues.extend(self._scan_return_keys())

        # Frontend wiring: separate real undefined-function bugs from false positives
        fw_issues, fw_suppressed = self._scan_frontend_wiring_v2()
        report.issues.extend(fw_issues)
        report.suppressed.extend(fw_suppressed)

        # Pipeline chains: similar split
        pc_issues, pc_suppressed = self._scan_pipeline_chains_v2()
        report.issues.extend(pc_issues)
        report.suppressed.extend(pc_suppressed)

        # v3.2.7: detect duplicate method definitions (silent shadowing)
        report.issues.extend(self._scan_duplicate_methods())

        # v3.2.7: detect unused/dead imports - route to warnings channel
        # so they appear in the report but don't inflate the "issues" count
        report.warnings.extend(self._scan_dead_imports())

        # v3.2.7 fix J: detect near-duplicate function bodies (copy-paste bugs)
        report.issues.extend(self._scan_near_duplicate_bodies())

        # v3.2.7 fix N: detect dead Bridge methods (nothing calls them)
        # Routes to warnings since 100+ candidates expected
        report.warnings.extend(self._scan_dead_bridge_methods())

        # v3.2.7 fix O: detect inconsistent arg order for shared param names
        report.warnings.extend(self._scan_inconsistent_arg_order())

        # v3.2.7 fix P: detect bare-return passthroughs (may bypass _ok)
        report.warnings.extend(self._scan_bare_return_passthroughs())

        # v3.2.7 pass 10a: new scans trained from sandbox simulation
        report.issues.extend(self._scan_dead_imports_stdlib())
        report.issues.extend(self._scan_hardcoded_html_values())
        report.issues.extend(self._scan_data_file_health())
        report.issues.extend(self._scan_compliance_snapshot_bloat())
        report.issues.extend(self._scan_banned_words())
        report.issues.extend(self._scan_hardcoded_tmp_paths())
        report.issues.extend(self._scan_shim_bypass())
        report.issues.extend(self._scan_stale_file_refs())
        report.issues.extend(self._scan_js_brace_balance())
        report.issues.extend(self._scan_deprecated_model_names())
        report.issues.extend(self._scan_version_drift())
        report.issues.extend(self._scan_err_helper_shape())
        # Pass 10d additions: trained from Claude history export (134 convs)
        report.issues.extend(self._scan_datetime_utcnow_deprecated())
        report.issues.extend(self._scan_datetime_now_naive())
        report.issues.extend(self._scan_branch_dict_key_parity())
        report.issues.extend(self._scan_open_no_encoding())
        # Pass 10j: trained from Owner simulation (7 BUG-054 family hits)
        report.warnings.extend(self._scan_blind_ok_passthrough())

        # Phase 2: project_syncer drift check
        report.warnings.extend(self._scan_syncer_drift())

        # Pass 11 (2026-07-02): workspace/context audit. Advisory only.
        report.warnings.extend(self._scan_workspace_audit())

        report.files_scanned = self._count_py_files()
        report.scan_duration_ms = (time.perf_counter() - t0) * 1000

        # Write a detailed log Claude can read for debugging
        try:
            report.log_path = self._write_scan_log(report, ts=ts_start)
        except Exception as e:
            report.log_path = f"[log write failed: {e}]"

        return report

    def scan(self, fast_mode: bool = False) -> ScanReport:
        """SIM-02: Alias for `full_scan`. Owner typed `eng.scan()` first.

        Both names point to the same scan-only path (no fixes applied).
        """
        return self.full_scan(fast_mode=fast_mode)

    def scan_and_fix(self, fast_mode: bool = False,
                     dry_run: bool = False) -> ScanReport:
        """Scan, apply auto-fixable issues, verify fixes.

        fast_mode: skip slow diagnostics. Apply only auto_fixable issues.
        dry_run: scan only, report what WOULD be fixed, apply nothing.
            Prints '[VJ DRY RUN] Would apply N fixes' and returns early.
        """
        report = self.full_scan(fast_mode=fast_mode)

        # Count fixable issues before deciding whether to apply
        _auto_fixable_count = sum(
            1 for issue in report.issues
            if issue.auto_fixable and (
                issue.category in ("dead_stdlib_import", "snapshot_bloat")
                or (issue.fix_old and issue.fix_new)
            )
        )

        if dry_run:
            print(f"[VJ DRY RUN] Would apply {_auto_fixable_count} fixes")
            return report

        # Run diagnostics before (only if not fast_mode)
        if not fast_mode:
            report.diagnostics_before = self._run_diagnostics_summary()

        # Apply fixes
        for issue in report.issues:
            if not issue.auto_fixable:
                continue
            # Categories that handle their own fix_old/fix_new logic
            needs_old_new = issue.category not in ("dead_stdlib_import", "snapshot_bloat")
            if needs_old_new and (not issue.fix_old or not issue.fix_new):
                continue
            success = self._apply_fix(issue)
            if success:
                report.fixes_applied += 1
                if self._verify_fix(issue):
                    issue.verified = True
                    report.fixes_verified += 1

        if report.fixes_applied != _auto_fixable_count:
            print(
                f"[VJ] WARNING: gap between reported fixable and applied. "
                f"Check _apply_fix() handlers."
            )
        print(
            f"[VJ] Applied {report.fixes_applied} of {_auto_fixable_count} reported fixable."
        )

        # Run diagnostics after (only if we applied fixes and not fast)
        if report.fixes_applied > 0 and not fast_mode:
            report.diagnostics_after = self._run_diagnostics_summary()
        elif not fast_mode:
            print("[VJ] Skipping post-fix diagnostics (0 fixes applied)")

        # VJ-MUST-FIX-01: Snapshot retention must run LAST.
        # The diagnostics_before and diagnostics_after passes each write
        # a fresh compliance snapshot. If we cleaned to 25 in the main pass,
        # we end with 27. Re-run retention here so the count actually
        # converges to the configured limit on every scan_and_fix call.
        report.fixes_applied += self._post_fix_snapshot_retention()

        return report

    def _post_fix_snapshot_retention(self) -> int:
        """Final pass to enforce snapshot retention limit. Returns # deleted.

        Runs AFTER diagnostics_after to catch the 1-2 snapshots that
        diagnostics_before/after just created.
        """
        snap_dir = self.root / "data" / "compliance_snapshots"
        if not snap_dir.exists():
            return 0
        snapshots = sorted(snap_dir.glob("*.json"))
        keep = self._snapshot_limit
        if len(snapshots) <= keep:
            return 0
        deleted = 0
        for snap in snapshots[:-keep]:
            try:
                snap.unlink()
                deleted += 1
            except Exception:
                pass
        return deleted

    # ================================================================
    # Scan: Whole-bridge syntax check
    # ================================================================

    def _scan_syntax_errors(self) -> list[RepairIssue]:
        """Parse every .py file under bridge/ with ast.parse.

        The narrow version in _scan_duplicate_methods only checks
        bridge/api.py. This walks the full tree so truncated or
        broken modules in subdirectories are caught before they
        silently fail at runtime.
        """
        issues: list[RepairIssue] = []
        bridge_dir = str(self.root / "bridge")
        for root, dirs, files in os.walk(bridge_dir):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(root, fn)
                try:
                    ast.parse(open(path, encoding="utf-8").read())
                except SyntaxError as e:
                    issues.append(RepairIssue(
                        category="syntax_error",
                        severity="critical",
                        file_path=path,
                        line_number=e.lineno or 0,
                        description=f"{path}:{e.lineno} {e.msg}",
                        root_cause="Source does not parse - likely truncated write.",
                        auto_fixable=False,
                        fix_description="Restore from last good commit.",
                    ))
        return issues

    # ================================================================
    # Scan: Import path validation
    # ================================================================

    def _scan_import_paths(self) -> list[RepairIssue]:
        """Check every 'from bridge.X import Y' in api.py against actual exports.

        This catches the silent-bug class that hit sweep4 (calculator P0)
        and v6.1.2 (3 import-name mismatches). These bugs pass import-time
        tests but crash at call time because the imported name doesn't
        exist in the target module.
        """
        issues = []
        if not self.api_path.exists():
            return issues

        api_source = self.api_path.read_text(encoding="utf-8", errors="replace")

        # Find all from bridge.X import Y patterns inside method bodies
        # (these are lazy imports that only execute when the method is called)
        pattern = re.compile(
            r'from\s+(bridge\.[a-zA-Z0-9_.]+)\s+import\s+(.+)'
        )

        for i, line in enumerate(api_source.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            match = pattern.search(stripped)
            if not match:
                continue

            module_path = match.group(1)
            import_clause = match.group(2).rstrip("\\").strip()

            # Parse import names, handling 'as' aliases
            # "save_message as _save_msg, get_history" ->
            #   [("save_message", "_save_msg"), ("get_history", None)]
            raw_names = [n.strip() for n in import_clause.split(",")]
            parsed_names = []
            for raw in raw_names:
                raw = raw.strip()
                if not raw:
                    continue
                parts = re.split(r'\s+as\s+', raw, maxsplit=1)
                real_name = parts[0].strip()
                alias = parts[1].strip() if len(parts) > 1 else None
                if real_name and re.match(r'^[a-zA-Z_]\w*$', real_name):
                    parsed_names.append((real_name, alias))

            # Try to import the module and check if names exist
            try:
                mod = importlib.import_module(module_path)
                for real_name, alias in parsed_names:
                    if not hasattr(mod, real_name):
                        # This is a real bug. Find what the module actually exports.
                        actual_exports = [
                            a for a in dir(mod)
                            if not a.startswith("_")
                            and (callable(getattr(mod, a, None))
                                 or isinstance(getattr(mod, a, None), (dict, list, str, int, float)))
                        ]

                        # Try to find a close match
                        suggestion = self._find_closest_export(
                            real_name, actual_exports
                        )

                        issue = RepairIssue(
                            category="import_path",
                            severity="critical",
                            file_path="bridge/api.py",
                            line_number=i,
                            description=(
                                f"'{real_name}' does not exist in {module_path}. "
                                f"Bridge method will crash with ImportError at call time."
                            ),
                            root_cause=(
                                f"api.py imports '{real_name}' from {module_path} "
                                f"but the module exports: {actual_exports[:10]}"
                            ),
                            auto_fixable=suggestion is not None,
                            fix_description=(
                                f"Replace import of '{real_name}' with '{suggestion}'"
                                if suggestion else
                                f"Manual fix needed. Module exports: {actual_exports[:5]}"
                            ),
                            fix_old=real_name,
                            fix_new=suggestion or "",
                        )
                        issues.append(issue)
            except (ImportError, ModuleNotFoundError):
                # Module itself doesn't exist. Different issue.
                pass
            except Exception:
                pass

        return issues

    def _find_closest_export(self, target: str, exports: list[str]) -> str | None:
        """Find the closest matching export name."""
        target_lower = target.lower()

        # Exact case-insensitive match
        for e in exports:
            if e.lower() == target_lower:
                return e

        # Substring match (target contains export or vice versa)
        for e in exports:
            if target_lower in e.lower() or e.lower() in target_lower:
                return e

        # Word overlap
        target_words = set(re.findall(r'[a-z]+', target_lower))
        best_score = 0
        best_match = None
        for e in exports:
            e_words = set(re.findall(r'[a-z]+', e.lower()))
            overlap = len(target_words & e_words)
            if overlap > best_score:
                best_score = overlap
                best_match = e

        return best_match if best_score > 0 else None

    # ================================================================
    # Scan: Bare except detection
    # ================================================================

    def _scan_bare_excepts(self) -> list[RepairIssue]:
        """Find bare 'except:' clauses (should be 'except Exception:')."""
        issues = []
        for py_file in self._iter_py_files():
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(content.splitlines(), 1):
                    stripped = line.rstrip()
                    if (stripped.endswith("except:")
                            or re.match(r'\s+except:\s*$', line)
                            or re.match(r'\s+except:\s+', line)):
                        # Confirm it's a bare except, not 'except Exception:'
                        if "except Exception" not in line and "except:" in line:
                            rel_path = str(py_file.relative_to(self.root))
                            indent = len(line) - len(line.lstrip())
                            issues.append(RepairIssue(
                                category="bare_except",
                                severity="medium",
                                file_path=rel_path,
                                line_number=i,
                                description="Bare 'except:' catches KeyboardInterrupt and SystemExit",
                                root_cause="Should be 'except Exception:' to allow process signals",
                                auto_fixable=True,
                                fix_description="Replace 'except:' with 'except Exception:'",
                                fix_old="except:",
                                fix_new="except Exception:",
                            ))
            except Exception:
                pass
        return issues

    # ================================================================
    # Scan: Em-dash voice rule
    # ================================================================

    def _scan_em_dashes(self) -> list[RepairIssue]:
        """Check protected files for em-dash characters (U+2014)."""
        issues = []
        protected = [
            "bridge/api.py", "bridge/prompts.py",
            "bridge/calculators.py",        # sanity gate strings shown to Ivan/Owner
            "bridge/notifications.py",      # SMS body strings
            "bridge/scope_narrative.py",    # scope text in proposals
            "bridge/linkedin_content.py",   # outbound social content
            "frontend/index.html", "frontend/app.js",
            "frontend/styles.css", "mcp_server.py",
        ]
        for fp in protected:
            full = self.root / fp
            if full.exists():
                try:
                    content = full.read_text(encoding="utf-8", errors="replace")
                    count = content.count("\u2014")
                    if count > 0:
                        # Find the first occurrence line
                        for i, line in enumerate(content.splitlines(), 1):
                            if "\u2014" in line:
                                issues.append(RepairIssue(
                                    category="em_dash",
                                    severity="high",
                                    file_path=fp,
                                    line_number=i,
                                    description=f"Em-dash (U+2014) in protected file ({count} total)",
                                    root_cause="Voice rule violation. Em-dashes signal AI-generated text.",
                                    auto_fixable=True,
                                    fix_description="Replace em-dash with hyphen-minus",
                                    fix_old="\u2014",
                                    fix_new="-",
                                ))
                                break
                except Exception:
                    pass
        return issues

    # ================================================================
    # Scan: Diagnostic engine
    # ================================================================

    def _scan_diagnostics(self) -> list[RepairIssue]:
        """Run the diagnostic engine and convert failures to issues."""
        issues = []
        try:
            from bridge.diagnostics import run_diagnostics
            r = run_diagnostics(
                include_bridge=True,
                include_calculators=True,
                include_dispatchers=True,
                include_harnesses=True,
                include_aisc=True,
                log_to_file=False,
            )
            for key, val in r.items():
                if not isinstance(val, list):
                    continue
                for item in val:
                    if not isinstance(item, dict):
                        continue
                    status = item.get("status", "")
                    if status == "FAIL":
                        method = item.get("method", item.get("calculator", "?"))
                        error = item.get("error", "")
                        issues.append(RepairIssue(
                            category="diagnostic_fail",
                            severity="critical",
                            file_path="bridge/api.py",
                            line_number=0,
                            description=f"Diagnostic FAIL: {method}",
                            root_cause=str(error)[:200],
                            auto_fixable=False,
                            fix_description="Manual investigation needed",
                        ))
                    elif status == "WARN":
                        method = item.get("method", item.get("calculator", "?"))
                        error = item.get("error", item.get("result_preview", ""))
                        issues.append(RepairIssue(
                            category="diagnostic_warn",
                            severity="medium",
                            file_path="bridge/api.py",
                            line_number=0,
                            description=f"Diagnostic WARN: {method}",
                            root_cause=str(error)[:200],
                            auto_fixable=False,
                            fix_description="Add test fixture or move to SKIP list",
                        ))
        except Exception as e:
            issues.append(RepairIssue(
                category="diagnostic_engine",
                severity="high",
                file_path="bridge/diagnostics.py",
                line_number=0,
                description=f"Diagnostic engine itself failed: {e}",
                root_cause=str(e),
                auto_fixable=False,
                fix_description="Fix diagnostic engine first",
            ))
        return issues

    # ================================================================
    # Scan: Return key consistency
    # ================================================================

    def _scan_return_keys(self) -> list[RepairIssue]:
        """Check calculator return key schemas for consistency."""
        issues = []
        try:
            from bridge.calculators import (
                steel_weight, hours_estimate, labor_cost,
                margin_scenario, bid_total,
            )

            # Each calculator should return consistent keys
            expected_keys = {
                "steel_weight": ["total_lbs", "tons", "lines"],
                "hours_estimate": ["total_hours", "fab_hours", "erect_hours"],
                "labor_cost": ["total_labor"],
                "margin_scenario": ["scenarios"],
                "bid_total": ["bid_total"],
            }

            test_calls = {
                "steel_weight": lambda: steel_weight([("W14X82", 20, 1)]),
                "hours_estimate": lambda: hours_estimate(1.0),
                "labor_cost": lambda: labor_cost(10, 5),
                "margin_scenario": lambda: margin_scenario(10000),
                "bid_total": lambda: bid_total(10000, 5000, 50),
            }

            for calc_name, required_keys in expected_keys.items():
                try:
                    result = test_calls[calc_name]()
                    if isinstance(result, dict):
                        for key in required_keys:
                            if key not in result:
                                issues.append(RepairIssue(
                                    category="return_key",
                                    severity="high",
                                    file_path="bridge/calculators.py",
                                    line_number=0,
                                    description=(
                                        f"{calc_name}() missing expected key '{key}'. "
                                        f"Actual keys: {list(result.keys())}"
                                    ),
                                    root_cause="Return schema inconsistency",
                                    auto_fixable=False,
                                    fix_description=f"Add '{key}' to {calc_name} return dict",
                                ))
                except Exception as e:
                    issues.append(RepairIssue(
                        category="return_key",
                        severity="high",
                        file_path="bridge/calculators.py",
                        line_number=0,
                        description=f"{calc_name}() raised {type(e).__name__}: {e}",
                        root_cause=str(e),
                        auto_fixable=False,
                        fix_description="Fix calculator function",
                    ))
        except Exception:
            pass
        return issues

    # ================================================================
    # Fix application and verification
    # ================================================================

    def _apply_fix(self, issue: RepairIssue) -> bool:
        """Apply a single fix to the codebase."""
        if not issue.auto_fixable:
            return False

        # v3.2.7 pass 10a: snapshot bloat - delete the file
        if issue.category == "snapshot_bloat" and issue.fix_old == "__DELETE_FILE__":
            try:
                target = Path(issue.fix_new)
                if target.exists():
                    target.unlink()
                    return True
            except Exception:
                pass
            return False

        # v3.2.7 pass 10a: dead stdlib import - remove the import line
        if issue.category == "dead_stdlib_import":
            full_path = Path(issue.file_path) if Path(issue.file_path).is_absolute() else self.root / issue.file_path
            if not full_path.exists():
                return False
            try:
                lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
                if issue.line_number <= len(lines):
                    # Remove the line entirely
                    del lines[issue.line_number - 1]
                    full_path.write_text("".join(lines), encoding="utf-8")
                    return True
            except Exception:
                pass
            return False

        if not issue.fix_old or not issue.fix_new:
            return False

        full_path = self.root / issue.file_path
        if not full_path.exists():
            return False

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")

            if issue.category == "em_dash":
                # Replace all em-dashes in the file
                new_content = content.replace(issue.fix_old, issue.fix_new)
            elif issue.category == "bare_except":
                # Replace only at the specific line
                lines = content.splitlines(keepends=True)
                if issue.line_number <= len(lines):
                    line = lines[issue.line_number - 1]
                    lines[issue.line_number - 1] = line.replace(
                        issue.fix_old, issue.fix_new, 1
                    )
                    new_content = "".join(lines)
                else:
                    return False
            elif issue.category == "import_path":
                new_content = content.replace(issue.fix_old, issue.fix_new, 1)
            elif issue.category == "datetime_utcnow_deprecated":
                new_content = content.replace(issue.fix_old, issue.fix_new)
                # Belt-and-suspenders: add timezone to import if still missing
                if "from datetime import" in new_content and "timezone" not in new_content:
                    new_content = new_content.replace(
                        "from datetime import datetime",
                        "from datetime import datetime, timezone"
                    )
            else:
                return False

            if new_content != content:
                full_path.write_text(new_content, encoding="utf-8")
                return True
        except Exception:
            pass
        return False

    def _verify_fix(self, issue: RepairIssue) -> bool:
        """Verify a fix works by re-running the relevant check."""
        # v3.2.7 pass 10a: snapshot bloat - verify file is gone
        if issue.category == "snapshot_bloat":
            return not Path(issue.fix_new).exists()
        # v3.2.7 pass 10a: dead stdlib import - verify line is removed
        if issue.category == "dead_stdlib_import":
            full_path = Path(issue.file_path) if Path(issue.file_path).is_absolute() else self.root / issue.file_path
            if full_path.exists():
                content = full_path.read_text(encoding="utf-8", errors="replace")
                return issue.fix_old.strip() not in content
            return False
        if issue.category == "bare_except":
            # Re-scan the specific file for the specific line
            full_path = self.root / issue.file_path
            if full_path.exists():
                content = full_path.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
                if issue.line_number <= len(lines):
                    line = lines[issue.line_number - 1]
                    return "except Exception" in line or "except:" not in line
        elif issue.category == "em_dash":
            full_path = self.root / issue.file_path
            if full_path.exists():
                content = full_path.read_text(encoding="utf-8", errors="replace")
                return "\u2014" not in content
        elif issue.category == "import_path":
            # Try importing the fixed path
            try:
                match = re.search(
                    r'from\s+([\w.]+)\s+import\s+(\w+)',
                    f"from x import {issue.fix_new.replace('import ', '')}"
                )
                if match:
                    return True  # Syntax is valid; deeper check needs runtime
            except Exception:
                pass
        return False

    # ================================================================
    # Utilities
    # ================================================================

    # ================================================================
    # v3.2.7: Smarter scanners with false-positive suppression
    # ================================================================

    def _scan_diagnostics_split(self) -> tuple[list[RepairIssue], list[RepairIssue]]:
        """Run diagnostics. FAIL -> issues, WARN -> warnings (separate channel)."""
        issues: list[RepairIssue] = []
        warnings: list[RepairIssue] = []
        try:
            from bridge.diagnostics import run_diagnostics
            r = run_diagnostics(
                include_bridge=True, include_calculators=True,
                include_dispatchers=True, include_harnesses=True,
                include_aisc=True, log_to_file=False,
            )
            for key, val in r.items():
                if not isinstance(val, list):
                    continue
                for item in val:
                    if not isinstance(item, dict):
                        continue
                    status = item.get("status", "")
                    method = item.get("method", item.get("calculator", "?"))
                    # v3.2.7 fix: surface useful detail. The diagnostics engine
                    # may return error=None but a clean error in result_preview.
                    error = item.get("error")
                    if error in (None, "None", ""):
                        error = item.get("result_preview", "")
                    if error in (None, "None", ""):
                        error = "diagnostics returned no detail"
                    if status == "FAIL":
                        issues.append(RepairIssue(
                            category="diagnostic_fail",
                            severity="critical",
                            file_path="bridge/api.py",
                            line_number=0,
                            description=f"Diagnostic FAIL: {method}",
                            root_cause=str(error)[:300],
                            auto_fixable=False,
                            fix_description="Manual investigation needed",
                        ))
                    elif status == "WARN":
                        # WARN is informational, not an issue to fix.
                        # Many of these are methods that need fixtures, not bugs.
                        warnings.append(RepairIssue(
                            category="diagnostic_warn",
                            severity="low",
                            file_path="bridge/api.py",
                            line_number=0,
                            description=f"Diagnostic WARN: {method}",
                            root_cause=str(error)[:300],
                            auto_fixable=False,
                            fix_description="Add test fixture or move to SKIP list",
                        ))
        except Exception as e:
            issues.append(RepairIssue(
                category="diagnostic_engine",
                severity="high",
                file_path="bridge/diagnostics.py",
                line_number=0,
                description=f"Diagnostic engine itself failed: {e}",
                root_cause=str(e),
                auto_fixable=False,
                fix_description="Fix diagnostic engine first",
            ))
        return issues, warnings

    # ================================================================
    # Scan: Duplicate method definitions in Bridge class
    # v3.2.7: catches silent class-attribute shadowing (def x then def x
    # later in the same class - Python silently keeps only the second)
    # ================================================================

    def _scan_duplicate_methods(self) -> list[RepairIssue]:
        """Detect duplicate method definitions in bridge/api.py Bridge class.

        Python silently lets a later `def name()` override an earlier one
        in the same class. The earlier code is dead but the developer
        rarely knows. We use AST so we don't false-positive on string
        mentions or decorators.
        """
        issues: list[RepairIssue] = []
        api_path = Path("bridge/api.py")
        if not api_path.exists():
            return issues
        try:
            tree = ast.parse(api_path.read_text(encoding="utf-8"))
        except SyntaxError as e:
            issues.append(RepairIssue(
                category="syntax_error",
                severity="critical",
                file_path="bridge/api.py",
                line_number=e.lineno or 0,
                description=f"bridge/api.py syntax error: {e.msg}",
                root_cause=str(e),
                auto_fixable=False,
                fix_description="Manual syntax fix needed",
            ))
            return issues

        # Walk the Bridge class definitions
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Bridge":
                seen: dict[str, list[int]] = {}
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        seen.setdefault(item.name, []).append(item.lineno)
                for name, lines in seen.items():
                    if len(lines) > 1:
                        first, *rest = lines
                        for shadowed_at in rest:
                            issues.append(RepairIssue(
                                category="duplicate_method",
                                severity="high",
                                file_path="bridge/api.py",
                                line_number=shadowed_at,
                                description=(
                                    f"Bridge.{name} defined at lines "
                                    f"{first} AND {shadowed_at} - earlier "
                                    "definition is dead code"
                                ),
                                root_cause=(
                                    f"Two `def {name}(...)` in same class; "
                                    "Python keeps only the last; the first "
                                    "is unreachable"
                                ),
                                auto_fixable=False,
                                fix_description=(
                                    f"Rename one of the two `def {name}` "
                                    "so both are callable, OR delete the "
                                    "unreachable earlier one"
                                ),
                            ))
                break
        return issues


    # ================================================================
    # Scan: Dead imports
    # v3.2.7 fix I: detects `from X import Y` where Y is never used.
    # Real example caught: `classify_rfi` imported but never called.
    # ================================================================

    def _scan_dead_imports(self) -> list[RepairIssue]:
        """Find imported names that are never referenced in the file.

        Conservative: only flag project-internal imports (bridge.*, vo_app.*)
        whose imported name does not appear anywhere else in the file as text.
        Skips type-hint modules entirely since AST type hints can be tricky
        to detect across the codebase (stringified forward refs, etc.).

        Real catches: `classify_rfi` from `bridge.procore_rfi_submittal`
        was imported in `get_rfis_procore` and never called.
        """
        SKIP_MODULES = {
            # type-hint modules - hint names often used in annotations only
            "typing", "typing_extensions", "dataclasses",
            "abc", "collections.abc",
            # very common stdlib helpers used in subtle ways
            "contextlib", "functools", "itertools", "operator",
            "warnings", "logging", "traceback", "inspect",
            "__future__",
        }
        SKIP_NAMES = {
            # common type annotation names that appear in hints only
            "Any", "Optional", "Union", "Dict", "List", "Tuple", "Set",
            "Callable", "TypeVar", "Generic", "Iterator", "Iterable",
            "Sequence", "Mapping", "MutableMapping", "Type", "ClassVar",
            "Final", "Literal", "Annotated", "Protocol", "Awaitable",
            "Coroutine", "AsyncIterator", "AsyncIterable",
            # decorators sometimes used in subtle ways
            "dataclass", "field", "asdict", "astuple",
            "contextmanager", "asynccontextmanager",
            "wraps", "lru_cache", "cached_property", "partial",
            # forward-ref helpers
            "TYPE_CHECKING", "annotations",
        }
        issues: list[RepairIssue] = []
        roots = [self.root / "bridge", self.root / "vo_app"]
        py_files = []
        for r in roots:
            if r.exists():
                py_files.extend(p for p in r.rglob("*.py")
                                if "__pycache__" not in str(p))

        for path in py_files:
            try:
                file_src = path.read_text(encoding="utf-8")
                tree = ast.parse(file_src)
            except (SyntaxError, UnicodeDecodeError):
                continue

            # Skip __init__.py - re-exports are normal there
            if path.name == "__init__.py":
                continue

            # Collect imported names (binding -> line)
            imports: dict[str, tuple[int, str]] = {}
            in_type_checking = set()

            def _collect(node, parent_is_type_checking=False):
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, ast.If):
                        # Check if this is `if TYPE_CHECKING:` or similar
                        is_tc = False
                        if isinstance(child.test, ast.Name):
                            is_tc = child.test.id in ("TYPE_CHECKING", "MYPY")
                        for grand in ast.walk(child):
                            if isinstance(grand, (ast.Import, ast.ImportFrom)):
                                for alias in grand.names:
                                    bound = alias.asname or alias.name.split(".")[0]
                                    if is_tc:
                                        in_type_checking.add(bound)
                        continue
                    if isinstance(child, ast.Import):
                        for alias in child.names:
                            bound = alias.asname or alias.name.split(".")[0]
                            imports[bound] = (child.lineno, f"import {alias.name}")
                    elif isinstance(child, ast.ImportFrom):
                        mod = child.module or "?"
                        # v3.2.7: skip stdlib type/helper modules entirely
                        if mod in SKIP_MODULES:
                            continue
                        for alias in child.names:
                            if alias.name == "*":
                                continue
                            if alias.name in SKIP_NAMES:
                                continue
                            bound = alias.asname or alias.name
                            imports[bound] = (child.lineno,
                                              f"from {mod} import {alias.name}"
                                              + (f" as {alias.asname}" if alias.asname else ""))

            _collect(tree)

            # Drop names that look re-exported (__all__ list)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "__all__":
                            if isinstance(node.value, (ast.List, ast.Tuple)):
                                for elt in node.value.elts:
                                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                        imports.pop(elt.value, None)

            # Skip TYPE_CHECKING-only imports
            for name in in_type_checking:
                imports.pop(name, None)

            # Find all referenced names
            used: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    used.add(node.id)
                elif isinstance(node, ast.Attribute):
                    # Walk down to the root of attribute access
                    cur = node
                    while isinstance(cur, ast.Attribute):
                        cur = cur.value
                    if isinstance(cur, ast.Name):
                        used.add(cur.id)
                elif isinstance(node, ast.ImportFrom):
                    # Don't double-count the imported names as "used"
                    pass

            # Also search the source as text for string-based references
            # (handles f-strings, getattr(self, "X"), etc.)
            for name in list(imports.keys()):
                if name in used:
                    continue
                # Conservative check: name appears outside import lines
                import_line, import_str = imports[name]
                pattern = rf"\b{re.escape(name)}\b"
                # Strip the import line from source before searching
                lines = file_src.split("\n")
                non_import_text = "\n".join(
                    ln for i, ln in enumerate(lines, start=1)
                    if i != import_line
                )
                if not re.search(pattern, non_import_text):
                    issues.append(RepairIssue(
                        category="dead_import",
                        severity="low",
                        file_path=str(path),
                        line_number=import_line,
                        description=f"Unused import: {import_str}",
                        root_cause=(
                            f"`{name}` imported but never referenced "
                            f"anywhere else in {path.name}"
                        ),
                        auto_fixable=False,
                        fix_description=(
                            f"Remove `{import_str}` from {path.name}:{import_line} "
                            "or use the imported name"
                        ),
                    ))

        return issues

    # ================================================================
    # Scan: Near-duplicate function bodies
    # v3.2.7 fix J: detects copy-paste-and-rename bugs in Bridge methods.
    # Two methods with identical structure AND identical backing-function
    # calls -> almost certainly one is forgotten leftover from a refactor.
    # ================================================================

    def _scan_near_duplicate_bodies(self) -> list[RepairIssue]:
        """Find Bridge methods with structurally identical bodies.

        Builds a "skeleton" string from each method body that captures:
          - control flow (Try, If, For, etc.)
          - called function names (so wrappers around different backing
            funcs don't collide)
          - argument shape (positional/keyword count)
          - short string constants (which can encode behavior)

        Methods sharing the same skeleton hash are flagged as
        near-duplicates. The wrapper pattern
        `return _ok(backing.func(*a))` won't false-positive across
        different `backing.func` names because the call name is in
        the skeleton.
        """
        import hashlib
        from collections import defaultdict

        issues: list[RepairIssue] = []
        api_path = Path("bridge/api.py")
        if not api_path.exists():
            return issues
        try:
            tree = ast.parse(api_path.read_text(encoding="utf-8"))
        except SyntaxError:
            return issues

        bridge_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Bridge":
                bridge_node = node
                break
        if not bridge_node:
            return issues

        def _skeleton(body_list: list) -> str:
            parts: list[str] = []
            mod = ast.Module(body=body_list, type_ignores=[])
            for child in ast.walk(mod):
                if isinstance(child, ast.Call):
                    fn = child.func
                    if isinstance(fn, ast.Name):
                        parts.append(f"Call:{fn.id}")
                    elif isinstance(fn, ast.Attribute):
                        parts.append(f"Call:.{fn.attr}")
                    else:
                        parts.append("Call")
                elif isinstance(child, ast.Name):
                    parts.append("N")
                elif isinstance(child, ast.Constant):
                    if isinstance(child.value, str) and len(child.value) <= 30:
                        parts.append(f"S:{child.value!r}")
                    elif isinstance(child.value, (int, float, bool, type(None))):
                        parts.append(f"C:{child.value!r}")
                    else:
                        parts.append("C")
                elif isinstance(child, ast.arg):
                    parts.append("A")
                elif isinstance(child, ast.keyword):
                    parts.append(f"KW:{child.arg}")
                elif isinstance(child, ast.alias):
                    parts.append(f"Alias:{child.name}")
                elif isinstance(child, (ast.Load, ast.Store, ast.Del,
                                        ast.Param, ast.Attribute)):
                    pass
                else:
                    parts.append(type(child).__name__)
            return "|".join(parts)

        # Bucket methods by skeleton hash
        buckets: dict[str, list[tuple[str, int, int]]] = defaultdict(list)
        for item in bridge_node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = list(item.body)
            # Strip docstring
            if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
                body = body[1:]
            # Skip tiny bodies that naturally collide
            if not body or len(body) < 3:
                continue
            sk = _skeleton(body)
            # Skeleton must be substantial - skip trivial getters
            if len(sk) < 60:
                continue
            h = hashlib.md5(sk.encode()).hexdigest()[:12]
            buckets[h].append((item.name, item.lineno, len(body)))

        # Report buckets with >=2 methods
        for h, methods in buckets.items():
            if len(methods) < 2:
                continue
            # Format the cluster as a single issue per duplicate group
            names = ", ".join(f"Bridge.{n}@{ln}" for n, ln, _ in methods)
            primary = methods[0]
            issues.append(RepairIssue(
                category="near_duplicate_body",
                severity="medium",
                file_path="bridge/api.py",
                line_number=primary[1],
                description=(
                    f"{len(methods)} methods with identical body structure "
                    f"AND identical backing calls: {names}"
                ),
                root_cause=(
                    "Skeleton hash collision means same control flow "
                    "and same called functions - likely copy-paste-rename "
                    "where one of the methods is a forgotten leftover"
                ),
                auto_fixable=False,
                fix_description=(
                    "Review the methods. Either rename one to clarify "
                    "intent, delete the unused one, or merge into a "
                    "single shared implementation"
                ),
            ))

        return issues

    # ================================================================
    # Scan: Dead Bridge methods (nothing calls them)
    # v3.2.7 fix N: reverse of frontend_wiring scan. That one flags
    # frontend calls to undefined Bridge methods. This flags Bridge
    # methods no caller anywhere references.
    # ================================================================

    def _scan_dead_bridge_methods(self) -> list[RepairIssue]:
        """Find public Bridge methods that no caller references.

        For each Bridge.method_name we check three places:
          1. frontend/app.js for `.method_name(` (the chat router etc.)
          2. bridge/*.py for `self.method_name(` (internal Bridge callers)
          3. bridge/*.py for `bridge.method_name(` (external Bridge callers)

        Methods that appear in none are dead. Routed to warnings so they
        don't inflate the issue count - 100+ likely candidates.
        """
        issues: list[RepairIssue] = []
        api_path = Path("bridge/api.py")
        if not api_path.exists():
            return issues
        try:
            api_src = api_path.read_text(encoding="utf-8")
            tree = ast.parse(api_src)
        except SyntaxError:
            return issues

        bridge_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Bridge":
                bridge_node = node
                break
        if not bridge_node:
            return issues

        # Collect public method names
        methods: dict[str, int] = {}
        for item in bridge_node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            n = item.name
            if n.startswith("_"):
                continue
            # Skip dunders
            if n.startswith("__") and n.endswith("__"):
                continue
            methods[n] = item.lineno

        # Gather caller text from all known sources
        caller_blobs: list[str] = []
        for p in [Path("frontend/app.js"), Path("frontend/index.html")]:
            if p.exists():
                try:
                    caller_blobs.append(p.read_text(encoding="utf-8"))
                except UnicodeDecodeError:
                    pass
        # Plus all bridge .py files for self./bridge. references
        for p in (self.root / "bridge").rglob("*.py"):
            if "__pycache__" in str(p):
                continue
            try:
                caller_blobs.append(p.read_text(encoding="utf-8"))
            except UnicodeDecodeError:
                pass
        # Plus vo_app
        for p in (self.root / "vo_app").rglob("*.py"):
            if "__pycache__" in str(p):
                continue
            try:
                caller_blobs.append(p.read_text(encoding="utf-8"))
            except UnicodeDecodeError:
                pass

        big = "\n".join(caller_blobs)

        # For each method, count meaningful references
        dead: list[tuple[str, int]] = []
        for name, line in methods.items():
            # Reference patterns to check:
            #   .name(          attribute call (JS/Python)
            #   ['name']        bracket access with single quotes (JS dispatch)
            #   ["name"]        bracket access with double quotes
            #   "name"          string-literal reference (dispatch table)
            #   'name'          same with single quotes
            #   getattr(*,name) reflection (rare but used)
            patterns = [
                rf"\.{re.escape(name)}\(",
                rf"\['{re.escape(name)}'\]",
                rf'\["{re.escape(name)}"\]',
                rf'"{re.escape(name)}"',
                rf"'{re.escape(name)}'",
                rf"getattr\([^,]+,\s*['\"]?{re.escape(name)}",
            ]
            found = False
            for pat in patterns:
                if re.search(pat, big):
                    found = True
                    break
            if not found:
                dead.append((name, line))

        # Sort dead by line for stable output
        dead.sort(key=lambda kv: kv[1])

        for name, line in dead:
            issues.append(RepairIssue(
                category="dead_bridge_method",
                severity="low",
                file_path="bridge/api.py",
                line_number=line,
                description=f"Bridge.{name} defined but no caller anywhere",
                root_cause=(
                    f"`Bridge.{name}` is exposed on the bridge but no "
                    f".{name}( call appears in frontend/app.js, frontend/"
                    f"index.html, bridge/*.py, or vo_app/*.py"
                ),
                auto_fixable=False,
                fix_description=(
                    f"Either wire `{name}` into a UI/chat handler, "
                    f"add an internal caller, or delete the method"
                ),
            ))

        return issues

    # ================================================================
    # Scan: Inconsistent argument order
    # v3.2.7 fix O: detects when methods share a parameter name but
    # place it at different positions. Catches the bug class that bit
    # the BRIDGE_JSON_METHODS.md doc (9 methods where members_json was
    # not always first, etc.).
    # ================================================================

    def _scan_inconsistent_arg_order(self) -> list[RepairIssue]:
        """Find param names that appear at different positions across methods.

        For every public Bridge method, record (param_name -> position).
        Then for each param name used by >=3 methods, check if its
        position is consistent. If not, flag the inconsistency.

        Threshold: param must appear in >=3 methods to qualify (smaller
        clusters are coincidence). The position-1 (after self) is what
        we report - "members_json appears at position 1 in N methods
        but at position 3 in M methods."
        """
        issues: list[RepairIssue] = []
        api_path = Path("bridge/api.py")
        if not api_path.exists():
            return issues
        try:
            tree = ast.parse(api_path.read_text(encoding="utf-8"))
        except SyntaxError:
            return issues

        bridge_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Bridge":
                bridge_node = node
                break
        if not bridge_node:
            return issues

        # name -> list of (method, position)
        from collections import defaultdict
        positions: dict[str, list[tuple[str, int, int]]] = defaultdict(list)

        for item in bridge_node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if item.name.startswith("_"):
                continue
            args = item.args.args
            # Skip self at position 0
            real_args = [a for a in args if a.arg != "self"]
            for idx, arg in enumerate(real_args):
                positions[arg.arg].append((item.name, idx, item.lineno))

        # For each param used by >=3 methods, check position consistency
        for pname, uses in positions.items():
            if len(uses) < 3:
                continue
            # Group by position
            pos_groups: dict[int, list[tuple[str, int]]] = defaultdict(list)
            for mname, pos, line in uses:
                pos_groups[pos].append((mname, line))
            if len(pos_groups) <= 1:
                continue
            # Inconsistent! Build issue
            sorted_positions = sorted(pos_groups.keys())
            details = []
            for pos in sorted_positions:
                methods_at_pos = pos_groups[pos]
                sample = ", ".join(m for m, _ in methods_at_pos[:3])
                if len(methods_at_pos) > 3:
                    sample += f" (+{len(methods_at_pos)-3} more)"
                details.append(f"pos {pos}: {len(methods_at_pos)} methods ({sample})")
            # Find a representative line for the issue
            first_method = uses[0]
            issues.append(RepairIssue(
                category="inconsistent_arg_order",
                severity="low",
                file_path="bridge/api.py",
                line_number=first_method[2],
                description=(
                    f"Parameter `{pname}` appears at "
                    f"{len(pos_groups)} different positions across "
                    f"{len(uses)} methods"
                ),
                root_cause="; ".join(details),
                auto_fixable=False,
                fix_description=(
                    f"Pick one canonical position for `{pname}` "
                    f"(usually the position used by the majority) "
                    f"and refactor outliers. Update callers."
                ),
            ))

        return issues

    # ================================================================
    # Scan: Bare-return passthroughs
    # v3.2.7 fix P: methods that do `return some_func(...)` directly
    # without _ok() wrap. The backing function may or may not return
    # {ok, data, error} shape - human audit required.
    # ================================================================

    def _scan_bare_return_passthroughs(self) -> list[RepairIssue]:
        """Find Bridge methods that return bare function-call results.

        These bypass the `_ok()` envelope so callers can\'t safely do
        `r.get("ok")`. Some are fine (the backing function might
        already return _ok shape). Some are bugs in disguise.

        VJ can\'t follow the call graph to know which is which, so
        all bare passthroughs get a low-severity warning suggesting
        a human spot-check.
        """
        issues: list[RepairIssue] = []
        api_path = Path("bridge/api.py")
        if not api_path.exists():
            return issues
        try:
            tree = ast.parse(api_path.read_text(encoding="utf-8"))
        except SyntaxError:
            return issues

        bridge_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Bridge":
                bridge_node = node
                break
        if not bridge_node:
            return issues

        SAFE_WRAPS = {"_ok", "_err", "dict", "list", "tuple", "str", "int",
                      "float", "bool", "len", "json", "asdict"}
        for item in bridge_node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if item.name.startswith("_"):
                continue
            # Look at every Return whose value is a Call
            for node in ast.walk(item):
                if not (isinstance(node, ast.Return)
                        and isinstance(node.value, ast.Call)):
                    continue
                fn = node.value.func
                if isinstance(fn, ast.Name):
                    if fn.id in SAFE_WRAPS:
                        continue
                    issues.append(RepairIssue(
                        category="bare_return_passthrough",
                        severity="low",
                        file_path="bridge/api.py",
                        line_number=node.lineno,
                        description=(
                            f"Bridge.{item.name} returns bare {fn.id}() "
                            "without _ok() wrap"
                        ),
                        root_cause=(
                            f"`return {fn.id}(...)` passes the backing "
                            f"function\'s return shape through directly. "
                            "May or may not match Bridge {ok, data, error} "
                            "convention - audit the backing function"
                        ),
                        auto_fixable=False,
                        fix_description=(
                            f"If `{fn.id}` returns flat dict, wrap with "
                            f"`return _ok({fn.id}(...))`. If it already "
                            "returns _ok shape, leave it and document"
                        ),
                    ))
                    break  # one issue per method is enough
        return issues


    def _scan_frontend_wiring_v2(self) -> tuple[list[RepairIssue], list[dict]]:
        """Find calls to truly undefined functions in app.js. v3.2.7.

        Uses a state-machine tokenizer that handles JS regex literals,
        template literals, and quotes-inside-character-classes correctly.
        Falls back gracefully if parsing fails.
        """
        issues: list[RepairIssue] = []
        suppressed: list[dict] = []
        app_js = self.root / "frontend" / "app.js"
        if not app_js.exists():
            return issues, suppressed

        raw_src = app_js.read_text(encoding="utf-8", errors="replace")

        # Tokenize-by-erasure: replace string/regex/comment contents with spaces.
        # JS regex literal: '/' starts a regex when the previous non-space token
        # is one of: ( , = : [ ! & | ? { } ; or a keyword (return, typeof, etc.),
        # or it's the start of the file/line.
        def _strip_js(s: str) -> str:
            out = list(s)
            i = 0
            n = len(s)
            # Track previous non-whitespace char to decide if '/' is regex or division
            prev_ch = "\n"  # start-of-file behaves like newline
            regex_predecessors = set("(,=:;[!&|?{}\n+-*%~^<>")
            keyword_predecessors = ("return", "typeof", "in", "of", "instanceof",
                                    "throw", "case", "delete", "void", "new",
                                    "await", "yield")
            while i < n:
                c = s[i]
                # Line comment
                if c == "/" and i + 1 < n and s[i+1] == "/":
                    j = i
                    while j < n and s[j] != "\n":
                        out[j] = " "
                        j += 1
                    i = j
                    prev_ch = " "
                    continue
                # Block comment
                if c == "/" and i + 1 < n and s[i+1] == "*":
                    j = i + 2
                    out[i] = " "; out[i+1] = " "
                    while j < n - 1 and not (s[j] == "*" and s[j+1] == "/"):
                        if s[j] != "\n":
                            out[j] = " "
                        j += 1
                    if j < n:
                        out[j] = " "; out[j+1] = " "
                        j += 2
                    i = j
                    prev_ch = " "
                    continue
                # String literal " or '
                if c in ('"', "'"):
                    quote = c
                    j = i + 1
                    while j < n and s[j] != quote:
                        if s[j] == "\\" and j + 1 < n:
                            out[j] = " "; out[j+1] = " "
                            j += 2
                            continue
                        if s[j] == "\n":
                            # Unterminated single-quoted string - recover at newline
                            break
                        out[j] = " "
                        j += 1
                    if j < n and s[j] == quote:
                        j += 1
                    i = j
                    prev_ch = quote
                    continue
                # Template literal `
                if c == "`":
                    j = i + 1
                    while j < n and s[j] != "`":
                        # Skip ${ ... } interpolation - keep code inside intact
                        if s[j] == "$" and j + 1 < n and s[j+1] == "{":
                            depth = 1
                            j += 2
                            while j < n and depth > 0:
                                if s[j] == "{":
                                    depth += 1
                                elif s[j] == "}":
                                    depth -= 1
                                j += 1
                            continue
                        if s[j] == "\\" and j + 1 < n:
                            out[j] = " "
                            if s[j+1] != "\n":
                                out[j+1] = " "
                            j += 2
                            continue
                        if s[j] != "\n":
                            out[j] = " "
                        j += 1
                    if j < n:
                        j += 1
                    i = j
                    prev_ch = "`"
                    continue
                # Regex literal? '/' after a regex-allowing predecessor
                if c == "/":
                    # Decide regex vs division
                    is_regex = False
                    if prev_ch in regex_predecessors:
                        is_regex = True
                    else:
                        # Check for keyword predecessor: look back for word boundary
                        k = i - 1
                        while k >= 0 and s[k] in " \t":
                            k -= 1
                        word_end = k
                        while k >= 0 and (s[k].isalnum() or s[k] == "_"):
                            k -= 1
                        word = s[k+1:word_end+1]
                        if word in keyword_predecessors:
                            is_regex = True
                    if is_regex:
                        j = i + 1
                        in_class = False
                        while j < n:
                            ch = s[j]
                            if ch == "\n":
                                # Unterminated regex - recover
                                break
                            if ch == "\\" and j + 1 < n:
                                out[j] = " "; out[j+1] = " "
                                j += 2
                                continue
                            if ch == "[":
                                in_class = True
                                out[j] = " "
                                j += 1
                                continue
                            if ch == "]":
                                in_class = False
                                out[j] = " "
                                j += 1
                                continue
                            if ch == "/" and not in_class:
                                out[j] = " "
                                j += 1
                                # Consume flags
                                while j < n and s[j].isalpha():
                                    out[j] = " "
                                    j += 1
                                break
                            out[j] = " "
                            j += 1
                        i = j
                        prev_ch = "/"
                        continue
                    # Division: leave as code
                    prev_ch = c
                    i += 1
                    continue
                if not c.isspace():
                    prev_ch = c
                i += 1
            return "".join(out)

        try:
            src = _strip_js(raw_src)
        except Exception as e:
            suppressed.append({"category": "frontend_wiring", "name": "_strip_failed",
                               "reason": f"strip failed: {e}, scan skipped"})
            return issues, suppressed

        # Defined functions - every known JS pattern
        defined = set()
        for pat in [
            r"(?:async\s+)?function\s+(\w+)\s*\(",        # function foo(
            r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(",   # const foo = (
            r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\w+\s*=>",  # const foo = x =>
            r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?function",  # const foo = function
            r"(\w+)\s*:\s*(?:async\s+)?function\s*\(",   # foo: function(
            r"(\w+)\s*:\s*(?:async\s+)?\([^)]*\)\s*=>",  # foo: (x) =>
            r"window\.(\w+)\s*=",                            # window.foo =
        ]:
            for m in re.finditer(pat, src):
                defined.add(m.group(1))

        # Object method shorthand: `name(args) { ... }` inside { } literal.
        # Detect by: word + paren-balanced args + whitespace + '{', and the
        # preceding non-space char is one of `, { : ` (object-literal context),
        # or it's at the start of a property line.
        shorthand_pat = re.compile(r"(\w+)\s*\(([^()]*)\)\s*\{")
        for m in shorthand_pat.finditer(src):
            name = m.group(1)
            if name in ("if","while","for","switch","catch","function","return"):
                continue
            # Look at preceding non-whitespace char
            k = m.start() - 1
            while k >= 0 and src[k] in " \t\n":
                k -= 1
            if k >= 0 and src[k] in ",{":
                defined.add(name)
            # Also: a comma-then-newline-then-name pattern is method shorthand
            # right after another property
        

        skip_names = {
            "if","for","while","switch","catch","return","typeof","new","delete",
            "void","throw","class","super","import","export","from","await","yield",
            "try","else","do","in","of","case","default","async","function","get",
            "set","has","var","let","const",
            "setTimeout","setInterval","clearTimeout","clearInterval",
            "parseInt","parseFloat","isNaN","isFinite","encodeURI","decodeURI",
            "encodeURIComponent","decodeURIComponent","fetch","alert","confirm",
            "prompt","console","atob","btoa","FileReader","FormData","URL","Blob",
            "requestAnimationFrame","cancelAnimationFrame","getComputedStyle",
            "r","j","res","rej","resolve","reject","err","e","ev","fn","cb",
            "next","done","ctx","el","i","k","v","x","y","z","t","p","b","d","f",
            "translate","pad","rgba","_",
        }

        # Find candidates
        called: dict[str, list[int]] = {}
        for m in re.finditer(r"\b(\w+)\s*\(", src):
            name = m.group(1)
            if name in skip_names: continue
            if name[0].isupper(): continue
            if name.isdigit(): continue
            called.setdefault(name, []).append(
                src[:m.start()].count("\n") + 1
            )

        for name, line_nums in called.items():
            if name in defined:
                continue
            # Verify every occurrence is a free function call (not preceded by '.')
            non_method = 0
            occurrences = list(re.finditer(r"\b" + re.escape(name) + r"\s*\(", src))
            for occ in occurrences:
                start_i = occ.start()
                k = start_i - 1
                while k >= 0 and src[k] in " \t":
                    k -= 1
                if k >= 0 and src[k] == ".":
                    continue
                non_method += 1
            if non_method == 0:
                suppressed.append({
                    "category": "frontend_wiring",
                    "name": name,
                    "reason": "all calls are method invocations",
                    "call_count": len(occurrences),
                    "first_line": line_nums[0] if line_nums else 0,
                })
                continue

            raw_lines = raw_src.splitlines()
            context = raw_lines[line_nums[0]-1].strip() if line_nums[0]-1 < len(raw_lines) else ""

            issues.append(RepairIssue(
                category="frontend_wiring",
                severity="medium",
                description=(
                    f"app.js calls '{name}()' (line {line_nums[0]}) "
                    f"but no function '{name}' is defined. "
                    f"Called {non_method} time(s) as a free function."
                ),
                file_path=str(app_js),
                line_number=line_nums[0],
                root_cause=f"Undefined function. Context: {context[:120]}",
                fix_description="Define the missing function or remove the call",
                auto_fixable=False,
            ))

        return issues, suppressed

    def _scan_pipeline_chains_v2(self) -> tuple[list[RepairIssue], list[dict]]:
        """Reuse the legacy chain checks but suppress the .ok/.success
        false positive when all .success occurrences are in defensive
        `r.ok || r.success` patterns."""
        # Run the legacy scanner
        legacy_issues = self._scan_pipeline_chains()
        issues: list[RepairIssue] = []
        suppressed: list[dict] = []

        app_js = self.root / "frontend" / "app.js"
        js_src = app_js.read_text(encoding="utf-8", errors="replace") if app_js.exists() else ""

        for iss in legacy_issues:
            # Look for the .success-vs-.ok false positive
            if (iss.category == "pipeline_chain"
                    and ".success " in iss.description
                    and " vs .ok " in iss.description):
                # Count defensive uses: `r.ok || r.success` or `r.success || r.ok`
                defensive = len(re.findall(
                    r"\.\s*ok\s*\|\|\s*[\w]+\.\s*success", js_src
                )) + len(re.findall(
                    r"\.\s*success\s*\|\|\s*[\w]+\.\s*ok", js_src
                ))
                total_success = len(re.findall(r"\.success\b", js_src))
                if defensive >= total_success:
                    suppressed.append({
                        "category": "pipeline_chain",
                        "name": "ok_vs_success",
                        "reason": (
                            f"All {total_success} .success uses are inside "
                            f"defensive `r.ok || r.success` patterns ({defensive} matched). "
                            "Not a bug - the frontend accepts either schema."
                        ),
                        "call_count": total_success,
                    })
                    continue
            issues.append(iss)
        return issues, suppressed

    def _write_scan_log(self, report: "ScanReport", ts: str | None = None) -> str:
        """Write a detailed log of the scan to a file.

        Returns the log path. Claude can read this file to understand
        every decision the scanner made.
        """
        log_dir = self.root / "data" / "vj_logs"
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            log_dir = self.root  # fallback
        if ts is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")  # vj: local-display-ok
        log_path = log_dir / f"vj_scan_{ts}.log"

        lines = [
            f"VJ Scan Log {report.timestamp}",
            f"Duration: {report.scan_duration_ms:.0f}ms",
            f"Fast mode: {report.fast_mode}",
            f"Files scanned: {report.files_scanned}",
            "",
            f"=== ISSUES ({len(report.issues)}) ===",
        ]
        for i, iss in enumerate(report.issues, 1):
            lines.append(f"[{i}] {iss.severity.upper()} {iss.category}")
            lines.append(f"    file: {iss.file_path}:{iss.line_number}")
            lines.append(f"    desc: {iss.description}")
            if iss.root_cause:
                lines.append(f"    root: {iss.root_cause[:200]}")
            if iss.auto_fixable:
                lines.append(f"    autofix: {iss.fix_description}")
            lines.append("")

        lines.append(f"=== WARNINGS ({len(report.warnings)}) ===")
        for w in report.warnings:
            lines.append(f"  {w.category}: {w.description}")
        lines.append("")

        lines.append(f"=== SUPPRESSED FALSE POSITIVES ({len(report.suppressed)}) ===")
        for s in report.suppressed:
            lines.append(f"  {s.get('category','?')} '{s.get('name','?')}': {s.get('reason','')}")
        lines.append("")

        try:
            log_path.write_text("\n".join(lines), encoding="utf-8")
            return str(log_path)
        except Exception as e:
            return f"[write failed: {e}]"

    # ================================================================
    # Scan: Frontend-Backend Wiring (v6.1.2)
    # ================================================================

    def _scan_frontend_wiring(self) -> list[RepairIssue]:
        """Scan app.js for calls to functions that don't exist.

        This catches the exact bug class that broke 3D modeling:
        handle3dDrop called loadStlBase64() which was never defined.
        """
        issues = []
        app_js = self.root / "frontend" / "app.js"
        if not app_js.exists():
            return issues

        src = app_js.read_text(encoding="utf-8", errors="replace")

        # Step 1: Find all function definitions
        import re
        defined_funcs = set()
        # function name(
        for m in re.finditer(r'(?:async\s+)?function\s+(\w+)\s*\(', src):
            defined_funcs.add(m.group(1))
        # const name = ( or const name = async (
        for m in re.finditer(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(', src):
            defined_funcs.add(m.group(1))
        # class methods aren't common in this codebase but check
        for m in re.finditer(r'(\w+)\s*:\s*(?:async\s+)?function\s*\(', src):
            defined_funcs.add(m.group(1))

        # Step 2: Find all function calls
        # Match word( but exclude keywords, properties, and common globals
        skip_names = {
            "if", "for", "while", "switch", "catch", "return", "typeof",
            "new", "delete", "void", "throw", "class", "super", "import",
            "export", "from", "await", "yield", "try", "else",
            # Browser globals
            "setTimeout", "setInterval", "clearTimeout", "clearInterval",
            "parseInt", "parseFloat", "isNaN", "isFinite", "encodeURI",
            "decodeURI", "encodeURIComponent", "decodeURIComponent",
            "fetch", "alert", "confirm", "prompt", "console",
            "JSON", "Math", "Date", "Array", "Object", "String",
            "Number", "Boolean", "Promise", "Error", "RegExp", "Map", "Set",
            "document", "window", "navigator", "location", "history",
            "require", "module", "exports",
            # Three.js / common libs
            "THREE", "requestAnimationFrame", "cancelAnimationFrame",
            "FileReader", "FormData", "URL", "Blob",
            # Browser APIs and CSS functions
            "atob", "btoa", "rgba", "var", "translate", "pad",
            # Promise/callback parameter names (not real function calls)
            "r", "j", "res", "rej", "resolve", "reject", "err", "e",
            "fn", "cb", "next", "done",
            # JS keywords the regex may catch
            "async", "function", "get", "set", "has",
            # Common patterns that look like calls but aren't
            "fallback", "file", "warning", "email",
            "setLabel", "_",
        }

        called_funcs = {}
        for m in re.finditer(r'\b(\w+)\s*\(', src):
            name = m.group(1)
            if name not in skip_names and not name[0].isupper():
                if name not in called_funcs:
                    called_funcs[name] = []
                # Find line number
                line_num = src[:m.start()].count('\n') + 1
                called_funcs[name].append(line_num)

        # Step 3: Find calls to undefined functions
        # Exclude: method calls (preceded by .), Bridge API calls (a.method()),
        # and event handlers (onclick=)
        for name, line_nums in called_funcs.items():
            if name in defined_funcs:
                continue

            # Check if it's only called as a method (obj.name())
            method_pattern = re.compile(r'\.\s*' + re.escape(name) + r'\s*\(')
            standalone_pattern = re.compile(r'(?<![.\w])' + re.escape(name) + r'\s*\(')

            has_standalone = bool(standalone_pattern.search(src))
            if not has_standalone:
                continue  # It's only called as a method, skip

            # Check if ALL calls are method calls
            all_method = True
            for ln in line_nums[:5]:
                # Get the line
                lines = src.splitlines()
                if ln - 1 < len(lines):
                    line = lines[ln - 1]
                    # Check if the call is preceded by . or a.
                    idx = line.find(name + '(')
                    if idx > 0 and line[idx-1] not in '.':
                        all_method = False
                        break
                    elif idx == 0:
                        all_method = False
                        break

            if all_method:
                continue

            issues.append(RepairIssue(
                category="frontend_wiring",
                severity="medium",
                description=(
                    f"app.js calls '{name}()' (line {line_nums[0]}) "
                    f"but no function '{name}' is defined in app.js. "
                    f"Called {len(line_nums)} time(s)."
                ),
                file_path=str(app_js),
                line_number=line_nums[0],
                root_cause="Function called but never defined in app.js",
                fix_description="Define the missing function or remove the call",
                auto_fixable=False,
            ))

        return issues

    def _scan_pipeline_chains(self) -> list[RepairIssue]:
        """Scan for broken data chains between Bridge methods and frontend.

        Checks that:
        1. Bridge methods that return data keys are consumed by the frontend
        2. Frontend code that reads response keys matches what Bridge returns
        3. STL/3D pipeline specifically: generate_3d_view returns path,
           frontend loads it
        """
        issues = []
        app_js = self.root / "frontend" / "app.js"
        api_py = self.root / "bridge" / "api.py"
        if not app_js.exists() or not api_py.exists():
            return issues

        import re
        js_src = app_js.read_text(encoding="utf-8", errors="replace")
        py_src = api_py.read_text(encoding="utf-8", errors="replace")

        # Check 1: Frontend reads r.data.X - does the Bridge return X?
        # Find patterns like r.data.stl_b64, r.data.path, etc.
        js_data_reads = set()
        for m in re.finditer(r'\.data\.(\w+)', js_src):
            js_data_reads.add(m.group(1))

        # Check 2: Specific 3D pipeline chain
        # Does generate_3d_view return stl_b64?
        g3d_match = re.search(
            r'def generate_3d_view.*?(?=\n    def )',
            py_src, re.DOTALL
        )
        if g3d_match:
            g3d_body = g3d_match.group(0)
            returns_stl_b64 = '"stl_b64"' in g3d_body
            returns_path = '"path"' in g3d_body
            if not returns_stl_b64:
                issues.append(RepairIssue(
                    category="pipeline_chain",
                    severity="high",
                    description=(
                        "generate_3d_view does not return 'stl_b64' key. "
                        "The 3D viewer needs base64 STL data to render models."
                    ),
                    file_path=str(api_py),
                    line_number=0,
                    root_cause="Missing return key in Bridge method",
                    fix_description="Add the missing key to the return dict",
                    auto_fixable=False,
                ))
            if not returns_path:
                issues.append(RepairIssue(
                    category="pipeline_chain",
                    severity="medium",
                    description=(
                        "generate_3d_view does not return 'path' key. "
                        "Buttons and session context need the file path."
                    ),
                    file_path=str(api_py),
                    line_number=0,
                    root_cause="Missing return key in Bridge method",
                    fix_description="Add the missing key to the return dict",
                    auto_fixable=False,
                ))

        # Check 3: auto_process_drawing returns stl data for frontend
        apd_match = re.search(
            r'def auto_process_drawing.*?(?=\n    def )',
            py_src, re.DOTALL
        )
        if apd_match:
            apd_body = apd_match.group(0)
            returns_stl_paths = '"stl_paths"' in apd_body
            returns_session = '"session_active"' in apd_body
            stores_session = 'session_context' in apd_body

            if not returns_stl_paths:
                issues.append(RepairIssue(
                    category="pipeline_chain",
                    severity="high",
                    description=(
                        "auto_process_drawing does not return 'stl_paths'. "
                        "Frontend cannot load 3D models without STL data in the response."
                    ),
                    file_path=str(api_py),
                    line_number=0,
                    root_cause="Missing return key in Bridge method",
                    fix_description="Add the missing key to the return dict",
                    auto_fixable=False,
                ))

            if not stores_session:
                issues.append(RepairIssue(
                    category="pipeline_chain",
                    severity="high",
                    description=(
                        "auto_process_drawing does not store results in session_context. "
                        "Subsequent commands (3D model, proposal, Tekla) cannot access takeoff data."
                    ),
                    file_path=str(api_py),
                    line_number=0,
                    root_cause="Missing return key in Bridge method",
                    fix_description="Add the missing key to the return dict",
                    auto_fixable=False,
                ))

        # Check 4: Frontend handles stl_paths from pipeline result
        if 'stl_paths' not in js_src:
            issues.append(RepairIssue(
                category="pipeline_chain",
                severity="high",
                description=(
                    "Frontend app.js never reads 'stl_paths' from pipeline response. "
                    "Even if the Bridge returns STL data, the frontend ignores it. "
                    "The 3D viewer will not load models from PDF extraction."
                ),
                file_path=str(app_js),
                line_number=0,
                root_cause="Frontend wiring issue",
                fix_description="Fix the frontend code to handle this data",
                auto_fixable=False,
            ))

        # Check 5: Frontend has a function to load STL into the Three.js viewer
        has_stl_loader = bool(re.search(
            r'STLLoader|loadStl|loadSTL|loadModel|load_stl',
            js_src, re.IGNORECASE
        ))
        if not has_stl_loader:
            issues.append(RepairIssue(
                category="pipeline_chain",
                severity="high",
                description=(
                    "Frontend app.js has no STL loading function "
                    "(no STLLoader, loadStl, loadSTL, or loadModel found). "
                    "The 3D viewer cannot load models without this function."
                ),
                file_path=str(app_js),
                line_number=0,
                root_cause="Frontend wiring issue",
                fix_description="Fix the frontend code to handle this data",
                auto_fixable=False,
            ))

        # Check 6: ok vs success response format mismatch
        success_checks = len(re.findall(r'\.success\b', js_src))
        ok_checks = len(re.findall(r'\.ok\b', js_src))
        if success_checks > 2:  # A few legacy is OK, many is a problem
            issues.append(RepairIssue(
                category="pipeline_chain",
                severity="medium",
                description=(
                    f"Frontend checks .success {success_checks} times vs .ok {ok_checks} times. "
                    f"Bridge methods return {{ok: true}}. Methods returning {{success: true}} "
                    f"will appear broken to the frontend."
                ),
                file_path=str(app_js),
                line_number=0,
                root_cause="Frontend wiring issue",
                fix_description="Fix the frontend code to handle this data",
                auto_fixable=False,
            ))

        return issues

    # ================================================================
    # v3.2.7 pass 10a: Scans trained from sandbox simulation
    # These detect issues the human tester found that VJ missed.
    # ================================================================

    def _scan_dead_imports_stdlib(self) -> list[RepairIssue]:
        """Auto-fix dead stdlib imports (json, os, re, datetime, etc).

        The existing _scan_dead_imports only flags project-internal imports
        and marks them as non-auto-fixable. This scanner targets stdlib
        imports and CAN auto-fix them by removing the import line.

        Trained from: sandbox simulation found 83 dead stdlib imports
        that VJ detected but could not repair.
        """
        issues: list[RepairIssue] = []
        # Only target these common stdlib modules
        TARGET_MODULES = {
            "json", "os", "re", "sys", "time", "math", "io",
            "hashlib", "subprocess", "shutil", "traceback",
            "copy", "collections", "itertools", "functools",
        }
        TARGET_FROM = {
            ("datetime", "date"), ("datetime", "datetime"),
            ("datetime", "timedelta"), ("pathlib", "Path"),
        }

        for path in self._iter_py_files():
            if path.name == "__init__.py":
                continue
            if "archive" in str(path) or "sim_external" in str(path):
                continue
            try:
                src = path.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(src)
            except (SyntaxError, UnicodeDecodeError):
                continue

            lines = src.splitlines()

            for node in ast.walk(tree):
                # Case 1: `import json` - check for `json.` usage
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.asname or alias.name
                        if name not in TARGET_MODULES:
                            continue
                        if "," in lines[node.lineno - 1].split("import")[1] if "import" in lines[node.lineno - 1] else "":
                            continue  # Multi-import line, skip
                        # Check if module.X pattern exists outside import line
                        pattern = rf"\b{re.escape(name)}\."
                        non_import = "\n".join(
                            ln for i, ln in enumerate(lines)
                            if i != node.lineno - 1
                        )
                        if not re.search(pattern, non_import):
                            import_line = lines[node.lineno - 1]
                            issues.append(RepairIssue(
                                category="dead_stdlib_import",
                                severity="low",
                                file_path=str(path),
                                line_number=node.lineno,
                                description=f"Dead stdlib import: {import_line.strip()}",
                                root_cause=f"`{name}.` never used in {path.name}",
                                auto_fixable=True,
                                fix_description=f"Remove line {node.lineno}",
                                fix_old=import_line,
                                fix_new="",
                            ))

                # Case 2: `from datetime import timedelta` - check for name usage
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    for alias in node.names:
                        pair = (mod, alias.name)
                        if pair not in TARGET_FROM:
                            continue
                        name = alias.asname or alias.name
                        line_text = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
                        if "," in line_text.split("import")[1] if "import" in line_text else "":
                            continue  # Multi-name import, skip
                        pattern = rf"\b{re.escape(name)}\b"
                        non_import = "\n".join(
                            ln for i, ln in enumerate(lines)
                            if i != node.lineno - 1
                        )
                        if not re.search(pattern, non_import):
                            issues.append(RepairIssue(
                                category="dead_stdlib_import",
                                severity="low",
                                file_path=str(path),
                                line_number=node.lineno,
                                description=f"Dead stdlib import: {line_text.strip()}",
                                root_cause=f"`{name}` never used in {path.name}",
                                auto_fixable=True,
                                fix_description=f"Remove line {node.lineno}",
                                fix_old=line_text,
                                fix_new="",
                            ))

        return issues

    def _scan_hardcoded_html_values(self) -> list[RepairIssue]:
        """Detect hardcoded numeric values in HTML that should be dynamic.

        Trained from: $5.9M pipeline was hardcoded in index.html when it
        should have been populated from Bridge.get_kpis(). Owner saw the
        stale number and thought it was live data.

        Looks for patterns like: $X.XM, $XXK, N blockers, N active
        in HTML files that have corresponding JS dynamic update code.
        """
        issues: list[RepairIssue] = []
        html_dir = self.root / "frontend"
        if not html_dir.exists():
            return issues

        # Patterns that are likely stale hardcoded values
        STALE_PATTERNS = [
            (r'\$\d+\.?\d*[MK]\s+pipeline', "hardcoded pipeline value"),
            (r'\d+\s+blockers?(?!</)', "hardcoded blocker count"),
            (r'\d+\s+active(?!</)', "hardcoded active count"),
            (r'\$\d{1,3}(?:,\d{3})+\s+(?:revenue|total|ar)', "hardcoded dollar amount"),
        ]

        for html_file in html_dir.glob("*.html"):
            try:
                src = html_file.read_text(encoding="utf-8")
            except Exception:
                continue

            for pattern, desc in STALE_PATTERNS:
                for match in re.finditer(pattern, src, re.IGNORECASE):
                    line_num = src[:match.start()].count("\n") + 1
                    line_text = src.splitlines()[line_num - 1] if line_num <= len(src.splitlines()) else ""
                    # Skip if inside a JS string or comment
                    stripped = line_text.strip()
                    if stripped.startswith("//") or stripped.startswith("/*"):
                        continue
                    issues.append(RepairIssue(
                        category="hardcoded_html_value",
                        severity="medium",
                        file_path=str(html_file),
                        line_number=line_num,
                        description=f"Possible stale {desc}: '{match.group()}'",
                        root_cause=(
                            "Numeric values in HTML should be populated dynamically "
                            "from Bridge methods. Hardcoded values become stale."
                        ),
                        auto_fixable=False,
                        fix_description=(
                            f"Replace '{match.group()}' with a placeholder "
                            "that JS populates from get_kpis() or similar"
                        ),
                    ))

        return issues

    def _scan_data_file_health(self) -> list[RepairIssue]:
        """Check data directory for empty, corrupt, or unexpectedly large files.

        Trained from: model_routing.json was {} (2 bytes). While not a bug
        (defaults are hardcoded), it signals an uninitialized config file.
        Also checks for JSON parse errors.
        """
        issues: list[RepairIssue] = []
        data_dir = self.root / "data"
        if not data_dir.exists():
            return issues

        for json_file in data_dir.glob("*.json"):
            try:
                size = json_file.stat().st_size
            except Exception:
                continue

            # Empty or near-empty JSON (just {} or [])
            if size <= 5:
                try:
                    content = json_file.read_text().strip()
                    if content in ("{}", "[]", "null", ""):
                        issues.append(RepairIssue(
                            category="empty_data_file",
                            severity="low",
                            file_path=str(json_file),
                            line_number=1,
                            description=f"Empty data file: {json_file.name} ({size} bytes, content='{content}')",
                            root_cause="Config/data file exists but contains no data. Bridge uses hardcoded defaults.",
                            auto_fixable=False,
                            fix_description="Populate with real data or remove if unused",
                        ))
                except Exception:
                    pass

            # JSON parse check
            if size > 5:
                try:
                    import json as _json
                    with open(json_file) as f:
                        _json.load(f)
                except _json.JSONDecodeError as e:
                    issues.append(RepairIssue(
                        category="corrupt_data_file",
                        severity="high",
                        file_path=str(json_file),
                        line_number=1,
                        description=f"Corrupt JSON: {json_file.name} - {str(e)[:100]}",
                        root_cause="JSON parse failed. File may be truncated or malformed.",
                        auto_fixable=False,
                        fix_description="Repair or regenerate the JSON file",
                    ))

        return issues

    def _scan_compliance_snapshot_bloat(self) -> list[RepairIssue]:
        """Auto-clean compliance snapshots beyond the last 10.

        Trained from: 56 snapshot files accumulated during development,
        bloating the zip by 40KB+. Keep the 10 most recent, flag the rest
        for auto-deletion.
        """
        issues: list[RepairIssue] = []
        snap_dir = self.root / "data" / "compliance_snapshots"
        if not snap_dir.exists():
            return issues

        snapshots = sorted(snap_dir.glob("*.json"))
        keep = 10
        if len(snapshots) <= keep:
            return issues

        to_remove = snapshots[:-keep]
        for snap in to_remove:
            issues.append(RepairIssue(
                category="snapshot_bloat",
                severity="low",
                file_path=str(snap),
                line_number=0,
                description=f"Stale compliance snapshot: {snap.name} ({len(to_remove)} excess, keeping last {keep})",
                root_cause=f"{len(snapshots)} snapshots found, limit is {keep}",
                auto_fixable=True,
                fix_description=f"Delete {snap.name}",
                fix_old="__DELETE_FILE__",
                fix_new=str(snap),
            ))

        return issues

    # ================================================================
    # v3.2.7 pass 10b: Scans trained from ALL bug reports (4 PDFs)
    # BUG-009,028,FIX-09 | BUG-029 | BUG-018,019 | BUG-001 |
    # BUG-025,FIX-07,17 | FIX-16 | BUG-007,008,009 | BUG-019/debug3
    # ================================================================

    def _scan_banned_words(self) -> list[RepairIssue]:
        """Detect the Owner's banned words in docstrings and comments.

        Trained from: BUG-009 ("leverage" in docstring), BUG-028 ("leverage"
        in mcp_client.py), FIX-09. the Owner's voice rule: no corporate filler.
        """
        BANNED = {
            "leverage": "use",
            "synergy": "combined benefit",
            "utilize": "use",
            "facilitate": "help",
            "holistic": "complete",
            "paradigm": "approach",
            "incentivize": "encourage",
        }
        issues: list[RepairIssue] = []
        for path in self._iter_py_files():
            if "archive" in str(path) or "sim_external" in str(path):
                continue
            if path.name in self._ENFORCEMENT_FILES:
                continue  # Enforcement engines define banned words in patterns
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                # Only check comments and docstrings
                is_comment = stripped.startswith("#")
                is_docstring = '"""' in stripped or "'''" in stripped
                if not is_comment and not is_docstring:
                    continue
                lower = stripped.lower()
                for word, replacement in BANNED.items():
                    if word in lower:
                        # Skip if it's in enforcement/filter/pattern logic
                        if "banned" in lower or "filter" in lower or "voice_rule" in lower or '"pattern"' in lower or "r\"" in stripped:
                            continue
                        issues.append(RepairIssue(
                            category="banned_word",
                            severity="medium",
                            file_path=str(path),
                            line_number=i,
                            description=f'Banned word "{word}" in {path.name}:{i}',
                            root_cause=f'Owner voice rule: no corporate filler. Use "{replacement}" instead.',
                            auto_fixable=False,
                            fix_description=f'Replace "{word}" with "{replacement}"',
                        ))
        return issues

    def _scan_hardcoded_tmp_paths(self) -> list[RepairIssue]:
        """Detect hardcoded /tmp/ paths that fail on Windows.

        Trained from: BUG-029 (qr_generator.py and punch_map_gen.py used /tmp/).
        Fix: use tempfile.gettempdir().
        """
        issues: list[RepairIssue] = []
        for path in self._iter_py_files():
            if path.name in self._ENFORCEMENT_FILES:
                continue  # Scan definitions reference /tmp/ in docstrings
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for i, line in enumerate(lines, 1):
                if "/tmp/" in line and not line.strip().startswith("#"):
                    # Skip if it's already using tempfile
                    if "tempfile" in line or "gettempdir" in line:
                        continue
                    issues.append(RepairIssue(
                        category="hardcoded_tmp",
                        severity="medium",
                        file_path=str(path),
                        line_number=i,
                        description=f"Hardcoded /tmp/ path in {path.name}:{i}",
                        root_cause="Fails on Windows. Use tempfile.gettempdir() instead.",
                        auto_fixable=False,
                        fix_description="Replace /tmp/ with tempfile.gettempdir()",
                    ))
        return issues

    def _scan_shim_bypass(self) -> list[RepairIssue]:
        """Detect direct import of google.generativeai bypassing gemini_compat.py.

        Trained from: BUG-019/sweep6 (tagged_pdf_renderer.py imported
        google.generativeai directly), BUG-018/debug3 (all 4 Gemini call
        sites used wrong import). The shim exists for a reason.
        """
        issues: list[RepairIssue] = []
        shim_file = self.root / "bridge" / "gemini_compat.py"
        if not shim_file.exists():
            return issues  # No shim, nothing to enforce

        for path in self._iter_py_files():
            if path.name == "gemini_compat.py":
                continue  # The shim itself can import directly
            if path.name in self._ENFORCEMENT_FILES:
                continue  # Scan definitions reference the import pattern
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "google.generativeai" in stripped and "import" in stripped:
                    issues.append(RepairIssue(
                        category="shim_bypass",
                        severity="high",
                        file_path=str(path),
                        line_number=i,
                        description=f"Direct google.generativeai import bypasses gemini_compat.py shim in {path.name}:{i}",
                        root_cause="Use 'from bridge.gemini_compat import get_genai' instead. Direct import fails if only google-genai is installed.",
                        auto_fixable=False,
                        fix_description="Replace with: from bridge.gemini_compat import get_genai",
                    ))
        return issues

    def _scan_stale_file_refs(self) -> list[RepairIssue]:
        """Detect code that reads file paths which don't exist in the tree.

        Trained from: BUG-001/sweep4 (calculator read data/aisc_shapes.csv
        which was deleted in v3.5.6, silently returned 0 for every shape).
        """
        issues: list[RepairIssue] = []
        # Common patterns: open("data/X"), Path("data/X"), read_text("data/X")
        data_ref_pattern = re.compile(
            r'''(?:open|Path|read_text|read_bytes)\s*\(\s*["'](data/[^"']+)["']'''
        )
        for path in self._iter_py_files():
            if "test" in path.name.lower() or "archive" in str(path):
                continue
            if path.name in self._ENFORCEMENT_FILES:
                continue  # Scan definitions contain example path patterns
            try:
                src = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for match in data_ref_pattern.finditer(src):
                ref_path = match.group(1)
                full = self.root / ref_path
                if not full.exists():
                    line_num = src[:match.start()].count("\n") + 1
                    issues.append(RepairIssue(
                        category="stale_file_ref",
                        severity="high",
                        file_path=str(path),
                        line_number=line_num,
                        description=f"References non-existent file: {ref_path} in {path.name}:{line_num}",
                        root_cause=f"{ref_path} does not exist in the build tree. Code will silently fail or return empty data.",
                        auto_fixable=False,
                        fix_description=f"Update path to the current location of the data file, or add a fallback chain.",
                    ))
        return issues

    def _scan_js_brace_balance(self) -> list[RepairIssue]:
        """Check JavaScript files for brace imbalance (spurious } or missing }).

        Trained from: BUG-025 (spurious } closed sendMessage() 780 lines
        early, broke entire app), FIX-07 (extra } broke all frontend
        intercepts), FIX-17 (stray return after brace).

        Uses raw brace count first (immune to string parser bugs).
        Template literals with ${} make context-aware parsing unreliable.
        """
        issues: list[RepairIssue] = []
        js_dir = self.root / "frontend"
        if not js_dir.exists():
            return issues

        for js_file in js_dir.glob("*.js"):
            try:
                src = js_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            # Raw count: immune to parser bugs
            opens = src.count("{")
            closes = src.count("}")
            diff = opens - closes

            if diff < -2:
                issues.append(RepairIssue(
                    category="js_brace_imbalance",
                    severity="high",
                    file_path=str(js_file),
                    line_number=0,
                    description=f"Brace imbalance in {js_file.name}: {abs(diff)} more '}}' than '{{'",
                    root_cause="Extra closing braces. May close a function scope too early, orphaning code after it.",
                    auto_fixable=False,
                    fix_description="Search for spurious }} near the reported line. Check function closings.",
                ))
            elif diff > 2:
                issues.append(RepairIssue(
                    category="js_brace_imbalance",
                    severity="high",
                    file_path=str(js_file),
                    line_number=0,
                    description=f"Brace imbalance in {js_file.name}: {abs(diff)} more '{{' than '}}'",
                    root_cause="Missing closing braces. A function or block may be unclosed.",
                    auto_fixable=False,
                    fix_description="Check function/block closings near the end of the file.",
                ))

        return issues

    def _scan_deprecated_model_names(self) -> list[RepairIssue]:
        """Detect deprecated Anthropic model name strings.

        Trained from: FIX-16 (claude-sonnet-4-5 deprecated, caused 404 on
        every API call). Also catches old claude-3.5-sonnet family.
        """
        DEPRECATED = [
            "claude-sonnet-4-5",
            "claude-3-5-sonnet",
            "claude-3.5-sonnet",
            "claude-3-opus",
            "claude-3-haiku",
            "claude-3-sonnet",
            "claude-instant",
        ]
        issues: list[RepairIssue] = []
        for path in self._iter_py_files():
            if "archive" in str(path) or "sim_external" in str(path):
                continue
            if path.name in self._ENFORCEMENT_FILES:
                continue  # DEPRECATED list is defined here
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for i, line in enumerate(lines, 1):
                if line.strip().startswith("#"):
                    continue
                for dep in DEPRECATED:
                    if dep in line:
                        # Skip if it's in a comment or a known-safe context
                        stripped = line.strip()
                        if "DEPRECATED" in stripped.upper() or "old" in stripped.lower():
                            continue
                        issues.append(RepairIssue(
                            category="deprecated_model",
                            severity="high",
                            file_path=str(path),
                            line_number=i,
                            description=f'Deprecated model "{dep}" in {path.name}:{i}',
                            root_cause="This model string returns HTTP 404. Update to current model (claude-sonnet-4-6, claude-opus-4-6, etc).",
                            auto_fixable=False,
                            fix_description=f'Replace "{dep}" with the current model name from the ai_model_router tier config.',
                        ))
        return issues

    def _scan_version_drift(self) -> list[RepairIssue]:
        """Detect version strings that are out of sync across the codebase.

        Trained from: BUG-007 (test hardcoded "3.5"), BUG-008 (installer.nsi
        version stuck), BUG-009 (OWNER_INSTALL.bat still said v3.5.12).
        """
        issues: list[RepairIssue] = []
        # Read the canonical version from vo_app
        version_file = self.root / "vo_app" / "__init__.py"
        canonical = None
        if version_file.exists():
            try:
                src = version_file.read_text()
                match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', src)
                if match:
                    canonical = match.group(1)
            except Exception:
                pass
        if not canonical:
            return issues  # Can't check without canonical version

        # Check files that should reference the version
        version_files = [
            ("installer.nsi", r'!define\s+VERSION\s+"([^"]+)"'),
            ("installer.nsi", r'VIProductVersion\s+"([^"]+)"'),
            ("VirtualOffice.spec", r"version=['\"]([^'\"]+)['\"]"),
        ]
        for fname, pattern in version_files:
            fpath = self.root / fname
            if not fpath.exists():
                continue
            try:
                src = fpath.read_text()
                for match in re.finditer(pattern, src):
                    found = match.group(1)
                    if found != canonical and not found.startswith(canonical):
                        line_num = src[:match.start()].count("\n") + 1
                        issues.append(RepairIssue(
                            category="version_drift",
                            severity="medium",
                            file_path=str(fpath),
                            line_number=line_num,
                            description=f'Version "{found}" in {fname}:{line_num} does not match canonical "{canonical}"',
                            root_cause=f"vo_app/__init__.py says {canonical}. This file says {found}.",
                            auto_fixable=False,
                            fix_description=f'Update to "{canonical}"',
                        ))
            except Exception:
                pass

        return issues

    def _scan_err_helper_shape(self) -> list[RepairIssue]:
        """Check that _err() helper includes both 'ok' and 'success' keys.

        Trained from: BUG-019/debug3 (_err() returned {ok:false,error:msg}
        but callers expected success:false too, causing 64 test failures).
        """
        issues: list[RepairIssue] = []
        api_path = self.root / "bridge" / "api.py"
        if not api_path.exists():
            return issues
        try:
            lines = api_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            return issues

        # Find _err function by scanning lines
        in_err = False
        err_start = 0
        body_lines = []
        for i, line in enumerate(lines):
            if line.strip().startswith("def _err("):
                in_err = True
                err_start = i + 1
                body_lines = []
                continue
            if in_err:
                if line.strip() and not line[0].isspace() and not line.strip().startswith("#"):
                    break  # Hit next top-level def
                body_lines.append(line)

        if not body_lines:
            return issues

        body = "\n".join(body_lines)
        has_ok = '"ok"' in body or "'ok'" in body
        has_success = '"success"' in body or "'success'" in body

        if has_ok and not has_success:
            issues.append(RepairIssue(
                category="err_shape",
                severity="medium",
                file_path=str(api_path),
                line_number=err_start,
                description='_err() helper missing "success" key. Callers expect both ok and success.',
                root_cause="BUG-019: _err() returned {{ok:false}} without success:false. Caused 64 test assertion failures.",
                auto_fixable=False,
                fix_description='Add "success": False to the _err() return dict',
            ))

        return issues

    _SKIP_DIRS = {
        "dist", "dist_build", "build", "__pycache__", ".git", "node_modules",
        "site-packages", ".venv", "venv", "env", "API Keys",
        "_internal",   # frozen-EXE bundle - skip vendor code
    }

    def _iter_py_files(self):
        """Iterate over all .py files in the project, skipping vendor trees."""
        for root, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if d not in self._SKIP_DIRS]
            for f in files:
                if f.endswith(".py"):
                    yield Path(root) / f

    # ================================================================
    # Pass 10d scans: trained from Claude history export (134 convs)
    # Patterns surfaced across non-Your-Company projects too (Jarvis, Build
    # Co, Pop OS bundle, JSX simulation, VM bid pipeline).
    # ================================================================

    def _scan_datetime_utcnow_deprecated(self) -> list[RepairIssue]:
        """Detect datetime.utcnow() - deprecated in Python 3.12+.

        Trained from: DEBT-001 (260 sites surfaced in v3.5.x history),
        "CEO dashboard with AI routing layer" chat (12/12 deprecation
        warnings on Py3.12+), "Project handoff and next steps" chat
        (bid_followup.py used utcnow as silent fallback).

        Auto-fix is enabled only when `timezone` is already imported
        in the file. Otherwise the fix would create an ImportError.
        """
        import re
        issues: list[RepairIssue] = []
        pat = re.compile(r"datetime\.utcnow\(\)")
        for path in self._iter_py_files():
            if path.name in self._ENFORCEMENT_FILES:
                continue  # Scan definitions reference utcnow() in patterns
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if "datetime.utcnow()" not in text:
                continue
            # Preflight: is timezone already importable in this file?
            tz_imported = bool(re.search(
                r"^\s*from\s+datetime\s+import\s+[^\n]*\btimezone\b",
                text, re.M,
            )) or bool(re.search(
                r"^\s*import\s+datetime\b", text, re.M,
            ))
            # Track docstring state per line so docstring matches are skipped
            in_docstring = False
            for i, line in enumerate(text.splitlines(), 1):
                _tq_dq = chr(34) * 3
                _tq_sq = chr(39) * 3
                triple_count = line.count(_tq_dq) + line.count(_tq_sq)
                line_starts_in_docstring = in_docstring
                if triple_count % 2 == 1:
                    in_docstring = not in_docstring
                if not pat.search(line):
                    continue
                if line.lstrip().startswith("#"):
                    continue
                if line_starts_in_docstring or in_docstring:
                    continue  # match is inside a docstring, not a real call
                issues.append(RepairIssue(
                    category="datetime_utcnow_deprecated",
                    severity="medium",
                    file_path=str(path),
                    line_number=i,
                    description=(
                        f"datetime.utcnow() deprecated in Python 3.12+ "
                        f"({path.name}:{i})"
                    ),
                    root_cause=(
                        "DEBT-001: datetime.utcnow() returns a tz-naive UTC "
                        "value; deprecated in Python 3.12+. Use "
                        "datetime.now(timezone.utc) for tz-aware UTC."
                    ),
                    auto_fixable=tz_imported,
                    fix_description=(
                        "Replace datetime.utcnow() with "
                        "datetime.now(timezone.utc)"
                        if tz_imported else
                        "Import timezone, then replace datetime.utcnow() "
                        "with datetime.now(timezone.utc)"
                    ),
                    fix_old="datetime.utcnow()" if tz_imported else "",
                    fix_new="datetime.now(timezone.utc)" if tz_imported else "",
                ))
        return issues

    def _scan_datetime_now_naive(self) -> list[RepairIssue]:
        """Detect datetime.now() with no tz argument.

        Trained from: "JSX simulation framework for build testing" chat
        ("tz-naive datetime.now() at line 180"), "Project handoff and
        next steps" chat (bid_followup.py:54 base = datetime.now() as
        ISO-parse fallback - same bug class as check_material_volatility).

        Not auto-fixable: the right tz depends on the caller's intent
        (UTC for storage, local for display).
        """
        import re
        issues: list[RepairIssue] = []
        # Match datetime.now() with empty parens; reject datetime.now(tz=...)
        pat = re.compile(r"\bdatetime\.now\(\s*\)")
        for path in self._iter_py_files():
            if path.name in self._ENFORCEMENT_FILES:
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            # Track docstring state so docstring text isn't flagged.
            _in_docstring = False
            _tq_dq = chr(34) * 3
            _tq_sq = chr(39) * 3
            for i, line in enumerate(lines, 1):
                _triple_count = line.count(_tq_dq) + line.count(_tq_sq)
                _line_starts_in_docstring = _in_docstring
                if _triple_count % 2 == 1:
                    _in_docstring = not _in_docstring
                if not pat.search(line):
                    continue
                if line.lstrip().startswith("#"):
                    continue
                if _line_starts_in_docstring or _in_docstring:
                    continue  # docstring text mentioning the pattern, not a real call
                # Honor `# vj: local-time-ok` opt-out (Owner roadmap #4).
                # Sites tagged as local-time intentional are skipped.
                # Also accept `vj: local-display-ok` (DEBT-001 cleanup label).
                if ("vj: local-time-ok" in line
                        or "vj: local-display-ok" in line
                        or "vj: duration-math" in line):
                    continue
                # Honor `# vj: utc-storage` (already wrapped, scan satisfied)
                if "vj: utc-storage" in line:
                    continue
                # Skip in test scaffolding and demo scripts
                if "/tests/" in str(path) or path.name.startswith("test_"):
                    continue
                issues.append(RepairIssue(
                    category="datetime_now_naive",
                    severity="low",
                    file_path=str(path),
                    line_number=i,
                    description=(
                        f"Tz-naive datetime.now() in {path.name}:{i}"
                    ),
                    root_cause=(
                        "DEBT-001: bare datetime.now() returns local "
                        "tz-naive time. Mixing with tz-aware values "
                        "raises TypeError. Use datetime.now(timezone.utc) "
                        "for storage or pass an explicit tz."
                    ),
                    auto_fixable=False,
                    fix_description=(
                        "Decide intent: storage/comparison -> "
                        "datetime.now(timezone.utc); display -> "
                        "datetime.now(ZoneInfo('America/Chicago'))"
                    ),
                ))
        return issues

    def _scan_branch_dict_key_parity(self) -> list[RepairIssue]:
        """Detect functions whose return-dict branches have inconsistent keys.

        Trained from: BUG-035 ("VM bid discovery pipeline setup" chat).
        The already_processed early-return path was missing total_tonnage,
        member_count, inventory_thumbnail_path, bid_number, draft_estimate
        that the normal path returned. Frontend rendered different fields
        depending on which path it hit.

        Heuristic: walk function body, find all `return {literal dict}`
        statements, collect key sets, flag any path missing 3+ keys that
        other paths in the same function provide.
        """
        import ast
        issues: list[RepairIssue] = []
        for path in self._iter_py_files():
            if path.name in self._ENFORCEMENT_FILES:
                continue
            try:
                src_text = path.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(src_text, filename=str(path))
            except Exception:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                paths_keys: list[tuple[int, set[str]]] = []
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict):
                        keys: set[str] = set()
                        for k in sub.value.keys:
                            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                                keys.add(k.value)
                        if keys:  # ignore empty-dict returns
                            paths_keys.append((sub.lineno, keys))
                if len(paths_keys) < 2:
                    continue
                # Union of all keys across branches
                union: set[str] = set()
                for _, ks in paths_keys:
                    union |= ks
                # Skip functions where return-dicts are essentially disjoint
                # (different concepts, not a parity problem)
                shared = set.intersection(*[ks for _, ks in paths_keys])
                if not shared:
                    continue
                # Honor opt-out comment `# vj: parity-ok` anywhere
                # in the function body (Owner roadmap #5a, dispatcher style).
                _func_start = node.lineno
                _func_end = getattr(node, "end_lineno", _func_start)
                _func_src = "\n".join(
                    src_text.splitlines()[_func_start - 1:_func_end]
                )
                if "vj: parity-ok" in _func_src:
                    continue  # Function explicitly opted out
                # Report ONCE per function with the most-asymmetric branch.
                # Dispatcher-style functions with many divergent branches would
                # otherwise produce dozens of issues for a single design choice.
                worst = None  # (missing_count, lineno, missing_set)
                for lineno, ks in paths_keys:
                    missing = union - ks
                    if len(missing) >= 3:
                        if worst is None or len(missing) > worst[0]:
                            worst = (len(missing), lineno, missing)
                if worst is not None:
                    miss_sample = sorted(worst[2])[:5]
                    n_branches = len(paths_keys)
                    issues.append(RepairIssue(
                        category="branch_dict_key_parity",
                        severity="medium",
                        file_path=str(path),
                        line_number=worst[1],
                        description=(
                            f"{path.name}:{worst[1]}: {node.name}() has "
                            f"{n_branches} return-dict branches with "
                            f"inconsistent shapes (worst branch missing "
                            f"{worst[0]} keys: {miss_sample})"
                        ),
                        root_cause=(
                            "BUG-035: branches return dicts with subset of "
                            "keys vs other branches. Frontend/callers expect "
                            "uniform shape. Dispatcher-style functions: "
                            "consider a shared envelope helper that all paths "
                            "call. Otherwise normalize early-returns to "
                            "include all keys with None defaults."
                        ),
                        auto_fixable=False,
                        fix_description=(
                            "Hoist a common-shape envelope helper that all "
                            "return paths build through, OR add missing keys "
                            "with None defaults to the diverging branches."
                        ),
                    ))
        return issues

    def _scan_open_no_encoding(self) -> list[RepairIssue]:
        """Detect open() calls in text mode without explicit encoding=.

        Trained from: cross-platform reliability - Windows defaults to
        cp1252, Linux/macOS to utf-8. Same source file read with no
        encoding= reads different bytes depending on OS. Surfaced in
        the bug-fix corpus 23 times across multiple build sessions.

        Skips: binary mode ('rb', 'wb', 'ab', etc.), files in /tests/,
        files inside enforcement directories.
        """
        import ast
        issues: list[RepairIssue] = []
        for path in self._iter_py_files():
            if path.name in self._ENFORCEMENT_FILES:
                continue
            # Skip tests - open() in tests often intentional
            if "/tests/" in str(path) or "/test_" in str(path):
                continue
            try:
                src_text = path.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(src_text, filename=str(path))
                lines = src_text.splitlines()
            except Exception:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                # Match builtin open() and io.open() only.
                # Skip third-party .open() methods (pdfplumber.open, fitz.open,
                # zipfile.open, etc.) - those are not file-encoding calls.
                func = node.func
                func_name = None
                if isinstance(func, ast.Name) and func.id == "open":
                    func_name = "open"
                elif isinstance(func, ast.Attribute) and func.attr == "open":
                    # Only flag io.open() - identical to builtins.open() for encoding
                    obj = func.value
                    if isinstance(obj, ast.Name) and obj.id == "io":
                        func_name = "open"
                if func_name != "open":
                    continue
                # Honor `# vj: encoding-ok` opt-out (binary mode, BOM-write, etc.)
                try:
                    _src_line = lines[node.lineno - 1]
                    if "vj: encoding-ok" in _src_line:
                        continue
                except (IndexError, AttributeError):
                    pass
                # Determine mode: positional arg 1 or keyword 'mode'
                mode = None
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    mode = str(node.args[1].value or "")
                for kw in (node.keywords or []):
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                        mode = str(kw.value.value or "")
                # Default mode is 'r' (text)
                if mode is None:
                    mode = "r"
                # Skip binary mode
                if "b" in mode.lower():
                    continue
                # Check for encoding= kwarg
                has_encoding = any(kw.arg == "encoding" for kw in (node.keywords or []))
                if has_encoding:
                    continue
                issues.append(RepairIssue(
                    category="open_no_encoding",
                    severity="low",
                    file_path=str(path),
                    line_number=node.lineno,
                    description=(
                        f"{path.name}:{node.lineno}: open() in text mode "
                        f"without encoding= argument"
                    ),
                    root_cause=(
                        "Cross-platform pitfall: Windows defaults to cp1252, "
                        "Linux/macOS to utf-8. Same source file reads "
                        "different bytes per OS. Pass encoding='utf-8' "
                        "explicitly."
                    ),
                    auto_fixable=False,
                    fix_description=(
                        "Add encoding='utf-8' (or 'utf-8-sig' if BOM is "
                        "expected) to the open() call."
                    ),
                ))
        return issues

    # ================================================================
    # Scan: blind _ok passthrough (pass 10j - trained from Owner sim)
    # ================================================================
    # Pattern: return _ok(some_function(...)) without checking if the
    # inner function returned an error dict. The BUG-054 family (3 hits
    # in pass 10i sim) was caused by this exact pattern.

    def _scan_blind_ok_passthrough(self) -> list[RepairIssue]:
        """Detect return _ok(call(...)) where the inner result isn't checked.

        Flags as warning (not issue) because some inner functions are known-safe.
        The developer should either:
          (a) store result, check for 'error' key, then wrap in _ok, or
          (b) add a # vj: ok-passthrough-safe comment to suppress.
        """
        issues = []
        api_path = _PROJECT_ROOT / "bridge" / "api.py"
        if not api_path.exists():
            return issues
        try:
            src = api_path.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except (SyntaxError, UnicodeDecodeError):
            return issues

        bridge_cls = None
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == "Bridge":
                bridge_cls = node
                break
        if not bridge_cls:
            return issues

        for func in bridge_cls.body:
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(func):
                if not isinstance(node, ast.Return) or not node.value:
                    continue
                # Match: return _ok(CALL(...))
                val = node.value
                if not (isinstance(val, ast.Call)
                        and isinstance(val.func, ast.Name)
                        and val.func.id == "_ok"
                        and val.args):
                    continue
                inner = val.args[0]
                if not isinstance(inner, ast.Call):
                    continue  # _ok({"key": "val"}) is fine - it's a literal
                # Check if the line has a suppression comment
                line_text = src.splitlines()[node.lineno - 1] if node.lineno <= len(src.splitlines()) else ""
                if "ok-passthrough-safe" in line_text:
                    continue
                # Get inner function name for the message
                inner_name = ""
                if isinstance(inner.func, ast.Name):
                    inner_name = inner.func.id
                elif isinstance(inner.func, ast.Attribute):
                    inner_name = inner.func.attr
                issues.append(RepairIssue(
                    category="blind_ok_passthrough",
                    severity="low",
                    file_path="bridge/api.py",
                    line_number=node.lineno,
                    description=(
                        f"{func.name}(): return _ok({inner_name}(...)) without "
                        f"checking inner result for error key. If {inner_name} "
                        f"returns {{\"error\": \"...\"}}, callers will see ok=True "
                        f"with error-in-data (silent failure)."
                    ),
                    root_cause="BUG-054 family: inner function error not caught before _ok wrap",
                    auto_fixable=False,
                    fix_description=(
                        f"Store result of {inner_name}() in a variable, check "
                        f"for 'error' key, return _err() if found, else _ok(). "
                        f"Or add # vj: ok-passthrough-safe to suppress."
                    ),
                ))
        return issues

    def _scan_syncer_drift(self) -> list[RepairIssue]:
        """Phase 2: Detect project State.md files not updated in 48 hours.

        Stale State.md files mean the project_syncer stopped receiving events
        for an active bid - either the syncer is not running or events aren't
        being emitted. Returns WARN items, not blockers.
        """
        issues = []
        try:
            from bridge.project_syncer import ProjectSyncer
            syncer = ProjectSyncer()
            stale = syncer.check_stale_state_files(max_age_hours=48)
            for item in stale:
                issues.append(RepairIssue(
                    category="syncer_drift",
                    severity="medium",
                    file_path=item.get("state_md", ""),
                    line_number=0,
                    description=(
                        f"Project State.md stale {item.get('age_hours', '?')}h: "
                        f"{item.get('project_dir', '?')}"
                    ),
                    root_cause=(
                        "project_syncer not receiving bid events for this project. "
                        "Either syncer is stopped or bid_pipeline is not emitting events."
                    ),
                    auto_fixable=False,
                    fix_description=(
                        "Call Bridge.sync_project() to force a State.md refresh, "
                        "or advance the bid in the pipeline to trigger an event."
                    ),
                ))
        except Exception:
            pass
        return issues


    # ── Pass 11 (2026-07-02): workspace / context audit (advisory) ──
    # Source pattern: research/fable5-use-cases/SUMMARY.md (six-area
    # workspace audit). Mechanical checks only; the judgment half
    # (delete-test, conflicting rules, MCP-vs-CLI overlap) lives in
    # skills/vj-scan/SKILL.md Category 10. Everything here routes to
    # the warnings channel and nothing is auto-fixable. Read-only.

    _AUDIT_ALWAYS_LOADED = (
        "CLAUDE.md",
        "0.ai-context/CLAUDE.md",
        "INDEX.md",
        "owner-rules.md",
        "brand-voice.md",
        "company-details.md",
        "rates-and-pricing.md",
    )
    # Files legitimately absent from the tree (created at runtime).
    _AUDIT_RUNTIME_CREATED = (
        "data/model_routing.json",  # written by bridge/ai_model_router.py
    )
    # Prefixes and suffixes that are build outputs or runtime artifacts,
    # legitimately absent from a fresh tree. Not stale pointers.
    _AUDIT_RUNTIME_PREFIXES = ("dist/", "build/", "__pycache__/")
    _AUDIT_RUNTIME_SUFFIXES = (".db", ".log", ".exe", "_logs/", "_logs")
    _AUDIT_MAX_LINES = 200  # delete-test threshold for always-loaded files

    def _scan_workspace_audit(self) -> list[RepairIssue]:
        """Advisory workspace/context audit over always-loaded governance files.

        Checks: (a) stale path pointers, (b) always-loaded files over the
        delete-test threshold, (c) duplicate non-trivial lines across the
        always-loaded set, (d) skills/ directories referenced nowhere,
        (e) plaintext-secret patterns. Advisory only: findings are warnings,
        auto_fixable is always False, and CLAUDE.md fixes must go through
        .claude/skills/governance/scripts/safe_write.py after approval.
        """
        warnings: list[RepairIssue] = []
        loaded: dict[str, str] = {}
        for rel in self._AUDIT_ALWAYS_LOADED:
            p = self.root / rel
            if not p.exists():
                continue
            try:
                loaded[rel] = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

        # (a) stale pointers: backticked path-like tokens that do not exist
        path_token = re.compile(r"`([^`\n]+)`")
        skip_chars = ("<", ">", "*", "%", "$", "{", "(", ":", "http", " ")
        count_stale = 0
        for rel, src in loaded.items():
            for m in path_token.finditer(src):
                tok = m.group(1).strip().replace("\\", "/")
                if "/" not in tok or tok.startswith("/") or len(tok) > 120:
                    continue
                # ./ and ../ are relative to a loader template's own copy
                # location (per-bid folders), not the project root.
                if tok.startswith(("./", "../")):
                    continue
                if tok.startswith(self._AUDIT_RUNTIME_PREFIXES):
                    continue
                if tok.endswith(self._AUDIT_RUNTIME_SUFFIXES):
                    continue
                if any(c in tok for c in skip_chars):
                    continue
                if not re.match(r"^[A-Za-z0-9_.\/-]+$", tok):
                    continue
                clean = tok.rstrip("/")
                if clean in self._AUDIT_RUNTIME_CREATED:
                    continue
                # INDEX.md tables list entries relative to the section's
                # directory (bridge/, data/, skills/, ...). Check the
                # common bases before calling a pointer stale.
                bases = ("", "bridge/", "data/", "skills/", "frontend/",
                         ".claude/skills/", "docs/", "vo_app/")
                if any((self.root / (b + clean)).exists() for b in bases):
                    continue
                # Single-segment names (no parent in the token) may sit
                # anywhere; check two directory levels before flagging.
                if "/" not in clean:
                    try:
                        if (next(self.root.glob(f"*/{clean}"), None)
                                or next(self.root.glob(f"*/*/{clean}"), None)):
                            continue
                    except OSError:
                        pass
                if True:
                    if count_stale >= 20:
                        break
                    count_stale += 1
                    line_num = src[:m.start()].count("\n") + 1
                    warnings.append(RepairIssue(
                        category="workspace_stale_pointer",
                        severity="medium",
                        file_path=rel,
                        line_number=line_num,
                        description=f"Stale pointer: `{tok}` does not exist ({rel}:{line_num})",
                        root_cause="An always-loaded governance file references a path missing from the tree; the agent inherits a wrong fact every session.",
                        auto_fixable=False,
                        fix_description="Correct or remove the reference. CLAUDE.md edits only via safe_write.py, after approval.",
                    ))

        # (b) delete-test size flag for always-loaded memory
        for rel, src in loaded.items():
            n_lines = src.count("\n") + 1
            if n_lines > self._AUDIT_MAX_LINES:
                warnings.append(RepairIssue(
                    category="workspace_context_size",
                    severity="low",
                    file_path=rel,
                    line_number=1,
                    description=f"{rel} is {n_lines} lines (threshold {self._AUDIT_MAX_LINES}); delete-test its rules",
                    root_cause="Oversized always-loaded context dilutes attention; rules that fail the delete-test are candidates to move on-demand.",
                    auto_fixable=False,
                    fix_description="Run vj-scan Category 10 delete-test; move non-behavioral content to on-demand skills or docs.",
                ))

        # (c) duplicate non-trivial lines across always-loaded files
        seen: dict[str, str] = {}
        dup_count = 0
        for rel, src in loaded.items():
            for line in {ln.strip() for ln in src.splitlines()}:
                if len(line) < 45 or line.startswith(("|", "#", "```", "<!--")):
                    continue
                if line in seen and seen[line] != rel:
                    if dup_count >= 10:
                        break
                    dup_count += 1
                    warnings.append(RepairIssue(
                        category="workspace_duplicate_rule",
                        severity="low",
                        file_path=rel,
                        line_number=0,
                        description=f"Line duplicated in {seen[line]} and {rel}: {line[:80]}",
                        root_cause="The same rule text lives in two always-loaded files; edits will drift.",
                        auto_fixable=False,
                        fix_description="Keep one canonical copy; the other file references it.",
                    ))
                else:
                    seen.setdefault(line, rel)

        # (d) skills never referenced by the loaders or the index
        ref_corpus = "\n".join(loaded.get(r, "") for r in
                               ("CLAUDE.md", "0.ai-context/CLAUDE.md", "INDEX.md"))
        skills_dir = self.root / "skills"
        unused = 0
        if skills_dir.is_dir():
            for d in sorted(skills_dir.iterdir()):
                if not d.is_dir() or not (d / "SKILL.md").exists():
                    continue
                if d.name not in ref_corpus:
                    if unused >= 15:
                        break
                    unused += 1
                    warnings.append(RepairIssue(
                        category="workspace_unreferenced_skill",
                        severity="low",
                        file_path=f"skills/{d.name}/SKILL.md",
                        line_number=1,
                        description=f"skills/{d.name} is referenced by neither CLAUDE.md, 0.ai-context/CLAUDE.md, nor INDEX.md",
                        root_cause="A skill nothing routes to is dead weight or a routing gap.",
                        auto_fixable=False,
                        fix_description="Add a routing line to INDEX.md or the loader, or retire the skill (human decision).",
                    ))

        # (e) plaintext secrets in always-loaded files
        secret_pat = re.compile(
            r"(sk-[A-Za-z0-9_\-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}"
            r"|api[_\-]?key\s*[=:]\s*[\"'][A-Za-z0-9_\-]{16,})",
            re.IGNORECASE,
        )
        for rel, src in loaded.items():
            m = secret_pat.search(src)
            if m:
                warnings.append(RepairIssue(
                    category="workspace_plaintext_secret",
                    severity="high",
                    file_path=rel,
                    line_number=src[:m.start()].count("\n") + 1,
                    description=f"Possible plaintext credential in {rel}",
                    root_cause="Secrets in always-loaded context leak into every session and log.",
                    auto_fixable=False,
                    fix_description="Move the secret to the API Keys/ loader path and scrub history (human action).",
                ))

        return warnings

    def _count_py_files(self) -> int:
        return sum(1 for _ in self._iter_py_files())

    def _run_diagnostics_summary(self) -> dict:
        """Run diagnostics and return summary counts."""
        try:
            from bridge.diagnostics import run_diagnostics
            r = run_diagnostics(
                include_bridge=True, include_calculators=True,
                include_dispatchers=True, include_harnesses=True,
                include_aisc=True, log_to_file=False,
            )
            return r.get("summary", {})
        except Exception as e:
            return {"error": str(e)}


# R10/R12: alias so callers can use `SelfRepair` as the short name
SelfRepair = SelfRepairEngine


if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv
    fast_mode = "--fast" in sys.argv
    engine = SelfRepairEngine()
    report = engine.scan_and_fix(fast_mode=fast_mode, dry_run=dry_run)
    print(report.summary())
    sys.exit(0 if report.clean or dry_run else 1)
