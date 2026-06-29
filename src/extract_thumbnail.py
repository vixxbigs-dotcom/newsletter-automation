import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "newsletters.json"
THUMBNAIL_DIR = BASE_DIR / "assets" / "thumbnails"


HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def slugify(text):
    text = re.sub(r"[^a-zA-Z0-9가-힣_-]", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-").lower()


def get_image_url(article_url):
    response = requests.get(article_url, headers=HEADERS, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    og_image = soup.select_one('meta[property="og:image"]')
    if og_image and og_image.get("content"):
        return urljoin(article_url, og_image["content"])

    twitter_image = soup.select_one('meta[name="twitter:image"]')
    if twitter_image and twitter_image.get("content"):
        return urljoin(article_url, twitter_image["content"])

    first_image = soup.select_one("img")
    if first_image and first_image.get("src"):
        return urljoin(article_url, first_image["src"])

    return None


def download_image(image_url, save_path):
    response = requests.get(image_url, headers=HEADERS, timeout=15)
    response.raise_for_status()

    with open(save_path, "wb") as f:
        f.write(response.content)


def update_newsletters():
    THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        newsletters = json.load(f)

    for newsletter in newsletters:
        newsletter_id = newsletter["id"]

        for index, article in enumerate(newsletter.get("source_articles", []), start=1):
            article_url = article.get("url")

            if not article_url:
                continue

            filename = f"{newsletter_id}-news-{index:02d}.jpg"
            save_path = THUMBNAIL_DIR / filename
            html_path = f"../../assets/thumbnails/{filename}"

            try:
                image_url = get_image_url(article_url)

                if not image_url:
                    print(f"이미지 없음: {article.get('title')}")
                    continue

                download_image(image_url, save_path)
                article["thumbnail"] = html_path

                print(f"썸네일 저장 완료: {filename}")

            except Exception as e:
                print(f"썸네일 추출 실패: {article.get('title')} / {e}")

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(newsletters, f, ensure_ascii=False, indent=2)

    print("newsletters.json 썸네일 경로 업데이트 완료")


if __name__ == "__main__":
    update_newsletters()