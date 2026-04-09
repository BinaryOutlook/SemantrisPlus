from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from sqlalchemy import Boolean, DateTime, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from settings import Settings


class Base(DeclarativeBase):
    pass


class RunRecord(Base):
    __tablename__ = "run_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mode_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    pack_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    vocabulary_name: Mapped[str] = mapped_column(String(256), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    turns: Mapped[int] = mapped_column(Integer, nullable=False)
    elapsed_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    game_result: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    used_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


@dataclass(frozen=True)
class BestRunSummary:
    run_record_id: int
    score: int
    turns: int
    elapsed_seconds: int
    created_at_iso: str


@dataclass(frozen=True)
class RecordedRunSummary:
    run_record_id: int | None
    is_new_best: bool
    best_run: BestRunSummary | None


class RunStore(Protocol):
    def best_run_for(self, *, mode_id: str, pack_id: str) -> BestRunSummary | None:
        ...

    def record_completed_run(
        self,
        *,
        mode_id: str,
        pack_id: str,
        vocabulary_name: str,
        score: int,
        turns: int,
        elapsed_seconds: int,
        game_result: str,
        provider_label: str | None,
        used_fallback: bool,
    ) -> RecordedRunSummary:
        ...


class NullRunStore:
    def best_run_for(self, *, mode_id: str, pack_id: str) -> BestRunSummary | None:
        return None

    def record_completed_run(
        self,
        *,
        mode_id: str,
        pack_id: str,
        vocabulary_name: str,
        score: int,
        turns: int,
        elapsed_seconds: int,
        game_result: str,
        provider_label: str | None,
        used_fallback: bool,
    ) -> RecordedRunSummary:
        return RecordedRunSummary(
            run_record_id=None,
            is_new_best=False,
            best_run=None,
        )


def _best_run_ordering():
    return (
        RunRecord.score.desc(),
        RunRecord.elapsed_seconds.asc(),
        RunRecord.turns.asc(),
        RunRecord.id.asc(),
    )


def _to_best_run_summary(record: RunRecord | None) -> BestRunSummary | None:
    if record is None:
        return None
    created_at = record.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return BestRunSummary(
        run_record_id=record.id,
        score=record.score,
        turns=record.turns,
        elapsed_seconds=record.elapsed_seconds,
        created_at_iso=created_at.isoformat(),
    )


class SqlAlchemyRunStore:
    def __init__(self, database_url: str, base_dir: Path) -> None:
        if database_url.startswith("sqlite:///"):
            database_path = Path(database_url.removeprefix("sqlite:///"))
            if not database_path.is_absolute():
                database_path = base_dir / database_path
            database_path.parent.mkdir(parents=True, exist_ok=True)
            database_url = f"sqlite:///{database_path}"

        self._engine = create_engine(database_url, future=True)
        self._session_factory = sessionmaker(self._engine, expire_on_commit=False, future=True)
        Base.metadata.create_all(self._engine)

    def _open_session(self) -> Session:
        return self._session_factory()

    def best_run_for(self, *, mode_id: str, pack_id: str) -> BestRunSummary | None:
        with self._open_session() as session:
            statement = (
                select(RunRecord)
                .where(RunRecord.mode_id == mode_id, RunRecord.pack_id == pack_id)
                .order_by(*_best_run_ordering())
                .limit(1)
            )
            record = session.scalar(statement)
            return _to_best_run_summary(record)

    def record_completed_run(
        self,
        *,
        mode_id: str,
        pack_id: str,
        vocabulary_name: str,
        score: int,
        turns: int,
        elapsed_seconds: int,
        game_result: str,
        provider_label: str | None,
        used_fallback: bool,
    ) -> RecordedRunSummary:
        with self._open_session() as session:
            record = RunRecord(
                mode_id=mode_id,
                pack_id=pack_id,
                vocabulary_name=vocabulary_name,
                score=score,
                turns=turns,
                elapsed_seconds=max(0, elapsed_seconds),
                game_result=game_result,
                provider_label=provider_label,
                used_fallback=used_fallback,
            )
            session.add(record)
            session.commit()
            session.refresh(record)

            best_statement = (
                select(RunRecord)
                .where(RunRecord.mode_id == mode_id, RunRecord.pack_id == pack_id)
                .order_by(*_best_run_ordering())
                .limit(1)
            )
            best_record = session.scalar(best_statement)

            return RecordedRunSummary(
                run_record_id=record.id,
                is_new_best=best_record is not None and best_record.id == record.id,
                best_run=_to_best_run_summary(best_record),
            )


def build_run_store(settings: Settings) -> RunStore:
    if not settings.semantris_run_store_enabled:
        return NullRunStore()
    if settings.semantris_persistence_backend == "sqlite":
        return SqlAlchemyRunStore(
            database_url=settings.semantris_database_url,
            base_dir=settings.base_dir,
        )
    return NullRunStore()
