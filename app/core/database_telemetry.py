from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import event, text

try:
    from opentelemetry import metrics
except Exception:
    metrics = None


@dataclass(frozen=True)
class DatabaseTelemetryConfig:
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 1800
    slow_query_ms: float = 500.0


class DatabaseTelemetry:
    VERSION = "1.0"
    SCHEMA = "kemet.database_telemetry.v1"

    def __init__(self, config: DatabaseTelemetryConfig | None = None) -> None:
        self.config = config or DatabaseTelemetryConfig()
        self._installed = False
        self._engine = None
        self._query_started: dict[int, float] = {}
        self._meter = None
        self._queries = None
        self._query_errors = None
        self._query_duration = None
        self._pool_checkouts = None
        self._pool_checkins = None
        self._pool_invalidations = None
        if metrics is not None:
            try:
                self._meter = metrics.get_meter("kemet.database", self.VERSION)
                self._queries = self._meter.create_counter("kemet.db.queries", unit="{query}")
                self._query_errors = self._meter.create_counter("kemet.db.query.errors", unit="{error}")
                self._query_duration = self._meter.create_histogram("kemet.db.query.duration", unit="ms")
                self._pool_checkouts = self._meter.create_counter("kemet.db.pool.checkouts", unit="{checkout}")
                self._pool_checkins = self._meter.create_counter("kemet.db.pool.checkins", unit="{checkin}")
                self._pool_invalidations = self._meter.create_counter("kemet.db.pool.invalidations", unit="{invalidation}")
            except Exception:
                self._meter = None

    @property
    def installed(self) -> bool:
        return self._installed

    def install(self, engine: Any) -> None:
        if self._installed and self._engine is engine:
            return
        self._engine = engine
        event.listen(engine, "before_cursor_execute", self._before_cursor_execute)
        event.listen(engine, "after_cursor_execute", self._after_cursor_execute)
        event.listen(engine, "handle_error", self._handle_error)
        event.listen(engine, "checkout", self._checkout)
        event.listen(engine, "checkin", self._checkin)
        event.listen(engine, "invalidate", self._invalidate)
        self._installed = True

    def _before_cursor_execute(self, conn, cursor, statement, parameters, context, executemany):
        self._query_started[id(context)] = time.perf_counter()

    def _after_cursor_execute(self, conn, cursor, statement, parameters, context, executemany):
        started = self._query_started.pop(id(context), None)
        duration_ms = (time.perf_counter() - started) * 1000 if started else 0.0
        attrs = {"db.system": conn.dialect.name}
        if self._queries:
            self._queries.add(1, attrs)
        if self._query_duration:
            self._query_duration.record(duration_ms, attrs)

    def _handle_error(self, exception_context):
        if self._query_errors:
            self._query_errors.add(1, {"db.system": exception_context.dialect.name})
        return None

    def _checkout(self, dbapi_connection, connection_record, connection_proxy):
        if self._pool_checkouts:
            self._pool_checkouts.add(1)

    def _checkin(self, dbapi_connection, connection_record):
        if self._pool_checkins:
            self._pool_checkins.add(1)

    def _invalidate(self, dbapi_connection, connection_record, exception):
        if self._pool_invalidations:
            self._pool_invalidations.add(1)

    def pool_snapshot(self) -> dict[str, Any]:
        if self._engine is None:
            return {"available": False, "reason": "not_installed"}
        pool = self._engine.pool
        result: dict[str, Any] = {
            "available": True,
            "pool_class": type(pool).__name__,
            "checked_out": None,
            "checked_in": None,
            "size": None,
            "overflow": None,
        }
        for name in ("checkedout", "checkedin", "size", "overflow"):
            method = getattr(pool, name, None)
            if callable(method):
                try:
                    result[name.replace("checkedout", "checked_out").replace("checkedin", "checked_in")] = int(method())
                except Exception:
                    pass
        return result

    def postgres_snapshot(self) -> dict[str, Any]:
        if self._engine is None:
            return {"available": False, "reason": "not_installed"}
        if not self._engine.dialect.name.startswith("postgres"):
            return {
                "available": False,
                "database": self._engine.dialect.name,
                "reason": "postgresql_required",
            }
        report: dict[str, Any] = {
            "available": True,
            "database": "postgresql",
            "connection_ok": False,
            "server_version_major": None,
            "max_connections": None,
            "active_connections": None,
            "waiting_locks": None,
            "transactions_committed": None,
            "transactions_rolled_back": None,
            "cache_hit_ratio": None,
            "pg_stat_statements": False,
            "track_activities": None,
            "error": None,
        }
        try:
            with self._engine.connect() as conn:
                version = conn.execute(text("SELECT current_setting('server_version')")).scalar_one()
                max_connections = conn.execute(text("SHOW max_connections")).scalar_one()
                active = conn.execute(text("SELECT count(*) FROM pg_stat_activity")).scalar_one()
                waiting = conn.execute(text("SELECT count(*) FROM pg_locks WHERE NOT granted")).scalar_one()
                stats = conn.execute(text("""
                    SELECT xact_commit, xact_rollback, blks_hit, blks_read
                    FROM pg_stat_database
                    WHERE datname = current_database()
                """)).mappings().one()
                track = conn.execute(text("SELECT current_setting('track_activities')")).scalar_one()
                extension = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
                    )
                """)).scalar_one()
            reads = int(stats["blks_read"] or 0)
            hits = int(stats["blks_hit"] or 0)
            report.update({
                "connection_ok": True,
                "server_version_major": str(version).split(".")[0],
                "max_connections": int(max_connections),
                "active_connections": int(active),
                "waiting_locks": int(waiting),
                "transactions_committed": int(stats["xact_commit"] or 0),
                "transactions_rolled_back": int(stats["xact_rollback"] or 0),
                "cache_hit_ratio": round(hits / (hits + reads), 6) if hits + reads else None,
                "pg_stat_statements": bool(extension),
                "track_activities": str(track),
            })
        except Exception as exc:
            report["error"] = type(exc).__name__
        return report

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "pool": self.pool_snapshot(),
            "postgresql": self.postgres_snapshot(),
            "read_only": True,
            "secret_exposed": False,
        }


database_telemetry = DatabaseTelemetry()
