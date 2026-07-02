"""
Your Company Virtual Office - Skill Registry
==========================================
Progressive-disclosure skill loader following Anthropic's SKILL.md pattern.

At startup, loads only frontmatter (~80 tokens per skill = ~560 tokens total).
Full skill body (~2K tokens each) loads only when the intent router or
user query matches a skill's triggers.

Usage:
    from bridge.skill_registry import SkillRegistry
    registry = SkillRegistry()
    
    # Lightweight: returns all skill names + descriptions (~560 tokens)
    prompt_section = registry.metadata_prompt()
    
    # On-demand: loads full body when needed (~2K tokens)
    body = registry.load("drawing-reading")
    
    # Auto-match: finds best skill for a message
    skill = registry.match("take off this drawing set")
    if skill:
        body = registry.load(skill.name)
"""

import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class SkillMetadata:
    """Lightweight skill descriptor (frontmatter only)."""
    name: str
    description: str
    triggers: list[str]
    path: Path


class SkillRegistry:
    """Progressive-disclosure skill loader."""

    def __init__(self, skills_dir: Optional[Path] = None):
        if skills_dir is None:
            skills_dir = Path(__file__).resolve().parent.parent / "skills"
        self._dir = skills_dir
        self._skills: dict[str, SkillMetadata] = {}
        self._body_cache: dict[str, str] = {}
        self._load_metadata()

    def _load_metadata(self):
        """Load frontmatter from all SKILL.md files (~80 tokens each)."""
        if not self._dir.exists():
            log.warning("Skills directory not found: %s", self._dir)
            return

        for skill_dir in sorted(self._dir.iterdir()):
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                content = skill_md.read_text(encoding="utf-8")
                fm, body = self._parse_frontmatter(content)
                if fm and "name" in fm:
                    self._skills[fm["name"]] = SkillMetadata(
                        name=fm["name"],
                        description=fm.get("description", "").strip(),
                        triggers=fm.get("triggers", []),
                        path=skill_md,
                    )
            except Exception as e:
                log.warning("Failed to load skill %s: %s", skill_dir.name, e)

        log.info("SkillRegistry: loaded %d skills", len(self._skills))

    @staticmethod
    def _parse_frontmatter(content: str) -> tuple[dict, str]:
        """Parse YAML-like frontmatter from SKILL.md content.
        
        Returns (frontmatter_dict, body_text).
        Simple parser - handles name, description, triggers without
        requiring PyYAML dependency.
        """
        if not content.startswith("---"):
            return {}, content

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content

        fm_text = parts[1].strip()
        body = parts[2].strip()

        # Simple YAML-like parser (no PyYAML dependency)
        fm = {}
        current_key = None
        current_value_lines = []

        for line in fm_text.splitlines():
            stripped = line.strip()

            # List item (for triggers)
            if stripped.startswith("- ") and current_key:
                if current_key not in fm:
                    fm[current_key] = []
                if isinstance(fm[current_key], list):
                    fm[current_key].append(stripped[2:].strip())
                continue

            # Multi-line value continuation
            if line.startswith("  ") and current_key and current_key not in fm:
                current_value_lines.append(stripped)
                continue

            # Flush accumulated multi-line value
            if current_value_lines and current_key:
                fm[current_key] = " ".join(current_value_lines)
                current_value_lines = []

            # Key: value pair
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()

                current_key = key

                if val == ">":
                    # Multi-line scalar follows
                    current_value_lines = []
                elif val:
                    fm[key] = val
                else:
                    # Could be a list (triggers:) with items below
                    fm[key] = []

        # Flush last accumulated value
        if current_value_lines and current_key:
            fm[current_key] = " ".join(current_value_lines)

        return fm, body

    def metadata_prompt(self) -> str:
        """Return lightweight prompt section listing all skills.
        
        ~80 tokens per skill. Include in system prompt for discovery.
        """
        if not self._skills:
            return ""

        lines = ["Available skills (say 'load skill X' for full instructions):"]
        for s in self._skills.values():
            triggers = ", ".join(s.triggers[:4])
            lines.append(f"  - {s.name}: {s.description[:80]}... "
                         f"[triggers: {triggers}]")
        return "\n".join(lines)

    def load(self, name: str) -> str:
        """Load full skill body on demand (~2K tokens).
        
        Returns the full SKILL.md body (everything after frontmatter).
        Cached after first load.
        """
        if name in self._body_cache:
            return self._body_cache[name]

        if name not in self._skills:
            return f"Skill '{name}' not found. Available: {', '.join(self._skills)}"

        skill = self._skills[name]
        content = skill.path.read_text(encoding="utf-8")
        _, body = self._parse_frontmatter(content)
        self._body_cache[name] = body
        return body

    def match(self, message: str) -> Optional[SkillMetadata]:
        """Find the best matching skill for a message.
        
        Returns the skill with the most trigger matches, or None.
        """
        msg_lower = message.lower()
        best_skill = None
        best_score = 0

        for skill in self._skills.values():
            score = 0
            for trigger in skill.triggers:
                if trigger.lower() in msg_lower:
                    score += len(trigger)  # longer matches = better
            if score > best_score:
                best_score = score
                best_skill = skill

        return best_skill if best_score > 0 else None

    def list_skills(self) -> list[dict]:
        """List all skills for display."""
        return [
            {
                "name": s.name,
                "description": s.description[:100],
                "triggers": s.triggers,
                "path": str(s.path),
            }
            for s in self._skills.values()
        ]

    @property
    def count(self) -> int:
        return len(self._skills)
