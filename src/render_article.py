import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_PATH = BASE_DIR / "data" / "newsletters.json"
TEMPLATE_PATH = BASE_DIR / "templates" / "article.html"
OUTPUT_DIR = BASE_DIR / "output" / "articles"


def load_newsletters():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def article_asset_path(path):
    """
    article html은 output/articles/ 안에 생성됨.
    따라서 assets 경로는 ../assets/... 로 접근해야 함.
    """
    if not path:
        return ""

    if path.startswith("http"):
        return path

    path = path.replace("\\", "/")

    if path.startswith("../assets/"):
        return path

    if path.startswith("../../assets/"):
        return path.replace("../../assets/", "../assets/")

    if path.startswith("assets/"):
        return f"../{path}"

    return path


def render_list_items(items):
    return "\n".join(f"<li>{item}</li>" for item in items)


def render_tags(tags):
    return "\n".join(f'<span class="tag">#{tag}</span>' for tag in tags)


def render_source_articles(source_articles):
    html = ""

    for article in source_articles:
        thumbnail = article_asset_path(article.get("thumbnail", ""))

        html += f"""
        <a class="source-card" href="{article.get("url", "#")}" target="_blank" rel="noopener noreferrer">
          <div class="source-thumb">
            <img src="{thumbnail}" alt="{article.get("title", "")}" />
          </div>
          <h3>{article.get("title", "")}</h3>
          <p>{article.get("summary", "")}</p>
        </a>
        """

    return html


def render_one_newsletter(newsletter, template):
    html = template

    html = html.replace("{{ title }}", newsletter.get("title", ""))
    html = html.replace("{{ category }}", newsletter.get("category", ""))
    html = html.replace("{{ summary }}", newsletter.get("summary", ""))
    html = html.replace("{{ date }}", newsletter.get("date", ""))
    html = html.replace("{{ read_time }}", newsletter.get("read_time", ""))
    html = html.replace("{{ hero_image }}", article_asset_path(newsletter.get("hero_image", "")))
    html = html.replace("{{ insight_title }}", newsletter.get("insight_title", ""))
    html = html.replace("{{ insight }}", newsletter.get("insight", ""))
    html = html.replace("{{ key_points }}", render_list_items(newsletter.get("key_points", [])))
    html = html.replace("{{ source_articles }}", render_source_articles(newsletter.get("source_articles", [])))
    html = html.replace("{{ conclusion }}", newsletter.get("conclusion", ""))
    html = html.replace("{{ department_apply }}", render_list_items(newsletter.get("department_apply", [])))
    html = html.replace("{{ core_message }}", newsletter.get("core_message", ""))
    html = html.replace("{{ tags }}", render_tags(newsletter.get("tags", [])))

    return html


def render_articles():
    newsletters = load_newsletters()

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for newsletter in newsletters:
        html = render_one_newsletter(newsletter, template)
        output_path = OUTPUT_DIR / f"{newsletter['id']}.html"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"기사 페이지 생성 완료: {output_path}")


if __name__ == "__main__":
    render_articles()