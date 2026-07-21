from __future__ import annotations

import argparse
import inspect
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.gemini_client import GeminiClient
from src.json_schema import ARTICLE_ANALYSIS_SCHEMA, NEWSLETTER_SCHEMA


BASE_DIR = Path(__file__).resolve().parent.parent
NEWSLETTERS_PATH = BASE_DIR / "data" / "newsletters.json"

REQUEST_TIMEOUT = 20
DEFAULT_RETRY_COUNT = 2
REVIEW_PASS_SCORE = 85

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    )
}


REVIEW_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "score": {
            "type": "INTEGER",
            "description": "뉴스레터 완성도 점수. 0~100",
        },
        "issues": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "수정이 필요한 핵심 문제",
        },
        "newsletter": NEWSLETTER_SCHEMA,
    },
    "required": ["score", "issues", "newsletter"],
}


def _clean_text(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "")
    return value.strip()


def _safe_slug(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^0-9a-z가-힣]+", "-", value)
    return value.strip("-") or "newsletter"


def _load_prompt_module(module_name: str):
    try:
        return __import__(
            f"src.gemini_prompts.{module_name}",
            fromlist=["*"],
        )
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            f"src/gemini_prompts/{module_name}.py 파일을 찾을 수 없습니다."
        ) from exc


def _find_system_prompt(module: Any, module_name: str) -> str:
    prefix = module_name.replace("_prompt", "").upper()

    candidates = [
        f"{prefix}_SYSTEM_PROMPT",
        "SYSTEM_PROMPT",
        "PROMPT",
    ]

    for name in candidates:
        value = getattr(module, name, None)
        if isinstance(value, str) and value.strip():
            return value.strip()

    raise AttributeError(
        f"{module_name}.py에서 시스템 프롬프트를 찾을 수 없습니다. "
        f"{prefix}_SYSTEM_PROMPT 또는 SYSTEM_PROMPT를 정의하세요."
    )


def _find_prompt_builder(module: Any, module_name: str):
    prefix = module_name.replace("_prompt", "")

    candidates = [
        f"build_{prefix}_prompt",
        "build_prompt",
        "get_prompt",
        "create_prompt",
    ]

    for name in candidates:
        builder = getattr(module, name, None)
        if callable(builder):
            return builder

    raise AttributeError(
        f"{module_name}.py에서 프롬프트 생성 함수를 찾을 수 없습니다."
    )


def _build_prompt_from_context(
    builder: Any,
    module_name: str,
    context: dict[str, Any],
) -> str:
    signature = inspect.signature(builder)
    kwargs: dict[str, Any] = {}

    alias_groups = {
        "article_analysis": [
            "article_analysis",
            "analysis",
            "editor_result",
        ],
        "analysis": [
            "analysis",
            "article_analysis",
            "editor_result",
        ],
        "editor_result": [
            "editor_result",
            "analysis",
            "article_analysis",
        ],
        "newsletter": [
            "newsletter",
            "draft",
            "newsletter_draft",
        ],
        "draft": [
            "draft",
            "newsletter",
            "newsletter_draft",
        ],
        "newsletter_draft": [
            "newsletter_draft",
            "draft",
            "newsletter",
        ],
        "feedback": [
            "feedback",
            "reviewer_feedback",
            "issues",
        ],
        "reviewer_feedback": [
            "reviewer_feedback",
            "feedback",
            "issues",
        ],
        "issues": [
            "issues",
            "reviewer_feedback",
            "feedback",
        ],
        "issue": [
            "issue",
            "shared_theme",
            "category",
        ],
        "category": [
            "category",
            "issue",
        ],
        "articles": [
            "articles",
        ],
    }

    missing_parameters = []

    for parameter_name, parameter in signature.parameters.items():
        if parameter_name in context:
            kwargs[parameter_name] = context[parameter_name]
            continue

        aliases = alias_groups.get(parameter_name, [])

        matched = False

        for alias in aliases:
            if alias in context:
                kwargs[parameter_name] = context[alias]
                matched = True
                break

        if matched:
            continue

        if parameter.default is inspect.Parameter.empty:
            missing_parameters.append(parameter_name)

    if missing_parameters:
        raise ValueError(
            f"{module_name}.py의 필수 인자 값이 없습니다: "
            + ", ".join(missing_parameters)
        )

    result = builder(**kwargs)
    return str(result).strip()

def _load_prompt_parts(
    module_name: str,
    context: dict[str, Any],
) -> tuple[str, str]:
    module = _load_prompt_module(module_name)
    system_prompt = _find_system_prompt(module, module_name)
    builder = _find_prompt_builder(module, module_name)
    user_prompt = _build_prompt_from_context(
        builder=builder,
        module_name=module_name,
        context=context,
    )
    return system_prompt, user_prompt


