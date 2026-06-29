import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

import yaml


BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_PATH = BASE_DIR / "config" / "email_config.yaml"
EMAIL_HTML_PATH = BASE_DIR / "output" / "newsletter_email.html"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_email_html():
    with open(EMAIL_HTML_PATH, "r", encoding="utf-8") as f:
        return f.read()


def send_email(subject=None):
    config = load_config()
    html = load_email_html()

    sender_email = config["sender_email"]
    sender_password = config["sender_password"]
    receiver_email = config["receiver_email"]

    msg = EmailMessage()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = subject or "HRD Radar 뉴스레터"
    msg.set_content("HTML을 지원하는 메일 클라이언트에서 확인해주세요.")
    msg.add_alternative(html, subtype="html")

    context = ssl.create_default_context()

    with smtplib.SMTP(config["smtp_server"], config["smtp_port"]) as server:
        server.starttls(context=context)
        server.login(sender_email, sender_password)
        server.send_message(msg)

    print(f"메일 발송 완료: {receiver_email}")


if __name__ == "__main__":
    send_email()