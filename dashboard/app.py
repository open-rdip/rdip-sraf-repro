# dashboard/app.py
"""
RDIP SRE Dashboard — Streamlit frontend.
Run with: streamlit run dashboard/app.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from dashboard.fair_r_scorer import compute_fair_r, DIMENSIONS
from sre_engine.diff_engine import run_diff
from sre_engine.conflict_report import generate_report
from triplestore_client import graph_exists, count_triples, sparql_query

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="RDIP SRE Dashboard",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_available_studies() -> list[str]:
    """Get list of study IDs available in Oxigraph."""
    q = """
    SELECT DISTINCT ?g WHERE {
      GRAPH ?g { ?s ?p ?o }
      FILTER(STRSTARTS(STR(?g), "https://w3id.org/rdip/graph/"))
      FILTER(!CONTAINS(STR(?g), "/conflicts"))
      FILTER(!CONTAINS(STR(?g), "/schema"))
    }
    ORDER BY ?g
    """
    try:
        results = sparql_query(q)
        graphs  = [
            r["g"]["value"].replace("https://w3id.org/rdip/graph/", "")
            for r in results["results"]["bindings"]
        ]
        return graphs
    except Exception:
        return []


def radar_chart(dimension_scores: dict) -> go.Figure:
    """Render a radar chart for FAIR-R dimension scores."""
    dims   = list(dimension_scores.keys())
    scores = [dimension_scores[d]["score"] for d in dims]
    maxes  = [dimension_scores[d]["max"] for d in dims]
    pcts   = [dimension_scores[d]["percent"] for d in dims]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=scores + [scores[0]],
        theta=dims + [dims[0]],
        fill="toself",
        fillcolor="rgba(99, 110, 250, 0.2)",
        line=dict(color="rgb(99, 110, 250)", width=2),
        name="Score",
        hovertemplate="<b>%{theta}</b><br>Score: %{r}<extra></extra>",
    ))
    fig.add_trace(go.Scatterpolar(
        r=maxes + [maxes[0]],
        theta=dims + [dims[0]],
        fill="toself",
        fillcolor="rgba(200, 200, 200, 0.1)",
        line=dict(color="rgba(150,150,150,0.5)", width=1, dash="dot"),
        name="Maximum",
        hovertemplate="<b>%{theta}</b><br>Max: %{r}<extra></extra>",
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 30]),
        ),
        showlegend=True,
        height=400,
        margin=dict(t=40, b=40),
    )
    return fig


def score_gauge(score: float) -> go.Figure:
    """Render a gauge chart for the total FAIR-R score."""
    if score >= 85:
        color = "#2ecc71"
    elif score >= 70:
        color = "#f39c12"
    elif score >= 50:
        color = "#e67e22"
    else:
        color = "#e74c3c"

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": "FAIR-R Score", "font": {"size": 20}},
        delta={"reference": 70, "increasing": {"color": "#2ecc71"}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar":  {"color": color},
            "steps": [
                {"range": [0,  50], "color": "#fde8e8"},
                {"range": [50, 70], "color": "#fef3e2"},
                {"range": [70, 85], "color": "#eafaf1"},
                {"range": [85,100], "color": "#d5f5e3"},
            ],
            "threshold": {
                "line":  {"color": "black", "width": 2},
                "thickness": 0.75,
                "value": 70,
            },
        }
    ))
    fig.update_layout(height=300, margin=dict(t=40, b=20))
    return fig


def severity_badge(severity: str) -> str:
    colors = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
    return colors.get(severity, "⚪")


# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.image(
    "https://www.w3.org/RDF/icons/rdf_w3c_icon.48",
    width=48
)
st.sidebar.title("RDIP SRE")
st.sidebar.caption("Semantic Reproducibility Engine")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigation",
    ["FAIR-R Scorer", "Semantic Diff", "Knowledge Graph Explorer"],
    index=0,
)

st.sidebar.divider()
studies = get_available_studies()
st.sidebar.caption(f"Studies in KG: **{len(studies)}**")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — FAIR-R Scorer
# ═══════════════════════════════════════════════════════════════════════════════

if page == "FAIR-R Scorer":
    st.title("🔬 FAIR-R Reproducibility Scorer")
    st.caption(
        "Compute a quantitative FAIR-R score for a study "
        "based on its RDIP Knowledge Graph metadata."
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        study_id = st.selectbox(
            "Select study",
            options=studies,
            help="Studies loaded from the RDIP Knowledge Graph"
        )
    with col2:
        st.write("")
        st.write("")
        run_btn = st.button("Compute Score", type="primary", use_container_width=True)

    if run_btn and study_id:
        with st.spinner(f"Computing FAIR-R score for {study_id} ..."):
            result = compute_fair_r(study_id)

        # ── Score display ──────────────────────────────────────────────────────
        col_gauge, col_dims = st.columns([1, 2])

        with col_gauge:
            st.plotly_chart(score_gauge(result["total_score"]),
                           use_container_width=True)
            tier_colors = {
                "excellent": "success",
                "good":      "info",
                "fair":      "warning",
                "poor":      "error"
            }
            tier = result["tier"]
            getattr(st, tier_colors[tier])(
                f"**Tier: {tier.upper()}** — "
                f"{result['total_score']}/100"
            )

        with col_dims:
            st.plotly_chart(radar_chart(result["dimension_scores"]),
                           use_container_width=True)

        # ── Dimension breakdown ────────────────────────────────────────────────
        st.subheader("Dimension Breakdown")
        dim_data = []
        for dim_name, dim in result["dimension_scores"].items():
            dim_data.append({
                "Dimension":  dim_name,
                "Score":      f"{dim['score']}/{dim['max']}",
                "Percent":    f"{dim['percent']}%",
                "Status":     "✓" if dim["percent"] == 100 else "✗",
            })
        st.dataframe(
            pd.DataFrame(dim_data),
            use_container_width=True,
            hide_index=True,
        )

        # ── Criterion detail ───────────────────────────────────────────────────
        st.subheader("Criterion Detail")
        for dim_name, dim in result["dimension_scores"].items():
            with st.expander(
                f"{dim_name} — {dim['score']}/{dim['max']} "
                f"({dim['percent']}%)",
                expanded=(dim["percent"] < 100)
            ):
                for c in dim["criteria"]:
                    icon = "✅" if c["met"] else ("❌" if c["severity"] == "critical" else "⚠️")
                    st.markdown(
                        f"{icon} **{c['label']}** "
                        f"(+{c['points']}/{c['max']} pts)"
                    )
                    if c.get("rda_indicator"):
                        st.caption(f"RDA Maturity Indicator: {c['rda_indicator']}")
                    if not c["met"] and c["fix"]:
                        st.info(f"💡 {c['fix']}")

        # ── Recommendations ────────────────────────────────────────────────────
        if result["recommendations"]:
            st.subheader("Actionable Recommendations")
            st.caption(
                "Fix these to improve your FAIR-R score. "
                "Critical items block replication; warnings reduce trust."
            )
            for i, rec in enumerate(result["recommendations"], 1):
                badge = severity_badge(rec["severity"])
                with st.expander(
                    f"{badge} [{rec['dimension']}] {rec['label']}",
                    expanded=(rec["severity"] == "critical")
                ):
                    if rec.get("rda_indicator"):                                      # ← add
                        st.caption(f"RDA Maturity Indicator: {rec['rda_indicator']}")
                    st.markdown(f"**Recommendation:** {rec['fix']}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — Semantic Diff
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "Semantic Diff":
    st.title("🔀 Semantic Diff Engine")
    st.caption(
        "Compare an original study against a reproduction attempt. "
        "Detects version conflicts, missing seeds, and image digest mismatches "
        "before re-execution."
    )

    col1, col2 = st.columns(2)
    with col1:
        original_id = st.selectbox(
            "Original study",
            options=studies,
            key="orig"
        )
    with col2:
        reproduction_id = st.selectbox(
            "Reproduction attempt",
            options=studies,
            key="repr"
        )

    diff_btn = st.button(
        "Run Semantic Diff",
        type="primary",
        use_container_width=True
    )

    if diff_btn:
        with st.spinner("Running Semantic Diff ..."):
            result = run_diff(original_id, reproduction_id)

        cc       = result.get("conflict_counts", {})
        shacl    = result.get("shacl_violations", {})
        critical = shacl.get("critical", [])
        warnings = shacl.get("warnings", [])
        total    = sum(cc.values()) + len(critical)

        # ── Metrics ────────────────────────────────────────────────────────────
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Version conflicts",  cc.get("version_conflicts", 0))
        m2.metric("Digest conflicts",   cc.get("digest_conflicts", 0))
        m3.metric("Seed conflicts",     cc.get("seed_conflicts", 0))
        m4.metric("SHACL critical",     len(critical))

        if total == 0 and len(warnings) == 0:
            st.success(
                "✔ No conflicts detected — reproduction environment matches original."
            )
        elif total == 0:
            st.warning(
                f"⚠ No blocking conflicts, but {len(warnings)} warning(s) "
                f"may affect result quality."
            )
        else:
            st.error(
                f"✖ {total} conflict(s) detected — "
                f"pre-execution reproduction is AT RISK."
            )

        # ── Graph stats ────────────────────────────────────────────────────────
        st.subheader("Graph Statistics")
        g1, g2 = st.columns(2)
        g1.metric(
            f"Original ({original_id})",
            f"{result.get('original_triples', 0)} triples"
        )
        g2.metric(
            f"Reproduction ({reproduction_id})",
            f"{result.get('reproduction_triples', 0)} triples"
        )

        # ── SHACL violations ───────────────────────────────────────────────────
        if critical or warnings:
            st.subheader("SHACL Constraint Violations")
            for v in critical:
                st.error(f"❌ **CRITICAL:** {v['message']}")
            for v in warnings:
                st.warning(f"⚠️ **WARNING:** {v['message']}")

        # ── Raw JSON ───────────────────────────────────────────────────────────
        with st.expander("Raw result JSON"):
            st.json(result)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — Knowledge Graph Explorer
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "Knowledge Graph Explorer":
    st.title("🗃 Knowledge Graph Explorer")
    st.caption("Browse entity types and triples in the RDIP Knowledge Graph.")

    if not studies:
        st.warning("No studies found in the Knowledge Graph.")
    else:
        selected = st.selectbox("Select study", options=studies)

        if selected:
            graph_uri = f"https://w3id.org/rdip/graph/{selected}"
            n         = count_triples(graph_uri)
            st.metric("Total triples", n)

            # Entity type breakdown
            q = f"""
            PREFIX rdip: <https://w3id.org/rdip/>
            SELECT ?type (COUNT(?s) AS ?count)
            WHERE {{
              GRAPH <{graph_uri}> {{
                ?s a ?type .
                FILTER(STRSTARTS(STR(?type), "https://w3id.org/rdip/"))
              }}
            }}
            GROUP BY ?type
            ORDER BY DESC(?count)
            """
            results = sparql_query(q)
            rows    = results["results"]["bindings"]

            if rows:
                df = pd.DataFrame([{
                    "Type":  r["type"]["value"].replace("https://w3id.org/rdip/", "rdip:"),
                    "Count": int(r["count"]["value"])
                } for r in rows])

                col_table, col_chart = st.columns([1, 1])
                with col_table:
                    st.subheader("Entity Types")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                with col_chart:
                    fig = px.bar(
                        df, x="Count", y="Type",
                        orientation="h",
                        color="Count",
                        color_continuous_scale="Blues",
                    )
                    fig.update_layout(
                        height=350,
                        showlegend=False,
                        margin=dict(l=0, r=0, t=20, b=0),
                        yaxis=dict(autorange="reversed"),
                    )
                    st.plotly_chart(fig, use_container_width=True)

            # Dependencies table
            st.subheader("Software Dependencies")
            dep_q = f"""
            PREFIX rdip: <https://w3id.org/rdip/>
            SELECT ?name ?version ?type WHERE {{
              GRAPH <{graph_uri}> {{
                ?d a rdip:SoftwareDependency ;
                   rdip:dependencyName    ?name ;
                   rdip:dependencyVersion ?version .
                OPTIONAL {{ ?d rdip:dependencyType ?type }}
              }}
            }}
            ORDER BY ?name
            """
            dep_results = sparql_query(dep_q)
            dep_rows    = dep_results["results"]["bindings"]
            if dep_rows:
                dep_df = pd.DataFrame([{
                    "Name":    r["name"]["value"],
                    "Version": r["version"]["value"],
                    "Type":    r.get("type", {}).get("value", ""),
                } for r in dep_rows])
                st.dataframe(dep_df, use_container_width=True, hide_index=True)
            else:
                st.info("No dependencies found.")