def fetch_article(url: str) -> dict[str, str]:
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(
        ["script", "style", "noscript", "iframe", "svg", "form", "nav", "footer"]
    ):
        tag.decompose()

    title = ""
    og_title = soup.select_one('meta[property="og:title"]')
    if og_title and og_title.get("content"):
        title = _clean_text(og_title["content"])
    elif soup.title:
        title = _clean_text(soup.title.get_text(" ", strip=True))

    thumbnail = ""
    og_image = soup.select_one('meta[property="og:image"]')
    if og_image and og_image.get("content"):
        thumbnail = urljoin(url, og_image["content"].strip())

    published_at = ""
    published_selectors = [
        'meta[property="article:published_time"]',
        'meta[name="article:published_time"]',
        'meta[name="date"]',
        'meta[itemprop="datePublished"]',
    ]
    for selector in published_selectors:
        node = soup.select_one(selector)
        if node and node.get("content"):
            published_at = _clean_text(node["content"])
            break

    selectors = [
        "article",
        ".article-body",
        ".article_body",
        ".article-content",
        ".article_content",
        ".post-content",
        ".post_content",
        ".news-body",
        ".news_body",
        ".view-content",
        ".view_content",
        "#articleBody",
        "#article_body",
        "#content",
        "main",
    ]

    candidates: list[str] = []
    for selector in selectors:
        for node in soup.select(selector):
            text = _clean_text(node.get_text(" ", strip=True))
            if len(text) >= 300:
                candidates.append(text)

    if candidates:
        body = max(candidates, key=len)
    else:
        paragraphs = [
            _clean_text(paragraph.get_text(" ", strip=True))
            for paragraph in soup.find_all("p")
        ]
        body = " ".join(
            paragraph for paragraph in paragraphs if len(paragraph) >= 20
        )

    body = _clean_text(body)

    if len(body) < 200:
        raise ValueError(f"기사 본문을 충분히 추출하지 못했습니다: {url}")

    return {
        "url": url,
        "title": title or url,
        "thumbnail": thumbnail,
        "published_at": published_at,
        "body": body[:18000],
    }


def collect_articles(urls: list[str]) -> list[dict[str, str]]:
    articles: list[dict[str, str]] = []

    cleaned_urls = [url.strip() for url in urls if url.strip()]

    for index, url in enumerate(cleaned_urls, start=1):
        print(f"[{index}/{len(cleaned_urls)}] 기사 수집: {url}")
        articles.append(fetch_article(url))

    if not articles:
        raise ValueError("처리할 기사 URL이 없습니다.")

    return articles


def run_editor(
    client: GeminiClient,
    articles: list[dict[str, str]],
    category: str,
) -> dict[str, Any]:
    system_prompt, user_prompt = _load_prompt_parts(
        "editor_prompt",
        {
            "category": category,
            "articles": articles,
        },
    )

    return client.rewrite_until_valid(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        json_schema=ARTICLE_ANALYSIS_SCHEMA,
        retry=3,
    )


def run_writer(
    client: GeminiClient,
    articles: list[dict[str, str]],
    analysis: dict[str, Any],
    category: str,
    reviewer_feedback: list[str] | None = None,
) -> dict[str, Any]:
    feedback = reviewer_feedback or []

    issue = (
        analysis.get("shared_theme")
        or category
        or "HRD 트렌드"
    )

    system_prompt, user_prompt = _load_prompt_parts(
        "writer_prompt",
        {
            "issue": issue,
            "category": category,
            "articles": articles,
            "analysis": analysis,
            "article_analysis": analysis,
            "editor_result": analysis,
            "reviewer_feedback": feedback,
            "feedback": feedback,
        },
    )

    if feedback:
        user_prompt += (
            "\n\n이전 결과의 수정사항:\n- "
            + "\n- ".join(feedback)
        )

    return client.rewrite_until_valid(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        json_schema=NEWSLETTER_SCHEMA,
        retry=3,
    )


def run_reviewer(
    client: GeminiClient,
    articles: list[dict[str, str]],
    analysis: dict[str, Any],
    newsletter: dict[str, Any],
    category: str,
) -> dict[str, Any]:
    issue = (
        analysis.get("shared_theme")
        or category
        or "HRD 트렌드"
    )

    system_prompt, user_prompt = _load_prompt_parts(
        "reviewer_prompt",
        {
            "issue": issue,
            "category": category,
            "articles": articles,

            "analysis": analysis,
            "article_analysis": analysis,
            "editor_result": analysis,

            "newsletter": newsletter,
            "draft": newsletter,
            "newsletter_draft": newsletter,
        },
    )

    result = client.rewrite_until_valid(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        json_schema=REVIEW_SCHEMA,
        retry=3,
    )

    result["score"] = max(
        0,
        min(100, int(result.get("score", 0))),
    )

    return result

