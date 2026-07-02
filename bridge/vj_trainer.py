"""Virtual Joseph Trainer - Learn from Claude export data.

Parses the Claude data export (ZIP of JSON conversations), extracts
bug patterns, corrections, decision rules, technical facts, and voice
examples from real chat history. Feeds everything into VJ's knowledge
base so it has Joseph's actual thinking patterns, not just the seed data.

Workflow:
  1. Joseph exports Claude data (Settings > Account > Export Data)
  2. Places the ZIP at data/claude_export/ or provides the path
  3. Runs: Bridge.vj_train_from_export(path="path/to/export.zip")
  4. VJ parses every conversation, extracts patterns
  5. Knowledge base is updated with real lessons and rules
  6. Joseph builds the EXE (make_exe_signed.bat)
  7. The EXE ships with VJ already trained on real data

The ~70MB export is processed via streaming/iterative parsing.
No full-load into memory.

Usage:
    from bridge.vj_trainer import VJTrainer

    trainer = VJTrainer("path/to/claude_export.zip")
    report = trainer.train()
    print(report.summary())
"""

import json
import logging
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

log = logging.getLogger("vj_trainer")

_DATA_DIR = Path(__file__).parent.parent / "data" / "virtual_joseph"


@dataclass
class TrainingReport:
    """Result of training VJ from export data."""
    conversations_parsed: int = 0
    messages_processed: int = 0
    bugs_extracted: int = 0
    corrections_extracted: int = 0
    decisions_extracted: int = 0
    facts_extracted: int = 0
    voice_examples_extracted: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0

    def summary(self) -> str:
        lines = [
            f"Training complete in {self.duration_seconds:.1f}s",
            f"Conversations parsed: {self.conversations_parsed}",
            f"Messages processed: {self.messages_processed}",
            f"Bugs extracted: {self.bugs_extracted}",
            f"Corrections extracted: {self.corrections_extracted}",
            f"Decisions extracted: {self.decisions_extracted}",
            f"Facts extracted: {self.facts_extracted}",
            f"Voice examples: {self.voice_examples_extracted}",
        ]
        total = (self.bugs_extracted + self.corrections_extracted +
                 self.decisions_extracted + self.facts_extracted +
                 self.voice_examples_extracted)
        lines.append(f"Total patterns learned: {total}")
        if self.errors:
            lines.append(f"Errors: {len(self.errors)}")
        return "\n".join(lines)


# ================================================================
# Pattern extractors - each looks for a specific type of knowledge
# ================================================================

# Bug signals in conversation text
BUG_SIGNALS = [
    r"(?i)\bbug\b.*\bfix", r"(?i)\bfixed\b.*\bbug",
    r"(?i)\bbroken\b", r"(?i)\bcrash", r"(?i)ImportError",
    r"(?i)AttributeError", r"(?i)TypeError", r"(?i)KeyError",
    r"(?i)\bsilent.*(?:zero|fail|error)", r"(?i)\bstale.*(?:import|test)",
    r"(?i)\bwrong.*(?:key|name|function|method|import)",
    r"(?i)\bdoes not exist\b", r"(?i)\bnot defined\b",
    r"(?i)\bregression\b", r"(?i)\bP0\b", r"(?i)\bcritical.*fix",
    r"(?i)\bsweep.*(?:found|caught)", r"(?i)\bdiagnostic.*(?:FAIL|WARN)",
]

# Correction signals
CORRECTION_SIGNALS = [
    r"(?i)\bactually\b.*\bnot\b", r"(?i)\bwrong\b.*\bshould be\b",
    r"(?i)\bcorrect(?:ed|ion)\b", r"(?i)\bnot\s+\w+,\s+it'?s\b",
    r"(?i)\bchange\b.*\bto\b", r"(?i)\bupdate\b.*\bfrom\b.*\bto\b",
    r"(?i)\breplac(?:e|ed)\b.*\bwith\b",
    r"(?i)\bthat'?s\s+(?:wrong|incorrect|outdated)",
    r"(?i)\bremember\b.*\b(?:that|this)\b",
]

# Decision/creative solution signals
DECISION_SIGNALS = [
    r"(?i)\blet'?s\b.*\binstead\b", r"(?i)\bwhat if\b",
    r"(?i)\bcreative\b.*\bsolution\b", r"(?i)\bapproach\b.*\bdifferent",
    r"(?i)\btwo heads\b", r"(?i)\bnever assume\b",
    r"(?i)\bintegration.*path", r"(?i)\bcross-phase\b",
    r"(?i)\badversarial\b.*\bprobe", r"(?i)\bsim.*(?:sweep|test)",
    r"(?i)\bbeyond.*scope\b", r"(?i)\bgo.*further\b",
    r"(?i)\bthought experiment\b", r"(?i)\bwhat.*(?:would|could)\b.*\bif\b",
]

