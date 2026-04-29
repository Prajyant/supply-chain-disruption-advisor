"""
Fake Email Sender — Supply Chain Disruption Advisor (PREDICTIVE MODE)
=====================================================================
Sends a stream of NORMAL, BORING operational supply chain emails to your
own Gmail inbox. These are NOT disaster alerts — they are routine updates
like shipment confirmations, invoices, and capacity reports.

The Predictive Engine will then cross-reference these normal operations
against real-time world news to predict potential disruptions.

Usage:
    python tools/send_fake_emails.py            # sends all emails
    python tools/send_fake_emails.py --count 5  # sends first 5
    python tools/send_fake_emails.py --delay 2  # 2 second gap between sends
"""
from __future__ import annotations

import argparse
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_APP_PASSWORD")

# ---------------------------------------------------------------------------
# Normal, boring supply chain operational emails
# The predictive engine will cross-reference these against world news
# ---------------------------------------------------------------------------
FAKE_EMAILS = [
    {
        "from_name": "Alpha Metals Supply Co.",
        "from_addr": "logistics@alphametals-fake.com",
        "subject": "Shipment confirmation — Order AM-4421 (Copper Coil)",
        "body": (
            "Hi Team,\n\n"
            "Confirming that Order AM-4421 (500 units copper coil) has left our "
            "Shanghai facility and is en route to your LA warehouse.\n\n"
            "Estimated transit time is 14 days via ocean freight through the "
            "Strait of Hormuz and Suez Canal.\n"
            "Vessel: MV Oriental Fortune\n"
            "Tracking: COSCO-88412\n\n"
            "Everything is on schedule. No issues to report.\n\n"
            "Best regards,\nAlpha Metals Logistics"
        ),
    },
    {
        "from_name": "Zenith Circuits Ltd.",
        "from_addr": "ops@zenithcircuits-fake.com",
        "subject": "Weekly capacity update — Taipei fab running smoothly",
        "body": (
            "Hello,\n\n"
            "This is our weekly operations update from the Taipei fabrication facility.\n\n"
            "Current utilization: 92%\n"
            "Your standing order for 3,000 PCB assemblies is on track for delivery "
            "next Tuesday. All wafer supplies are confirmed and quality checks are passing.\n\n"
            "No issues to report this week.\n\n"
            "Best regards,\nZenith Circuits Operations"
        ),
    },
    {
        "from_name": "Nova Plastics International",
        "from_addr": "invoicing@novaplastics-fake.com",
        "subject": "Invoice & dispatch notice — 2000kg polymer pellets",
        "body": (
            "Dear Procurement,\n\n"
            "Please find attached Invoice #NP-7823 for 2,000kg polymer pellets "
            "dispatched from our Rotterdam plant yesterday.\n\n"
            "Ship: MS European Spirit\n"
            "Route: Rotterdam → Newark via North Atlantic\n"
            "Expected arrival: 10 days\n"
            "Payment terms: Net 30\n\n"
            "Thank you for your continued business.\n\n"
            "Nova Plastics Accounts"
        ),
    },
    {
        "from_name": "Pacific Freight Partners",
        "from_addr": "bookings@pacificfreight-fake.com",
        "subject": "Booking confirmation — Container PFPC-221 (Busan → LA)",
        "body": (
            "Dear Customer,\n\n"
            "Your container PFPC-221 carrying mixed cargo from Busan, South Korea "
            "has been loaded onto MV Pacific Star.\n\n"
            "Departure: April 24\n"
            "Route: Busan → Port of Los Angeles\n"
            "ETA: May 8 (14 days)\n\n"
            "All documentation is in order. You will receive an arrival notice "
            "48 hours before docking.\n\n"
            "Pacific Freight Partners"
        ),
    },
    {
        "from_name": "SteelBridge Manufacturing",
        "from_addr": "production@steelbridge-fake.com",
        "subject": "Production schedule update — 300 steel frames (Guangzhou)",
        "body": (
            "Hello,\n\n"
            "Your order for 300 steel frames is currently in production at our "
            "Guangzhou facility.\n\n"
            "Production completion: April 28\n"
            "Shipment date: April 29\n"
            "ETA to your LA hub: 16 days from ship date\n\n"
            "All raw materials are in stock and production is proceeding normally.\n\n"
            "SteelBridge Manufacturing"
        ),
    },
    {
        "from_name": "Meridian Chemicals",
        "from_addr": "sales@meridianchemicals-fake.com",
        "subject": "Q3 pricing confirmed — chemical feedstock from Gujarat",
        "body": (
            "Dear Customer,\n\n"
            "As discussed, we are holding Q2 pricing for your chemical feedstock "
            "orders through Q3 2026.\n\n"
            "Your next scheduled delivery of 800kg ships from our Gujarat plant "
            "on May 1. Transit to your Newark facility: 18 days.\n\n"
            "Route: Mundra Port → Newark via Cape of Good Hope\n\n"
            "Please confirm your May order quantities by April 28.\n\n"
            "Meridian Chemicals Sales"
        ),
    },
    {
        "from_name": "Delta Components GmbH",
        "from_addr": "quality@deltacomponents-fake.com",
        "subject": "QC passed — Batch DX-55 thermal sensors ready to ship",
        "body": (
            "Good news!\n\n"
            "Batch DX-55 (thermal sensors, 1,200 units) has cleared our quality "
            "inspection at the Tokyo facility with a 99.7% pass rate.\n\n"
            "Shipment is scheduled for Thursday.\n"
            "ETA to your East Coast warehouse: 12 days\n"
            "Carrier: NYK Line\n\n"
            "All certificates of conformity are attached.\n\n"
            "Delta Components Quality Assurance"
        ),
    },
    {
        "from_name": "BrightPower Electronics",
        "from_addr": "warehouse@brightpower-fake.com",
        "subject": "Component availability confirmed — May order (Ho Chi Minh City)",
        "body": (
            "Hi,\n\n"
            "All components for your May order are confirmed available at our "
            "Ho Chi Minh City warehouse.\n\n"
            "Assembly start: April 28\n"
            "Ship date: May 2\n"
            "Expected delivery: 11 days after dispatch\n"
            "Route: HCMC → Port of Los Angeles\n\n"
            "We have buffer stock available if you need to increase the order size.\n\n"
            "BrightPower Electronics Warehouse Team"
        ),
    },
]


