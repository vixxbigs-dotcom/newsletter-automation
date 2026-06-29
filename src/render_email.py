import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_PATH = BASE_DIR / "data" / "newsletters.json"
TEMPLATE_PATH = BASE_DIR / "templates" / "email.html"
OUTPUT_PATH = BASE_DIR / "output" / "newsletter_email.html"

# GitHub Pages 주소로 바꾸기
SITE_URL = "https://vixxbigs-doctom.github.io/newsletter-automation"


def load_newsletters():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_latest_newsletter(newsletters):
    if not newsletters:
        raise ValueError("newsletters.json에 뉴스레터 데이터가 없습니다.")
    return newsletters[-1]


def email_asset_path(path):
    if not path:
        return ""

    if path.startswith("http"):
        return path

    path = path.replace("\\", "/")
    path = path.replace("../../assets/", "assets/")
    path = path.replace("../assets/", "assets/")

    if path.startswith("assets/"):
        return f"{SITE_URL}/{path}"

    return f"{SITE_URL}/{path}"


def render_bullet_items(items):
    html = ""

    for item in items:
        html += f"""
        <div style="margin:8px 0; padding:13px 15px; background:#fff7ef; border:1px solid #ffe0c2; border-radius:10px; font-size:15px; line-height:1.6; color:#222222;">
          {item}
        </div>
        """

    return html


def render_source_articles(source_articles):
    cards = []

    for article in source_articles:
        thumbnail = email_asset_path(article.get("thumbnail", ""))

        card = f"""
        <td width="50%" valign="top" style="padding:0 10px 26px 10px;">
          <a href="{article.get("url", "#")}" target="_blank" style="text-decoration:none; color:#111111;">
            <img src="{thumbnail}" alt="{article.get("title", "")}" width="282" height="159" style="display:block; width:100%; max-width:282px; height:159px; object-fit:cover; border-radius:12px; border:1px solid #eeeeee; margin-bottom:12px;" />
            <h4 style="margin:0 0 9px; font-size:18px; line-height:1.4; color:#111111;">
              {article.get("title", "")}
            </h4>
          </a>
          <p style="margin:0; font-size:14px; line-height:1.65; color:#444444;">
            {article.get("summary", "")}
          </p>
        </td>
        """

        cards.append(card)

    rows = ""

    for i in range(0, len(cards), 2):
        left = cards[i]
        right = cards[i + 1] if i + 1 < len(cards) else '<td width="50%"></td>'

        rows += f"""
        <tr>
          {left}
          {right}
        </tr>
        """

    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
      {rows}
    </table>
    """


def render_email():
    newsletters = load_newsletters()
    newsletter = get_latest_newsletter(newsletters)

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    html = template
    html = html.replace("{{ title }}", newsletter.get("title", ""))
    html = html.replace("{{ category }}", newsletter.get("category", ""))
    html = html.replace("{{ date }}", newsletter.get("date", ""))
    html = html.replace("{{ summary }}", newsletter.get("summary", ""))
    html = html.replace("{{ hero_image }}", email_asset_path(newsletter.get("hero_image", "")))
    html = html.replace("{{ insight_title }}", newsletter.get("insight_title", ""))
    html = html.replace("{{ insight }}", newsletter.get("insight", ""))
    html = html.replace("{{ key_points }}", render_bullet_items(newsletter.get("key_points", [])))
    html = html.replace("{{ source_articles }}", render_source_articles(newsletter.get("source_articles", [])))
    html = html.replace("{{ conclusion }}", newsletter.get("conclusion", ""))
    html = html.replace("{{ department_apply }}", render_bullet_items(newsletter.get("department_apply", [])))
    html = html.replace("{{ core_message }}", newsletter.get("core_message", ""))
    html = html.replace("{{ tags }}", " ".join([f"#{tag}" for tag in newsletter.get("tags", [])]))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"메일 HTML 생성 완료: {OUTPUT_PATH}")


if __name__ == "__main__":
    render_email()