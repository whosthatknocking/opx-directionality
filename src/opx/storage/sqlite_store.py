from __future__ import annotations
# pylint: disable=line-too-long

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from opx.canonical import apply_canonical_selection
from opx.models import BatchRunResult, SignalResult, SignalRunRecord
from opx.storage.base import SignalStore


SCHEMA = """
CREATE TABLE IF NOT EXISTS signal_runs (
    run_id TEXT PRIMARY KEY,
    run_timestamp TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    signal_time_et TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    config_version TEXT NOT NULL,
    config_fingerprint TEXT NOT NULL,
    tickers_json TEXT NOT NULL,
    signal_time_reached INTEGER NOT NULL,
    completion_rate REAL NOT NULL,
    validation_state TEXT NOT NULL,
    validation_issues_json TEXT NOT NULL,
    selection_status TEXT NOT NULL,
    selection_reason TEXT NOT NULL,
    log_path TEXT
);

CREATE TABLE IF NOT EXISTS ticker_signals (
    run_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    signal_time TEXT NOT NULL,
    signal_price REAL,
    status TEXT NOT NULL,
    reason TEXT,
    bias TEXT,
    confidence INTEGER,
    regime TEXT,
    option_posture TEXT,
    raw_score INTEGER,
    validation_state TEXT NOT NULL,
    validation_issues_json TEXT NOT NULL,
    factor_summary_json TEXT,
    features_json TEXT,
    realized_close REAL,
    realized_return_pct REAL,
    realized_outcome TEXT,
    directional_hit INTEGER,
    PRIMARY KEY (run_id, ticker),
    FOREIGN KEY (run_id) REFERENCES signal_runs(run_id)
);
"""


