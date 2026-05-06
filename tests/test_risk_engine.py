from app.services.risk_engine import RiskAnalyzer


def test_detects_critical_from_financial_signal() -> None:
    analyzer = RiskAnalyzer()
    event = {
        "source": "supplier_email",
        "reference_id": "X1",
        "text": "Supplier announced insolvency and possible plant shutdown next month.",
    }
    result = analyzer.analyze_event(event)
    assert result.severity in {"critical", "high"}
    assert result.disruption_type in {"financial", "operations"}
    assert len(result.recommendations) >= 2


def test_detects_low_when_no_signal() -> None:
    analyzer = RiskAnalyzer()
    event = {
        "source": "news_feed",
        "reference_id": "X2",
        "text": "Supplier shared quarterly newsletter and sustainability progress.",
    }
    result = analyzer.analyze_event(event)
    assert result.severity == "low"


def test_news_events_are_neutral_context() -> None:
    """News events should NOT be individually scored — they are context for cross-reference."""
    analyzer = RiskAnalyzer()
    event = {
        "source": "global_news",
        "reference_id": "N1",
        "text": (
            "Port worker strike intensifies. "
            "Logistics experts report severe port congestion and vessel backlog across key terminals."
        ),
        "metadata": {
            "title": "Port worker strike intensifies",
            "summary": "Logistics experts report severe port congestion and vessel backlog.",
            "link": "https://example.com/article",
        },
    }
    result = analyzer.analyze_event(event)
    # News events should be low/neutral placeholders, not CRITICAL
    assert result.severity == "low"
    assert result.confidence == 0.0
    assert result.metadata.get("_news_context_only") is True
    assert result.headline  # Should still have the title


def test_email_with_self_reported_problem_is_flagged() -> None:
    """Emails that self-report a problem (delay, shortage) should be flagged."""
    analyzer = RiskAnalyzer()
    event = {
        "source": "live_email",
        "reference_id": "E1",
        "supplier": "Gulf Metals",
        "text": "Material shortage warning — Aluminum ingots low. Our stockpile is running lower than usual.",
        "metadata": {"sender_name": "Gulf Metals", "subject": "Material shortage warning"},
    }
    result = analyzer.analyze_event(event)
    assert result.severity == "medium"
    assert "shortage" in result.signals


def test_boring_email_is_low() -> None:
    """Routine operational emails should be LOW severity."""
    analyzer = RiskAnalyzer()
    event = {
        "source": "live_email",
        "reference_id": "E2",
        "supplier": "Alpha Metals",
        "text": "Shipment confirmation — Order AM-4421 copper coil dispatched from our Shanghai warehouse. ETA 14 days.",
        "metadata": {"sender_name": "Alpha Metals", "subject": "Shipment confirmation"},
    }
    result = analyzer.analyze_event(event)
    assert result.severity == "low"
    assert result.confidence < 0.6

