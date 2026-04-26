"""
Fake Email Sender — Supply Chain Disruption Advisor
====================================================
Sends a stream of realistic fake supplier disruption emails to your own
Gmail inbox so the live email ingestion pipeline has real data to scan.

Usage:
    python tools/send_fake_emails.py            # sends all 12 emails
    python tools/send_fake_emails.py --count 5  # sends first 5 emails
    python tools/send_fake_emails.py --delay 3  # 3 second gap between sends
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
# Fake email scenarios — variety of severity levels and disruption types
# ---------------------------------------------------------------------------
FAKE_EMAILS = [
    {
        "from_name": "Alpha Metals Supply Co.",
        "from_addr": "alerts@alphametals-fake.com",
        "subject": "URGENT: Port Congestion — Copper Shipment Delayed",
        "body": (
            "Dear Procurement Team,\n\n"
            "We regret to inform you that due to severe port congestion at the Port of "
            "Shanghai, your copper shipment (Order #CM-4421) will be delayed by 7–10 business days.\n\n"
            "Our vessel has been waiting at anchor for 4 days. Congestion levels are at a 3-year high "
            "due to the recent typhoon season disrupting berthing schedules.\n\n"
            "We will provide daily updates and prioritise your cargo as soon as a berth becomes available.\n\n"
            "Regards,\nAlpha Metals Supply Co."
        ),
    },
    {
        "from_name": "Nova Plastics International",
        "from_addr": "cfo@novaplastics-fake.com",
        "subject": "Confidential: Insolvency Proceedings Initiated",
        "body": (
            "Dear Valued Customer,\n\n"
            "We are writing to formally inform you that Nova Plastics International has initiated "
            "voluntary insolvency proceedings as of today. Our parent company's financial restructuring "
            "has created uncertainty for all upcoming deliveries.\n\n"
            "All pending orders are currently on hold pending court approval. We advise you to "
            "immediately identify alternative suppliers for your polymer requirements.\n\n"
            "An administrator has been appointed and will be in touch within 5 business days.\n\n"
            "Regards,\nNova Plastics CFO Office"
        ),
    },
    {
        "from_name": "Zenith Circuits Ltd.",
        "from_addr": "operations@zenithcircuits-fake.com",
        "subject": "Capacity Constraint — Q2 Orders Affected",
        "body": (
            "Hello,\n\n"
            "Due to unexpected equipment failure at our Taipei manufacturing facility, we are "
            "currently operating at 65% of normal capacity.\n\n"
            "We can only fulfil 70% of your scheduled Q2 orders on time. The remaining 30% will "
            "experience a 2–3 week delay. We are working to source additional capacity from our "
            "Shenzhen facility but lead times will be extended.\n\n"
            "Please review your production schedules accordingly.\n\n"
            "Best regards,\nZenith Circuits Operations"
        ),
    },
    {
        "from_name": "Delta Components GmbH",
        "from_addr": "quality@deltacomponents-fake.com",
        "subject": "Quality Recall Notice — Batch QX-44 Affected",
        "body": (
            "QUALITY ALERT — ACTION REQUIRED\n\n"
            "A quality recall has been issued for batch QX-44 (manufactured between March 10–18, 2026). "
            "Internal testing has identified a defect in the thermal bonding layer that may cause failure "
            "under high-temperature operating conditions.\n\n"
            "Replacement units are being manufactured but lead time will increase by 3–4 weeks. "
            "Please quarantine any affected units immediately and do not use in production.\n\n"
            "Contact your account manager for RMA instructions.\n\n"
            "Delta Components Quality Assurance"
        ),
    },
    {
        "from_name": "Pacific Freight Partners",
        "from_addr": "dispatch@pacificfreight-fake.com",
        "subject": "Worker Strike — West Coast Port Operations Suspended",
        "body": (
            "Urgent Advisory,\n\n"
            "We are writing to advise that dock workers at the Port of Los Angeles and Long Beach "
            "have begun an indefinite strike as of 06:00 this morning. All container operations have "
            "been suspended until further notice.\n\n"
            "Approximately 14 vessels are currently waiting at anchor. We estimate a backlog of 8–12 "
            "days even once the strike is resolved. We recommend diverting urgent cargo to the Port of "
            "Seattle as an alternative.\n\n"
            "We will keep you updated every 24 hours.\n\n"
            "Pacific Freight Partners"
        ),
    },
    {
        "from_name": "SteelBridge Manufacturing",
        "from_addr": "emergency@steelbridge-fake.com",
        "subject": "Factory Fire — Production Halted at Facility 3",
        "body": (
            "EMERGENCY NOTICE\n\n"
            "A fire broke out in Facility 3 of our Guangzhou plant at 02:30 local time. Emergency "
            "services have contained the blaze but the facility has sustained significant structural "
            "damage. All production at Facility 3 is halted indefinitely.\n\n"
            "Facility 3 accounted for 40% of your monthly order volume. We are assessing whether "
            "Facilities 1 and 2 can absorb the additional load. An update will follow within 48 hours.\n\n"
            "SteelBridge Emergency Response Team"
        ),
    },
    {
        "from_name": "TechSource Semiconductors",
        "from_addr": "security@techsource-fake.com",
        "subject": "Cyberattack — Systems Partially Restored",
        "body": (
            "Dear Partners,\n\n"
            "TechSource Semiconductors was the target of a ransomware cyberattack on April 20th. "
            "Our ERP and order management systems were taken offline as a precautionary measure.\n\n"
            "Core manufacturing systems have been restored, however order processing and shipment "
            "tracking remain limited. Expect delays of 5–8 business days on all pending shipments "
            "while we complete forensic investigation and system restoration.\n\n"
            "We apologise for the disruption and are working around the clock to restore full service.\n\n"
            "TechSource IT Security Team"
        ),
    },
    {
        "from_name": "Global Logistics Express",
        "from_addr": "updates@globallogistics-fake.com",
        "subject": "Export Ban — Rare Earth Minerals (Trade Advisory)",
        "body": (
            "Trade Advisory — Immediate Action Required\n\n"
            "Effective immediately, the Ministry of Commerce has implemented an export ban on "
            "rare earth minerals including neodymium, dysprosium, and terbium. This follows "
            "escalating trade tensions and new sanction measures.\n\n"
            "Shipments currently in transit may be held at customs. We advise immediate review of "
            "your rare earth mineral inventory levels and sourcing strategy.\n\n"
            "Our trade compliance team is available 24/7 to assist.\n\n"
            "Global Logistics Express — Trade Compliance Division"
        ),
    },
    {
        "from_name": "Meridian Chemicals",
        "from_addr": "supply@meridianchemicals-fake.com",
        "subject": "Price Increase Notice — Chemical Feedstocks Q3 2026",
        "body": (
            "Dear Customer,\n\n"
            "Due to rising energy costs and feedstock shortages, Meridian Chemicals will be "
            "implementing a 12% price increase on all polymer-grade chemical feedstocks effective "
            "July 1, 2026.\n\n"
            "We understand the impact this has on your supply chain planning and are happy to "
            "offer volume-locked pricing for customers who commit to Q3 and Q4 orders before May 15.\n\n"
            "Please contact your account manager to lock in current rates.\n\n"
            "Meridian Chemicals Sales Team"
        ),
    },
    {
        "from_name": "Yangtze River Transport",
        "from_addr": "ops@yangtzeriver-fake.com",
        "subject": "Flood Warning — River Operations Suspended",
        "body": (
            "Urgent — Operational Advisory\n\n"
            "Severe flooding along the Yangtze River has forced the suspension of all barge "
            "operations between Chongqing and Wuhan. Water levels are 4.2 metres above the "
            "seasonal average following record rainfall.\n\n"
            "All inland waterway shipments are on hold. Cargo currently in transit is being held "
            "at Wuhan staging area. We expect operations to resume in 10–14 days pending water "
            "levels receding to safe navigation levels.\n\n"
            "Weather alert status: RED\n\n"
            "Yangtze River Transport Operations"
        ),
    },
    {
        "from_name": "BrightPower Electronics",
        "from_addr": "logistics@brightpower-fake.com",
        "subject": "Late Shipment Advisory — Order BP-7721",
        "body": (
            "Hi,\n\n"
            "We wanted to proactively notify you that Order BP-7721 (PCB assemblies, 2,500 units) "
            "will arrive approximately 4 days later than originally scheduled.\n\n"
            "The delay is due to a late shipment of capacitors from our sub-supplier in Vietnam, "
            "which has created a backlog on our production line. The order is now 85% complete and "
            "we expect to dispatch on Thursday.\n\n"
            "We apologise for any inconvenience this may cause.\n\n"
            "BrightPower Electronics Logistics"
        ),
    },
    {
        "from_name": "Apex Raw Materials",
        "from_addr": "trading@apexrawmaterials-fake.com",
        "subject": "Critical Shortage — Steel Coil Availability Q2",
        "body": (
            "Market Alert,\n\n"
            "We are issuing a critical shortage warning for hot-rolled steel coils. Global steel "
            "production has been impacted by simultaneous plant shutdowns in South Korea and Germany, "
            "reducing available supply by an estimated 18%.\n\n"
            "Current lead times have extended from 6 weeks to 14–16 weeks. Spot prices have "
            "increased by 23% month-on-month. We recommend securing forward contracts immediately "
            "if steel coils are critical to your production schedule.\n\n"
            "Apex Raw Materials Trading Desk"
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
    parser = argparse.ArgumentParser(description="Send fake supply chain disruption emails.")
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
            print(f"✅  Connected. Sending {len(emails_to_send)} fake emails to {GMAIL_USER}\n")

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
                    print(f"  [{i}/{len(emails_to_send)}] ✉️  Sent: {email_data['subject'][:60]}")
                    if i < len(emails_to_send):
                        time.sleep(args.delay)
                except Exception as e:
                    print(f"  [{i}/{len(emails_to_send)}] ❌  Failed: {e}")

        print(f"\n🎉  Done! {len(emails_to_send)} emails sent to {GMAIL_USER}.")
        print("     Now go to your dashboard → Settings → Live Gmail Inbox → Ingest Data!\n")

    except smtplib.SMTPAuthenticationError:
        print("❌  Authentication failed. Make sure GMAIL_APP_PASSWORD is a valid 16-char App Password.")
    except Exception as e:
        print(f"❌  SMTP error: {e}")


if __name__ == "__main__":
    main()
