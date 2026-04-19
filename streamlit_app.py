import os
from typing import Any
import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("STREAMLIT_API_URL", "http://localhost:8000")

st.set_page_config(page_title="Supply Chain Disruption Advisor", layout="wide")
st.title("Supply Chain Disruption Advisor")
st.caption("Proactive disruption detection and mitigation recommendations")


def api_post(path: str, payload: dict[str, Any]) -> Any:
    response = requests.post(f"{API_URL}{path}", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def api_get(path: str) -> Any:
    response = requests.get(f"{API_URL}{path}", timeout=30)
    response.raise_for_status()
    return response.json()


left, right = st.columns([1, 2])

with left:
    st.subheader("Data Ingestion")
    supplier_emails_path = st.text_input("Supplier Emails CSV", value="data/supplier_emails.csv")
    news_feed_path = st.text_input("News Feed CSV", value="data/news_feed.csv")
    inventory_path = st.text_input("Inventory CSV", value="data/inventory.csv")

    if st.button("Ingest Sample Data", use_container_width=True):
        try:
            result = api_post(
                "/ingest",
                {
                    "supplier_emails_path": supplier_emails_path,
                    "news_feed_path": news_feed_path,
                    "inventory_path": inventory_path,
                },
            )
            st.success(
                f"Ingested {result['ingested_events']} events, indexed {result['indexed_chunks']} chunks."
            )
        except Exception as exc:
            st.error(str(exc))

    if st.button("Refresh Risks", use_container_width=True):
        st.session_state["refresh_risks"] = True

with right:
    st.subheader("Detected Risks")
    if st.session_state.get("refresh_risks", True):
        try:
            risks = api_get("/risks")
            if risks:
                df = pd.DataFrame(
                    [
                        {
                            "severity": r["severity"],
                            "type": r["disruption_type"],
                            "source": r["source"],
                            "reference_id": r["reference_id"],
                            "confidence": r["confidence"],
                            "summary": r["summary"],
                        }
                        for r in risks
                    ]
                )
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No risks available yet. Ingest data first.")
        except Exception:
            st.info("Start the backend and ingest data to view risks.")

st.divider()
st.subheader("Ask the Advisor")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

question = st.chat_input("Ask about disruptions, suppliers, buffer stock, or mitigation...")
if question:
    try:
        chat_resp = api_post("/chat", {"question": question, "top_k": 5})
        st.session_state.chat_history.append({"q": question, "a": chat_resp["answer"], "recs": chat_resp["recommendations"]})
    except Exception as exc:
        st.session_state.chat_history.append({"q": question, "a": f"Error: {exc}", "recs": []})

for entry in reversed(st.session_state.chat_history):
    with st.chat_message("user"):
        st.write(entry["q"])
    with st.chat_message("assistant"):
        st.markdown(entry["a"])
        if entry["recs"]:
            st.markdown("**Recommendations**")
            for rec in entry["recs"]:
                st.write(f"- {rec}")
