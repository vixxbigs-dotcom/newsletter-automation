import json
import re
from collections import Counter
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


STOPWORDS = {
    "그리고", "그러나", "하지만", "또한", "있는", "없는", "통해", "위해", "대한", "관련",
    "이번", "지난", "최근", "이런", "저런", "하는", "했다", "한다", "있다", "된다",
    "뉴스", "기사", "사진", "출처", "홈", "메일전송", "공유하기", "스크랩하기",
    "페이스북", "트위터", "네이버", "블로그", "프린트하기", "글자확대", "글자축소",
    "login", "join", "update", "home"
}


def clean_text(text):
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)
    return text.strip()


def make_short_summary(text, max_len=180):
    text = clean_text(text)

    remove_patterns = [
        "Login Join",
        "사람이 희망!",
        "인적자원을 디자인 하라!",
        "페이스북 공유하기",
        "트위터 공유하기",
        "스크랩하기",
        "프린트하기",
        "이메일보내기",
        "글자확대",
        "글자축소",
    ]

    for pattern in remove_patterns:
        text = text.replace(pattern, " ")

    text = clean_text(text)

    if len(text) <= max_len:
        return text

    return text[:max_len].rstrip() + "..."


def extract_keywords(texts, top_n=4):
    merged = " ".join(texts)
    words = re.findall(r"[가-힣A-Za-z0-9]{2,}", merged)

    cleaned = []
    for word in words:
        word = word.strip().lower()

        if word in STOPWORDS:
            continue

        if len(word) < 2:
            continue

        cleaned.append(word)

    counter = Counter(cleaned)
    keywords = [word for word, _ in counter.most_common(top_n)]

    return keywords or ["HRD", "교육", "온보딩"]


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

    return {
        "title": title,
        "url": url,
        "thumbnail": "",
        "image_url": image_url,
        "summary": make_short_summary(body),
        "raw_text": body
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
    raw_texts = []

    for url in urls:
        try:
            article = fetch_article(url)
            raw_texts.append(article.get("raw_text", ""))
            article.pop("raw_text", None)
            source_articles.append(article)
            print(f"기사 수집 완료: {article['title']}")
        except Exception as e:
            print(f"기사 수집 실패: {url} / {e}")

    keyword_tags = extract_keywords(raw_texts, top_n=4)

    new_newsletter = {
        "id": newsletter_id,
        "issue": source_data.get("issue", "HRD Trend Newsletter"),
        "category": source_data.get("category", "신입사원 교육"),
        "title": source_data.get("title", "뉴스레터 제목을 입력하세요"),
        "date": source_data.get("date", datetime.now().strftime("%Y.%m.%d")),
        "read_time": source_data.get("read_time", "5분 뉴스"),
        "hero_image": source_data.get("hero_image", "assets/banners/onboarding-001-banner.png"),
        "summary": source_data.get(
            "summary",
            "기사 4개를 바탕으로 작성할 뉴스레터 한 줄 요약을 입력하세요."
        ),
        "insight_title": source_data.get("insight_title", "🔎 HRD 인사이트"),
        "insight": source_data.get(
            "insight",
            "수집된 기사들을 바탕으로 HRD 인사이트를 입력하세요."
        ),
        "key_points": source_data.get(
            "key_points",
            [
                "🤖 주요 기사에서 반복적으로 등장하는 변화 흐름을 정리해보세요.",
                "🤝 교육 대상자에게 필요한 경험과 역량을 연결해보세요.",
                "🏢 현업 적용 가능성이 높은 교육 설계 포인트를 도출해보세요."
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
                "교육 기획 포인트 1",
                "교육 기획 포인트 2",
                "교육 기획 포인트 3"
            ]
        ),
        "tags": source_data.get("tags", keyword_tags)
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