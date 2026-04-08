"""
send_email.py
Sends the acquisition report as an email with a file attachment.
Mirrors the style of the Econ Newsletter emailer.
"""
import os
import smtplib
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


def _build_html_body(num_deals: int, acquirers: list[str], run_date: str) -> str:
    acquirer_list = "".join(f"<li>{a}</li>" for a in acquirers)
    return f"""
    <html><body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: auto;">
      <h2 style="color: #1F3864;">🔎 Acquisition Tracker Report</h2>
      <p style="color: #555;">Run date: <strong>{run_date}</strong></p>
      <hr style="border: 1px solid #eee;">
      <p>Found <strong>{num_deals} new deal(s)</strong> across the following acquirers:</p>
      <ul>{acquirer_list}</ul>
      <p>The full report is attached as a spreadsheet.</p>
      <hr style="border: 1px solid #eee;">
      <p style="font-size: 12px; color: #999;">
        Generated automatically by Acquisition Tracker ·
        <a href="https://github.com" style="color: #999;">GitHub Actions</a>
      </p>
    </body></html>
    """


def send_email_report(
    attachment_data: bytes | str,
    attachment_filename: str,
    num_deals: int,
    acquirers: list[str],
    subject: str = "🔎 Software Acquisition Tracker Report",
    extra_recipients: list[str] | None = None,
) -> bool:
    """
    Send the acquisition report as an email with the XLSX/CSV attached.
    Matches the credential pattern from the Econ Newsletter emailer.
    """
    sender_email = os.getenv("EMAIL")
    sender_password = os.getenv("EMAIL_PASSWORD")

    if not sender_email or not sender_password:
        print("✗ EMAIL or EMAIL_PASSWORD not found in environment.")
        return False

    recipients = [sender_email]
    if extra_recipients:
        recipients.extend(extra_recipients)

    run_date = datetime.utcnow().strftime("%Y-%m-%d")

    # Build message
    message = MIMEMultipart()
    message["Subject"] = subject
    message["From"] = sender_email
    message["To"] = ", ".join(recipients)

    # HTML body
    html_body = _build_html_body(num_deals, acquirers, run_date)
    message.attach(MIMEText(html_body, "html", "utf-8"))

    # Attachment
    part = MIMEBase("application", "octet-stream")
    if isinstance(attachment_data, str):
        part.set_payload(attachment_data.encode("utf-8"))
    else:
        part.set_payload(attachment_data)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{attachment_filename}"')
    message.attach(part)

    try:
        print("Connecting to Gmail SMTP server...")
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()

        print("Logging in...")
        server.login(sender_email, sender_password)

        print(f"Sending email to {', '.join(recipients)}...")
        server.send_message(message)
        server.quit()

        print(f"✓ Email sent successfully to {', '.join(recipients)}!")
        return True

    except Exception as e:
        print(f"✗ Error sending email: {str(e)}")
        return False
