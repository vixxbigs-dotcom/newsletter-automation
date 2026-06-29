import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_PATH = BASE_DIR / "data" / "articles.json"
TEMPLATE_PATH = BASE_DIR / "templates" / "home.html"
OUTPUT_PATH = BASE_DIR / "output" / "index.html"


def load_articles():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        articles = json.load(f)

    return [article for article in articles if article.get("published", False)]


def get_featured_article(articles):
    if not articles:
        return None

    return articles[-1]


def create_image_html(article):
    thumbnail = article.get("thumbnail", "")

    if thumbnail:
        return f'<img src="{thumbnail}" alt="{article["title"]}" />'

    return '<div class="placeholder-thumb">📰</div>'


def create_article_card(article):
    return f"""
        <article class="article-card" onclick="location.href='articles/{article["id"]}.html'">
          {create_image_html(article)}
          <div class="article-category">{article.get("category", "")}</div>
          <h3>{article.get("title", "")}</h3>
          <p>{article.get("subtitle", "")}</p>
          <div class="article-date">{article.get("date", "")}</div>
        </article>
    """


def create_featured_html(article):
    if not article:
        return ""

    banner = article.get("banner") or article.get("thumbnail") or ""

    image_html = (
        f'<img src="{banner}" alt="{article["title"]}" />'
        if banner
        else '<div class="placeholder-thumb">📰</div>'
    )

    return f"""
      <div class="hero-copy">
        <div class="eyebrow">TODAY'S HRD INSIGHT</div>
        <h1>{article.get("title", "")}</h1>
        <p>{article.get("subtitle", "")}</p>
        <div class="hero-meta">
          {article.get("category", "")} · {article.get("date", "")} · {article.get("read_time", "")}
        </div>
      </div>

      <div class="hero-image" onclick="location.href='articles/{article["id"]}.html'">
        {image_html}
      </div>
    """


def create_category_section(category_name, articles):
    category_articles = [
        article for article in articles
        if article.get("category") == category_name
    ]

    if not category_articles:
        return ""

    cards_html = "\n".join(create_article_card(article) for article in category_articles[:3])

    return f"""
    <section class="section-block">
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
    articles = load_articles()
    featured_article = get_featured_article(articles)

    featured_html = create_featured_html(featured_article)

    recommended_articles = [
        article for article in articles
        if article.get("id") != featured_article.get("id")
    ][:4]

    recommended_html = "\n".join(
        create_article_card(article) for article in recommended_articles
    )

    categories = [
        "AI/AX 교육",
        "신입사원 교육",
        "승격자 교육",
        "리더 교육",
        "조직활성화 교육",
    ]

    category_sections_html = "\n".join(
        create_category_section(category, articles)
        for category in categories
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

    print(f"홈페이지 생성 완료: {OUTPUT_PATH}")


if __name__ == "__main__":
    render_home()