import json
import shutil
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_PATH = BASE_DIR / "data" / "newsletters.json"
TEMPLATE_PATH = BASE_DIR / "templates" / "home.html"
OUTPUT_PATH = BASE_DIR / "output" / "index.html"


def load_newsletters():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_latest_newsletter(newsletters):
    if not newsletters:
        return None

    return max(newsletters, key=lambda item: str(item.get("created_at", item.get("date", ""))))


def home_asset_path(path):
    """
    home html은 output/index.html에 생성됨.
    따라서 assets 경로는 assets/... 로 접근해야 함.
    """
    if not path:
        return ""

    if path.startswith("http"):
        return path

    path = path.replace("\\", "/")
    path = path.replace("../../assets/", "assets/")
    path = path.replace("../assets/", "assets/")

    return path


def create_article_card(newsletter):
    thumbnail = home_asset_path(newsletter.get("hero_image", ""))
    article_url = f"articles/{newsletter['id']}.html"

    image_html = (
        f'<img src="{thumbnail}" alt="{newsletter["title"]}" />'
        if thumbnail
        else '<div class="placeholder-thumb">📰</div>'
    )

    return f"""
        <article class="article-card" onclick="location.href='{article_url}'">
          {image_html}
          <div class="article-category">{newsletter.get("category", "")}</div>
          <h3>{newsletter.get("title", "")}</h3>
          <p>{newsletter.get("summary", "")}</p>
          <div class="article-date">{newsletter.get("date", "")}</div>
        </article>
    """


def create_featured_html(newsletter):
    if not newsletter:
        return ""

    article_url = f"articles/{newsletter['id']}.html"
    hero_image = home_asset_path(newsletter.get("hero_image", ""))

    image_html = (
        f'<img src="{hero_image}" alt="{newsletter["title"]}" />'
        if hero_image
        else '<div class="placeholder-thumb">📰</div>'
    )

    return f"""
      <div class="hero-copy">
        <div class="eyebrow">TODAY'S HRD INSIGHT</div>
        <h1>{newsletter.get("title", "")}</h1>
        <p>{newsletter.get("summary", "")}</p>
        <div class="hero-meta">
          {newsletter.get("category", "")} · {newsletter.get("date", "")} · {newsletter.get("read_time", "")}
        </div>
      </div>

      <div class="hero-image" onclick="location.href='{article_url}'">
        {image_html}
      </div>
    """


def create_category_section(category_name, category_slug, newsletters):
    category_items = [
        item for item in newsletters
        if item.get("category") == category_name
    ]

    if not category_items:
        return ""

    cards_html = "\n".join(create_article_card(item) for item in category_items)

    return f"""
    <section class="section-block category-section" data-category="{category_slug}">
      <div class="section-title-row">
        <h2>{category_name}</h2>
        <a href="#">더보기</a>
      </div>

      <div class="article-grid three">
        {cards_html}
      </div>
    </section>
    """


def render_home():
    newsletters = load_newsletters()
    latest = get_latest_newsletter(newsletters)

    featured_html = create_featured_html(latest)

    recommended = [
        item for item in reversed(newsletters)
        if latest and item.get("id") != latest.get("id")
    ][:4]

    recommended_html = "\n".join(create_article_card(item) for item in recommended)

    categories = {
        "AI/AX 교육": "ai-ax",
        "신입사원 교육": "onboarding",
        "승격자 교육": "promotion",
        "리더 교육": "leadership",
        "조직활성화 교육": "culture",
    }

    category_sections_html = "\n".join(
        create_category_section(category, slug, newsletters)
        for category, slug in categories.items()
    )

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    html = template
    html = html.replace("{{ featured_article }}", featured_html)
    html = html.replace("{{ recommended_articles }}", recommended_html)
    html = html.replace("{{ category_sections }}", category_sections_html)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    assets_src = BASE_DIR / "assets"
    assets_dst = BASE_DIR / "output" / "assets"
    if assets_dst.exists():
        shutil.rmtree(assets_dst)
    if assets_src.exists():
        shutil.copytree(assets_src, assets_dst)

    print(f"홈페이지 생성 완료: {OUTPUT_PATH}")


if __name__ == "__main__":
    render_home()