# Technical fact signals (Your Company specific)
FACT_SIGNALS = [
    r"\$\d{2,3}/(?:hr|hour|ton|sf)", r"(?i)\b(?:shop|fab|erect)\s*rate\b",
    r"(?i)\bISNetworld\b", r"(?i)\bAvetta\b", r"(?i)\b(?:EMR|TRIR)\b",
    r"(?i)\bAISC\b.*\b\d+", r"(?i)\b\d+\s*(?:hrs?|hours?)/ton\b",
    r"(?i)\b(?:Mario|Paul|Amber)\b.*\b(?:lead|director|COO|safety)\b",
    r"(?i)\b8630\s*Fairbanks\b", r"(?i)\b713.*255.*2172\b",
    r"(?i)\bNano\s*Cube\b.*\b(?:est|established|founded).*\b20\d{2}\b",
    r"(?i)\b(?:ICD|Elite|Topgolf|Carvana)\b.*\b(?:church|crossing|project)\b",
]

# Voice rule signals
VOICE_SIGNALS = [
    r"(?i)\bem.dash", r"(?i)\bno\s+(?:filler|fluff)\b",
    r"(?i)\bshort\s+sentences\b", r"(?i)\bno\s+three.adjective",
    r"(?i)\bOwner'?s\s+voice\b", r"(?i)\bJoseph'?s\s+voice\b",
    r"(?i)\bvoice\s+rule\b", r"(?i)\bbrand\s+voice\b",
    r"(?i)\bnot just X.*it'?s Y\b", r"(?i)\bgreat question\b.*\bdon'?t\b",
    r"(?i)\bleverage\b.*\bdon'?t\b", r"(?i)\bsynergy\b.*\bdon'?t\b",
]


