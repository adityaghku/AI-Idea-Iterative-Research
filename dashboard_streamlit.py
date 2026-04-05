import streamlit as st
import sqlite3
import json
from datetime import datetime

DB_PATH = "idea_harvester.sqlite"


def get_connection():
    return sqlite3.connect(DB_PATH)


def get_all_ideas():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM ideas
        WHERE canonical_idea_id IS NULL
        ORDER BY score DESC
    """).fetchall()
    conn.close()
    
    ideas = []
    for r in rows:
        d = dict(r)
        d["source_urls"] = json.loads(d.get("source_urls") or "[]")
        d["score_breakdown"] = json.loads(d.get("score_breakdown") or "{}")
        d["idea_payload"] = json.loads(d.get("idea_payload") or "{}")
        d["created_at_dt"] = datetime.fromtimestamp(d["created_at"]) if d.get("created_at") else None
        ideas.append(d)
    return ideas


def get_runs():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_sources():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM sources ORDER BY last_attempt_at DESC LIMIT 100").fetchall()
    conn.close()
    return [dict(r) for r in rows]


st.set_page_config(page_title="Idea Harvester", layout="wide", initial_sidebar_state="expanded")

if st.button("Refresh"):
    st.rerun()

ideas = get_all_ideas()
runs = get_runs()
sources = get_sources()

if not ideas:
    st.warning("No ideas yet. Run the harvester first.")
    st.stop()

st.title("Idea Harvester Dashboard")

st.sidebar.header("Filters & Sorting")

sort_by = st.sidebar.selectbox("Sort By", ["Score (High to Low)", "Score (Low to High)", "Newest First", "Oldest First"])

search = st.sidebar.text_input("Search Ideas", placeholder="Type to search...")

filtered = ideas
if search:
    search_lower = search.lower()
    filtered = [i for i in filtered if search_lower in i["idea_title"].lower() or search_lower in i["idea_summary"].lower()]

if sort_by == "Score (High to Low)":
    filtered = sorted(filtered, key=lambda x: x["score"], reverse=True)
elif sort_by == "Score (Low to High)":
    filtered = sorted(filtered, key=lambda x: x["score"])
elif sort_by == "Newest First":
    filtered = sorted(filtered, key=lambda x: x.get("created_at") or 0, reverse=True)
else:
    filtered = sorted(filtered, key=lambda x: x.get("created_at") or 0)

st.metric("Total Ideas", len(filtered), f"of {len(ideas)} total")

for idea in filtered:
    payload = idea["idea_payload"]
    
    with st.expander(f"**{idea['idea_title']}** | Score: {idea['score']}", expanded=False):
        
        col_score, col_created = st.columns([1, 2])
        col_score.metric("Score", idea["score"])
        if idea.get("created_at_dt"):
            col_created.write(f"**Created:** {idea['created_at_dt'].strftime('%Y-%m-%d %H:%M')}")
        
        st.subheader("Summary")
        st.write(idea["idea_summary"])
        
        st.subheader("Score Breakdown")
        scores = idea["score_breakdown"]
        score_cols = st.columns(4)
        score_items = [
            ("Overall", idea["score"]),
            ("Novelty", scores.get("novelty", "N/A")),
            ("Feasibility", scores.get("feasibility", "N/A")),
            ("Market Potential", scores.get("market_potential", "N/A")),
        ]
        for col, (name, val) in zip(score_cols, score_items):
            col.metric(name, val)
        
        detailed = payload.get("detailed_scores", {})
        if detailed:
            st.write("**Detailed Scores:**")
            detail_cols = st.columns(len(detailed))
            for col, (name, val) in zip(detail_cols, detailed.items()):
                col.metric(name.replace("_", " ").title(), val)
        
        verdict = payload.get("verdict")
        if verdict:
            st.subheader("Verdict")
            st.info(verdict)
        
        target_user = payload.get("target_user")
        if target_user:
            st.subheader("Target User")
            st.write(target_user)
        
        strengths = payload.get("strengths", [])
        if strengths:
            st.subheader("Strengths")
            for s in strengths:
                st.write(f"- {s}")
        
        risks = payload.get("risks", [])
        if risks:
            st.subheader("Risks")
            for r in risks:
                st.write(f"- {r}")
        
        red_flags = payload.get("red_flags", [])
        if red_flags:
            st.subheader("Red Flags")
            for rf in red_flags:
                st.write(f"- {rf}")
        
        advice = payload.get("advice")
        if advice:
            st.subheader("Advice")
            if isinstance(advice, list):
                for a in advice:
                    st.write(f"- {a}")
            else:
                st.write(advice)
        
        go_to_market = payload.get("go_to_market_hypothesis")
        if go_to_market:
            st.subheader("Go-to-Market")
            st.write(go_to_market)
        
        differentiation = payload.get("differentiation")
        if differentiation:
            st.subheader("Differentiation")
            st.write(differentiation)
        
        open_questions = payload.get("open_questions", [])
        if open_questions:
            st.subheader("Open Questions")
            for q in open_questions:
                st.write(f"- {q}")
        
        citations = payload.get("citations", [])
        if citations:
            st.subheader("Citations (Evidence)")
            for c in citations:
                st.write(f'> "{c}"')
        
        if idea["source_urls"]:
            st.subheader("Sources")
            for url in idea["source_urls"]:
                st.write(f"- [{url}]({url})")
        
        extraction = payload.get("extraction", {})
        if extraction:
            st.subheader("Extraction Notes")
            if extraction.get("supporting_quotes"):
                st.write("**Supporting Quotes:**")
                for q in extraction["supporting_quotes"]:
                    st.write(f'> "{q}"')
            if extraction.get("mobile_features"):
                st.write(f"**Mobile Features:** {', '.join(extraction['mobile_features'])}")
            if extraction.get("notes"):
                st.write(f"**Notes:** {extraction['notes']}")
        
        with st.expander("View Raw Data"):
            st.json(idea["idea_payload"])
        
        st.divider()