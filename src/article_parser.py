import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    )
}


def clean_text(text):
    if not text:
        return ""

    return re.sub(r"\s+", " ", str(text)).strip()


def extract_title(soup):
    og_title = soup.select_one('meta[property="og:title"]')

    if og_title and og_title.get("content"):
        return clean_text(og_title["content"])

    for selector in ["h1", ".view_title", ".article-title", "title"]:
        node = soup.select_one(selector)

        if node:
            title = clean_text(node.get_text(" ", strip=True))

            if title:
                return title

    return ""


def extract_image_url(soup, article_url):
    selectors = [
        'meta[property="og:image"]',
        'meta[name="twitter:image"]',
    ]

    for selector in selectors:
        node = soup.select_one(selector)

        if node and node.get("content"):
            return urljoin(article_url, node["content"])

    content_image = soup.select_one(
        "#viewContent img, article img, .article_body img"
    )

    if content_image and content_image.get("src"):
        return urljoin(article_url, content_image["src"])

    return ""


def extract_published_date(soup):
    selectors = [
        'meta[property="article:published_time"]',
        'meta[name="article:published_time"]',
        'meta[name="date"]',
        "time",
    ]

    for selector in selectors:
        node = soup.select_one(selector)

        if not node:
            continue

        value = (
            node.get("content")
            or node.get("datetime")
            or node.get_text(" ", strip=True)
        )

        match = re.search(
            r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})",
            clean_text(value),
        )

        if match:
            year, month, day = match.groups()
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    page_text = clean_text(soup.get_text(" ", strip=True))

    patterns = [
        r"기사등록\s*(\d{4})[-./](\d{1,2})[-./](\d{1,2})",
        r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})",
    ]

    for pattern in patterns:
        match = re.search(pattern, page_text)

        if match:
            year, month, day = match.groups()
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    return ""


def remove_unwanted_nodes(node):
    selectors = [
        "script",
        "style",
        "nav",
        "footer",
        "form",
        "button",
        ".share",
        ".sns",
        ".advertisement",
        ".ad",
    ]

    for selector in selectors:
        for unwanted in node.select(selector):
            unwanted.decompose()


def extract_body(soup):
    selectors = [
        "#viewContent",
        ".viewContent",
        ".article-view-content",
        ".article_body",
        ".news_body",
        ".view_cont",
        ".article-content",
        "article",
    ]

    candidates = []

    for selector in selectors:
        node = soup.select_one(selector)

        if not node:
            continue

        remove_unwanted_nodes(node)

        text = clean_text(
            node.get_text(
                " ",
                strip=True,
            )
        )

        if text:
            candidates.append(text)

    if candidates:
        return max(candidates, key=len)

    body = soup.select_one("body")

    if body:
        remove_unwanted_nodes(body)
        return clean_text(body.get_text(" ", strip=True))

    return ""


def remove_site_noise(text):
    noise_phrases = [
        "Login Join",
        "사람이 희망!",
        "인적자원을 디자인 하라!",
        "페이스북 공유하기",
        "트위터 공유하기",
        "구글플러스 공유하기",
        "싸이월드 공유하기",
        "라인 공유하기",
        "네이버블로그 공유하기",
        "네이버밴드 공유하기",
        "네이트온쪽지 공유하기",
        "구글북마크 공유하기",
        "스크랩하기",
        "프린트하기",
        "이메일보내기",
        "글자확대",
        "글자축소",
    ]

    cleaned = text

    for phrase in noise_phrases:
        cleaned = cleaned.replace(phrase, " ")

    return clean_text(cleaned)


def fetch_article(article_url, max_body_length=12000):
    response = requests.get(
        article_url,
        headers=HEADERS,
        timeout=25,
    )
    response.raise_for_status()

    response.encoding = response.apparent_encoding or "utf-8"

    soup = BeautifulSoup(response.text, "html.parser")

    title = extract_title(soup)
    body = remove_site_noise(extract_body(soup))

    if not title:
        raise ValueError("기사 제목을 추출하지 못했습니다.")

    if len(body) < 100:
        raise ValueError(
            "기사 본문이 너무 짧습니다. 로그인 페이지 또는 잘못된 URL일 수 있습니다."
        )

    if len(body) > max_body_length:
        body = body[:max_body_length]

    return {
        "title": title,
        "url": article_url,
        "published_at": extract_published_date(soup),
        "image_url": extract_image_url(soup, article_url),
        "body": body,
        "preview": body[:500] + ("..." if len(body) > 500 else ""),
    }


def fetch_articles(urls):
    articles = []
    failures = []

    for index, url in enumerate(urls, start=1):
        try:
            article = fetch_article(url)
            articles.append(article)
            print(f"기사 {index} 수집 완료: {article['title']}")

        except Exception as error:
            failures.append(
                {
                    "url": url,
                    "error": str(error),
                }
            )
            print(f"기사 {index} 수집 실패: {url} / {error}")

    return articles, failures