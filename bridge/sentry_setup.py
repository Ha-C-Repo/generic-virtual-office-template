"""
Your Company Virtual Office - Sentry Setup
========================================
Initializes sentry-sdk with the correct release tag from __version__.
Prevents the @3.2.0 vs @3.5.1 misattribution issue.

Usage:
    from bridge.sentry_setup import init_sentry
    init_sentry()  # reads DSN from API Keys/Sentry DSN.txt
"""

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def _app_root() -> Path:
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _read_dsn() -> str:
    """Read Sentry DSN from API Keys folder."""
    dsn_path = _app_root() / "API Keys" / "Sentry DSN.txt"
    if dsn_path.exists():
        for line in dsn_path.read_text().splitlines():
            cleaned = line.strip().strip('"').strip("'")
            if cleaned and cleaned.startswith("https://"):
                return cleaned
    return ""


def get_release_tag() -> str:
    """Build the release tag from __version__.

    Format: steel-office@X.Y.Z (Sentry's package@version format
    enables semver-aware features like regression detection).
    """
    try:
        from vo_app import __version__
        return f"steel-office@{__version__}"
    except ImportError:
        return "steel-office@unknown"


def init_sentry(dsn: str = "", env: str = "production"):
    """Initialize Sentry with correct release tag.

    Args:
        dsn: Sentry DSN. If empty, reads from API Keys/Sentry DSN.txt.
        env: Environment name (production, development, staging).
    """
    dsn = dsn or _read_dsn()
    if not dsn:
        log.info("Sentry: no DSN configured, skipping init")
        return False

    try:
        import sentry_sdk
    except ImportError:
        log.warning("Sentry: sentry-sdk not installed, skipping")
        return False

    release = get_release_tag()

    sentry_sdk.init(
        dsn=dsn,
        release=release,
        environment=env,
        traces_sample_rate=0.1,
        send_default_pii=False,
        # Don't send breadcrumbs for API keys
        before_breadcrumb=_scrub_breadcrumb,
    )

    log.info("Sentry initialized: release=%s env=%s", release, env)
    return True


def _scrub_breadcrumb(crumb, hint):
    """Remove any breadcrumbs that might contain API keys."""
    msg = crumb.get("message", "")
    if any(k in msg.lower() for k in ("api_key", "api key", "sk-", "token")):
        return None
    return crumb
