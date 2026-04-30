"""Feedback Service — SQLite-backed reinforcement learning loop.

Tracks which playbook recommendations users accepted/rejected to
provide acceptance rates and improve future suggestions.

Database: data/feedback.db — auto-creates, no migrations.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.models.feedback import ContextSnapshot, FeedbackRecord, PlaybookStats

logger = logging.getLogger(__name__)

DB_PATH = Path("data/feedback.db")


class FeedbackService:
    """SQLite-backed feedback storage for the playbook system."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self._db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a SQLite connection with row factory."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS feedback_records (
                    feedback_id TEXT PRIMARY KEY,
                    execution_id TEXT NOT NULL UNIQUE,
                    playbook_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    comment TEXT,
                    context_node_id TEXT,
                    context_risk_score REAL,
                    context_days_buffer INTEGER,
                    context_shipment_count INTEGER,
                    context_financial_exposure REAL
                );

                CREATE TABLE IF NOT EXISTS playbook_stats (
                    playbook_id TEXT PRIMARY KEY,
                    total_executions INTEGER DEFAULT 0,
                    accepted INTEGER DEFAULT 0,
                    rejected INTEGER DEFAULT 0,
                    partial INTEGER DEFAULT 0,
                    last_triggered TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_feedback_playbook
                    ON feedback_records(playbook_id);
                CREATE INDEX IF NOT EXISTS idx_feedback_execution
                    ON feedback_records(execution_id);
            """)
            conn.commit()
            logger.info(f"Feedback DB initialized at {self._db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize feedback DB: {e}")
        finally:
            conn.close()

    # -------------------------------------------------------------------
    # Record feedback (with 409 duplicate check)
    # -------------------------------------------------------------------

    def record_feedback(
        self,
        execution_id: str,
        playbook_id: str,
        decision: str,
        user_id: str,
        comment: Optional[str] = None,
        context: Optional[ContextSnapshot] = None,
    ) -> FeedbackRecord | None:
        """Store a feedback decision. Returns None if duplicate (409 case).

        🔴 Critical: execution_id is UNIQUE — prevents double-click corruption.
        """
        conn = self._get_conn()
        try:
            # Check for duplicate
            existing = conn.execute(
                "SELECT feedback_id FROM feedback_records WHERE execution_id = ?",
                (execution_id,),
            ).fetchone()
            if existing:
                logger.warning(f"Duplicate feedback for execution {execution_id}")
                return None  # Caller should return 409

            feedback_id = f"fb_{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc).isoformat()

            ctx = context or ContextSnapshot(node_id="unknown", risk_score=0.0)

            conn.execute(
                """INSERT INTO feedback_records
                   (feedback_id, execution_id, playbook_id, decision, user_id,
                    timestamp, comment, context_node_id, context_risk_score,
                    context_days_buffer, context_shipment_count, context_financial_exposure)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    feedback_id,
                    execution_id,
                    playbook_id,
                    decision,
                    user_id,
                    now,
                    comment,
                    ctx.node_id,
                    ctx.risk_score,
                    ctx.days_buffer,
                    ctx.active_shipment_count,
                    ctx.financial_exposure_usd,
                ),
            )

            # Update aggregated stats
            self._update_stats(conn, playbook_id, decision)
            conn.commit()

            record = FeedbackRecord(
                feedback_id=feedback_id,
                execution_id=execution_id,
                playbook_id=playbook_id,
                decision=decision,
                user_id=user_id,
                timestamp=datetime.fromisoformat(now),
                comment=comment,
                context_snapshot=ctx,
            )
            logger.info(
                f"Feedback recorded: {decision} for execution {execution_id} "
                f"(playbook: {playbook_id})"
            )
            return record

        except sqlite3.IntegrityError:
            logger.warning(f"Duplicate feedback for execution {execution_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to record feedback: {e}", exc_info=True)
            return None
        finally:
            conn.close()

    def _update_stats(self, conn: sqlite3.Connection, playbook_id: str, decision: str) -> None:
        """Update aggregated stats for a playbook."""
        now = datetime.now(timezone.utc).isoformat()

        # Upsert stats row
        existing = conn.execute(
            "SELECT playbook_id FROM playbook_stats WHERE playbook_id = ?",
            (playbook_id,),
        ).fetchone()

        if existing:
            conn.execute(
                f"""UPDATE playbook_stats
                    SET total_executions = total_executions + 1,
                        {decision} = {decision} + 1,
                        last_triggered = ?
                    WHERE playbook_id = ?""",
                (now, playbook_id),
            )
        else:
            cols = {"accepted": 0, "rejected": 0, "partial": 0}
            cols[decision] = 1
            conn.execute(
                """INSERT INTO playbook_stats
                   (playbook_id, total_executions, accepted, rejected, partial, last_triggered)
                   VALUES (?, 1, ?, ?, ?, ?)""",
                (playbook_id, cols["accepted"], cols["rejected"], cols["partial"], now),
            )

    # -------------------------------------------------------------------
    # Track playbook triggers (separate from user feedback)
    # -------------------------------------------------------------------

    def record_trigger(self, playbook_id: str) -> None:
        """Record that a playbook was triggered (for stats count)."""
        conn = self._get_conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            existing = conn.execute(
                "SELECT playbook_id FROM playbook_stats WHERE playbook_id = ?",
                (playbook_id,),
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE playbook_stats
                        SET total_executions = total_executions + 1,
                            last_triggered = ?
                        WHERE playbook_id = ?""",
                    (now, playbook_id),
                )
            else:
                conn.execute(
                    """INSERT INTO playbook_stats
                       (playbook_id, total_executions, accepted, rejected, partial, last_triggered)
                       VALUES (?, 1, 0, 0, 0, ?)""",
                    (playbook_id, now),
                )
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to record trigger: {e}")
        finally:
            conn.close()

    # -------------------------------------------------------------------
    # Query stats
    # -------------------------------------------------------------------

    def get_playbook_stats(self, playbook_id: str) -> Optional[PlaybookStats]:
        """Get stats for a single playbook."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM playbook_stats WHERE playbook_id = ?",
                (playbook_id,),
            ).fetchone()
            if row:
                return self._row_to_stats(row)
            return None
        finally:
            conn.close()

    def get_all_stats(self) -> list[PlaybookStats]:
        """Get stats for all playbooks."""
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM playbook_stats").fetchall()
            return [self._row_to_stats(row) for row in rows]
        finally:
            conn.close()

    def get_feedback_history(self, limit: int = 50) -> list[FeedbackRecord]:
        """Get recent feedback records."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM feedback_records ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_feedback(row) for row in rows]
        finally:
            conn.close()

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------

    @staticmethod
    def _row_to_stats(row: sqlite3.Row) -> PlaybookStats:
        total = row["total_executions"] or 0
        accepted = row["accepted"] or 0
        rate = (accepted / total * 100) if total > 0 else 0.0
        last = row["last_triggered"]

        return PlaybookStats(
            playbook_id=row["playbook_id"],
            total_executions=total,
            accepted=accepted,
            rejected=row["rejected"] or 0,
            partial=row["partial"] or 0,
            acceptance_rate=round(rate, 1),
            last_triggered=datetime.fromisoformat(last) if last else None,
        )

    @staticmethod
    def _row_to_feedback(row: sqlite3.Row) -> FeedbackRecord:
        return FeedbackRecord(
            feedback_id=row["feedback_id"],
            execution_id=row["execution_id"],
            playbook_id=row["playbook_id"],
            decision=row["decision"],
            user_id=row["user_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            comment=row["comment"],
            context_snapshot=ContextSnapshot(
                node_id=row["context_node_id"] or "unknown",
                risk_score=row["context_risk_score"] or 0.0,
                days_buffer=row["context_days_buffer"],
                active_shipment_count=row["context_shipment_count"] or 0,
                financial_exposure_usd=row["context_financial_exposure"],
            ),
        )
