"""Database models and connection management."""

from __future__ import annotations

from datetime import datetime
from typing import AsyncGenerator, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from db.config import get_database_url, get_database_url_sync


class Base(DeclarativeBase):
    pass


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    signal_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # problem_statement, complaint, unmet_need, repeated_pattern
    signal_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    ideas: Mapped[list["Idea"]] = relationship(
        "Idea", secondary="idea_signals", back_populates="signals"
    )
    outgoing_relations: Mapped[list["SignalRelation"]] = relationship(
        "SignalRelation",
        foreign_keys="SignalRelation.from_signal_id",
        back_populates="from_signal",
    )
    incoming_relations: Mapped[list["SignalRelation"]] = relationship(
        "SignalRelation",
        foreign_keys="SignalRelation.to_signal_id",
        back_populates="to_signal",
    )


class Idea(Base):
    __tablename__ = "ideas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    problem: Mapped[str] = mapped_column(Text, nullable=False)
    target_user: Mapped[str] = mapped_column(String(500), nullable=False)
    solution: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="new", nullable=False
    )  # new, analysed, enriched, critiqued, finalized
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_crossed_out: Mapped[bool] = mapped_column(Boolean, default=False)
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False)
    merged_into_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ideas.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    signals: Mapped[list["Signal"]] = relationship(
        "Signal", secondary="idea_signals", back_populates="ideas"
    )
    analysis: Mapped[Optional["Analysis"]] = relationship(
        "Analysis", back_populates="idea", uselist=False
    )
    enrichment: Mapped[Optional["Enrichment"]] = relationship(
        "Enrichment", back_populates="idea", uselist=False
    )
    critique: Mapped[Optional["Critique"]] = relationship(
        "Critique", back_populates="idea", uselist=False
    )
    embedding: Mapped[Optional["IdeaEmbedding"]] = relationship(
        "IdeaEmbedding", back_populates="idea", uselist=False
    )
    outgoing_relations: Mapped[list["IdeaRelation"]] = relationship(
        "IdeaRelation",
        foreign_keys="IdeaRelation.from_idea_id",
        back_populates="from_idea",
    )
    incoming_relations: Mapped[list["IdeaRelation"]] = relationship(
        "IdeaRelation",
        foreign_keys="IdeaRelation.to_idea_id",
        back_populates="to_idea",
    )


class IdeaSignal(Base):
    __tablename__ = "idea_signals"

    idea_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ideas.id"), primary_key=True
    )
    signal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("signals.id"), primary_key=True
    )


class IdeaEmbedding(Base):
    __tablename__ = "idea_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idea_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ideas.id"), nullable=False, unique=True
    )
    vector: Mapped[list[float]] = mapped_column(Vector(256), nullable=False)
    model_name: Mapped[str] = mapped_column(
        String(100), nullable=False, default="hashing-v1"
    )
    model_version: Mapped[str] = mapped_column(String(30), nullable=False, default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    idea: Mapped["Idea"] = relationship("Idea", back_populates="embedding")


class IdeaRelation(Base):
    __tablename__ = "idea_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_idea_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ideas.id"), nullable=False
    )
    to_idea_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ideas.id"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    similarity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    relation_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    from_idea: Mapped["Idea"] = relationship(
        "Idea", foreign_keys=[from_idea_id], back_populates="outgoing_relations"
    )
    to_idea: Mapped["Idea"] = relationship(
        "Idea", foreign_keys=[to_idea_id], back_populates="incoming_relations"
    )

    __table_args__ = (
        Index(
            "ix_idea_relations_unique_edge",
            "from_idea_id",
            "to_idea_id",
            "relation_type",
            unique=True,
        ),
        Index("ix_idea_relations_relation_type", "relation_type"),
    )


class SignalRelation(Base):
    __tablename__ = "signal_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_signal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("signals.id"), nullable=False
    )
    to_signal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("signals.id"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    similarity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    relation_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    from_signal: Mapped["Signal"] = relationship(
        "Signal", foreign_keys=[from_signal_id], back_populates="outgoing_relations"
    )
    to_signal: Mapped["Signal"] = relationship(
        "Signal", foreign_keys=[to_signal_id], back_populates="incoming_relations"
    )

    __table_args__ = (
        Index(
            "ix_signal_relations_unique_edge",
            "from_signal_id",
            "to_signal_id",
            "relation_type",
            unique=True,
        ),
        Index("ix_signal_relations_relation_type", "relation_type"),
    )


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idea_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ideas.id"), nullable=False, unique=True
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100
    monetization_potential: Mapped[str] = mapped_column(String(50), nullable=False)
    complexity: Mapped[str] = mapped_column(String(50), nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    assumptions: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    idea: Mapped["Idea"] = relationship("Idea", back_populates="analysis")


class Enrichment(Base):
    __tablename__ = "enrichments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idea_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ideas.id"), nullable=False, unique=True
    )
    competitors: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    competitor_details: Mapped[Optional[list[dict]]] = mapped_column(JSON, nullable=True)
    app_landscape: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    monetization_strategies: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list
    )
    tech_stack: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    feasibility: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evidence_snippets: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    risks: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    go_to_market_hypotheses: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    additional_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    idea: Mapped["Idea"] = relationship("Idea", back_populates="enrichment")


class Critique(Base):
    __tablename__ = "critiques"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idea_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ideas.id"), nullable=False, unique=True
    )
    saturation_issues: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    distribution_blockers: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list
    )
    technical_blockers: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    additional_concerns: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    idea: Mapped["Idea"] = relationship("Idea", back_populates="critique")


async_engine = create_async_engine(get_database_url(), echo=False, pool_pre_ping=True)
async_session_maker = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

sync_engine = create_engine(get_database_url_sync(), echo=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def init_db() -> None:
    async with async_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS competitor_details JSON")
        )
        await conn.execute(
            text("ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS confidence FLOAT")
        )
        await conn.execute(
            text("ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS evidence_snippets VARCHAR[] DEFAULT '{}'::varchar[]")
        )
        await conn.execute(
            text("ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS risks VARCHAR[] DEFAULT '{}'::varchar[]")
        )
        await conn.execute(
            text(
                "ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS go_to_market_hypotheses VARCHAR[] DEFAULT '{}'::varchar[]"
            )
        )


async def close_db() -> None:
    await async_engine.dispose()


def init_db_sync() -> None:
    with sync_engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(conn)
        conn.execute(
            text("ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS competitor_details JSON")
        )
        conn.execute(
            text("ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS confidence FLOAT")
        )
        conn.execute(
            text("ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS evidence_snippets VARCHAR[] DEFAULT '{}'::varchar[]")
        )
        conn.execute(
            text("ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS risks VARCHAR[] DEFAULT '{}'::varchar[]")
        )
        conn.execute(
            text(
                "ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS go_to_market_hypotheses VARCHAR[] DEFAULT '{}'::varchar[]"
            )
        )


async def get_session() -> AsyncSession:
    return async_session_maker()
