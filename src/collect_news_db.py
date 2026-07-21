import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta


BASE_DIR = Path(__file__).resolve().parent.parent
NEWS_DB_PATH = BASE_DIR / "data" / "news_db.xlsx"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    )
}


COLUMNS = [
    "뉴스레터 반영 여부",
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
    "썸네일 경로",
]


def clean_text(text):
    if not text:
        return ""

    return re.sub(r"\s+", " ", str(text)).strip()


def normalize_title(title):
    """
    기사 제목 비교용 정규화.
    공백과 특수문자를 제거하고 소문자로 변환합니다.
    """
    title = clean_text(title).lower()
    title = re.sub(r"[^0-9a-z가-힣]", "", title)

    return title


def normalize_url(url):
    """
    월간HRD 기사 URL의 검색어, 날짜 등 불필요한 쿼리값을 제거하고
    실제 기사 식별값인 idx만 남깁니다.

    예:
    https://www.khrd.co.kr/news/view.php?idx=5057102&sm=w_total&stx=온보딩
    ->
    https://www.khrd.co.kr/news/view.php?idx=5057102
    """
    if not url:
        return ""

    parsed = urlsplit(str(url).strip())

    query_items = parse_qsl(
        parsed.query,
        keep_blank_values=True,
    )

    useful_query_items = []

    for key, value in query_items:
        if key.lower() == "idx":
            useful_query_items.append(
                (key, value)
            )

    normalized_query = urlencode(
        useful_query_items
    )

    normalized_url = urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            normalized_query,
            "",
        )
    )

    return normalized_url


def parse_date_value(value):
    """
    다양한 날짜 문자열을 datetime으로 변환합니다.

    지원 형식:
    - 2026-07-13
    - 2026.07.13
    - 2026/07/13
    - 2026년 7월 13일
    """
    if not value:
        return None

    value = clean_text(value)

    patterns = [
        r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})",
        r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            value,
        )

        if not match:
            continue

        year, month, day = map(
            int,
            match.groups(),
        )

        try:
            return datetime(
                year,
                month,
                day,
            )
        except ValueError:
            return None

    return None


def is_within_age_limit(
    published_date,
    max_age_months,
):
    """
    수집 기간 조건을 확인합니다.

    max_age_months:
    - None: 기간 제한 없음
    - 0: 이번 달 기사만
    - 1 이상: 현재 날짜 기준 최근 N개월
    """
    if max_age_months is None:
        return True

    parsed_date = parse_date_value(
        published_date
    )

    # 발행일을 추출하지 못한 기사는 우선 수집합니다.
    # 이후 관리자 화면에서 직접 확인할 수 있습니다.
    if parsed_date is None:
        return True

    now = datetime.now()

    if max_age_months == 0:
        return (
            parsed_date.year == now.year
            and parsed_date.month == now.month
        )

    cutoff_date = now - relativedelta(
        months=max_age_months
    )

    return parsed_date >= cutoff_date


def extract_published_date(
    soup,
    body_text,
):
    """
    메타 태그와 본문에서 발행일을 추출합니다.
    """
    meta_selectors = [
        'meta[property="article:published_time"]',
        'meta[name="article:published_time"]',
        'meta[property="og:regDate"]',
        'meta[name="pubdate"]',
        'meta[name="date"]',
        "time",
    ]

    for selector in meta_selectors:
        node = soup.select_one(selector)

        if not node:
            continue

        value = (
            node.get("content")
            or node.get("datetime")
            or node.get_text(
                " ",
                strip=True,
            )
        )

        parsed_date = parse_date_value(
            value
        )

        if parsed_date:
            return parsed_date.strftime(
                "%Y-%m-%d"
            )

    body_patterns = [
        r"기사등록\s*(\d{4}-\d{2}-\d{2})",
        r"기사등록\s*(\d{4}\.\d{2}\.\d{2})",
        r"기사등록\s*(\d{4}/\d{2}/\d{2})",
        r"기사등록\s*(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)",
        r"(\d{4}-\d{2}-\d{2})",
        r"(\d{4}\.\d{2}\.\d{2})",
        r"(\d{4}/\d{2}/\d{2})",
        r"(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)",
    ]

    for pattern in body_patterns:
        match = re.search(
            pattern,
            body_text,
        )

        if not match:
            continue

        parsed_date = parse_date_value(
            match.group(1)
        )

        if parsed_date:
            return parsed_date.strftime(
                "%Y-%m-%d"
            )

    return ""


def extract_article_body(soup):
    """
    월간HRD 본문 후보 영역에서 가장 긴 텍스트를 선택합니다.
    """
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

        text = clean_text(
            node.get_text(
                " ",
                strip=True,
            )
        )

        if text:
            candidates.append(text)

    if candidates:
        return max(
            candidates,
            key=len,
        )

    body_node = soup.select_one("body")

    if body_node:
        return clean_text(
            body_node.get_text(
                " ",
                strip=True,
            )
        )

    return ""


