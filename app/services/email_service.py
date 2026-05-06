"""Email service using AWS SES for sending supply chain alerts and notifications."""
from __future__ import annotations

import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)


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


class EmailService:
    """AWS SES email service for supply chain notifications."""

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

    def send_email(self, request: EmailRequest) -> EmailResult:
        """Send an email via AWS SES.

        Args:
            request: Email request with recipients, subject, and body.

        Returns:
            EmailResult with success status and message ID.
        """
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
            logger.info("Email sent successfully: MessageId=%s, To=%s", message_id, request.to)
            return EmailResult(success=True, message_id=message_id)
        except ClientError as exc:
            error_msg = exc.response["Error"]["Message"]
            logger.error("SES send failed: %s", error_msg)
            return EmailResult(success=False, error=error_msg)
        except Exception as exc:
            logger.error("Email send failed: %s", exc)
            return EmailResult(success=False, error=str(exc))

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
    ) -> EmailResult:
        """Send a risk alert email to stakeholders.

        Args:
            to: Recipient email addresses.
            risk_severity: critical, high, medium, or low.
            risk_headline: Short description of the risk.
            supplier: Affected supplier name.
            disruption_type: Type of disruption.
            recommendations: List of recommended actions.
        """
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
                <h2 style="margin: 0;">⚠️ Supply Chain Risk Alert — {risk_severity.upper()}</h2>
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
                <p style="color: #6b7280; font-size: 12px;">This alert was generated by the Supply Chain Disruption Advisor. Log in to the dashboard for full details.</p>
            </div>
        </div>
        """

        body_text = (
            f"SUPPLY CHAIN RISK ALERT — {risk_severity.upper()}\n\n"
            f"{risk_headline}\n"
            f"Severity: {risk_severity}\n"
            f"{'Supplier: ' + supplier if supplier else ''}\n"
            f"{'Type: ' + disruption_type if disruption_type else ''}\n\n"
            f"{'Recommendations:\\n' + chr(10).join('- ' + r for r in recommendations) if recommendations else ''}"
        )

        return self.send_email(EmailRequest(
            to=to,
            subject=f"[{risk_severity.upper()}] Supply Chain Alert: {risk_headline[:80]}",
            body_html=body_html,
            body_text=body_text,
        ))

    def send_playbook_notification(
        self,
        to: list[str],
        playbook_name: str,
        node_name: str,
        actions: list[str],
        risk_score: float,
    ) -> EmailResult:
        """Send a notification when a playbook is triggered.

        Args:
            to: Recipient email addresses.
            playbook_name: Name of the triggered playbook.
            node_name: Affected supply chain node.
            actions: List of actions the playbook will execute.
            risk_score: The risk score that triggered the playbook.
        """
        actions_html = "".join(f"<li>{a}</li>" for a in actions)

        body_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: #7c3aed; color: white; padding: 16px 24px; border-radius: 8px 8px 0 0;">
                <h2 style="margin: 0;">⚡ Playbook Triggered</h2>
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
            to=to,
            subject=f"[Playbook] {playbook_name} triggered for {node_name}",
            body_html=body_html,
            body_text=body_text,
        ))

    def send_shipment_delay_alert(
        self,
        to: list[str],
        shipment_id: str,
        supplier: str,
        material: str,
        origin: str,
        destination: str,
        delay_reason: str = "",
    ) -> EmailResult:
        """Send an alert when a shipment is delayed.

        Args:
            to: Recipient email addresses.
            shipment_id: The shipment identifier.
            supplier: Supplier name.
            material: Material being shipped.
            origin: Origin location.
            destination: Destination location.
            delay_reason: Reason for the delay if known.
        """
        body_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: #ea580c; color: white; padding: 16px 24px; border-radius: 8px 8px 0 0;">
                <h2 style="margin: 0;">🚢 Shipment Delay Alert</h2>
            </div>
            <div style="border: 1px solid #e5e7eb; border-top: none; padding: 24px; border-radius: 0 0 8px 8px;">
                <p style="font-size: 16px; margin-top: 0;">Shipment <strong>{shipment_id}</strong> has been delayed.</p>
                <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                    <tr><td style="padding: 8px 0; color: #6b7280;">Supplier</td><td style="padding: 8px 0;">{supplier}</td></tr>
                    <tr><td style="padding: 8px 0; color: #6b7280;">Material</td><td style="padding: 8px 0;">{material}</td></tr>
                    <tr><td style="padding: 8px 0; color: #6b7280;">Route</td><td style="padding: 8px 0;">{origin} → {destination}</td></tr>
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
            f"Route: {origin} → {destination}\n"
            f"{'Reason: ' + delay_reason if delay_reason else ''}"
        )

        return self.send_email(EmailRequest(
            to=to,
            subject=f"[Delay] Shipment {shipment_id} from {supplier} delayed",
            body_html=body_html,
            body_text=body_text,
        ))