class SQLiteSignalStore(SignalStore):
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)
            self._ensure_outcome_columns(conn)

    def save_batch(self, batch: BatchRunResult) -> None:
        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            self._upsert_batch(conn, batch)
            selected = apply_canonical_selection(self._load_batches(conn))
            for selected_batch in selected:
                self._update_run_selection(conn, selected_batch)
            conn.commit()

    def load_batches(self, limit: int | None = None) -> list[BatchRunResult]:
        with sqlite3.connect(self.db_path) as conn:
            batches = self._load_batches(conn)
        if limit is not None:
            return batches[-limit:]
        return batches

    def _upsert_batch(self, conn: sqlite3.Connection, batch: BatchRunResult) -> None:
        conn.execute(
            """
            INSERT OR REPLACE INTO signal_runs
            (run_id, run_timestamp, trade_date, signal_time_et, provider_name, engine_version, config_version,
             config_fingerprint, tickers_json, signal_time_reached, completion_rate, validation_state,
             validation_issues_json, selection_status, selection_reason, log_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch.run.run_id,
                batch.run.run_timestamp.isoformat(),
                batch.run.trade_date,
                batch.run.signal_time_et,
                batch.run.provider_name,
                batch.run.engine_version,
                batch.run.config_version,
                batch.run.config_fingerprint,
                json.dumps(batch.run.tickers),
                int(batch.run.signal_time_reached),
                batch.run.completion_rate,
                batch.run.validation_state,
                json.dumps(batch.run.validation_issues),
                batch.run.selection_status,
                batch.run.selection_reason,
                batch.run.log_path,
            ),
        )
        for signal in batch.signals:
            conn.execute(
                """
                INSERT OR REPLACE INTO ticker_signals
                (run_id, ticker, signal_time, signal_price, status, reason, bias, confidence, regime, option_posture,
                 raw_score, validation_state, validation_issues_json, factor_summary_json, features_json, realized_close,
                 realized_return_pct, realized_outcome, directional_hit)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch.run.run_id,
                    signal.ticker,
                    signal.signal_time.isoformat(),
                    signal.signal_price,
                    signal.status,
                    signal.reason,
                    signal.bias,
                    signal.confidence,
                    signal.regime,
                    signal.option_posture,
                    signal.raw_score,
                    signal.validation_state,
                    json.dumps(signal.validation_issues),
                    json.dumps(signal.factor_summary),
                    json.dumps(signal.factors),
                    signal.realized_close,
                    signal.realized_return_pct,
                    signal.realized_outcome,
                    None if signal.directional_hit is None else int(signal.directional_hit),
                ),
            )

    def _update_run_selection(self, conn: sqlite3.Connection, batch: BatchRunResult) -> None:
        conn.execute(
            """
            UPDATE signal_runs
            SET completion_rate = ?, validation_state = ?, validation_issues_json = ?, selection_status = ?, selection_reason = ?
            WHERE run_id = ?
            """,
            (
                batch.run.completion_rate,
                batch.run.validation_state,
                json.dumps(batch.run.validation_issues),
                batch.run.selection_status,
                batch.run.selection_reason,
                batch.run.run_id,
            ),
        )

    def _load_batches(self, conn: sqlite3.Connection) -> list[BatchRunResult]:
        runs = conn.execute(
            """
            SELECT run_id, run_timestamp, trade_date, signal_time_et, provider_name, engine_version, config_version,
                   config_fingerprint, tickers_json, signal_time_reached, completion_rate, validation_state,
                   validation_issues_json, selection_status, selection_reason, log_path
            FROM signal_runs
            ORDER BY run_timestamp
            """
        ).fetchall()

        batches = []
        for row in runs:
            run_id = row[0]
            signals = conn.execute(
                """
                SELECT ticker, signal_time, signal_price, status, reason, bias, confidence, regime, option_posture,
                       raw_score, validation_state, validation_issues_json, factor_summary_json, features_json,
                       realized_close, realized_return_pct, realized_outcome, directional_hit
                FROM ticker_signals
                WHERE run_id = ?
                ORDER BY ticker
                """,
                (run_id,),
            ).fetchall()
            run = SignalRunRecord(
                run_id=run_id,
                run_timestamp=datetime.fromisoformat(row[1]),
                trade_date=row[2],
                signal_time_et=row[3],
                provider_name=row[4],
                engine_version=row[5],
                config_version=row[6],
                config_fingerprint=row[7],
                tickers=json.loads(row[8]),
                signal_time_reached=bool(row[9]),
                completion_rate=float(row[10]),
                validation_state=row[11],
                validation_issues=json.loads(row[12]),
                selection_status=row[13],
                selection_reason=row[14],
                log_path=row[15],
            )
            batches.append(
                BatchRunResult(
                    run=run,
                    signals=[
                        SignalResult(
                            ticker=signal[0],
                            signal_time=datetime.fromisoformat(signal[1]),
                            signal_price=signal[2],
                            status=signal[3],
                            reason=signal[4],
                            bias=signal[5],
                            confidence=int(signal[6]),
                            regime=signal[7],
                            option_posture=signal[8],
                            raw_score=int(signal[9]),
                            validation_state=signal[10],
                            validation_issues=json.loads(signal[11]),
                            factor_summary=json.loads(signal[12]),
                            factors=json.loads(signal[13]),
                            realized_close=signal[14],
                            realized_return_pct=signal[15],
                            realized_outcome=signal[16],
                            directional_hit=None if signal[17] is None else bool(signal[17]),
                        )
                        for signal in signals
                    ],
                )
            )
        return batches

    def _ensure_outcome_columns(self, conn: sqlite3.Connection) -> None:
        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(ticker_signals)").fetchall()
        }
        additions = {
            "signal_price": "ALTER TABLE ticker_signals ADD COLUMN signal_price REAL",
            "realized_close": "ALTER TABLE ticker_signals ADD COLUMN realized_close REAL",
            "realized_return_pct": "ALTER TABLE ticker_signals ADD COLUMN realized_return_pct REAL",
            "realized_outcome": "ALTER TABLE ticker_signals ADD COLUMN realized_outcome TEXT",
            "directional_hit": "ALTER TABLE ticker_signals ADD COLUMN directional_hit INTEGER",
        }
        for column, statement in additions.items():
            if column not in existing:
                conn.execute(statement)
