# Governance Delta

Additive to `.specify/constitution.md`. Does not replace it. Five review gates plus one principle. Keep them proportional: this is bid tooling and small utilities, not a distributed system, so most gates fire rarely.

## Review gates
| Gate | Rule | Fires when | Basis |
|---|---|---|---|
| Premature-scaling | Exhaust native capability before adding infrastructure | Add a cache, queue, or service | YAGNI |
| Monolith-first | Prefer one process and proven primitives | Split into services or add a framework | DHH majestic monolith |
| Dependency-tax | Build with native primitives before importing a package | Any new third-party dependency | left-pad 2016, event-stream 2018, chalk 2025 |
| Profile-don't-guess | Measure before optimizing | Any optimization claim | Acton, data-oriented design 2014 |
| One-layer-down | Know what the runtime or database does under the call | Any ORM or abstraction over SQL or IO | senior review |

## Principle: verify, do not generate
AI checks work that costs money if wrong; it does not produce the system-of-record output unguarded. Estimates and quantities get a verification step. Drawing counts from a model are approximate, not accurate, so a human verifies. Low-risk content may be generated.
## Principle: canonical file plus rendered mirror

Recurring reference data lives in one canonical, versioned file; anything
derived from it (a rendered mirror, a generated document, styled output) is
regenerated from that file, never edited independently. Read the canonical
file before editing the domain it governs. Reuse its values by name instead
of pasting literals. Update the canonical file and every mirror in the same
commit, with a verify step that they agree. Applied instances: BID_RATES in
`bridge/bid_rates.py` and the AISC database behind `bridge/aisc_validator.py`
(numbers), `docs/design.md` plus `docs/design.html` (frontend tokens),
`brand/brand-tokens.json` under `brand/LOGO_RULES.md` (brand). This is the
verify-do-not-generate principle applied to reference data.
