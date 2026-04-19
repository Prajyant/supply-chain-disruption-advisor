from app.retrieval.index import RetrievalIndex


def test_retrieval_returns_relevant_context() -> None:
    index = RetrievalIndex()
    events = [
        {
            "source": "supplier_email",
            "reference_id": "E1",
            "text": "Port congestion will delay shipments by 7 days.",
            "metadata": {},
        },
        {
            "source": "news_feed",
            "reference_id": "N1",
            "text": "Strong demand increase in consumer electronics this quarter.",
            "metadata": {},
        },
    ]
    index.build(events)
    contexts = index.query("Which suppliers have shipment delay risks?", top_k=1)
    assert len(contexts) == 1
    assert "delay" in contexts[0].text.lower() or "shipment" in contexts[0].text.lower()
