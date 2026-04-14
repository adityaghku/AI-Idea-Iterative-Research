"""Dashboard app - Streamlit visualization of idea pipeline results."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from db.config import get_database_url_sync
from db import (
    Analysis,
    Critique,
    Enrichment,
    FeedbackEvent,
    Idea,
    IdeaRelation,
    PortfolioMemory,
    Signal,
    SignalRelation,
    init_db_sync,
)

st.set_page_config(
    page_title="Idea Pipeline Dashboard",
    page_icon="💡",
    layout="wide",
    initial_sidebar_state="expanded",
)

_sync_engine = create_engine(get_database_url_sync())
_SyncSession = sessionmaker(bind=_sync_engine)
_LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
_CROSSOUT_REASON_LABELS = {
    "weak_buyer": "Weak buyer / unclear willingness to pay",
    "low_urgency": "Low urgency / nice-to-have",
    "too_crowded": "Too crowded / hard to differentiate",
    "bad_distribution": "Distribution looks too hard",
    "too_complex": "Too complex for a solo founder",
    "platform_risk": "Platform / API / policy risk",
    "not_interesting": "Not interesting enough to pursue",
    "other": "Other",
}

init_db_sync()


@st.cache_data(ttl=300, show_spinner="Loading data...")
def get_ideas_data() -> pd.DataFrame:
    """Get all ideas with related data."""
    with _SyncSession() as session:
        ideas = session.execute(select(Idea).where(Idea.is_active == True)).scalars().all()

        idea_ids = [idea.id for idea in ideas]
        analyses_by_idea = {}
        enrichments_by_idea = {}
        critiques_by_idea = {}
        if idea_ids:
            analyses = session.execute(
                select(Analysis).where(Analysis.idea_id.in_(idea_ids))
            ).scalars().all()
            enrichments = session.execute(
                select(Enrichment).where(Enrichment.idea_id.in_(idea_ids))
            ).scalars().all()
            critiques = session.execute(
                select(Critique).where(Critique.idea_id.in_(idea_ids))
            ).scalars().all()
            analyses_by_idea = {a.idea_id: a for a in analyses}
            enrichments_by_idea = {e.idea_id: e for e in enrichments}
            critiques_by_idea = {c.idea_id: c for c in critiques}

        data = []
        for idea in ideas:
            analysis = analyses_by_idea.get(idea.id)
            enrichment = enrichments_by_idea.get(idea.id)
            critique = critiques_by_idea.get(idea.id)

            data.append({
                "id": idea.id,
                "title": idea.title,
                "problem": idea.problem,
                "target_user": idea.target_user,
                "solution": idea.solution,
                "monetization_hypothesis": idea.monetization_hypothesis,
                "payer": idea.payer,
                "pricing_model": idea.pricing_model,
                "wedge": idea.wedge,
                "why_now": idea.why_now,
                "status": idea.status,
                "created_at": idea.created_at,
                "is_crossed_out": idea.is_crossed_out,
                "is_saved": idea.is_saved,
                "score": analysis.score if analysis else None,
                "demand_score": analysis.demand_score if analysis else None,
                "gtm_score": analysis.gtm_score if analysis else None,
                "build_risk_score": analysis.build_risk_score if analysis else None,
                "retention_score": analysis.retention_score if analysis else None,
                "monetization_score": analysis.monetization_score if analysis else None,
                "validation_score": analysis.validation_score if analysis else None,
                "monetization_potential": analysis.monetization_potential if analysis else None,
                "complexity": analysis.complexity if analysis else None,
                "tags": analysis.tags if analysis else [],
                "assumptions": analysis.assumptions if analysis else [],
                "comments": analysis.comments if analysis else None,
                "competitors": enrichment.competitors if enrichment else [],
                "competitor_details": enrichment.competitor_details if enrichment else [],
                "pricing_landscape": enrichment.pricing_landscape if enrichment else {},
                "monetization_strategies": enrichment.monetization_strategies if enrichment else [],
                "paid_alternatives": enrichment.paid_alternatives if enrichment else [],
                "tech_stack": enrichment.tech_stack if enrichment else [],
                "feasibility": enrichment.feasibility if enrichment else None,
                "confidence": enrichment.confidence if enrichment else None,
                "evidence_snippets": enrichment.evidence_snippets if enrichment else [],
                "risks": enrichment.risks if enrichment else [],
                "go_to_market_hypotheses": enrichment.go_to_market_hypotheses if enrichment else [],
                "validation_tests": enrichment.validation_tests if enrichment else [],
                "switching_cost_notes": enrichment.switching_cost_notes if enrichment else None,
                "additional_notes": enrichment.additional_notes if enrichment else None,
                "saturation_issues": critique.saturation_issues if critique else [],
                "distribution_blockers": critique.distribution_blockers if critique else [],
                "technical_blockers": critique.technical_blockers if critique else [],
                "monetization_blockers": critique.monetization_blockers if critique else [],
                "validation_blockers": critique.validation_blockers if critique else [],
                "critique_concerns": critique.additional_concerns if critique else None,
            })
        return pd.DataFrame(data)


@st.cache_data(ttl=300, show_spinner="Loading signals...")
def get_signals_data() -> pd.DataFrame:
    """Get all signals with strength = max(metadata score 0–1, max relation similarity)."""
    with _SyncSession() as session:
        signals = session.execute(select(Signal)).scalars().all()
        rels = session.execute(select(SignalRelation)).scalars().all()

    max_sim_by_id: dict[int, float] = {}
    for rel in rels:
        if rel.similarity is None:
            continue
        sim = float(rel.similarity)
        for sid in (rel.from_signal_id, rel.to_signal_id):
            max_sim_by_id[sid] = max(max_sim_by_id.get(sid, 0.0), sim)

    data = []
    for signal in signals:
        meta = signal.signal_metadata if isinstance(signal.signal_metadata, dict) else {}
        meta_score = _metadata_score_0_1(meta)
        max_sim = max_sim_by_id.get(signal.id, 0.0)
        if meta_score is not None:
            strength = max(meta_score, max_sim)
        else:
            strength = max_sim

        data.append({
            "id": signal.id,
            "content": signal.content,
            "source_url": signal.source_url,
            "signal_type": signal.signal_type,
            "signal_metadata": signal.signal_metadata,
            "created_at": signal.created_at,
            "strength": strength,
        })
    return pd.DataFrame(data)


@st.cache_data(ttl=300, show_spinner="Loading relations...")
def get_relations_data() -> pd.DataFrame:
    """Get all idea relations."""
    with _SyncSession() as session:
        stmt = select(IdeaRelation).where(
            IdeaRelation.relation_type.in_(["similar_to", "potential_duplicate"])
        )
        relations = session.execute(stmt).scalars().all()
        idea_ids = {
            rel.from_idea_id for rel in relations
        } | {
            rel.to_idea_id for rel in relations
        }
        idea_lookup = {}
        if idea_ids:
            idea_rows = session.execute(
                select(Idea).where(Idea.id.in_(list(idea_ids)))
            ).scalars().all()
            idea_lookup = {idea.id: idea for idea in idea_rows}

        data = []
        for rel in relations:
            from_idea = idea_lookup.get(rel.from_idea_id)
            to_idea = idea_lookup.get(rel.to_idea_id)
            data.append({
                "id": rel.id,
                "from_idea_id": rel.from_idea_id,
                "to_idea_id": rel.to_idea_id,
                "from_title": from_idea.title if from_idea else f"Idea {rel.from_idea_id}",
                "to_title": to_idea.title if to_idea else f"Idea {rel.to_idea_id}",
                "from_problem": from_idea.problem if from_idea else "",
                "to_problem": to_idea.problem if to_idea else "",
                "relation_type": rel.relation_type,
                "similarity": rel.similarity,
            })
        return pd.DataFrame(data)


@st.cache_data(ttl=30, show_spinner="Loading feedback...")
def get_feedback_data() -> pd.DataFrame:
    with _SyncSession() as session:
        rows = session.execute(
            select(FeedbackEvent).where(FeedbackEvent.event_type == "crossed_out")
        ).scalars().all()
    data = [
        {
            "id": row.id,
            "idea_id": row.idea_id,
            "reason_code": row.reason_code,
            "reason_text": row.reason_text,
            "learning_weight": row.learning_weight,
            "created_at": row.created_at,
        }
        for row in rows
    ]
    return pd.DataFrame(data)


@st.cache_data(ttl=30, show_spinner="Loading portfolio guidance...")
def get_latest_portfolio_memory() -> dict | None:
    with _SyncSession() as session:
        latest = session.execute(
            select(PortfolioMemory).order_by(PortfolioMemory.id.desc()).limit(1)
        ).scalar_one_or_none()
    if not latest:
        return None
    return {
        "summary": latest.summary,
        "scout_guidance": latest.scout_guidance,
        "synthesizer_guidance": latest.synthesizer_guidance,
        "analyser_guidance": latest.analyser_guidance,
        "recurring_patterns": latest.recurring_patterns or [],
        "created_at": latest.created_at,
    }


@st.cache_data(ttl=10, show_spinner="Loading latest log...")
def get_latest_log_file() -> str | None:
    if not _LOGS_DIR.exists():
        return None
    log_files = sorted(_LOGS_DIR.glob("pipeline_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not log_files:
        return None
    return str(log_files[0])


@st.cache_data(ttl=10, show_spinner="Reading log...")
def read_log_content(path: str) -> list[str]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    return file_path.read_text(encoding="utf-8", errors="replace").splitlines()


def _metadata_score_0_1(meta: dict | None) -> float | None:
    """Read an optional 0–1 score from signal_metadata (also accepts 0–100)."""
    if not meta:
        return None
    for key in ("score", "relevance", "strength"):
        v = meta.get(key)
        if isinstance(v, (int, float)) and pd.notna(v):
            x = float(v)
            if x > 1.0:
                x = x / 100.0
            return max(0.0, min(1.0, x))
    return None


def filter_log_lines(lines: list[str], selected_levels: list[str]) -> list[str]:
    """Filter log lines by selected log levels."""
    if not selected_levels:
        return lines
    level_tokens = [f"| {lvl:<8} |" for lvl in selected_levels]
    return [line for line in lines if any(token in line for token in level_tokens)]


def get_all_tags(df: pd.DataFrame) -> list[str]:
    """Extract all unique tags from ideas."""
    if df.empty or "tags" not in df.columns:
        return []
    all_tags = set()
    for tags in df["tags"].dropna():
        if isinstance(tags, list):
            all_tags.update(tags)
    return sorted(all_tags)


def _idea_mark_header_suffix(row: pd.Series) -> str:
    """Short label for crossed/saved (both can be true)."""
    parts: list[str] = []
    if bool(row.get("is_crossed_out")):
        parts.append("Crossed")
    if bool(row.get("is_saved")):
        parts.append("Saved")
    return " | ".join(parts)


def _crossout_reason_options() -> list[tuple[str, str]]:
    return [("", "Select reason")] + list(_CROSSOUT_REASON_LABELS.items())


def _sort_ideas_df(filtered: pd.DataFrame, sort_by: str, ascending: bool) -> pd.DataFrame:
    """Sort ideas dataframe."""
    if filtered.empty:
        return filtered
    out = filtered.copy()
    if sort_by == "complexity":
        complexity_order = {"low": 1, "medium": 2, "high": 3}
        out["_complexity_order"] = out["complexity"].map(complexity_order).fillna(0)
        out = out.sort_values("_complexity_order", ascending=ascending, na_position="last")
        out = out.drop(columns=["_complexity_order"])
    elif sort_by != "id":
        out = out.sort_values(sort_by, ascending=ascending, na_position="last")
    else:
        out = out.sort_values("id", ascending=False)
    return out


def apply_filters(
    df: pd.DataFrame,
    tags: list[str],
    min_score: int,
    status: str,
    filter_crossed: bool,
    filter_saved: bool,
    sort_by: str,
    ascending: bool,
) -> pd.DataFrame:
    """Apply filtering and sorting to ideas dataframe.

    filter_crossed: False = hide crossed-out ideas; True = show only crossed-out ideas.
    filter_saved: True = include saved ideas (default); False = exclude saved ideas.
    """
    if df.empty:
        return df

    filtered = df.copy()

    if not filter_crossed:
        filtered = filtered[filtered["is_crossed_out"] != True]
    else:
        filtered = filtered[filtered["is_crossed_out"] == True]

    if not filter_saved:
        filtered = filtered[filtered["is_saved"] != True]

    if tags:
        mask = filtered["tags"].apply(lambda x: any(t in x for t in tags) if isinstance(x, list) else False)
        filtered = filtered[mask]

    if min_score > 0:
        filtered = filtered[filtered["score"] >= min_score]

    if status != "All":
        filtered = filtered[filtered["status"] == status]

    return _sort_ideas_df(filtered, sort_by, ascending)


def render_idea_detail(idea_row: pd.Series):
    """Render detailed view of a single idea."""
    st.markdown(f"### {idea_row['title']}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Problem:**")
        st.write(idea_row["problem"])
        st.markdown("**Target User:**")
        st.write(idea_row["target_user"])
    with col2:
        st.markdown("**Solution:**")
        st.write(idea_row["solution"])

    if idea_row.get("monetization_hypothesis"):
        st.markdown("**Monetization Hypothesis:**")
        st.write(idea_row["monetization_hypothesis"])
    if idea_row.get("payer") or idea_row.get("pricing_model"):
        st.markdown(
            f"**Buyer / Pricing:** {idea_row.get('payer') or 'N/A'} / {idea_row.get('pricing_model') or 'N/A'}"
        )
    if idea_row.get("wedge"):
        st.markdown(f"**Wedge:** {idea_row['wedge']}")
    if idea_row.get("why_now"):
        st.markdown(f"**Why Now:** {idea_row['why_now']}")
    
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Score", f"{idea_row['score']}/100" if pd.notna(idea_row['score']) else "N/A")
        st.markdown(f"**Status:** {idea_row['status']}")
    with col2:
        st.markdown(f"**Monetization:** {idea_row['monetization_potential'] or 'N/A'}")
        st.markdown(f"**Complexity:** {idea_row['complexity'] or 'N/A'}")
    with col3:
        st.markdown(f"**Feasibility:** {idea_row['feasibility'] or 'N/A'}")
        st.markdown(f"**Created:** {idea_row['created_at'].strftime('%Y-%m-%d') if pd.notna(idea_row['created_at']) else 'N/A'}")
    
    if isinstance(idea_row["tags"], list) and idea_row["tags"]:
        st.markdown("**Tags:** " + " ".join([f":blue[{tag}]" for tag in idea_row["tags"]]))
    
    if isinstance(idea_row["assumptions"], list) and idea_row["assumptions"]:
        st.markdown("**Assumptions:**")
        for assumption in idea_row["assumptions"]:
            st.write(f"- {assumption}")

    score_pairs = [
        ("Demand", idea_row.get("demand_score")),
        ("GTM", idea_row.get("gtm_score")),
        ("Build Risk", idea_row.get("build_risk_score")),
        ("Retention", idea_row.get("retention_score")),
        ("Monetization", idea_row.get("monetization_score")),
        ("Validation", idea_row.get("validation_score")),
    ]
    populated_score_pairs = [(label, value) for label, value in score_pairs if pd.notna(value)]
    if populated_score_pairs:
        st.markdown("**Subscores:**")
        for label, value in populated_score_pairs:
            st.write(f"- {label}: {int(value)}/100")
    
    if isinstance(idea_row["competitors"], list) and idea_row["competitors"]:
        st.markdown("**Competitors:**")
        details = idea_row.get("competitor_details", [])
        details_by_name = {}
        if isinstance(details, list):
            for detail in details:
                if isinstance(detail, dict) and detail.get("name"):
                    details_by_name[detail["name"]] = detail
        for comp in idea_row["competitors"]:
            comp_name = comp if isinstance(comp, str) else str(comp)
            detail = details_by_name.get(comp_name, {})
            summary = detail.get("summary")
            url = detail.get("url")
            line = f"- {comp_name}"
            if summary:
                line += f": {summary}"
            st.write(line)
            if url:
                st.markdown(f"  - [URL]({url})")
    
    if isinstance(idea_row["monetization_strategies"], list) and idea_row["monetization_strategies"]:
        st.markdown("**Monetization Strategies:**")
        for strat in idea_row["monetization_strategies"]:
            st.write(f"- {strat}")

    if isinstance(idea_row.get("paid_alternatives"), list) and idea_row["paid_alternatives"]:
        st.markdown("**Paid Alternatives / Current Spend:**")
        for alt in idea_row["paid_alternatives"]:
            st.write(f"- {alt}")

    pricing_landscape = idea_row.get("pricing_landscape")
    if isinstance(pricing_landscape, dict) and pricing_landscape:
        st.markdown("**Pricing Landscape:**")
        st.json(pricing_landscape)
    
    if isinstance(idea_row["tech_stack"], list) and idea_row["tech_stack"]:
        st.markdown("**Tech Stack:**")
        for tech in idea_row["tech_stack"]:
            st.markdown(f":blue-badge[{tech}]")
    
    if pd.notna(idea_row.get("additional_notes")) and idea_row["additional_notes"]:
        st.markdown("**Enrichment Notes:**")
        notes = idea_row["additional_notes"]
        if isinstance(notes, str):
            try:
                parsed = json.loads(notes)
                st.json(parsed)
            except json.JSONDecodeError:
                st.write(notes)
        else:
            st.write(notes)

    if pd.notna(idea_row.get("confidence")) and idea_row["confidence"] is not None:
        st.markdown(f"**Deep Dive Confidence:** {idea_row['confidence']:.2f}")

    if isinstance(idea_row.get("evidence_snippets"), list) and idea_row["evidence_snippets"]:
        st.markdown("**Evidence Snippets:**")
        for snippet in idea_row["evidence_snippets"]:
            st.write(f"- {snippet}")

    if isinstance(idea_row.get("risks"), list) and idea_row["risks"]:
        st.markdown("**Risks:**")
        for risk in idea_row["risks"]:
            st.write(f"- {risk}")

    if isinstance(idea_row.get("go_to_market_hypotheses"), list) and idea_row["go_to_market_hypotheses"]:
        st.markdown("**Go-to-Market Hypotheses:**")
        for hypothesis in idea_row["go_to_market_hypotheses"]:
            st.write(f"- {hypothesis}")

    if isinstance(idea_row.get("validation_tests"), list) and idea_row["validation_tests"]:
        st.markdown("**Validation Tests:**")
        for test in idea_row["validation_tests"]:
            st.write(f"- {test}")

    if pd.notna(idea_row.get("switching_cost_notes")) and idea_row["switching_cost_notes"]:
        st.markdown("**Switching Cost Notes:**")
        st.write(idea_row["switching_cost_notes"])
    
    if isinstance(idea_row["saturation_issues"], list) and idea_row["saturation_issues"]:
        st.markdown("**Saturation Issues:**")
        for issue in idea_row["saturation_issues"]:
            st.write(f"- {issue}")
    
    if isinstance(idea_row["distribution_blockers"], list) and idea_row["distribution_blockers"]:
        st.markdown("**Distribution Blockers:**")
        for blocker in idea_row["distribution_blockers"]:
            st.write(f"- {blocker}")
    
    if isinstance(idea_row["technical_blockers"], list) and idea_row["technical_blockers"]:
        st.markdown("**Technical Blockers:**")
        for blocker in idea_row["technical_blockers"]:
            st.write(f"- {blocker}")

    if isinstance(idea_row.get("monetization_blockers"), list) and idea_row["monetization_blockers"]:
        st.markdown("**Monetization Blockers:**")
        for blocker in idea_row["monetization_blockers"]:
            st.write(f"- {blocker}")

    if isinstance(idea_row.get("validation_blockers"), list) and idea_row["validation_blockers"]:
        st.markdown("**Validation Blockers:**")
        for blocker in idea_row["validation_blockers"]:
            st.write(f"- {blocker}")
    
    if pd.notna(idea_row.get("critique_concerns")) and idea_row["critique_concerns"]:
        st.markdown("**Critique Concerns:**")
        st.write(idea_row["critique_concerns"])


def update_idea_flag(idea_id: int, field: str, value: bool) -> None:
    """Set a boolean column on Idea (e.g. is_crossed_out, is_saved)."""
    if field not in ("is_crossed_out", "is_saved"):
        return
    with _SyncSession() as session:
        idea = session.get(Idea, idea_id)
        if idea:
            setattr(idea, field, value)
            session.commit()


def submit_crossout_feedback(idea_id: int, reason_code: str, reason_text: str | None) -> bool:
    """Cross out an idea and persist explicit negative-feedback rationale."""
    reason_code = reason_code.strip()
    if not reason_code:
        return False
    with _SyncSession() as session:
        idea = session.get(Idea, idea_id)
        if not idea:
            return False
        idea.is_crossed_out = True
        session.add(
            FeedbackEvent(
                idea_id=idea_id,
                event_type="crossed_out",
                reason_code=reason_code,
                reason_text=(reason_text or "").strip() or None,
                learning_weight=1.0,
            )
        )
        session.commit()
    return True


def main():
    st.title("💡 Idea Pipeline Dashboard")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📊 Ideas", "📡 Signals", "🔗 Relations", "📈 Overview", "📜 Logs"]
    )
    
    ideas_df = get_ideas_data()
    signals_df = get_signals_data()
    relations_df = get_relations_data()
    feedback_df = get_feedback_data()
    portfolio_memory = get_latest_portfolio_memory()
    
    with tab1:
        st.subheader("Ideas")
        
        if ideas_df.empty:
            st.info("No ideas found. Run the pipeline to generate ideas.")
        else:
            with st.sidebar:
                st.header("Filters")

                st.caption(
                    "✕ Crossed: off hides crossed-out ideas; on lists only crossed-out. "
                    "🚩 Saved: on (default) includes saved ideas; off excludes them."
                )
                fc1, fc2 = st.columns(2)
                with fc1:
                    filter_crossed = st.checkbox("✕ Crossed only", value=False)
                with fc2:
                    filter_saved = st.checkbox("🚩 Include saved", value=True)
                
                all_tags = get_all_tags(ideas_df)
                selected_tags = st.multiselect("Filter by Tags", all_tags, default=[])
                
                min_score = st.slider("Min Score", 0, 100, 0)
                
                status_options = ["All"] + sorted(ideas_df["status"].dropna().unique().tolist())
                selected_status = st.selectbox("Status", status_options)
                
                st.header("Sort")
                sort_options = ["id", "score", "complexity", "created_at"]
                sort_by = st.selectbox("Sort by", sort_options)
                ascending = st.checkbox("Ascending", value=False)
            
            filtered_df = apply_filters(
                ideas_df,
                selected_tags,
                min_score,
                selected_status,
                filter_crossed,
                filter_saved,
                sort_by,
                ascending,
            )
            
            st.write(f"Showing {len(filtered_df)} of {len(ideas_df)} ideas")
            st.caption("Detail view only. Expand an idea to inspect full analysis.")

            for _, row in filtered_df.iterrows():
                score_text = f"{row['score']}/100" if pd.notna(row.get("score")) else "N/A"
                tags = row["tags"] if isinstance(row.get("tags"), list) else []
                tags_text = ", ".join(tags) if tags else "No tags"
                mark_suffix = _idea_mark_header_suffix(row)
                header = f"{row['title']} (ID: {row['id']}) | Score: {score_text} | Tags: {tags_text}"
                if mark_suffix:
                    header += f" | {mark_suffix}"
                
                col1, col2 = st.columns([4, 1])
                with col1:
                    with st.expander(header, expanded=False):
                        render_idea_detail(row)
                with col2:
                    st.write(" ")
                    is_co = bool(row.get("is_crossed_out"))
                    is_sd = bool(row.get("is_saved"))
                    iid = int(row["id"])
                    bx1, bx2 = st.columns(2)
                    with bx1:
                        if not is_co:
                            reason_value = st.selectbox(
                                "Cross-out reason",
                                options=[code for code, _ in _crossout_reason_options()],
                                format_func=lambda code: "Select reason"
                                if not code
                                else _CROSSOUT_REASON_LABELS[code],
                                key=f"cross_reason_{iid}",
                                label_visibility="collapsed",
                            )
                            reason_text = st.text_input(
                                "Cross-out notes",
                                key=f"cross_notes_{iid}",
                                placeholder="Optional notes",
                                label_visibility="collapsed",
                            )
                            if st.button(
                                "✕",
                                key=f"cross_{iid}",
                                use_container_width=True,
                                help="Cross out and submit feedback",
                                type="secondary",
                            ):
                                if submit_crossout_feedback(iid, reason_value, reason_text):
                                    get_ideas_data.clear()
                                    get_feedback_data.clear()
                                    get_latest_portfolio_memory.clear()
                                    st.rerun()
                                else:
                                    st.warning("Select a cross-out reason first.", icon="⚠️")
                        else:
                            if st.button(
                                "Undo ✕",
                                key=f"cross_{iid}",
                                use_container_width=True,
                                help="Remove crossed-out flag without deleting past feedback",
                                type="primary",
                            ):
                                update_idea_flag(iid, "is_crossed_out", False)
                                get_ideas_data.clear()
                                st.rerun()
                    with bx2:
                        if st.button(
                            "🚩",
                            key=f"save_{iid}",
                            use_container_width=True,
                            help="Toggle saved",
                            type="primary" if is_sd else "secondary",
                        ):
                            update_idea_flag(iid, "is_saved", not is_sd)
                            get_ideas_data.clear()
                            st.rerun()
    
    with tab2:
        st.subheader("Signals")
        
        if signals_df.empty:
            st.info("No signals found.")
        else:
            min_strength = st.slider(
                "Minimum strength (0–1)",
                min_value=0.0,
                max_value=1.0,
                value=0.4,
                step=0.05,
                help="Strength is the max of any stored metadata score and the highest "
                "signal–signal similarity for this row. Default 0.4 hides weak/unconnected signals.",
            )
            view = signals_df[signals_df["strength"] >= min_strength].copy()
            st.caption(
                f"Showing **{len(view)}** of **{len(signals_df)}** signals with strength **≥** {min_strength:.2f}"
            )
            
            with st.expander("Raw Data"):
                st.dataframe(view, use_container_width=True)
            
            st.write("Signal Types Distribution")
            if view.empty:
                st.info("No signals in this range. Lower the minimum strength to see more.")
            else:
                type_counts = view["signal_type"].value_counts()
                st.bar_chart(type_counts)
    
    with tab3:
        st.subheader("Relations")
        st.write(f"Total similar relations: {len(relations_df)}")
        
        if relations_df.empty:
            st.info("No similar relations found.")
        else:
            st.caption("Showing only similarity relationships (`similar_to`, `potential_duplicate`).")
            for _, rel in relations_df.sort_values("similarity", ascending=False).iterrows():
                similarity = rel.get("similarity")
                sim_text = f"{similarity:.2f}" if pd.notna(similarity) else "N/A"
                with st.container(border=True):
                    st.markdown(
                        f"**{rel['from_title']}**  ↔  **{rel['to_title']}**  \n"
                        f"Type: `{rel['relation_type']}` | Similarity: `{sim_text}`"
                    )
                    if rel.get("from_problem"):
                        st.write(f"**A problem:** {rel['from_problem']}")
                    if rel.get("to_problem"):
                        st.write(f"**B problem:** {rel['to_problem']}")
    
    with tab4:
        st.subheader("Overview")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Ideas", len(ideas_df))
        with col2:
            st.metric("Signals", len(signals_df))
        with col3:
            avg_score = ideas_df["score"].mean()
            st.metric("Avg Score", f"{avg_score:.1f}" if pd.notna(avg_score) else "N/A")
        with col4:
            st.metric("Relations", len(relations_df))
        
        st.divider()
        
        if not ideas_df.empty:
            col1, col2 = st.columns(2)
            with col1:
                st.write("Ideas by Status")
                status_counts = ideas_df["status"].value_counts()
                st.bar_chart(status_counts)
            with col2:
                st.write("Score Distribution")
                scores = ideas_df["score"].dropna()
                if not scores.empty:
                    score_bins = pd.cut(scores, bins=10).value_counts().sort_index()
                    score_bins.index = [str(x) for x in score_bins.index]
                    st.bar_chart(score_bins)
        else:
            st.info("Run the pipeline to generate ideas.")

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.write("Crossed-Out Feedback")
            if feedback_df.empty:
                st.info("No explicit crossed-out feedback yet.")
            else:
                reason_counts = (
                    feedback_df["reason_code"]
                    .fillna("unknown")
                    .map(lambda code: _CROSSOUT_REASON_LABELS.get(code, code))
                    .value_counts()
                )
                st.bar_chart(reason_counts)
        with col2:
            st.write("Latest Portfolio Guidance")
            if not portfolio_memory:
                st.info("No portfolio guidance written yet.")
            else:
                if portfolio_memory.get("summary"):
                    st.write(portfolio_memory["summary"])
                recurring_patterns = portfolio_memory.get("recurring_patterns") or []
                if recurring_patterns:
                    st.markdown("**Recurring rejection patterns:**")
                    for pattern in recurring_patterns:
                        label = _CROSSOUT_REASON_LABELS.get(
                            pattern.get("reason_code"), pattern.get("reason_code")
                        )
                        st.write(f"- {label}: {pattern.get('count', 0)}")

    with tab5:
        st.subheader("Latest Pipeline Log")
        latest_log = get_latest_log_file()
        if not latest_log:
            st.info("No pipeline logs found yet.")
        else:
            st.write(f"Latest file: `{latest_log}`")
            if st.button("Refresh Log View"):
                st.cache_data.clear()
                st.rerun()
            lines = read_log_content(latest_log)
            if not lines:
                st.info("Log file is empty.")
            else:
                total = len(lines)
                max_lines = st.slider("Lines to display", min_value=100, max_value=5000, value=800, step=100)
                selected_levels = st.multiselect(
                    "Log Levels",
                    options=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                    default=["INFO", "DEBUG"],
                    help="Show only lines matching selected levels.",
                )
                mode = st.radio("Display", ["Tail (most recent)", "Head (from start)"], horizontal=True)
                if mode == "Tail (most recent)":
                    candidate = lines[-max_lines:]
                else:
                    candidate = lines[:max_lines]
                shown = filter_log_lines(candidate, selected_levels)
                st.caption(
                    f"Showing {len(shown)} filtered lines out of {len(candidate)} displayed "
                    f"(source file has {total} lines)"
                )
                st.code("\n".join(shown), language="text")


if __name__ == "__main__":
    main()
