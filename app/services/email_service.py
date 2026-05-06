"""Email service using AWS SES for sending supply chain alerts and notifications.

Supports role-based routing: alerts are automatically sent to the right people
based on the alert category (operations, finance, analyst, executive).
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Alert categories → role routing
# ------------------------------------------------------------------

class AlertCategory(str, Enum):
    """Categories that determine who receives an alert."""
    OPERATIONS = "operations"    # Shipment delays, logistics issues, port disruptions
    FINANCE = "finance"          # Cost impacts, tariff changes, budget overruns
    ANALYST = "analyst"          # Risk assessments, trend analysis, predictions
    EXECUTIVE = "executive"      # Critical escalations, major disruptions
    ALL = "all"                  # Broadcast to everyone


# Maps disruption types to alert categories
DISRUPTION_CATEGORY_MAP: dict[str, AlertCategory] = {
    # Operations
    "shipping_delay": AlertCategory.OPERATIONS,
    "port_congestion": AlertCategory.OPERATIONS,
    "logistics_failure": AlertCategory.OPERATIONS,
    "weather_disruption": AlertCategory.OPERATIONS,
    "vessel_delay": AlertCategory.OPERATIONS,
    "route_disruption": AlertCategory.OPERATIONS,
    "capacity_shortage": AlertCategory.OPERATIONS,
    "labor_strike": AlertCategory.OPERATIONS,
    # Finance
    "tariff_change": AlertCategory.FINANCE,
    "cost_increase": AlertCategory.FINANCE,
    "currency_fluctuation": AlertCategory.FINANCE,
    "insurance_claim": AlertCategory.FINANCE,
    "budget_overrun": AlertCategory.FINANCE,
    # Analyst
    "demand_shift": AlertCategory.ANALYST,
    "market_volatility": AlertCategory.ANALYST,
    "supplier_risk": AlertCategory.ANALYST,
    "geopolitical": AlertCategory.ANALYST,
    "trade_policy": AlertCategory.ANALYST,
    # Executive (critical only)
    "supplier_bankruptcy": AlertCategory.EXECUTIVE,
    "sanctions": AlertCategory.EXECUTIVE,
    "force_majeure": AlertCategory.EXECUTIVE,
    "plant_shutdown": AlertCategory.EXECUTIVE,
}

# Severity-based escalation: critical always goes to executive too
SEVERITY_ESCALATION: dict[str, list[AlertCategory]] = {
    "critical": [AlertCategory.EXECUTIVE, AlertCategory.OPERATIONS],
    "high": [AlertCategory.OPERATIONS],
    "medium": [],
    "low": [],
}


class EmailRequest(BaseModel):
    """Request model for sending an email."""
    to: list[str]
    subject: str
    body_html: str
    body_text: str | None = None
    cc: list[str] | None = None
    bcc: list[str] | None = None
    reply_to: list[str] | None = None


class EmailResult(BaseModel):
    """Result of an email send operation."""
    success: bool
    message_id: str | None = None
    error: str | None = None
    recipients_notified: list[str] | None = None
    category: str | None = None


class EmailService:
    """AWS SES email service with role-based alert routing."""

    def __init__(self) -> None:
        self._client = None
        self._settings = get_settings()

    @property
    def client(self):
        """Lazy-initialize the SES client."""
        if self._client is None:
            try:
                self._client = boto3.client(
                    "ses",
                    region_name=self._settings.ses_region or self._settings.aws_region,
                    aws_access_key_id=self._settings.aws_access_key_id or None,
                    aws_secret_access_key=self._settings.aws_secret_access_key or None,
                    aws_session_token=self._settings.aws_session_token or None,
                )
                logger.info("SES client initialized in region: %s", self._settings.ses_region or self._settings.aws_region)
            except Exception as exc:
                logger.error("Failed to initialize SES client: %s", exc)
                raise
        return self._client

    @property
    def sender(self) -> str:
        """Return the configured sender email address."""
        return self._settings.ses_sender_email

    # ------------------------------------------------------------------
    # Role-based recipient resolution
    # ------------------------------------------------------------------

    def get_recipients_for_category(self, category: AlertCategory) -> list[str]:
        """Resolve email recipients for a given alert category.

        Reads from environment config:
        - SES_RECIPIENTS_OPERATIONS -> ops team
        - SES_RECIPIENTS_FINANCE -> CFO, finance team
        - SES_RECIPIENTS_ANALYST -> risk analysts
        - SES_RECIPIENTS_EXECUTIVE -> C-suite, VP supply chain
        - SES_ALERT_RECIPIENTS -> fallback for all
        """
        settings = self._settings
        category_env_map = {
            AlertCategory.OPERATIONS: settings.ses_recipients_operations,
            AlertCategory.FINANCE: settings.ses_recipients_finance,
            AlertCategory.ANALYST: settings.ses_recipients_analyst,
            AlertCategory.EXECUTIVE: settings.ses_recipients_executive,
            AlertCategory.ALL: settings.ses_alert_recipients,
        }

        raw = category_env_map.get(category, "")
        if raw:
            return [e.strip() for e in raw.split(",") if e.strip()]

        # Fallback to general alert recipients
        fallback = settings.ses_alert_recipients
        if fallback:
            return [e.strip() for e in fallback.split(",") if e.strip()]

        return []

    def resolve_recipients(
        self,
        disruption_type: str = "",
        severity: str = "medium",
        explicit_recipients: list[str] | None = None,
    ) -> tuple[list[str], AlertCategory]:
        """Determine who should receive an alert based on disruption type and severity.

        Logic:
        1. If explicit recipients are provided, use those.
        2. Otherwise, map disruption_type -> category -> recipients.
        3. Apply severity escalation (critical -> also notify executive).
        4. Deduplicate.

        Returns:
            Tuple of (deduplicated recipient list, primary category).
        """
        # Determine primary category
        category = DISRUPTION_CATEGORY_MAP.get(
            disruption_type.lower().strip(),
            AlertCategory.OPERATIONS,
        )

        if explicit_recipients:
            return explicit_recipients, category

        recipients: set[str] = set()

        # Primary category recipients
        recipients.update(self.get_recipients_for_category(category))

        # Severity-based escalation
        escalation_categories = SEVERITY_ESCALATION.get(severity.lower(), [])
        for esc_category in escalation_categories:
            if esc_category != category:
                recipients.update(self.get_recipients_for_category(esc_category))

        return list(recipients), category

    # ------------------------------------------------------------------
    # Core send
    # ------------------------------------------------------------------

    def send_email(self, request: EmailRequest) -> EmailResult:
        """Send an email via AWS SES."""
        if not self.sender:
            return EmailResult(success=False, error="SES sender email not configured (SES_SENDER_EMAIL)")

        if not request.to:
            return EmailResult(success=False, error="No recipients specified")

        destination: dict[str, Any] = {"ToAddresses": request.to}
        if request.cc:
            destination["CcAddresses"] = request.cc
        if request.bcc:
            destination["BccAddresses"] = request.bcc

        body: dict[str, Any] = {
            "Html": {"Charset": "UTF-8", "Data": request.body_html},
        }
        if request.body_text:
            body["Text"] = {"Charset": "UTF-8", "Data": request.body_text}

        kwargs: dict[str, Any] = {
            "Source": self.sender,
            "Destination": destination,
            "Message": {
                "Subject": {"Charset": "UTF-8", "Data": request.subject},
                "Body": body,
            },
        }
        if request.reply_to:
            kwargs["ReplyToAddresses"] = request.reply_to

        try:
            response = self.client.send_email(**kwargs)
            message_id = response.get("MessageId", "")
            logger.info("Email sent: MessageId=%s, To=%s", message_id, request.to)
            return EmailResult(success=True, message_id=message_id, recipients_notified=request.to)
        except ClientError as exc:
            error_msg = exc.response["Error"]["Message"]
            logger.error("SES send failed: %s", error_msg)
            return EmailResult(success=False, error=error_msg)
        except Exception as exc:
            logger.error("Email send failed: %s", exc)
            return EmailResult(success=False, error=str(exc))

    # ------------------------------------------------------------------
    # Smart routed alert (auto-routes based on disruption type + severity)
    # ------------------------------------------------------------------

    def send_routed_alert(
        self,
        risk_severity: str,
        risk_headline: str,
        supplier: str = "",
        disruption_type: str = "",
        recommendations: list[str] | None = None,
        explicit_recipients: list[str] | None = None,
    ) -> EmailResult:
        """Send a risk alert with automatic role-based routing.

        This is the main method to call. It figures out who should be
        notified based on the disruption type and severity level.

        Examples:
        - shipping_delay + high -> ops team + ops escalation
        - tariff_change + medium -> finance team
        - supplier_bankruptcy + critical -> executive + ops
        - geopolitical + high -> analyst + ops escalation
        """
        recipients, category = self.resolve_recipients(
            disruption_type=disruption_type,
            severity=risk_severity,
            explicit_recipients=explicit_recipients,
        )

        if not recipients:
            return EmailResult(
                success=False,
                error="No recipients resolved. Configure SES_RECIPIENTS_* or SES_ALERT_RECIPIENTS in .env",
                category=category.value,
            )

        logger.info(
            "Routing alert: type=%s, severity=%s, category=%s, recipients=%s",
            disruption_type, risk_severity, category.value, recipients,
        )

        result = self.send_risk_alert(
            to=recipients,
            risk_severity=risk_severity,
            risk_headline=risk_headline,
            supplier=supplier,
            disruption_type=disruption_type,
            recommendations=recommendations,
            subject_prefix=f"[{category.value.upper()}]",
        )
        result.category = category.value
        return result

    # ------------------------------------------------------------------
    # Pre-built notification templates
    # ------------------------------------------------------------------

    def send_risk_alert(
        self,
        to: list[str],
        risk_severity: str,
        risk_headline: str,
        supplier: str = "",
        disruption_type: str = "",
        recommendations: list[str] | None = None,
        subject_prefix: str = "",
    ) -> EmailResult:
        """Send a risk alert email to specified recipients."""
        severity_colors = {
            "critical": "#dc2626",
            "high": "#ea580c",
            "medium": "#ca8a04",
            "low": "#16a34a",
        }
        color = severity_colors.get(risk_severity, "#6b7280")

        recs_html = ""
        if recommendations:
            recs_items = "".join(f"<li>{r}</li>" for r in recommendations)
            recs_html = f"<h3>Recommended Actions</h3><ul>{recs_items}</ul>"

        body_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: {color}; color: white; padding: 16px 24px; border-radius: 8px 8px 0 0;">
                <h2 style="margin: 0;">&#9888;&#65039; Supply Chain Risk Alert &mdash; {risk_severity.upper()}</h2>
            </div>
            <div style="border: 1px solid #e5e7eb; border-top: none; padding: 24px; border-radius: 0 0 8px 8px;">
                <p style="font-size: 16px; margin-top: 0;"><strong>{risk_headline}</strong></p>
                <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                    <tr><td style="padding: 8px 0; color: #6b7280;">Severity</td><td style="padding: 8px 0;"><strong style="color: {color};">{risk_severity.upper()}</strong></td></tr>
                    {"<tr><td style='padding: 8px 0; color: #6b7280;'>Supplier</td><td style='padding: 8px 0;'>" + supplier + "</td></tr>" if supplier else ""}
                    {"<tr><td style='padding: 8px 0; color: #6b7280;'>Disruption Type</td><td style='padding: 8px 0;'>" + disruption_type + "</td></tr>" if disruption_type else ""}
                </table>
                {recs_html}
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
                <p style="color: #6b7280; font-size: 12px;">This alert was generated by the Supply Chain Disruption Advisor.</p>
            </div>
        </div>
        """

        body_text = (
            f"SUPPLY CHAIN RISK ALERT - {risk_severity.upper()}\n\n"
            f"{risk_headline}\n"
            f"Severity: {risk_severity}\n"
            f"{'Supplier: ' + supplier if supplier else ''}\n"
            f"{'Type: ' + disruption_type if disruption_type else ''}\n\n"
            f"{'Recommendations:\n' + chr(10).join('- ' + r for r in recommendations) if recommendations else ''}"
        )

        prefix = f"{subject_prefix} " if subject_prefix else ""
        return self.send_email(EmailRequest(
            to=to,
            subject=f"{prefix}[{risk_severity.upper()}] Supply Chain Alert: {risk_headline[:80]}",
            body_html=body_html,
            body_text=body_text,
        ))

    def send_playbook_notification(
        self,
        playbook_name: str,
        node_name: str,
        actions: list[str],
        risk_score: float,
        to: list[str] | None = None,
    ) -> EmailResult:
        """Send a notification when a playbook is triggered.

        Auto-routes to operations team if no recipients specified.
        """
        recipients = to or self.get_recipients_for_category(AlertCategory.OPERATIONS)
        if not recipients:
            return EmailResult(success=False, error="No operations recipients configured")

        actions_html = "".join(f"<li>{a}</li>" for a in actions)

        body_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: #7c3aed; color: white; padding: 16px 24px; border-radius: 8px 8px 0 0;">
                <h2 style="margin: 0;">&#9889; Playbook Triggered</h2>
            </div>
            <div style="border: 1px solid #e5e7eb; border-top: none; padding: 24px; border-radius: 0 0 8px 8px;">
                <p style="font-size: 16px; margin-top: 0;"><strong>{playbook_name}</strong> was automatically triggered.</p>
                <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                    <tr><td style="padding: 8px 0; color: #6b7280;">Node</td><td style="padding: 8px 0;">{node_name}</td></tr>
                    <tr><td style="padding: 8px 0; color: #6b7280;">Risk Score</td><td style="padding: 8px 0;"><strong>{risk_score:.2f}</strong></td></tr>
                </table>
                <h3>Actions Taken</h3>
                <ul>{actions_html}</ul>
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
                <p style="color: #6b7280; font-size: 12px;">Review and provide feedback in the Playbooks dashboard.</p>
            </div>
        </div>
        """

        body_text = (
            f"PLAYBOOK TRIGGERED: {playbook_name}\n\n"
            f"Node: {node_name}\n"
            f"Risk Score: {risk_score:.2f}\n\n"
            f"Actions:\n" + "\n".join(f"- {a}" for a in actions)
        )

        return self.send_email(EmailRequest(
            to=recipients,
            subject=f"[OPERATIONS] [Playbook] {playbook_name} triggered for {node_name}",
            body_html=body_html,
            body_text=body_text,
        ))

    def send_shipment_delay_alert(
        self,
        shipment_id: str,
        supplier: str,
        material: str,
        origin: str,
        destination: str,
        delay_reason: str = "",
        to: list[str] | None = None,
    ) -> EmailResult:
        """Send an alert when a shipment is delayed. Auto-routes to ops team."""
        recipients = to or self.get_recipients_for_category(AlertCategory.OPERATIONS)
        if not recipients:
            return EmailResult(success=False, error="No operations recipients configured")

        body_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: #ea580c; color: white; padding: 16px 24px; border-radius: 8px 8px 0 0;">
                <h2 style="margin: 0;">&#128674; Shipment Delay Alert</h2>
            </div>
            <div style="border: 1px solid #e5e7eb; border-top: none; padding: 24px; border-radius: 0 0 8px 8px;">
                <p style="font-size: 16px; margin-top: 0;">Shipment <strong>{shipment_id}</strong> has been delayed.</p>
                <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                    <tr><td style="padding: 8px 0; color: #6b7280;">Supplier</td><td style="padding: 8px 0;">{supplier}</td></tr>
                    <tr><td style="padding: 8px 0; color: #6b7280;">Material</td><td style="padding: 8px 0;">{material}</td></tr>
                    <tr><td style="padding: 8px 0; color: #6b7280;">Route</td><td style="padding: 8px 0;">{origin} &rarr; {destination}</td></tr>
                    {"<tr><td style='padding: 8px 0; color: #6b7280;'>Reason</td><td style='padding: 8px 0;'>" + delay_reason + "</td></tr>" if delay_reason else ""}
                </table>
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
                <p style="color: #6b7280; font-size: 12px;">Check the Shipment Tracker for updated ETAs and alternative routing options.</p>
            </div>
        </div>
        """

        body_text = (
            f"SHIPMENT DELAY ALERT\n\n"
            f"Shipment: {shipment_id}\n"
            f"Supplier: {supplier}\n"
            f"Material: {material}\n"
            f"Route: {origin} -> {destination}\n"
            f"{'Reason: ' + delay_reason if delay_reason else ''}"
        )

        return self.send_email(EmailRequest(
            to=recipients,
            subject=f"[OPERATIONS] [Delay] Shipment {shipment_id} from {supplier} delayed",
            body_html=body_html,
            body_text=body_text,
        ))
