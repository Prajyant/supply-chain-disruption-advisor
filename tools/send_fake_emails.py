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
        "body": "Your order AM-4421 for 5000kg of copper coil has been dispatched from our Shanghai warehouse. Estimated arrival at Port of LA is 14 days. Bill of lading is attached.",
    },
    {
        "from_name": "Zenith Circuits Ltd.",
        "from_addr": "ops@zenithcircuits-fake.com",
        "subject": "Weekly capacity update — Taipei fab running smoothly",
        "body": "Just a quick update: our Taipei fabrication plant is currently running at 95% utilization. We are on track to meet all Q2 delivery commitments with no expected delays.",
    },
    {
        "from_name": "Nova Plastics International",
        "from_addr": "invoicing@novaplastics-fake.com",
        "subject": "Invoice & dispatch notice — 2000kg polymer pellets",
        "body": "Please find attached the invoice for your recent order of industrial polymer pellets. The shipment left our Munich facility this morning via ground transport.",
    },
    {
        "from_name": "Pacific Freight Partners",
        "from_addr": "bookings@pacificfreight-fake.com",
        "subject": "Booking confirmation — Container PFPC-221 (Busan → LA)",
        "body": "Container PFPC-221 has been successfully loaded onto the vessel at Busan Port. Expected transit time is standard. We will notify you of any schedule changes.",
    },
    {
        "from_name": "SteelBridge Manufacturing",
        "from_addr": "production@steelbridge-fake.com",
        "subject": "Production schedule update — 300 steel frames (Guangzhou)",
        "body": "Production of the 300 custom steel frames is progressing as planned at our Guangzhou plant. We expect to complete the batch by next Friday.",
    },
    {
        "from_name": "Meridian Chemicals",
        "from_addr": "sales@meridianchemicals-fake.com",
        "subject": "Q3 pricing confirmed — chemical feedstock from Gujarat",
        "body": "We are pleased to confirm that pricing for our chemical feedstock produced in Gujarat will remain steady through Q3. Your current allocations are guaranteed.",
    },
    {
        "from_name": "Delta Components GmbH",
        "from_addr": "quality@deltacomponents-fake.com",
        "subject": "QC passed — Batch DX-55 thermal sensors ready to ship",
        "body": "Quality control has signed off on the latest batch of DX-55 thermal sensors at our Shenzhen testing facility. Ready for handover to your freight forwarder.",
    },
    {
        "from_name": "BrightPower Electronics",
        "from_addr": "warehouse@brightpower-fake.com",
        "subject": "Component availability confirmed — May order (Ho Chi Minh City)",
        "body": "We have secured the necessary raw materials for your May production run at our Ho Chi Minh City plant. All components are allocated.",
    },
    {
        "from_name": "EuroLogistics",
        "from_addr": "dispatch@eurologistics-fake.com",
        "subject": "Logistics update — Fleet maintenance completed at Rotterdam depot",
        "body": "Routine maintenance on our European trucking fleet has concluded at the Rotterdam depot. Normal scheduling capacity resumes tomorrow.",
    },
    {
        "from_name": "Aussie Minerals",
        "from_addr": "contracts@aussieminerals-fake.com",
        "subject": "Supply contract renewed — 5-year agreement for lithium",
        "body": "We are thrilled to sign the 5-year lithium supply contract with you. The first quarterly extraction from our Perth site is scheduled for next month.",
    },
    {
        "from_name": "MicroTech Solutions",
        "from_addr": "inventory@microtech-fake.com",
        "subject": "Inventory snapshot — 50,000 units ready in Manila",
        "body": "As requested, here is the current inventory snapshot. We have 50,000 units of the logic board sitting securely in our Manila warehouse awaiting your dispatch orders.",
    },
    {
        "from_name": "EcoPack Industries",
        "from_addr": "sourcing@ecopack-fake.com",
        "subject": "Sourcing change — transitioning packaging supplier",
        "body": "We are transitioning our cardboard sourcing from our previous Jakarta partner to a new local supplier. This should not affect our delivery timelines to your facilities.",
    },
    {
        "from_name": "Global Freight Forwarders",
        "from_addr": "customs@globalfreight-fake.com",
        "subject": "Customs clearance — Air freight batch cleared at Heathrow",
        "body": "Good news. The high-priority air freight batch has cleared UK customs at Heathrow without any duties held. It will be out for last-mile delivery this afternoon.",
    },
    {
        "from_name": "MexiFab",
        "from_addr": "onboarding@mexifab-fake.com",
        "subject": "Supplier onboarding — Initial audit passed in Monterrey",
        "body": "Our new Monterrey facility has passed your initial quality audit. We are ready to begin the pilot production run of 50 units next week as discussed.",
    },
    {
        "from_name": "Midwest Rail",
        "from_addr": "updates@midwestrail-fake.com",
        "subject": "Transit delay — Rail shipment from Chicago delayed",
        "body": "Minor update: The rail cars carrying your automotive parts out of Chicago are currently delayed by approximately 2 days due to standard rail yard congestion.",
    },
    {
        "from_name": "Gulf Metals",
        "from_addr": "supply@gulfmetals-fake.com",
        "subject": "Material shortage warning — Aluminum ingots low",
        "body": "Please be advised that our aluminum ingot stockpile at the Dubai smelter is running lower than usual. We don't anticipate missing your current order, but future orders may face lead times.",
    },
    {
        "from_name": "Texonics",
        "from_addr": "receiving@texonics-fake.com",
        "subject": "Shipment received — 10 pallets arrived in Austin",
        "body": "Confirming that the 10 pallets of resistors from your Shenzhen supplier arrived safely at our Austin assembly plant today. No visible damage to the packaging.",
    },
    {
        "from_name": "Bengal Textiles",
        "from_addr": "orders@bengaltextiles-fake.com",
        "subject": "Order modification — Quantity increased for Q4",
        "body": "We have received your revised PO and updated our systems. The quantity for the Q4 apparel shipment from Dhaka has been increased by 15%.",
    },
    {
        "from_name": "Crystal Glass",
        "from_addr": "qa@crystalglass-fake.com",
        "subject": "Quality alert — Minor variance detected in Mumbai",
        "body": "During spot checks at our Mumbai factory, we noted a minor 2mm thickness variance in the latest batch of glass panels. We are reviewing if this falls within acceptable tolerances.",
    },
    {
        "from_name": "Nippon Parts",
        "from_addr": "notices@nipponparts-fake.com",
        "subject": "Holiday closure notice — Tokyo facility closed for Golden Week",
        "body": "Please remember that our Tokyo facility will be closed entirely next week in observance of the Golden Week holidays. Operations will resume the following Monday.",
    }
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
