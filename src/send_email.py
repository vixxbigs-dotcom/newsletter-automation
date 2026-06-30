import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

import yaml


BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_PATH = BASE_DIR / "config" / "email_config.yaml"
EMAIL_HTML_PATH = BASE_DIR / "output" / "newsletter_email.html"


def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError("config/email_config.yaml 파일이 없습니다.")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_email_html():
    if not EMAIL_HTML_PATH.exists():
        raise FileNotFoundError("output/newsletter_email.html 파일이 없습니다.")

    with open(EMAIL_HTML_PATH, "r", encoding="utf-8") as f:
        return f.read()


def send_email(subject=None):
    config = load_config()
    html = load_email_html()

    smtp_server = config["smtp_server"]
    smtp_port = int(config["smtp_port"])
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

    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(
                smtp_server,
                smtp_port,
                timeout=20,
                context=context
            ) as server:
                server.login(sender_email, sender_password)
                server.send_message(msg)

        else:
            with smtplib.SMTP(
                smtp_server,
                smtp_port,
                timeout=20
            ) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(sender_email, sender_password)
                server.send_message(msg)

        print(f"메일 발송 완료: {receiver_email}")

    except TimeoutError:
        raise TimeoutError(
            "SMTP 서버 연결 시간이 초과되었습니다. "
            "회사 네트워크에서 Gmail SMTP 접속이 차단됐을 가능성이 큽니다. "
            "휴대폰 핫스팟 또는 외부 네트워크에서 다시 시도하세요."
        )


if __name__ == "__main__":
    send_email()