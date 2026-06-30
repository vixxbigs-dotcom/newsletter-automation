import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_DIR = Path(__file__).resolve().parent.parent

SOURCE_URLS_PATH = BASE_DIR / "data" / "source_urls.json"
NEWSLETTERS_PATH = BASE_DIR / "data" / "newsletters.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def clean_text(text):
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_article(url):
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    title = ""

    og_title = soup.select_one('meta[property="og:title"]')
    if og_title and og_title.get("content"):
        title = og_title["content"]

    if not title and soup.title:
        title = soup.title.get_text()

    title = clean_text(title)

    image_url = ""

    og_image = soup.select_one('meta[property="og:image"]')
    if og_image and og_image.get("content"):
        image_url = urljoin(url, og_image["content"])

    body_candidates = []

    for selector in [
        "#viewContent",
        ".viewContent",
        ".article-view-content",
        ".article_body",
        ".news_body",
        "article",
        "body"
    ]:
        node = soup.select_one(selector)
        if node:
            body_candidates.append(node.get_text(" ", strip=True))

    body = max(body_candidates, key=len) if body_candidates else ""
    body = clean_text(body)

    if len(body) > 700:
        preview = body[:700] + "..."
    else:
        preview = body

    return {
        "title": title,
        "url": url,
        "thumbnail": "",
        "image_url": image_url,
        "summary": preview
    }


def load_source_urls():
    with open(SOURCE_URLS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_newsletters():
    if not NEWSLETTERS_PATH.exists():
        return []

    with open(NEWSLETTERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_newsletters(newsletters):
    with open(NEWSLETTERS_PATH, "w", encoding="utf-8") as f:
        json.dump(newsletters, f, ensure_ascii=False, indent=2)


def create_newsletter():
    source_data = load_source_urls()
    newsletters = load_newsletters()

    newsletter_id = source_data.get("newsletter_id")

    if not newsletter_id:
        today = datetime.now().strftime("%Y%m%d")
        newsletter_id = f"newsletter-{today}"

    urls = source_data.get("urls", [])

    if not urls:
        raise ValueError("data/source_urls.json에 urls가 없습니다.")

    source_articles = []

    for url in urls:
        try:
            article = fetch_article(url)
            source_articles.append(article)
            print(f"기사 수집 완료: {article['title']}")
        except Exception as e:
            print(f"기사 수집 실패: {url} / {e}")

    new_newsletter = {
        "id": newsletter_id,
        "issue": source_data.get("issue", "HRD Trend Newsletter"),
        "category": source_data.get("category", "신입사원 교육"),
        "title": source_data.get("title", "뉴스레터 제목을 입력하세요"),
        "date": source_data.get("date", datetime.now().strftime("%Y.%m.%d")),
        "read_time": source_data.get("read_time", "4분 읽기"),
        "hero_image": source_data.get("hero_image", "assets/banners/onboarding-001-banner.png"),
        "summary": source_data.get(
            "summary",
            "기사 4개를 바탕으로 작성할 뉴스레터 한 줄 요약을 입력하세요."
        ),
        "insight_title": source_data.get("insight_title", "🔎 통합되는 인사이트"),
        "insight": source_data.get(
            "insight",
            "수집된 기사들을 바탕으로 통합 인사이트를 입력하세요."
        ),
        "key_points": source_data.get(
            "key_points",
            [
                "🤖 핵심 변화 포인트를 입력하세요.",
                "🤝 HRD 관점의 시사점을 입력하세요.",
                "🏢 우리 부서 적용 관점을 입력하세요."
            ]
        ),
        "source_articles": source_articles,
        "conclusion": source_data.get(
            "conclusion",
            "기사들을 종합한 결론을 입력하세요."
        ),
        "department_apply": source_data.get(
            "department_apply",
            [
                "적용 아이디어 1",
                "적용 아이디어 2",
                "적용 아이디어 3"
            ]
        ),
        "core_message": source_data.get(
            "core_message",
            "핵심 메시지를 입력하세요."
        ),
        "tags": source_data.get(
            "tags",
            ["HRD트렌드", "뉴스레터", "교육기획"]
        )
    }

    newsletters = [
        item for item in newsletters
        if item.get("id") != newsletter_id
    ]

    newsletters.append(new_newsletter)
    save_newsletters(newsletters)

    print(f"newsletters.json 생성/업데이트 완료: {newsletter_id}")


if __name__ == "__main__":
    create_newsletter()