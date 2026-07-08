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


def send_email(
    receiver_email,
    subject="HRD Radar 뉴스레터",
    cc_email="",
):
    """
    receiver_email:
        "aaa@gmail.com"
        또는
        "aaa@gmail.com,bbb@gmail.com"

    cc_email:
        "ccc@gmail.com"
        또는
        ""
    """

    config = load_config()
    html = load_email_html()

    smtp_server = config["smtp_server"]
    smtp_port = int(config["smtp_port"])
    sender_email = config["sender_email"]
    sender_password = config["sender_password"]

    msg = EmailMessage()

    msg["From"] = sender_email
    msg["To"] = receiver_email

    if cc_email.strip():
        msg["Cc"] = cc_email

    msg["Subject"] = subject

    msg.set_content("HTML을 지원하는 메일 클라이언트에서 확인해주세요.")
    msg.add_alternative(html, subtype="html")

    context = ssl.create_default_context()

    try:

        if smtp_port == 465:

            with smtplib.SMTP_SSL(
                smtp_server,
                smtp_port,
                timeout=20,
                context=context,
            ) as server:

                server.login(sender_email, sender_password)
                server.send_message(msg)

        else:

            with smtplib.SMTP(
                smtp_server,
                smtp_port,
                timeout=20,
            ) as server:

                server.ehlo()
                server.starttls(context=context)
                server.ehlo()

                server.login(sender_email, sender_password)
                server.send_message(msg)

        print("===================================")
        print("메일 발송 완료")
        print(f"보낸 사람 : {sender_email}")
        print(f"받는 사람 : {receiver_email}")

        if cc_email:
            print(f"참조 : {cc_email}")

        print("===================================")

    except TimeoutError:

        raise TimeoutError(
            "SMTP 서버 연결 시간이 초과되었습니다.\n"
            "회사 네트워크에서 Gmail SMTP 접속이 차단됐을 가능성이 있습니다.\n"
            "휴대폰 핫스팟 또는 외부 네트워크에서 다시 시도해주세요."
        )


if __name__ == "__main__":

    send_email(
        receiver_email="example@gmail.com",
        subject="HRD Radar 테스트 메일",
        cc_email="",
    )