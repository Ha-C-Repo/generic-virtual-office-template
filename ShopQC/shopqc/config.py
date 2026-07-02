"""Configuration. config.json lives next to the EXE (or project root in dev)."""

import json
import os
import sys

DEFAULTS = {
    # Local SQLite database file. When storage_mode is "supabase" this is the
    # offline cache and write outbox only and Supabase is the live system of record;
    # when storage_mode is "sqlite" it is the database itself. See SUPABASE_SETUP.md
    # and DEPLOY_JOSEPH.md.
    "db_path": "yourco_qc.db",
    # Printing mode: "win32" (Windows spooler RAW, recommended),
    # "share" (copy raw ZPL to a shared printer UNC path), "file" (debug).
    "printer_mode": "win32",
    "printer_name": "ZDesigner ZD421-203dpi ZPL",
    "printer_share": r"\\localhost\ZEBRA",
    "label_output_dir": "labels_out",
    "station_name": "STATION-1",
    # Storage backend: "sqlite" (single file, the shipped default) or "supabase"
    # (Supabase Postgres as the shared system of record, with the local SQLite file
    # as an offline cache and write outbox). See SUPABASE_SETUP.md.
    "storage_mode": "sqlite",
    # Supabase Postgres connection. Used only when storage_mode is "supabase". Fill
    # these on each host in this file (config.json is gitignored and is never
    # committed). Provide either supabase_db_url, or the five split fields below.
    # Environment variables override at runtime: SHOPQC_DB_URL, or SHOPQC_DB_HOST /
    # SHOPQC_DB_PORT / SHOPQC_DB_NAME / SHOPQC_DB_USER / SHOPQC_DB_PASSWORD /
    # SHOPQC_DB_SSLMODE. Leave blank to run on the local SQLite file. The Supabase
    # session pooler requires SSL, so sslmode defaults to "require".
    "supabase_db_url": "",
    "supabase_db_host": "",
    "supabase_db_port": "5432",
    "supabase_db_name": "",
    "supabase_db_user": "",
    "supabase_db_password": "",
    "supabase_db_sslmode": "require",
}


def app_dir() -> str:
    """Folder the EXE (frozen) or project (dev) runs from."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(rel: str) -> str:
    """Bundled read-only resources (PyInstaller _MEIPASS aware)."""
    base = getattr(sys, "_MEIPASS", app_dir())
    return os.path.join(base, rel)


def config_path() -> str:
    return os.path.join(app_dir(), "config.json")


def load() -> dict:
    cfg = dict(DEFAULTS)
    p = config_path()
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass  # corrupt config: run on defaults rather than crash the shop floor
    else:
        save(cfg)
    if not os.path.isabs(cfg["db_path"]):
        cfg["db_path"] = os.path.join(app_dir(), cfg["db_path"])
    return cfg


def save(cfg: dict) -> None:
    with open(config_path(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def _first(*vals) -> str:
    """First non-empty stripped value, or '' if none. Used to layer an environment
    variable over a config value."""
    for v in vals:
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def supabase_connection_params(cfg: dict):
    """Resolve the Supabase Postgres connection from config, with environment
    variables taking precedence. Returns a dict for psycopg2.connect (either
    {"dsn": url} or the keyword fields host/port/dbname/user/password), or None when
    nothing is configured so the caller falls back to the local SQLite file.

    Credentials are read here and handed straight to the driver; they are never
    logged or echoed. config.json holds them on each host and is gitignored."""
    url = _first(os.environ.get("SHOPQC_DB_URL"), cfg.get("supabase_db_url"))
    if url:
        return {"dsn": url}
    host = _first(os.environ.get("SHOPQC_DB_HOST"), cfg.get("supabase_db_host"))
    if not host:
        return None
    # Password is intentionally not stripped: it may legitimately contain spaces.
    password = (os.environ.get("SHOPQC_DB_PASSWORD")
                if os.environ.get("SHOPQC_DB_PASSWORD") not in (None, "")
                else cfg.get("supabase_db_password") or "")
    return {
        "host": host,
        "port": _first(os.environ.get("SHOPQC_DB_PORT"),
                       cfg.get("supabase_db_port"), "5432"),
        "dbname": _first(os.environ.get("SHOPQC_DB_NAME"),
                         cfg.get("supabase_db_name")),
        "user": _first(os.environ.get("SHOPQC_DB_USER"),
                       cfg.get("supabase_db_user")),
        "password": password,
        "sslmode": _first(os.environ.get("SHOPQC_DB_SSLMODE"),
                          cfg.get("supabase_db_sslmode"), "require"),
    }