def send_email(smtp: smtplib.SMTP_SSL, from_name: str, from_addr: str,
               to_addr: str, subject: str, body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_addr}>"
    msg["To"] = to_addr
    msg.attach(MIMEText(body, "plain"))
    smtp.sendmail(from_addr, to_addr, msg.as_string())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send normal supply chain operations emails for predictive testing."
    )
    parser.add_argument("--count", type=int, default=len(FAKE_EMAILS),
                        help=f"Number of emails to send (max {len(FAKE_EMAILS)})")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="Seconds to wait between emails (default: 1.5)")
    args = parser.parse_args()

    if not GMAIL_USER or not GMAIL_PASS:
        print("❌  GMAIL_USER or GMAIL_APP_PASSWORD not set in .env — aborting.")
        return

    emails_to_send = FAKE_EMAILS[:args.count]

    print(f"\n📬  Connecting to Gmail SMTP as {GMAIL_USER} ...")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_PASS)
            print(f"✅  Connected. Sending {len(emails_to_send)} normal operations emails\n")

            for i, email_data in enumerate(emails_to_send, start=1):
                try:
                    send_email(
                        smtp=smtp,
                        from_name=email_data["from_name"],
                        from_addr=email_data["from_addr"],
                        to_addr=GMAIL_USER,
                        subject=email_data["subject"],
                        body=email_data["body"],
                    )
                    print(f"  [{i}/{len(emails_to_send)}] ✉️  Sent: {email_data['subject'][:65]}")
                    if i < len(emails_to_send):
                        time.sleep(args.delay)
                except Exception as e:
                    print(f"  [{i}/{len(emails_to_send)}] ❌  Failed: {e}")

        print(f"\n🎉  Done! {len(emails_to_send)} normal emails sent to {GMAIL_USER}.")
        print("     These are BORING operational emails — no disasters!")
        print("     The Predictive Engine will cross-reference them with world news.\n")

    except smtplib.SMTPAuthenticationError:
        print("❌  Authentication failed. Make sure GMAIL_APP_PASSWORD is a valid 16-char App Password.")
    except Exception as e:
        print(f"❌  SMTP error: {e}")


if __name__ == "__main__":
    main()
