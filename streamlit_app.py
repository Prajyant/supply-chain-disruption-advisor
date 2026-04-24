"""
Supply Chain Disruption Advisor - Modern Multi-Page Dashboard
"""
import os
from typing import Any
from datetime import datetime
import pandas as pd
import requests
import streamlit as st

# Page config
st.set_page_config(
    page_title="Supply Chain Disruption Advisor",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_URL = os.getenv("STREAMLIT_API_URL", "http://localhost:8000")

# Custom CSS for modern styling
st.markdown("""
<style>
    /* Main theme colors */
    :root {
        --primary: #6366f1;
        --primary-dark: #4f46e5;
        --success: #10b981;
        --warning: #f59e0b;
        --danger: #ef4444;
        --critical: #dc2626;
        --bg-dark: #0f172a;
        --card-bg: #1e293b;
        --text-muted: #94a3b8;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Card styling */
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-radius: 16px;
        padding: 24px;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }

    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        color: #f8fafc;
    }

    .metric-label {
        color: #94a3b8;
        font-size: 0.875rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Severity badges */
    .severity-critical {
        background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%);
        color: white;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    .severity-high {
        background: linear-gradient(135deg, #f97316 0%, #c2410c 100%);
        color: white;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    .severity-medium {
        background: linear-gradient(135deg, #f59e0b 0%, #b45309 100%);
        color: white;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    .severity-low {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
    }

    /* Risk card */
    .risk-card {
        background: #1e293b;
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
        border-left: 4px solid var(--severity-color);
    }

    /* Chat styling */
    .stChatMessage {
        background: #1e293b;
        border-radius: 12px;
        margin: 8px 0;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    }

    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 12px 24px;
        font-weight: 600;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(99, 102, 241, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "risks_data" not in st.session_state:
    st.session_state.risks_data = []
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = None


def api_post(path: str, payload: dict[str, Any]) -> Any:
    response = requests.post(f"{API_URL}{path}", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def api_get(path: str) -> Any:
    response = requests.get(f"{API_URL}{path}", timeout=30)
    response.raise_for_status()
    return response.json()


def get_severity_color(severity: str) -> str:
    colors = {
        "critical": "#dc2626",
        "high": "#f97316",
        "medium": "#f59e0b",
        "low": "#10b981",
    }
    return colors.get(severity, "#64748b")


def severity_badge(severity: str) -> str:
    return f'<span class="severity-{severity}">{severity.upper()}</span>'


# Sidebar navigation
with st.sidebar:
    st.markdown("### 📦 Supply Chain Advisor")
    st.markdown("<span style='color: #94a3b8; font-size: 0.875rem;'>Real-time disruption detection & mitigation</span>", unsafe_allow_html=True)
    st.divider()

    page = st.radio(
        "Navigation",
        ["🏠 Dashboard", "⚠️ Risk Analysis", "📰 Real-Time News", "💬 Ask Advisor", "⚙️ Settings"],
        label_visibility="collapsed",
        index=0,
    )

    st.divider()

    # Quick stats in sidebar
    if st.session_state.risks_data:
        risks = st.session_state.risks_data
        critical_count = sum(1 for r in risks if r.get("severity") == "critical")
        high_count = sum(1 for r in risks if r.get("severity") == "high")

        if critical_count > 0:
            st.error(f"🚨 {critical_count} Critical Risks")
        if high_count > 0:
            st.warning(f"⚠️ {high_count} High Risks")

    st.markdown("---")
    st.markdown(f"*Last updated: {st.session_state.last_refresh or 'Never'}*")


# ==================== DASHBOARD PAGE ====================
if page == "🏠 Dashboard":
    st.markdown("## 🏠 Overview Dashboard")
    st.markdown("Real-time supply chain risk intelligence")
    st.divider()

    # Fetch risks if not loaded
    if not st.session_state.risks_data:
        try:
            st.session_state.risks_data = api_get("/risks")
            st.session_state.last_refresh = datetime.now().strftime("%H:%M:%S")
        except Exception:
            pass

    risks = st.session_state.risks_data

    # Calculate metrics
    total_risks = len(risks)
    critical_risks = sum(1 for r in risks if r.get("severity") == "critical")
    high_risks = sum(1 for r in risks if r.get("severity") == "high")
    avg_confidence = round(sum(r.get("confidence", 0) for r in risks) / max(total_risks, 1) * 100, 1)

    # Top metrics row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{total_risks}</div>
            <div class="metric-label">Total Risks</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card" style="border-color: #dc2626;">
            <div class="metric-value" style="color: #dc2626;">{critical_risks}</div>
            <div class="metric-label">Critical</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card" style="border-color: #f97316;">
            <div class="metric-value" style="color: #f97316;">{high_risks}</div>
            <div class="metric-label">High Priority</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: #6366f1;">{avg_confidence}%</div>
            <div class="metric-label">Avg Confidence</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # Risk distribution chart
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### Recent Risk Assessments")
        if risks:
            # Create DataFrame with styling
            df = pd.DataFrame([
                {
                    "Severity": r["severity"].upper(),
                    "Type": r["disruption_type"].replace("_", " ").title(),
                    "Source": r["source"].replace("_", " ").title(),
                    "Confidence": f"{r['confidence']*100:.0f}%",
                    "Summary": r["summary"][:80] + "..." if len(r["summary"]) > 80 else r["summary"],
                }
                for r in risks[:10]
            ])

            # Apply color coding
            def color_severity(val):
                colors = {
                    "CRITICAL": "color: #dc2626; font-weight: bold;",
                    "HIGH": "color: #f97316; font-weight: bold;",
                    "MEDIUM": "color: #f59e0b; font-weight: bold;",
                    "LOW": "color: #10b981;",
                }
                return colors.get(val, "")

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Severity": st.column_config.TextColumn(width="small"),
                    "Type": st.column_config.TextColumn(width="medium"),
                    "Source": st.column_config.TextColumn(width="small"),
                    "Confidence": st.column_config.TextColumn(width="small"),
                    "Summary": st.column_config.TextColumn(width="large"),
                },
            )
        else:
            st.info("📭 No risks detected yet. Ingest data to begin analysis.")

    with col2:
        st.markdown("### Risk by Type")
        if risks:
            type_counts = {}
            for r in risks:
                dtype = r["disruption_type"].replace("_", " ").title()
                type_counts[dtype] = type_counts.get(dtype, 0) + 1

            type_df = pd.DataFrame(
                {"Type": list(type_counts.keys()), "Count": list(type_counts.values())}
            ).sort_values("Count", ascending=False)

            st.bar_chart(type_df.set_index("Type"), use_container_width=True)
        else:
            st.caption("No data available")


# ==================== RISK ANALYSIS PAGE ====================
elif page == "⚠️ Risk Analysis":
    st.markdown("## ⚠️ Risk Analysis")
    st.markdown("Detailed disruption risk breakdown")
    st.divider()

    # Refresh button
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("")
    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            try:
                st.session_state.risks_data = api_get("/risks")
                st.session_state.last_refresh = datetime.now().strftime("%H:%M:%S")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to refresh: {e}")

    risks = st.session_state.risks_data

    if not risks:
        st.warning("No risks available. Please ingest data first from the Settings page.")
    else:
        # Filter controls
        filter_col1, filter_col2, filter_col3 = st.columns(3)

        with filter_col1:
            severity_filter = st.multiselect(
                "Severity",
                options=["critical", "high", "medium", "low"],
                default=["critical", "high", "medium", "low"],
            )

        with filter_col2:
            source_filter = st.multiselect(
                "Source",
                options=list(set(r["source"] for r in risks)),
                default=list(set(r["source"] for r in risks)),
            )

        with filter_col3:
            st.markdown("")
            st.markdown("")
            show_details = st.checkbox("Show Details", value=True)

        # Filter risks
        filtered_risks = [
            r for r in risks
            if r["severity"] in severity_filter and r["source"] in source_filter
        ]

        # Display risk cards
        for risk in filtered_risks:
            severity_color = get_severity_color(risk["severity"])

            with st.container():
                risk_col1, risk_col2 = st.columns([4, 1])

                with risk_col1:
                    st.markdown(
                        f"""
                        <div style="
                            background: #1e293b;
                            border-radius: 12px;
                            padding: 16px;
                            margin: 8px 0;
                            border-left: 4px solid {severity_color};
                        ">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <span style="
                                        background: {severity_color};
                                        color: white;
                                        padding: 4px 12px;
                                        border-radius: 9999px;
                                        font-size: 0.75rem;
                                        font-weight: 600;
                                    ">{risk['severity'].upper()}</span>
                                    <span style="color: #94a3b8; margin-left: 12px;">
                                        {risk['disruption_type'].replace('_', ' ').title()}
                                    </span>
                                </div>
                                <span style="color: #6366f1; font-weight: 600;">
                                    {risk['confidence']*100:.0f}% confidence
                                </span>
                            </div>
                            <p style="color: #e2e8f0; margin: 12px 0;">{risk['summary']}</p>
                        """
                        + (
                            f"""
                            <details style="color: #94a3b8;">
                                <summary style="cursor: pointer; color: #6366f1;">
                                    View Recommendations ({len(risk.get('recommendations', []))})
                                </summary>
                                <ul style="margin-top: 12px; padding-left: 20px;">
                            """
                            + "".join(
                                f"<li style='color: #e2e8f0; margin: 4px 0;'>{rec}</li>"
                                for rec in risk.get("recommendations", [])[:5]
                            )
                            + """
                                </ul>
                            </details>
                            """
                            if show_details
                            else ""
                        )
                        + """
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                with risk_col2:
                    st.markdown(
                        f"<div style='text-align: right; color: #94a3b8; font-size: 0.875rem;'>"
                        f"{risk['source'].replace('_', ' ').title()}<br>"
                        f"ID: {risk['reference_id']}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )


# ==================== REAL-TIME NEWS PAGE ====================
elif page == "📰 Real-Time News":
    st.markdown("## 📰 Real-Time News Feed")
    st.markdown("Live supply chain disruption intelligence")
    st.divider()

    # Ingest with realtime news
    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        use_realtime = st.checkbox(
            "Fetch Real-Time News",
            value=True,
            help="Fetch live news from RSS feeds (Supply Chain Dive, FreightWaves, Reuters, BBC)"
        )

    with col2:
        if st.button("🔄 Fetch News", use_container_width=True, type="primary"):
            try:
                result = api_post(
                    "/ingest",
                    {
                        "supplier_emails_path": "data/supplier_emails.csv",
                        "news_feed_path": "data/news_feed.csv",
                        "inventory_path": "data/inventory.csv",
                        "use_realtime_news": use_realtime,
                    },
                )
                st.session_state.risks_data = api_get("/risks")
                st.session_state.last_refresh = datetime.now().strftime("%H:%M:%S")
                st.success(f"✅ Ingested {result['ingested_events']} events")
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

    with col3:
        if st.button("🗑️ Clear Data", use_container_width=True):
            st.session_state.risks_data = []
            st.rerun()

    # Show news-sourced risks
    risks = st.session_state.risks_data
    news_risks = [r for r in risks if "news" in r.get("source", "").lower()] if risks else []

    if news_risks:
        st.markdown(f"### 📡 Live News Detections ({len(news_risks)})")

        for risk in news_risks:
            severity_color = get_severity_color(risk["severity"])

            with st.container():
                st.markdown(
                    f"""
                    <div style="
                        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                        border-radius: 12px;
                        padding: 16px;
                        margin: 12px 0;
                        border: 1px solid #334155;
                    ">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                            <span style="
                                background: {severity_color};
                                color: white;
                                padding: 4px 12px;
                                border-radius: 9999px;
                                font-size: 0.75rem;
                                font-weight: 600;
                            ">{risk['severity'].upper()}</span>
                            <span style="color: #10b981; font-size: 0.875rem;">
                                📡 {risk['disruption_type'].replace('_', ' ').title()}
                            </span>
                        </div>
                        <p style="color: #e2e8f0; margin: 0;">{risk['summary']}</p>
                        <p style="color: #64748b; font-size: 0.875rem; margin-top: 8px;">
                            Source: {risk.get('source', 'Unknown')} | ID: {risk.get('reference_id', 'N/A')}
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("📡 Click 'Fetch News' to load real-time supply chain news and detect disruptions")

    st.divider()

    # Show all risks from news and other sources
    if risks:
        st.markdown("### All Detected Risks")
        df = pd.DataFrame([
            {
                "Severity": r["severity"].upper(),
                "Type": r["disruption_type"].replace("_", " ").title(),
                "Source": r["source"],
                "Summary": r["summary"][:100] + "..." if len(r["summary"]) > 100 else r["summary"],
            }
            for r in risks
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)


# ==================== ASK ADVISOR PAGE ====================
elif page == "💬 Ask Advisor":
    st.markdown("## 💬 AI Advisor")
    st.markdown("Ask questions about supply chain risks and get mitigation recommendations")
    st.divider()

    # Quick action buttons
    st.markdown("#### Quick Questions")
    qcol1, qcol2, qcol3, qcol4 = st.columns(4)

    quick_questions = [
        "What are the critical risks?",
        "Which suppliers are affected?",
        "What mitigation actions should we take?",
        "Show me logistics disruptions",
    ]

    for i, q in enumerate(quick_questions):
        with [qcol1, qcol2, qcol3, qcol4][i]:
            if st.button(q, use_container_width=True, key=f"qq_{i}"):
                st.session_state.quick_question = q

    if "quick_question" in st.session_state:
        question = st.session_state.quick_question
        del st.session_state.quick_question
    else:
        question = None

    # Chat interface
    for entry in st.session_state.chat_history:
        with st.chat_message("user"):
            st.write(entry["q"])
        with st.chat_message("assistant"):
            st.markdown(entry["a"])
            if entry.get("recs"):
                with st.expander("📋 View Recommendations", expanded=False):
                    for rec in entry["recs"]:
                        st.markdown(f"• {rec}")

    # Chat input
    if prompt := st.chat_input("Ask about disruptions, suppliers, inventory, or mitigation..."):
        with st.spinner("Analyzing..."):
            try:
                chat_resp = api_post("/chat", {"question": prompt, "top_k": 5})
                st.session_state.chat_history.append({
                    "q": prompt,
                    "a": chat_resp["answer"],
                    "recs": chat_resp.get("recommendations", []),
                })
                st.rerun()
            except Exception as e:
                st.session_state.chat_history.append({
                    "q": prompt,
                    "a": f"❌ Error: {e}",
                    "recs": [],
                })
                st.rerun()

    if question:
        with st.spinner("Analyzing..."):
            try:
                chat_resp = api_post("/chat", {"question": question, "top_k": 5})
                st.session_state.chat_history.append({
                    "q": question,
                    "a": chat_resp["answer"],
                    "recs": chat_resp.get("recommendations", []),
                })
                st.rerun()
            except Exception as e:
                st.session_state.chat_history.append({
                    "q": question,
                    "a": f"❌ Error: {e}",
                    "recs": [],
                })
                st.rerun()


# ==================== SETTINGS PAGE ====================
elif page == "⚙️ Settings":
    st.markdown("## ⚙️ Data Settings")
    st.markdown("Configure data sources and ingestion options")
    st.divider()

    st.markdown("### Data Sources")

    col1, col2 = st.columns(2)

    with col1:
        supplier_path = st.text_input(
            "Supplier Emails CSV",
            value="data/supplier_emails.csv",
            help="Path to supplier communication data"
        )

        inventory_path = st.text_input(
            "Inventory CSV",
            value="data/inventory.csv",
            help="Path to inventory status data"
        )

    with col2:
        news_path = st.text_input(
            "News Feed CSV (fallback)",
            value="data/news_feed.csv",
            help="Path to static news data (used when realtime is disabled)"
        )

        use_realtime = st.checkbox(
            "Use Real-Time News Feeds",
            value=True,
            help="Fetch live news from RSS feeds instead of static CSV"
        )

    st.divider()

    st.markdown("### Ingestion Controls")

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.markdown("")

    with col2:
        if st.button("📥 Ingest Data", use_container_width=True, type="primary"):
            try:
                result = api_post(
                    "/ingest",
                    {
                        "supplier_emails_path": supplier_path,
                        "news_feed_path": news_path,
                        "inventory_path": inventory_path,
                        "use_realtime_news": use_realtime,
                    },
                )
                st.session_state.risks_data = api_get("/risks")
                st.session_state.last_refresh = datetime.now().strftime("%H:%M:%S")
                st.success(
                    f"✅ Ingested {result['ingested_events']} events, "
                    f"indexed {result['indexed_chunks']} chunks"
                )
            except Exception as e:
                st.error(f"❌ Failed: {e}")

    with col3:
        if st.button("🔄 Refresh Risks", use_container_width=True):
            try:
                st.session_state.risks_data = api_get("/risks")
                st.session_state.last_refresh = datetime.now().strftime("%H:%M:%S")
                st.success("Risks refreshed!")
            except Exception as e:
                st.error(f"❌ Failed: {e}")

    st.divider()

    # API Health Check
    st.markdown("### System Status")

    try:
        health = api_get("/health")
        st.success(f"✅ Backend API: {health.get('status', 'ok').upper()}")
    except Exception:
        st.error("❌ Backend API: Unreachable")

    # Data statistics
    if st.session_state.risks_data:
        risks = st.session_state.risks_data
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Events", len(risks))

        with col2:
            sources = len(set(r["source"] for r in risks))
            st.metric("Data Sources", sources)

        with col3:
            st.metric("Last Refresh", st.session_state.last_refresh or "Never")
