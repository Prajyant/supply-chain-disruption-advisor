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
