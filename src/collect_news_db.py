import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup


BASE_DIR = Path(__file__).resolve().parent.parent
NEWS_DB_PATH = BASE_DIR / "data" / "news_db.xlsx"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


COLUMNS = [
    "수집일",
    "발행호수",
    "뉴스레터 주제",
    "섹션 구분",
    "키워드",
    "자료 제목",
    "출처",
    "URL",
    "발행일",
    "핵심 내용",
    "HRD 시사점",
    "우리 부서 적용 아이디어",
    "활용 점수",
    "뉴스레터 반영 여부",
    "썸네일 경로",
]


def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def get_article_detail(url):
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    title = ""
    og_title = soup.select_one('meta[property="og:title"]')
    if og_title and og_title.get("content"):
        title = og_title["content"]
    elif soup.title:
        title = soup.title.get_text()

    title = clean_text(title)

    image_url = ""
    og_image = soup.select_one('meta[property="og:image"]')
    if og_image and og_image.get("content"):
        image_url = urljoin(url, og_image["content"])

    body_node = soup.select_one("#viewContent") or soup.select_one("article") or soup.select_one("body")
    body = clean_text(body_node.get_text(" ", strip=True)) if body_node else ""

    summary = body[:220] + "..." if len(body) > 220 else body

    published_at = ""
    date_match = re.search(r"\d{4}-\d{2}-\d{2}", body)
    if date_match:
        published_at = date_match.group(0)

    return {
        "title": title,
        "summary": summary,
        "published_at": published_at,
        "thumbnail": image_url,
    }


def search_khrd(keyword, max_count=10):
    encoded_keyword = quote(keyword)
    search_url = f"https://www.khrd.co.kr/news/search.php?sm=w_total&stx={encoded_keyword}"

    response = requests.get(search_url, headers=HEADERS, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    links = []
    for a in soup.select("a[href*='view.php?idx=']"):
        href = a.get("href")
        if not href:
            continue

        full_url = urljoin(search_url, href)

        if full_url not in links:
            links.append(full_url)

        if len(links) >= max_count:
            break

    return links


def load_news_db():
    if NEWS_DB_PATH.exists():
        return pd.read_excel(NEWS_DB_PATH)

    return pd.DataFrame(columns=COLUMNS)


def save_news_db(df):
    NEWS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(NEWS_DB_PATH, index=False)


def collect_news_to_db(
    newsletter_topic,
    keyword,
    issue="",
    section="",
    source="월간HRD",
    max_count=10,
):
    existing_df = load_news_db()
    existing_urls = set(existing_df["URL"].dropna().astype(str).tolist()) if "URL" in existing_df.columns else set()

    urls = search_khrd(keyword, max_count=max_count)

    rows = []

    for url in urls:
        if url in existing_urls:
            continue

        try:
            detail = get_article_detail(url)

            rows.append({
                "수집일": datetime.now().strftime("%Y-%m-%d"),
                "발행호수": issue,
                "뉴스레터 주제": newsletter_topic,
                "섹션 구분": section,
                "키워드": keyword,
                "자료 제목": detail["title"],
                "출처": source,
                "URL": url,
                "발행일": detail["published_at"],
                "핵심 내용": detail["summary"],
                "HRD 시사점": "",
                "우리 부서 적용 아이디어": "",
                "활용 점수": "",
                "뉴스레터 반영 여부": False,
                "썸네일 경로": detail["thumbnail"],
            })

            print(f"수집 완료: {detail['title']}")

        except Exception as e:
            print(f"수집 실패: {url} / {e}")

    if not rows:
        print("신규 수집 기사 없음")
        return existing_df

    new_df = pd.DataFrame(rows)

    result_df = pd.concat([existing_df, new_df], ignore_index=True)

    for col in COLUMNS:
        if col not in result_df.columns:
            result_df[col] = ""

    result_df = result_df[COLUMNS]
    save_news_db(result_df)

    print(f"news_db.xlsx 저장 완료: {NEWS_DB_PATH}")
    return result_df


if __name__ == "__main__":
    collect_news_to_db(
        newsletter_topic="신입사원 교육",
        keyword="온보딩",
        issue="HRD Trend Newsletter 1호",
        section="뉴스",
        max_count=10,
    )