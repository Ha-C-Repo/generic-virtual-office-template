"""Config-driven Supabase credentials with environment-variable fallback (Phase A1).

No live connection is made. This checks only the credential resolver and the
storage_mode default. Credentials live in gitignored config.json on each host;
environment variables override at runtime."""

from shopqc import config

ENV_KEYS = ["SHOPQC_DB_URL", "SHOPQC_DB_HOST", "SHOPQC_DB_PORT",
            "SHOPQC_DB_NAME", "SHOPQC_DB_USER", "SHOPQC_DB_PASSWORD"]


def _clear_env(monkeypatch):
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)


def test_storage_mode_default_is_sqlite():
    assert config.DEFAULTS["storage_mode"] == "sqlite"


def test_supabase_params_none_when_unconfigured(monkeypatch):
    _clear_env(monkeypatch)
    assert config.supabase_connection_params(dict(config.DEFAULTS)) is None


def test_supabase_params_from_url(monkeypatch):
    _clear_env(monkeypatch)
    cfg = dict(config.DEFAULTS)
    cfg["supabase_db_url"] = "postgresql://u:p@host:5432/db"
    assert config.supabase_connection_params(cfg) == {
        "dsn": "postgresql://u:p@host:5432/db"}


def test_supabase_params_from_split_fields(monkeypatch):
    _clear_env(monkeypatch)
    cfg = dict(config.DEFAULTS)
    cfg.update({"supabase_db_host": "db.example.co", "supabase_db_name": "qc",
                "supabase_db_user": "shopqc_app", "supabase_db_password": "secret",
                "supabase_db_port": "6543"})
    assert config.supabase_connection_params(cfg) == {
        "host": "db.example.co", "port": "6543", "dbname": "qc",
        "user": "shopqc_app", "password": "secret", "sslmode": "require"}


def test_supabase_params_env_overrides_config(monkeypatch):
    _clear_env(monkeypatch)
    cfg = dict(config.DEFAULTS)
    cfg["supabase_db_host"] = "config-host"
    monkeypatch.setenv("SHOPQC_DB_HOST", "env-host")
    monkeypatch.setenv("SHOPQC_DB_USER", "env-user")
    params = config.supabase_connection_params(cfg)
    assert params["host"] == "env-host"
    assert params["user"] == "env-user"


def test_supabase_params_url_env_used_when_config_blank(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("SHOPQC_DB_URL", "postgresql://env/db")
    assert config.supabase_connection_params(dict(config.DEFAULTS)) == {
        "dsn": "postgresql://env/db"}


def test_password_not_stripped(monkeypatch):
    # Passwords may legitimately contain spaces; the resolver must not mangle them.
    _clear_env(monkeypatch)
    cfg = dict(config.DEFAULTS)
    cfg.update({"supabase_db_host": "h", "supabase_db_password": "  spaced  "})
    assert config.supabase_connection_params(cfg)["password"] == "  spaced  "


def test_sslmode_defaults_to_require(monkeypatch):
    _clear_env(monkeypatch)
    cfg = dict(config.DEFAULTS)
    cfg["supabase_db_host"] = "h"
    assert config.supabase_connection_params(cfg)["sslmode"] == "require"


def test_selftest_sqlite_mode(monkeypatch, tmp_path, capsys):
    from shopqc import selftest, config as cfgmod
    monkeypatch.setattr(cfgmod, "load",
                        lambda: {"storage_mode": "sqlite",
                                 "db_path": str(tmp_path / "x.db")})
    assert selftest.main() == 0
    assert "storage_mode: sqlite" in capsys.readouterr().out


def test_selftest_supabase_without_keys(monkeypatch):
    from shopqc import selftest, config as cfgmod
    _clear_env(monkeypatch)
    monkeypatch.setattr(cfgmod, "load",
                        lambda: dict(cfgmod.DEFAULTS, storage_mode="supabase"))
    assert selftest.main() == 1   # no keys: reports the sqlite fallback, exit 1
