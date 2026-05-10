from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ainewsagent.domain.models import Item, ScoredItem


@dataclass(frozen=True)
class BriefingRecord:
    id: int
    date: str
    content: str
    report_path: str
    created_at: str
    status: str
    failures: list[str]


@dataclass(frozen=True)
class RunRecord:
    id: int
    started_at: str
    finished_at: str
    status: str
    report_path: str
    failures: list[str]


@dataclass(frozen=True)
class BriefingItemRecord:
    item: Item
    position: int
    rule_score: float
    llm_score: float
    total_score: float
    topic: str
    reason: str
    importance: str
    audience: str
    tags: list[str]


@dataclass(frozen=True)
class TrendRecord:
    topic: str
    count: int
    days: int
    latest_date: str


class AgentDatabase:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    report_path TEXT NOT NULL,
                    failures_json TEXT NOT NULL DEFAULT '[]'
                );

                CREATE TABLE IF NOT EXISTS briefings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    content TEXT NOT NULL,
                    report_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    failures_json TEXT NOT NULL DEFAULT '[]',
                    FOREIGN KEY(run_id) REFERENCES runs(id)
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_briefings_date ON briefings(date);

                CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    text TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    authors_json TEXT NOT NULL,
                    categories_json TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS briefing_items (
                    briefing_id INTEGER NOT NULL,
                    item_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    rule_score REAL NOT NULL DEFAULT 0,
                    llm_score REAL NOT NULL DEFAULT 0,
                    total_score REAL NOT NULL DEFAULT 0,
                    topic TEXT NOT NULL DEFAULT '',
                    reason TEXT NOT NULL DEFAULT '',
                    importance TEXT NOT NULL DEFAULT '值得扫读',
                    audience TEXT NOT NULL DEFAULT '',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    PRIMARY KEY (briefing_id, item_id),
                    FOREIGN KEY(briefing_id) REFERENCES briefings(id),
                    FOREIGN KEY(item_id) REFERENCES items(id)
                );
                """
            )
            self._ensure_column(conn, "briefing_items", "rule_score", "REAL NOT NULL DEFAULT 0")
            self._ensure_column(conn, "briefing_items", "llm_score", "REAL NOT NULL DEFAULT 0")
            self._ensure_column(conn, "briefing_items", "total_score", "REAL NOT NULL DEFAULT 0")
            self._ensure_column(conn, "briefing_items", "topic", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "briefing_items", "reason", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "briefing_items", "importance", "TEXT NOT NULL DEFAULT '值得扫读'")
            self._ensure_column(conn, "briefing_items", "audience", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "briefing_items", "tags_json", "TEXT NOT NULL DEFAULT '[]'")

    def save_run(
        self,
        *,
        started_at: datetime,
        finished_at: datetime,
        status: str,
        report_path: str,
        date: str,
        content: str,
        scored_items: list[ScoredItem],
        failures: list[str],
    ) -> int:
        failures_json = json.dumps(failures, ensure_ascii=False)
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO runs (started_at, finished_at, status, report_path, failures_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (started_at.isoformat(), finished_at.isoformat(), status, report_path, failures_json),
            )
            run_id = int(cursor.lastrowid)
            conn.execute(
                """
                INSERT INTO briefings (run_id, date, content, report_path, created_at, status, failures_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    run_id=excluded.run_id,
                    content=excluded.content,
                    report_path=excluded.report_path,
                    created_at=excluded.created_at,
                    status=excluded.status,
                    failures_json=excluded.failures_json
                """,
                (run_id, date, content, report_path, finished_at.isoformat(), status, failures_json),
            )
            briefing_id = self._briefing_id(conn, date)
            conn.execute("DELETE FROM briefing_items WHERE briefing_id = ?", (briefing_id,))
            for position, scored_item in enumerate(scored_items, start=1):
                item = scored_item.item
                self._upsert_item(conn, item, finished_at)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO briefing_items (
                        briefing_id, item_id, position, rule_score, llm_score, total_score,
                        topic, reason, importance, audience, tags_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        briefing_id,
                        item.id,
                        position,
                        scored_item.rule_score,
                        scored_item.llm_score,
                        scored_item.total_score,
                        scored_item.topic,
                        scored_item.reason,
                        scored_item.importance,
                        scored_item.audience,
                        json.dumps(scored_item.tags, ensure_ascii=False),
                    ),
                )
            return run_id

    def save_error_run(
        self,
        *,
        started_at: datetime,
        finished_at: datetime,
        status: str,
        failures: list[str],
    ) -> int:
        failures_json = json.dumps(failures, ensure_ascii=False)
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO runs (started_at, finished_at, status, report_path, failures_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (started_at.isoformat(), finished_at.isoformat(), status, "", failures_json),
            )
            return int(cursor.lastrowid)

    def latest_briefing(self) -> BriefingRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, date, content, report_path, created_at, status, failures_json
                FROM briefings
                ORDER BY date DESC
                LIMIT 1
                """
            ).fetchone()
        return _briefing_from_row(row) if row else None

    def briefing_by_date(self, date: str) -> BriefingRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, date, content, report_path, created_at, status, failures_json
                FROM briefings
                WHERE date = ?
                """,
                (date,),
            ).fetchone()
        return _briefing_from_row(row) if row else None

    def recent_briefings(self, limit: int = 30) -> list[BriefingRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, date, content, report_path, created_at, status, failures_json
                FROM briefings
                ORDER BY date DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_briefing_from_row(row) for row in rows]

    def recent_runs(self, limit: int = 20) -> list[RunRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, started_at, finished_at, status, report_path, failures_json
                FROM runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            RunRecord(
                id=int(row["id"]),
                started_at=str(row["started_at"]),
                finished_at=str(row["finished_at"]),
                status=str(row["status"]),
                report_path=str(row["report_path"]),
                failures=json.loads(row["failures_json"]),
            )
            for row in rows
        ]

    def items_for_briefing(self, briefing_id: int) -> list[BriefingItemRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    i.*,
                    bi.position,
                    bi.rule_score,
                    bi.llm_score,
                    bi.total_score,
                    bi.topic,
                    bi.reason,
                    bi.importance,
                    bi.audience,
                    bi.tags_json
                FROM items i
                JOIN briefing_items bi ON bi.item_id = i.id
                WHERE bi.briefing_id = ?
                ORDER BY bi.position ASC
                """,
                (briefing_id,),
            ).fetchall()
        return [_briefing_item_from_row(row) for row in rows]

    def topic_trends(self, *, days: int = 7, limit: int = 10) -> list[TrendRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    bi.topic AS topic,
                    COUNT(*) AS count,
                    COUNT(DISTINCT b.date) AS days,
                    MAX(b.date) AS latest_date
                FROM briefing_items bi
                JOIN briefings b ON b.id = bi.briefing_id
                WHERE b.date >= date('now', ?)
                  AND bi.topic != ''
                GROUP BY bi.topic
                ORDER BY count DESC, days DESC, latest_date DESC
                LIMIT ?
                """,
                (f"-{days - 1} days", limit),
            ).fetchall()
        return [
            TrendRecord(
                topic=str(row["topic"]),
                count=int(row["count"]),
                days=int(row["days"]),
                latest_date=str(row["latest_date"]),
            )
            for row in rows
        ]

    def search_briefing_items(
        self,
        *,
        query: str = "",
        source: str = "",
        topic: str = "",
        importance: str = "",
        audience: str = "",
        limit: int = 100,
    ) -> list[BriefingItemRecord]:
        clauses = ["1 = 1"]
        params: list[str | int] = []
        if query:
            clauses.append("(i.title LIKE ? OR i.text LIKE ? OR bi.reason LIKE ? OR bi.topic LIKE ?)")
            like = f"%{query}%"
            params.extend([like, like, like, like])
        if source:
            clauses.append("i.source = ?")
            params.append(source)
        if topic:
            clauses.append("bi.topic = ?")
            params.append(topic)
        if importance:
            clauses.append("bi.importance = ?")
            params.append(importance)
        if audience:
            clauses.append("bi.audience = ?")
            params.append(audience)
        params.append(limit)
        sql = f"""
            SELECT
                i.*,
                bi.position,
                bi.rule_score,
                bi.llm_score,
                bi.total_score,
                bi.topic,
                bi.reason,
                bi.importance,
                bi.audience,
                bi.tags_json
            FROM items i
            JOIN briefing_items bi ON bi.item_id = i.id
            JOIN briefings b ON b.id = bi.briefing_id
            WHERE {' AND '.join(clauses)}
            ORDER BY b.date DESC, bi.total_score DESC
            LIMIT ?
        """
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_briefing_item_from_row(row) for row in rows]

    def filter_options(self) -> dict[str, list[str]]:
        with self._connect() as conn:
            topics = _single_column(conn, "SELECT DISTINCT topic FROM briefing_items WHERE topic != '' ORDER BY topic")
            importances = _single_column(
                conn,
                "SELECT DISTINCT importance FROM briefing_items WHERE importance != '' ORDER BY importance",
            )
            audiences = _single_column(conn, "SELECT DISTINCT audience FROM briefing_items WHERE audience != '' ORDER BY audience")
        return {"topics": topics, "importances": importances, "audiences": audiences}

    def recent_items(self, limit: int = 100) -> list[Item]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM items
                ORDER BY last_seen_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_item_from_row(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _briefing_id(self, conn: sqlite3.Connection, date: str) -> int:
        row = conn.execute("SELECT id FROM briefings WHERE date = ?", (date,)).fetchone()
        if row is None:
            raise RuntimeError(f"Briefing for {date} was not saved")
        return int(row["id"])

    def _upsert_item(self, conn: sqlite3.Connection, item: Item, seen_at: datetime) -> None:
        conn.execute(
            """
            INSERT INTO items (
                id, source, title, url, text, published_at,
                authors_json, categories_json, metrics_json, last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                source=excluded.source,
                title=excluded.title,
                url=excluded.url,
                text=excluded.text,
                published_at=excluded.published_at,
                authors_json=excluded.authors_json,
                categories_json=excluded.categories_json,
                metrics_json=excluded.metrics_json,
                last_seen_at=excluded.last_seen_at
            """,
            (
                item.id,
                item.source.value,
                item.title,
                item.url,
                item.text,
                item.published_at.isoformat(),
                json.dumps(item.authors, ensure_ascii=False),
                json.dumps(item.categories, ensure_ascii=False),
                json.dumps(item.metrics, ensure_ascii=False),
                seen_at.isoformat(),
            ),
        )


def _briefing_from_row(row: sqlite3.Row) -> BriefingRecord:
    return BriefingRecord(
        id=int(row["id"]),
        date=str(row["date"]),
        content=str(row["content"]),
        report_path=str(row["report_path"]),
        created_at=str(row["created_at"]),
        status=str(row["status"]),
        failures=json.loads(row["failures_json"]),
    )


def _item_from_row(row: sqlite3.Row) -> Item:
    from ainewsagent.domain.models import Source

    return Item(
        id=str(row["id"]),
        source=Source(str(row["source"])),
        title=str(row["title"]),
        url=str(row["url"]),
        text=str(row["text"]),
        published_at=datetime.fromisoformat(str(row["published_at"])),
        authors=json.loads(row["authors_json"]),
        categories=json.loads(row["categories_json"]),
        metrics=json.loads(row["metrics_json"]),
    )


def _briefing_item_from_row(row: sqlite3.Row) -> BriefingItemRecord:
    return BriefingItemRecord(
        item=_item_from_row(row),
        position=int(row["position"]),
        rule_score=float(row["rule_score"]),
        llm_score=float(row["llm_score"]),
        total_score=float(row["total_score"]),
        topic=str(row["topic"]),
        reason=str(row["reason"]),
        importance=str(row["importance"]),
        audience=str(row["audience"]),
        tags=json.loads(row["tags_json"]),
    )


def _single_column(conn: sqlite3.Connection, sql: str) -> list[str]:
    return [str(row[0]) for row in conn.execute(sql).fetchall()]