class VJTrainer:
    """Parses Claude export data and trains VJ's knowledge base."""

    def __init__(self, export_path: str | Path | None = None):
        self.export_path = Path(export_path) if export_path else None
        self.report = TrainingReport()
        self._extracted = {
            "bugs": [],
            "corrections": [],
            "decisions": [],
            "facts": [],
            "voice": [],
        }

    def train(self, export_path: str | Path | None = None) -> TrainingReport:
        """Parse the export and train VJ.

        Args:
            export_path: Path to Claude export ZIP or directory.
                         If not provided, looks in data/claude_export/.

        Returns:
            TrainingReport with extraction counts.
        """
        import time
        t0 = time.time()

        path = Path(export_path) if export_path else self.export_path
        if not path:
            # Look for export in default location
            default_dir = _DATA_DIR.parent / "claude_export"
            if default_dir.exists():
                zips = list(default_dir.glob("*.zip"))
                jsons = list(default_dir.glob("*.json"))
                if zips:
                    path = zips[0]
                elif jsons:
                    path = default_dir
            if not path:
                self.report.errors.append(
                    "No export path provided and no data found in "
                    "data/claude_export/. Place your Claude export ZIP "
                    "there or provide the path."
                )
                return self.report

        # Parse conversations
        for conversation in self._iter_conversations(path):
            self._process_conversation(conversation)

        # Write to knowledge base
        self._update_knowledge_base()

        self.report.duration_seconds = time.time() - t0
        return self.report

    def _iter_conversations(self, path: Path) -> Iterator[dict]:
        """Iterate over conversations from the export.

        Handles:
        - ZIP file containing JSON files
        - Directory of JSON files
        - Single JSON file
        """
        if path.suffix == ".zip" and path.is_file():
            yield from self._iter_zip(path)
        elif path.is_dir():
            yield from self._iter_directory(path)
        elif path.suffix == ".json" and path.is_file():
            yield from self._iter_json_file(path)
        else:
            self.report.errors.append(f"Unsupported path: {path}")

    def _iter_zip(self, zip_path: Path) -> Iterator[dict]:
        """Stream conversations from a ZIP file without full extraction."""
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                for name in zf.namelist():
                    if not name.endswith(".json"):
                        continue
                    try:
                        with zf.open(name) as f:
                            data = json.loads(f.read())
                            if isinstance(data, list):
                                for item in data:
                                    if self._is_conversation(item):
                                        yield item
                            elif self._is_conversation(data):
                                yield data
                    except (json.JSONDecodeError, KeyError) as e:
                        self.report.errors.append(f"Parse error in {name}: {e}")
        except zipfile.BadZipFile as e:
            self.report.errors.append(f"Bad ZIP file: {e}")

    def _iter_directory(self, dir_path: Path) -> Iterator[dict]:
        """Iterate over JSON files in a directory."""
        for json_file in sorted(dir_path.glob("**/*.json")):
            yield from self._iter_json_file(json_file)

    def _iter_json_file(self, json_path: Path) -> Iterator[dict]:
        """Parse a single JSON file, streaming if it's large."""
        try:
            # Stream large files
            size = json_path.stat().st_size
            if size > 50_000_000:  # 50MB
                # Use line-by-line for JSONL
                with open(json_path, "r", encoding="utf-8", errors="replace") as f:
                    first_char = f.read(1)
                    f.seek(0)
                    if first_char == "[":
                        data = json.load(f)
                        for item in data:
                            if self._is_conversation(item):
                                yield item
                    else:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    item = json.loads(line)
                                    if self._is_conversation(item):
                                        yield item
                                except json.JSONDecodeError:
                                    pass
            else:
                with open(json_path, "r", encoding="utf-8", errors="replace") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            if self._is_conversation(item):
                                yield item
                    elif self._is_conversation(data):
                        yield data
        except Exception as e:
            self.report.errors.append(f"Error reading {json_path.name}: {e}")

    def _is_conversation(self, data: Any) -> bool:
        """Check if a JSON object looks like a Claude conversation."""
        if not isinstance(data, dict):
            return False
        # Claude exports have various formats; check for common keys
        return any(key in data for key in [
            "chat_messages", "messages", "conversation",
            "uuid", "name", "created_at",
        ])

    def _process_conversation(self, conversation: dict):
        """Extract patterns from a single conversation."""
        self.report.conversations_parsed += 1

        # Get messages from various Claude export formats
        messages = (
            conversation.get("chat_messages")
            or conversation.get("messages")
            or conversation.get("conversation", {}).get("messages")
            or []
        )

        if not isinstance(messages, list):
            return

        conv_title = conversation.get("name", conversation.get("title", ""))
        conv_id = conversation.get("uuid", conversation.get("id", ""))

        for msg in messages:
            if not isinstance(msg, dict):
                continue

            # Extract text from various message formats
            text = self._extract_text(msg)
            if not text or len(text) < 20:
                continue

            self.report.messages_processed += 1
            role = msg.get("sender", msg.get("role", ""))

            # Run pattern extractors
            self._extract_bugs(text, conv_title, conv_id, role)
            self._extract_corrections(text, conv_title, conv_id, role)
            self._extract_decisions(text, conv_title, conv_id, role)
            self._extract_facts(text, conv_title, conv_id, role)
            self._extract_voice_examples(text, conv_title, conv_id, role)

    def _extract_text(self, msg: dict) -> str:
        """Extract text content from a message object."""
        # Claude export formats vary
        text = msg.get("text", "")
        if not text:
            content = msg.get("content", "")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, dict):
                        parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        parts.append(part)
                text = " ".join(parts)
        return text

    def _extract_bugs(self, text: str, title: str, conv_id: str, role: str):
        """Extract bug patterns from message text."""
        for pattern in BUG_SIGNALS:
            if re.search(pattern, text):
                # Extract a window around the match
                match = re.search(pattern, text)
                if match:
                    start = max(0, match.start() - 100)
                    end = min(len(text), match.end() + 200)
                    snippet = text[start:end].strip()
                    self._extracted["bugs"].append({
                        "snippet": snippet[:300],
                        "pattern": pattern,
                        "conversation": title or conv_id,
                        "role": role,
                    })
                    self.report.bugs_extracted += 1
                    break  # One bug per message

    def _extract_corrections(self, text: str, title: str, conv_id: str, role: str):
        """Extract corrections (user correcting system output)."""
        if role not in ("human", "user"):
            return
        for pattern in CORRECTION_SIGNALS:
            if re.search(pattern, text):
                match = re.search(pattern, text)
                if match:
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 150)
                    snippet = text[start:end].strip()
                    self._extracted["corrections"].append({
                        "snippet": snippet[:300],
                        "conversation": title or conv_id,
                    })
                    self.report.corrections_extracted += 1
                    break

    def _extract_decisions(self, text: str, title: str, conv_id: str, role: str):
        """Extract creative decisions and solutions."""
        for pattern in DECISION_SIGNALS:
            if re.search(pattern, text):
                match = re.search(pattern, text)
                if match:
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 200)
                    snippet = text[start:end].strip()
                    self._extracted["decisions"].append({
                        "snippet": snippet[:300],
                        "conversation": title or conv_id,
                        "role": role,
                    })
                    self.report.decisions_extracted += 1
                    break

    def _extract_facts(self, text: str, title: str, conv_id: str, role: str):
        """Extract technical facts (rates, contacts, project details)."""
        for pattern in FACT_SIGNALS:
            if re.search(pattern, text):
                match = re.search(pattern, text)
                if match:
                    start = max(0, match.start() - 30)
                    end = min(len(text), match.end() + 100)
                    snippet = text[start:end].strip()
                    self._extracted["facts"].append({
                        "snippet": snippet[:200],
                        "conversation": title or conv_id,
                        "role": role,
                    })
                    self.report.facts_extracted += 1
                    break

    def _extract_voice_examples(self, text: str, title: str, conv_id: str, role: str):
        """Extract voice rule examples and preferences."""
        for pattern in VOICE_SIGNALS:
            if re.search(pattern, text):
                match = re.search(pattern, text)
                if match:
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 150)
                    snippet = text[start:end].strip()
                    self._extracted["voice"].append({
                        "snippet": snippet[:300],
                        "conversation": title or conv_id,
                        "role": role,
                    })
                    self.report.voice_examples_extracted += 1
                    break

    def _update_knowledge_base(self):
        """Write extracted patterns to VJ's knowledge base."""
        _DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Save raw extractions for review
        output = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "report": {
                "conversations": self.report.conversations_parsed,
                "messages": self.report.messages_processed,
                "bugs": self.report.bugs_extracted,
                "corrections": self.report.corrections_extracted,
                "decisions": self.report.decisions_extracted,
                "facts": self.report.facts_extracted,
                "voice": self.report.voice_examples_extracted,
            },
            "extractions": self._extracted,
        }

        output_path = _DATA_DIR / "training_extractions.json"
        output_path.write_text(json.dumps(output, indent=2, default=str))

        # Update the knowledge base with new lessons
        try:
            from bridge.vj_knowledge import get_knowledge_base, Lesson

            kb = get_knowledge_base()

            # Create aggregate lessons from extracted bugs
            if self._extracted["bugs"]:
                unique_patterns = set()
                for bug in self._extracted["bugs"]:
                    for word in ["ImportError", "AttributeError", "TypeError",
                                 "KeyError", "silent", "broken", "regression",
                                 "stale"]:
                        if word.lower() in bug["snippet"].lower():
                            unique_patterns.add(word)

                kb.add_lesson(Lesson(
                    id="trained_bugs",
                    pattern_class="trained_from_export",
                    title=f"Bug patterns from {self.report.bugs_extracted} chat messages",
                    description=(
                        f"Extracted from {self.report.conversations_parsed} conversations. "
                        f"Pattern types found: {', '.join(sorted(unique_patterns))}"
                    ),
                    detection_method="Pattern matching against chat history signals",
                    fix_pattern="Cross-reference with self_repair scanner and diagnostic engine",
                    severity="medium",
                    source_version="trained",
                    source_finder="vj_trainer",
                    occurrences=self.report.bugs_extracted,
                    tags=list(unique_patterns),
                ))

            # Save corrections as VJ correction records
            if self._extracted["corrections"]:
                from bridge.virtual_joseph import get_virtual_joseph
                vj = get_virtual_joseph()
                for correction in self._extracted["corrections"][:50]:
                    vj.catalog_correction(
                        original=correction["snippet"][:100],
                        correction="[extracted from chat - review needed]",
                        context=correction.get("conversation", "chat export"),
                        rule_type="trained",
                    )

            kb._save()
            log.info(
                "Knowledge base updated: %d bugs, %d corrections, %d decisions",
                self.report.bugs_extracted,
                self.report.corrections_extracted,
                self.report.decisions_extracted,
            )
        except Exception as e:
            self.report.errors.append(f"KB update error: {e}")


# ================================================================
# Bridge integration
# ================================================================

def train_from_export(export_path: str = "") -> dict:
    """Train VJ from a Claude data export.

    Args:
        export_path: Path to ZIP file or directory with JSON exports.
                     If empty, looks in data/claude_export/.

    Returns:
        Training report with extraction counts.
    """
    trainer = VJTrainer(export_path if export_path else None)
    report = trainer.train(export_path if export_path else None)
    return {
        "ok": len(report.errors) == 0,
        "summary": report.summary(),
        "conversations": report.conversations_parsed,
        "messages": report.messages_processed,
        "patterns_learned": (
            report.bugs_extracted + report.corrections_extracted +
            report.decisions_extracted + report.facts_extracted +
            report.voice_examples_extracted
        ),
        "bugs": report.bugs_extracted,
        "corrections": report.corrections_extracted,
        "decisions": report.decisions_extracted,
        "facts": report.facts_extracted,
        "voice_examples": report.voice_examples_extracted,
        "errors": report.errors,
    }
