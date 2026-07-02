# Project skeleton protection (standing rule, added 2026-06-12)

Why this exists: a sibling Cowork session deleted the empty ACP skeleton
folders (01-07, 09) as cleanup, and the Prompt 10 session had to restore
them. Empty folders carry state in this system. The award-to-budget gate
STOPS when `01 Contract` is empty, and the PC4 reader picks its files
from the 09 folder by name. A missing folder reads as a different
condition than an empty one and breaks those gates silently.

- Every awarded project carries the nine-folder skeleton, `01 Contract`
  through `09 Financials -GP CONFIDENTIAL`. The template lives at
  `Awarded Projects/_TEMPLATE/`; copy it to start a new project.
- Each skeleton folder carries a `.gitkeep` so git preserves it while
  empty. The `.gitkeep` files are part of the skeleton, not clutter.
  Do not remove them as cleanup.

Rule: project skeleton folders are never deleted by any session,
occupied or empty, and sessions create or edit only inside their
declared target paths.