def _normalize_newsletter(
    newsletter: dict[str, Any],
    articles: list[dict[str, str]],
    newsletter_id: str | None = None,
    category: str = "HRD 트렌드",
) -> dict[str, Any]:
    article_summaries = newsletter.get("article_summaries", [])

    normalized_articles: list[dict[str, str]] = []

    for index, source in enumerate(articles):
        summary_item = (
            article_summaries[index]
            if index < len(article_summaries)
            and isinstance(article_summaries[index], dict)
            else {}
        )

        normalized_articles.append(
            {
                "title": summary_item.get("title") or source["title"],
                "summary": summary_item.get("summary", ""),
                "url": source["url"],
                "thumbnail": source.get("thumbnail", ""),
            }
        )

    title = _clean_text(newsletter.get("title", "HRD Radar"))

    generated_id = newsletter_id or (
        f"{_safe_slug(title)[:40]}-"
        f"{datetime.now().strftime('%Y%m%d%H%M%S')}"
    )

    return {
        "id": generated_id,
        "category": category,
        "title": title,
        "summary": newsletter.get("summary", ""),
        "insight": newsletter.get("insight", ""),
        "key_points": newsletter.get("key_points", []),
        "articles": normalized_articles,
        "article_summaries": article_summaries,
        "conclusion": newsletter.get("conclusion", ""),
        "department_apply": newsletter.get("department_apply", []),
        "tags": newsletter.get("tags", []),
        "hero_image": (
            normalized_articles[0]["thumbnail"]
            if normalized_articles
            else ""
        ),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def load_newsletters() -> list[dict[str, Any]]:
    if not NEWSLETTERS_PATH.exists():
        return []

    with NEWSLETTERS_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        return data

    if isinstance(data, dict) and isinstance(data.get("newsletters"), list):
        return data["newsletters"]

    raise ValueError("newsletters.json 형식을 확인하세요.")


def save_newsletter(newsletter: dict[str, Any]) -> None:
    newsletters = load_newsletters()

    existing_index = next(
        (
            index
            for index, item in enumerate(newsletters)
            if item.get("id") == newsletter["id"]
        ),
        None,
    )

    if existing_index is None:
        newsletters.insert(0, newsletter)
    else:
        newsletters[existing_index] = newsletter

    with NEWSLETTERS_PATH.open("w", encoding="utf-8") as file:
        json.dump(
            newsletters,
            file,
            ensure_ascii=False,
            indent=2,
        )


def create_newsletter(
    urls: list[str],
    category: str = "HRD 트렌드",
    newsletter_id: str | None = None,
    retry_count: int = DEFAULT_RETRY_COUNT,
    save: bool = True,
) -> dict[str, Any]:
    articles = collect_articles(urls)
    client = GeminiClient()

    print("[1/3] Editor 분석")
    analysis = run_editor(
        client=client,
        articles=articles,
        category=category,
    )

    print("[2/3] Writer 초안")
    newsletter = run_writer(
        client=client,
        articles=articles,
        analysis=analysis,
        category=category,
    )

    final_review: dict[str, Any] | None = None

    for attempt in range(retry_count + 1):
        print(
            f"[3/3] Reviewer 검수 "
            f"{attempt + 1}/{retry_count + 1}"
        )

        review = run_reviewer(
            client=client,
            articles=articles,
            analysis=analysis,
            newsletter=newsletter,
            category=category,
        )

        final_review = review

        if review["score"] >= REVIEW_PASS_SCORE:
            newsletter = review["newsletter"]
            break

        if attempt < retry_count:
            print(
                f"검수 점수 {review['score']}점. "
                "피드백을 반영해 다시 작성합니다."
            )

            newsletter = run_writer(
                client=client,
                articles=articles,
                analysis=analysis,
                category=category,
                reviewer_feedback=review.get("issues", []),
            )

            time.sleep(1)
        else:
            newsletter = review["newsletter"]

    result = _normalize_newsletter(
        newsletter=newsletter,
        articles=articles,
        newsletter_id=newsletter_id,
        category=category,
    )

    result["_review_score"] = (
        final_review["score"] if final_review else None
    )
    result["_review_issues"] = (
        final_review.get("issues", [])
        if final_review
        else []
    )

    if save:
        persisted = {
            key: value
            for key, value in result.items()
            if not key.startswith("_")
        }

        save_newsletter(persisted)
        print(f"저장 완료: {NEWSLETTERS_PATH}")

    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="기사 URL로 Gemini HRD 뉴스레터를 생성합니다."
    )

    parser.add_argument(
        "urls",
        nargs="*",
        help="기사 URL 목록",
    )

    parser.add_argument(
        "--category",
        default="HRD 트렌드",
        help="뉴스레터 카테고리",
    )

    parser.add_argument(
        "--id",
        dest="newsletter_id",
        default=None,
        help="뉴스레터 ID를 직접 지정",
    )

    parser.add_argument(
        "--retry",
        type=int,
        default=DEFAULT_RETRY_COUNT,
        help="Reviewer 기준 미달 시 재작성 횟수",
    )

    parser.add_argument(
        "--no-save",
        action="store_true",
        help="newsletters.json에 저장하지 않음",
    )

    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    urls = args.urls

    if not urls:
        print(
            "기사 URL을 한 줄에 하나씩 입력하세요. "
            "빈 줄을 입력하면 시작합니다."
        )

        while True:
            value = input("> ").strip()

            if not value:
                break

            urls.append(value)

    try:
        result = create_newsletter(
            urls=urls,
            category=args.category,
            newsletter_id=args.newsletter_id,
            retry_count=max(0, args.retry),
            save=not args.no_save,
        )

    except Exception as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1

    print("\n생성 결과")
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