def make_summary(
    body,
    max_length=300,
):
    """
    기사 본문 일부를 뉴스 DB용 핵심 내용으로 정리합니다.
    """
    remove_phrases = [
        "Login Join",
        "사람이 희망!",
        "인적자원을 디자인 하라!",
        "HOME 기사 메일전송",
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

    cleaned_body = body

    for phrase in remove_phrases:
        cleaned_body = cleaned_body.replace(
            phrase,
            " ",
        )

    cleaned_body = clean_text(
        cleaned_body
    )

    if len(cleaned_body) <= max_length:
        return cleaned_body

    return (
        cleaned_body[:max_length].rstrip()
        + "..."
    )


def get_article_detail(url):
    """
    기사 상세 페이지에서 제목, 발행일, 본문 요약, 대표 이미지를 추출합니다.
    """
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=20,
    )

    response.raise_for_status()

    response.encoding = (
        response.apparent_encoding
        or "utf-8"
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    title = ""

    og_title = soup.select_one(
        'meta[property="og:title"]'
    )

    if (
        og_title
        and og_title.get("content")
    ):
        title = og_title["content"]

    if not title:
        title_node = soup.select_one(
            "h1"
        )

        if title_node:
            title = title_node.get_text(
                " ",
                strip=True,
            )

    if not title and soup.title:
        title = soup.title.get_text(
            " ",
            strip=True,
        )

    title = clean_text(title)

    image_url = ""

    og_image = soup.select_one(
        'meta[property="og:image"]'
    )

    if (
        og_image
        and og_image.get("content")
    ):
        image_url = urljoin(
            url,
            og_image["content"],
        )

    body_text = extract_article_body(
        soup
    )

    published_at = extract_published_date(
        soup,
        body_text,
    )

    return {
        "title": title,
        "summary": make_summary(body_text),
        "published_at": published_at,
        "thumbnail": image_url,
    }


def search_khrd(
    keyword,
    max_count=10,
):
    """
    월간HRD 검색 결과에서 기사 URL을 수집합니다.

    기간 필터와 중복 제거 과정에서 빠질 수 있으므로
    요청 개수보다 넉넉하게 후보 URL을 수집합니다.
    """
    encoded_keyword = quote(keyword)

    search_urls = [
        (
            "https://www.khrd.co.kr/news/search.php"
            f"?sm=w_total&stx={encoded_keyword}"
        ),
        (
            "https://www.khrd.co.kr/news/list.php"
            f"?sm=w_total&stx={encoded_keyword}"
        ),
    ]

    collected_urls = []
    seen_urls = set()

    target_candidate_count = max(
        max_count * 3,
        max_count,
    )

    for search_url in search_urls:
        try:
            response = requests.get(
                search_url,
                headers=HEADERS,
                timeout=20,
            )

            response.raise_for_status()

            response.encoding = (
                response.apparent_encoding
                or "utf-8"
            )

            soup = BeautifulSoup(
                response.text,
                "html.parser",
            )

            for link in soup.select(
                "a[href*='view.php?idx=']"
            ):
                href = link.get("href")

                if not href:
                    continue

                full_url = urljoin(
                    search_url,
                    href,
                )

                normalized_url = normalize_url(
                    full_url
                )

                if not normalized_url:
                    continue

                if normalized_url in seen_urls:
                    continue

                seen_urls.add(
                    normalized_url
                )

                collected_urls.append(
                    full_url
                )

                if (
                    len(collected_urls)
                    >= target_candidate_count
                ):
                    break

        except requests.RequestException as error:
            print(
                f"검색 페이지 수집 실패: "
                f"{search_url} / {error}"
            )

        if (
            len(collected_urls)
            >= target_candidate_count
        ):
            break

    return collected_urls


def load_news_db():
    """
    기존 news_db.xlsx를 읽고 누락된 컬럼과 불리언 값을 보정합니다.
    """
    if not NEWS_DB_PATH.exists():
        return pd.DataFrame(
            columns=COLUMNS
        )

    try:
        dataframe = pd.read_excel(
            NEWS_DB_PATH
        )
    except Exception:
        return pd.DataFrame(
            columns=COLUMNS
        )

    for column in COLUMNS:
        if column not in dataframe.columns:
            if column == "뉴스레터 반영 여부":
                dataframe[column] = False
            else:
                dataframe[column] = ""

    dataframe["뉴스레터 반영 여부"] = (
        dataframe["뉴스레터 반영 여부"]
        .fillna(False)
        .replace("", False)
        .astype(bool)
    )

    return dataframe[COLUMNS]


def save_news_db(dataframe):
    """
    뉴스 DB 엑셀 파일을 저장합니다.
    """
    NEWS_DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe.to_excel(
        NEWS_DB_PATH,
        index=False,
    )


def collect_news_to_db(
    newsletter_topic,
    keyword,
    issue="",
    section="뉴스",
    source="월간HRD",
    max_count=10,
    max_age_months=12,
):
    """
    월간HRD 기사 검색 결과를 news_db.xlsx에 저장합니다.

    중복 방지 기준:
    1. 정규화한 URL이 같은 경우
    2. 정규화한 기사 제목이 같은 경우
    3. 같은 수집 실행 안에서 중복되는 경우

    반환값:
    - result_df: 전체 뉴스 DB
    - new_count: 신규 저장 기사 수
    """
    if source != "월간HRD":
        raise ValueError(
            "현재 버전에서는 월간HRD만 수집할 수 있습니다."
        )

    if not keyword.strip():
        raise ValueError(
            "검색 키워드를 입력해주세요."
        )

    existing_df = load_news_db()

    existing_normalized_urls = set()
    existing_normalized_titles = set()

    if "URL" in existing_df.columns:
        for existing_url in (
            existing_df["URL"]
            .dropna()
            .astype(str)
        ):
            normalized_url = normalize_url(
                existing_url
            )

            if normalized_url:
                existing_normalized_urls.add(
                    normalized_url
                )

    if "자료 제목" in existing_df.columns:
        for existing_title in (
            existing_df["자료 제목"]
            .dropna()
            .astype(str)
        ):
            normalized_title = normalize_title(
                existing_title
            )

            if normalized_title:
                existing_normalized_titles.add(
                    normalized_title
                )

    candidate_urls = search_khrd(
        keyword=keyword,
        max_count=max_count,
    )

    new_rows = []

    current_run_urls = set()
    current_run_titles = set()

    skipped_duplicate_count = 0
    skipped_age_count = 0
    failed_count = 0

    for article_url in candidate_urls:
        if len(new_rows) >= max_count:
            break

        normalized_url = normalize_url(
            article_url
        )

        if not normalized_url:
            skipped_duplicate_count += 1
            continue

        if (
            normalized_url
            in existing_normalized_urls
            or normalized_url
            in current_run_urls
        ):
            skipped_duplicate_count += 1
            continue

        try:
            detail = get_article_detail(
                article_url
            )

        except Exception as error:
            failed_count += 1

            print(
                f"수집 실패: "
                f"{article_url} / {error}"
            )

            continue

        normalized_title = normalize_title(
            detail["title"]
        )

        if not normalized_title:
            failed_count += 1
            continue

        if (
            normalized_title
            in existing_normalized_titles
            or normalized_title
            in current_run_titles
        ):
            skipped_duplicate_count += 1
            continue

        if not is_within_age_limit(
            detail["published_at"],
            max_age_months,
        ):
            skipped_age_count += 1

            print(
                f"기간 제외: "
                f"{detail['published_at']} / "
                f"{detail['title']}"
            )

            continue

        new_rows.append(
            {
                "뉴스레터 반영 여부": False,
                "수집일": datetime.now().strftime(
                    "%Y-%m-%d"
                ),
                "발행호수": issue,
                "뉴스레터 주제": newsletter_topic,
                "섹션 구분": section or "뉴스",
                "키워드": keyword,
                "자료 제목": detail["title"],
                "출처": source,
                "URL": article_url,
                "발행일": detail["published_at"],
                "핵심 내용": detail["summary"],
                "HRD 시사점": "",
                "우리 부서 적용 아이디어": "",
                "활용 점수": "",
                "썸네일 경로": detail["thumbnail"],
            }
        )

        existing_normalized_urls.add(
            normalized_url
        )

        existing_normalized_titles.add(
            normalized_title
        )

        current_run_urls.add(
            normalized_url
        )

        current_run_titles.add(
            normalized_title
        )

        print(
            f"수집 완료: "
            f"{detail['title']}"
        )

    if not new_rows:
        print("신규 수집 기사 없음")
        print(
            f"중복 제외: "
            f"{skipped_duplicate_count}건"
        )
        print(
            f"기간 제외: "
            f"{skipped_age_count}건"
        )
        print(
            f"수집 실패: "
            f"{failed_count}건"
        )

        return existing_df, 0

    new_df = pd.DataFrame(
        new_rows
    )

    result_df = pd.concat(
        [
            existing_df,
            new_df,
        ],
        ignore_index=True,
    )

    for column in COLUMNS:
        if column not in result_df.columns:
            if column == "뉴스레터 반영 여부":
                result_df[column] = False
            else:
                result_df[column] = ""

    result_df["뉴스레터 반영 여부"] = (
        result_df["뉴스레터 반영 여부"]
        .fillna(False)
        .replace("", False)
        .astype(bool)
    )

    result_df = result_df[COLUMNS]

    save_news_db(
        result_df
    )

    print(
        f"신규 기사 저장: "
        f"{len(new_rows)}건"
    )

    print(
        f"중복 제외: "
        f"{skipped_duplicate_count}건"
    )

    print(
        f"기간 제외: "
        f"{skipped_age_count}건"
    )

    print(
        f"수집 실패: "
        f"{failed_count}건"
    )

    print(
        f"news_db.xlsx 저장 완료: "
        f"{NEWS_DB_PATH}"
    )

    return result_df, len(new_rows)


if __name__ == "__main__":
    collect_news_to_db(
        newsletter_topic="신입사원 교육",
        keyword="온보딩",
        issue="HRD Trend Newsletter 1호",
        section="뉴스",
        source="월간HRD",
        max_count=10,
        max_age_months=12,
    )