"""Connection self-test for the configured storage backend.

Two ways to run it:

    py -m shopqc.selftest      (from source: prints the result)
    ShopQC.exe --check-db      (the frozen app: shows the result in a dialog)

Either way it reads config.json next to the app, resolves the connection, and
reports the storage mode, where it is connecting (never the password), whether
Postgres is reachable, and that the schema resolves to shopqc. With
storage_mode=sqlite (or no Supabase keys) it reports the local file. summary()
returns (ok, text) so both entry points share one implementation.
"""

import sys

from . import config


def summary():
    """Return (ok: bool, text: str) describing the configured connection. Never
    includes the password. Safe to print or show in a dialog."""
    lines = []
    cfg = config.load()
    mode = (cfg.get("storage_mode") or "sqlite").strip().lower()
    lines.append(f"storage_mode: {mode}")
    if mode != "supabase":
        lines.append(f"local SQLite database: {cfg['db_path']}")
        return True, "\n".join(lines)

    params = config.supabase_connection_params(cfg)
    if not params:
        lines.append("supabase selected but no connection keys are set; the app "
                     "would fall back to the local SQLite file. Fill the "
                     "supabase_db_* keys in config.json. See SUPABASE_SETUP.md.")
        return False, "\n".join(lines)

    if "dsn" in params:
        lines.append("connecting via supabase_db_url")
    else:
        lines.append(f"connecting to {params.get('user')}@{params.get('host')}:"
                     f"{params.get('port')}/{params.get('dbname')} "
                     f"sslmode={params.get('sslmode')}")

    try:
        from . import pg_client
    except Exception as e:
        lines.append(f"psycopg2 is not installed: {e}")
        return False, "\n".join(lines)

    client = pg_client.Psycopg2Client(params)
    if not client.is_alive():
        lines.append("NOT reachable. Check the host, credentials, SSL, and network.")
        return False, "\n".join(lines)
    schema = (client.execute("SELECT current_schema() AS s") or [{}])[0].get("s")
    n = (client.execute("SELECT count(*) AS n FROM projects") or [{}])[0].get("n")
    client.close()
    lines.append(f"OK: reachable, current_schema={schema}, projects rows={n}")
    if schema != "shopqc":
        lines.append("WARNING: search_path did not resolve to the shopqc schema.")
        return False, "\n".join(lines)
    return True, "\n".join(lines)


def main() -> int:
    ok, text = summary()
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
