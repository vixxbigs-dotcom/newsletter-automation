import re
import time
import argparse
import urllib.parse
from pathlib import Path
from datetime import datetime, timedelta

import requests
import pandas as pd
from bs4 import BeautifulSoup


# =====================================================
# 1. 기본 설정
# =====================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
OUTPUT_EXCEL = DATA_DIR / "news_db.xlsx"

RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

ARTICLE_MAX_AGE_YEARS = 2
CUTOFF_DATE = datetime.now() - timedelta(days=ARTICLE_MAX_AGE_YEARS * 365)

REQUEST_SLEEP_SECONDS = 0.8
SUMMARY_MAX_CHARS = 900

CONTENT_DB_COLUMNS = [
    "수집일",
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
    "비고",
]

KEYWORD_ROWS = [
    {"topic": "신입사원 교육 및 온보딩", "keyword": "신입사원 교육"},
    {"topic": "신입사원 교육 및 온보딩", "keyword": "신입교육"},
    {"topic": "신입사원 교육 및 온보딩", "keyword": "신입사원"},
    {"topic": "신입사원 교육 및 온보딩", "keyword": "온보딩"},
    {"topic": "신입사원 교육 및 온보딩", "keyword": "조직사회화"},
    {"topic": "신입사원 교육 및 온보딩", "keyword": "신규입사자"},
    {"topic": "신입사원 교육 및 온보딩", "keyword": "직무적응"},
    {"topic": "신입사원 교육 및 온보딩", "keyword": "현장적응"},
    {"topic": "신입사원 교육 및 온보딩", "keyword": "입문교육"},
    {"topic": "신입사원 교육 및 온보딩", "keyword": "OJT"},
    {"topic": "신입사원 교육 및 온보딩", "keyword": "멘토링"},
    {"topic": "신입사원 교육 및 온보딩", "keyword": "버디 프로그램"},

    {"topic": "신입사원 피드백 및 코칭", "keyword": "피드백"},
    {"topic": "신입사원 피드백 및 코칭", "keyword": "피드백 문화"},
    {"topic": "신입사원 피드백 및 코칭", "keyword": "피드백 리더십"},
    {"topic": "신입사원 피드백 및 코칭", "keyword": "코칭"},
    {"topic": "신입사원 피드백 및 코칭", "keyword": "코칭 리더십"},
    {"topic": "신입사원 피드백 및 코칭", "keyword": "1on1"},
    {"topic": "신입사원 피드백 및 코칭", "keyword": "원온원"},
    {"topic": "신입사원 피드백 및 코칭", "keyword": "심리적 안전감"},

    {"topic": "요즘 신입사원 트렌드", "keyword": "MZ세대 신입사원"},
    {"topic": "요즘 신입사원 트렌드", "keyword": "Z세대 신입사원"},
    {"topic": "요즘 신입사원 트렌드", "keyword": "주니어 직원"},
    {"topic": "요즘 신입사원 트렌드", "keyword": "젊은 직원"},
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    )
}


# =====================================================
# 2. 공통 유틸
# =====================================================

def clean_text(text):
    if not text:
        return ""

    text = str(text).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def looks_broken_korean(text):
    if not text:
        return True

    broken_markers = ["�", "Ã", "Â", "êµ", "í", "ÇÑ", "±¹", "½", "´"]
    return any(marker in text for marker in broken_markers)


def decode_korean_response(response):
    content = response.content

    encodings = [
        "utf-8",
        "cp949",
        "euc-kr",
        response.encoding,
        response.apparent_encoding,
    ]

    cleaned_encodings = []

    for enc in encodings:
        if enc and enc not in cleaned_encodings:
            cleaned_encodings.append(enc)

    best_text = ""

    for enc in cleaned_encodings:
        try:
            text = content.decode(enc, errors="strict")

            if not looks_broken_korean(text):
                return text

            if not best_text:
                best_text = text

        except Exception:
            continue

    if best_text:
        return best_text

    try:
        return content.decode("cp949", errors="replace")
    except Exception:
        return content.decode("utf-8", errors="replace")


def safe_get(url, params=None, timeout=15, korean_decode=False):
    try:
        response = requests.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=timeout,
        )
        response.raise_for_status()

        if korean_decode:
            return decode_korean_response(response)

        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding

        return response.text

    except Exception as e:
        print(f"요청 실패: {url} / {e}")
        return ""


def normalize_url(url):
    if not url:
        return ""

    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)

    if "idx" in query:
        return f"{parsed.netloc}{parsed.path}?idx={query['idx'][0]}"

    match = re.search(r"/article_no/(\d+)", parsed.path)

    if match:
        return f"{parsed.netloc}/article_no/{match.group(1)}"

    return url.strip()


def parse_date(text):
    if not text:
        return None

    text = clean_text(text)

    patterns = [
        r"(\d{4})[-.](\d{1,2})[-.](\d{1,2})",
        r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일",
        r"(\d{4})년\s*(\d{1,2})월",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3)) if len(match.groups()) >= 3 else 1

            try:
                return datetime(year, month, day)
            except ValueError:
                return None

    return None


def is_recent_article(published_text):
    published_date = parse_date(published_text)

    # 발행일 파싱 실패 시 일단 저장 후 사람이 검토
    if published_date is None:
        return True

    return published_date >= CUTOFF_DATE


def extract_issue_date(text):
    if not text:
        return ""

    match = re.search(r"\((\d{4}년\s*\d{1,2}월[^)]*)\)", text)

    if match:
        return clean_text(match.group(1))

    return clean_text(text)


def make_summary_from_body(body_text, max_chars=SUMMARY_MAX_CHARS):
    body_text = clean_text(body_text)

    if not body_text:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+|(?<=다\.)\s+", body_text)
    sentences = [clean_text(sentence) for sentence in sentences if len(clean_text(sentence)) >= 15]

    if not sentences:
        return body_text[:max_chars].strip()

    selected = []
    total_len = 0

    for sentence in sentences:
        if total_len + len(sentence) > max_chars:
            break

        selected.append(sentence)
        total_len += len(sentence)

        if len(selected) >= 6:
            break

    summary = " ".join(selected)

    if not summary:
        summary = body_text[:max_chars]

    return summary[:max_chars].strip()


# =====================================================
# 3. 월간 HRD 본문 추출
# =====================================================

def extract_khrd_core_content(article_url):
    html = safe_get(article_url, korean_decode=True)

    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    view_content = soup.select_one("div#viewContent")

    if not view_content:
        return ""

    for tag in view_content.select("script, style, iframe, img, table.pdf-box, acronym"):
        tag.decompose()

    body_text = view_content.get_text(" ", strip=True)
    body_text = clean_text(body_text)

    if not body_text:
        return ""

    return make_summary_from_body(body_text, SUMMARY_MAX_CHARS)


# =====================================================
# 4. 월간 HRD 수집
# =====================================================

def collect_khrd(keyword_row, max_pages=3, sleep=REQUEST_SLEEP_SECONDS):
    base_url = "https://www.khrd.co.kr"
    search_url = "https://www.khrd.co.kr/news/search.php"

    keyword = keyword_row["keyword"]
    topic = keyword_row["topic"]

    parts = keyword.split()
    stx = parts[0] if parts else keyword
    stx2 = " ".join(parts[1:]) if len(parts) >= 2 else ""

    results = []

    for page in range(1, max_pages + 1):
        params = {
            "sm": "w_total",
            "stx": stx,
            "stx2": stx2,
            "w_section1": "",
            "sdate": "",
            "edate": "",
            "page": page,
        }

        html = safe_get(search_url, params=params, korean_decode=True)

        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        basic_list = soup.select_one("#contents > div.basicList")

        if not basic_list:
            break

        items = basic_list.select("li")

        if not items:
            break

        page_count = 0
        filtered_count = 0
        core_fail_count = 0

        for li in items:
            title_tag = li.select_one("dt.title > a")
            date_tag = li.select_one("dd.registDate")

            if not title_tag:
                continue

            title = clean_text(title_tag.get_text(" ", strip=True))
            href = title_tag.get("href", "")
            url = urllib.parse.urljoin(base_url + "/news/", href.replace("&amp;", "&"))
            published_date = clean_text(date_tag.get_text(" ", strip=True)) if date_tag else ""

            if not is_recent_article(published_date):
                filtered_count += 1
                continue

            if not title or not url:
                continue

            core_content = extract_khrd_core_content(url)

            if not core_content:
                core_fail_count += 1

            results.append({
                "수집일": datetime.now().strftime("%Y-%m-%d"),
                "뉴스레터 주제": topic,
                "섹션 구분": "분류대기",
                "키워드": keyword,
                "자료 제목": title,
                "출처": "월간 HRD",
                "URL": url,
                "발행일": published_date,
                "핵심 내용": core_content,
                "HRD 시사점": "",
                "우리 부서 적용 아이디어": "",
                "활용 점수": "",
                "뉴스레터 반영 여부": "검토",
                "비고": (
                    f"최근 {ARTICLE_MAX_AGE_YEARS}년 이내 / "
                    f"월간HRD 자동수집 후보"
                    + (" / 본문 추출 실패" if not core_content else "")
                ),
            })

            page_count += 1
            time.sleep(sleep)

        print(
            f"[월간HRD] {keyword} / {page}페이지 / "
            f"저장 {page_count}건 / 기간 제외 {filtered_count}건 / 본문 실패 {core_fail_count}건"
        )

        time.sleep(sleep)

    return results


# =====================================================
# 5. DBR 수집
# =====================================================

def collect_dbr(keyword_row, max_pages=3, sleep=REQUEST_SLEEP_SECONDS):
    base_url = "https://dbr.donga.com"
    search_url = "https://dbr.donga.com/search"

    keyword = keyword_row["keyword"]
    topic = keyword_row["topic"]

    results = []

    for page in range(1, max_pages + 1):
        params = {
            "set": "DBR_TOTAL",
            "page": page,
            "sort": "",
            "query": keyword,
            "oldq": "",
            "sno": "",
            "q": keyword,
        }

        html = safe_get(search_url, params=params)

        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        link_tags = soup.select("a[href*='dbr.donga.com/article/view/'], a[href*='/article/view/']")

        if not link_tags:
            break

        page_count = 0
        filtered_count = 0
        seen_in_page = set()

        for a_tag in link_tags:
            href = a_tag.get("href", "")
            url = urllib.parse.urljoin(base_url, href.replace("&amp;", "&"))

            if "/article/view/" not in url:
                continue

            title_tag = a_tag.select_one("span.title")
            con_tag = a_tag.select_one("span.con")
            date_tag = a_tag.select_one("span.m-date")

            if not title_tag:
                continue

            title = clean_text(title_tag.get_text(" ", strip=True))
            summary = clean_text(con_tag.get_text(" ", strip=True)) if con_tag else ""
            m_date = clean_text(date_tag.get_text(" ", strip=True)) if date_tag else ""
            issue_date = extract_issue_date(m_date)

            if not is_recent_article(issue_date):
                filtered_count += 1
                continue

            dedup_key = normalize_url(url)

            if dedup_key in seen_in_page:
                continue

            seen_in_page.add(dedup_key)

            if not title or not url:
                continue

            results.append({
                "수집일": datetime.now().strftime("%Y-%m-%d"),
                "뉴스레터 주제": topic,
                "섹션 구분": "분류대기",
                "키워드": keyword,
                "자료 제목": title,
                "출처": "DBR",
                "URL": url,
                "발행일": issue_date,
                "핵심 내용": summary,
                "HRD 시사점": "",
                "우리 부서 적용 아이디어": "",
                "활용 점수": "",
                "뉴스레터 반영 여부": "검토",
                "비고": f"최근 {ARTICLE_MAX_AGE_YEARS}년 이내 / DBR 자동수집 후보",
            })

            page_count += 1

        print(
            f"[DBR] {keyword} / {page}페이지 / "
            f"저장 {page_count}건 / 기간 제외 {filtered_count}건"
        )

        time.sleep(sleep)

    return results


# =====================================================
# 6. 중복 제거 / 기존 DB 비교
# =====================================================

def remove_duplicates(rows):
    unique = []
    seen = set()

    for row in rows:
        url_key = normalize_url(row.get("URL", ""))
        title_key = f"{row.get('출처', '')}|{re.sub(r'\\s+', '', row.get('자료 제목', '')).lower()}"
        key = url_key if url_key else title_key

        if key in seen:
            continue

        seen.add(key)
        unique.append(row)

    return unique


def load_existing_db():
    if not OUTPUT_EXCEL.exists():
        return pd.DataFrame(columns=CONTENT_DB_COLUMNS)

    try:
        return pd.read_excel(OUTPUT_EXCEL, sheet_name="콘텐츠DB")
    except Exception:
        return pd.DataFrame(columns=CONTENT_DB_COLUMNS)


def filter_new_rows(new_rows, existing_df):
    if existing_df.empty:
        return new_rows

    existing_keys = set()

    for _, row in existing_df.iterrows():
        url_key = normalize_url(str(row.get("URL", "")))
        title_key = f"{row.get('출처', '')}|{re.sub(r'\\s+', '', str(row.get('자료 제목', ''))).lower()}"
        existing_keys.add(url_key if url_key else title_key)

    filtered = []

    for row in new_rows:
        url_key = normalize_url(row.get("URL", ""))
        title_key = f"{row.get('출처', '')}|{re.sub(r'\\s+', '', row.get('자료 제목', '')).lower()}"
        key = url_key if url_key else title_key

        if key not in existing_keys:
            filtered.append(row)

    return filtered


# =====================================================
# 7. 저장
# =====================================================

def save_excel(final_df, collected_df, log_df):
    with pd.ExcelWriter(OUTPUT_EXCEL, engine="openpyxl", mode="w") as writer:
        final_df.to_excel(writer, sheet_name="콘텐츠DB", index=False)
        collected_df.to_excel(writer, sheet_name="이번수집", index=False)
        log_df.to_excel(writer, sheet_name="수집로그", index=False)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = RAW_DIR / f"newcomer_news_candidates_{timestamp}.xlsx"

    with pd.ExcelWriter(raw_path, engine="openpyxl", mode="w") as writer:
        collected_df.to_excel(writer, sheet_name="이번수집", index=False)
        log_df.to_excel(writer, sheet_name="수집로그", index=False)

    return raw_path


# =====================================================
# 8. 실행
# =====================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--sources", default="khrd,dbr")
    args = parser.parse_args()

    sources = [s.strip().lower() for s in args.sources.split(",")]

    print("신입사원 HRD 뉴스 수집 시작")
    print(f"키워드 수: {len(KEYWORD_ROWS)}")
    print(f"키워드별 최대 페이지: {args.pages}")
    print(f"수집 출처: {sources}")
    print(f"기간 필터: 최근 {ARTICLE_MAX_AGE_YEARS}년 이내")
    print(f"기준일: {CUTOFF_DATE.strftime('%Y-%m-%d')} 이후 기사만 저장")

    all_rows = []
    log_rows = []

    for keyword_row in KEYWORD_ROWS:
        keyword = keyword_row["keyword"]
        topic = keyword_row["topic"]
        before_count = len(all_rows)

        try:
            if "khrd" in sources:
                all_rows.extend(collect_khrd(keyword_row, max_pages=args.pages))

            if "dbr" in sources:
                all_rows.extend(collect_dbr(keyword_row, max_pages=args.pages))

            collected_count = len(all_rows) - before_count

            log_rows.append({
                "수집일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "검색키워드": keyword,
                "대주제": topic,
                "수집건수": collected_count,
                "오류여부": "N",
                "오류내용": "",
            })

        except Exception as e:
            log_rows.append({
                "수집일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "검색키워드": keyword,
                "대주제": topic,
                "수집건수": 0,
                "오류여부": "Y",
                "오류내용": str(e),
            })

            print(f"키워드 처리 오류: {keyword} / {e}")

    unique_rows = remove_duplicates(all_rows)
    existing_df = load_existing_db()
    new_rows = filter_new_rows(unique_rows, existing_df)

    collected_df = pd.DataFrame(new_rows, columns=CONTENT_DB_COLUMNS)
    log_df = pd.DataFrame(log_rows)

    if existing_df.empty:
        final_df = collected_df
    else:
        final_df = pd.concat([existing_df, collected_df], ignore_index=True)
        final_df = final_df[CONTENT_DB_COLUMNS]

    raw_path = save_excel(final_df, collected_df, log_df)

    print("")
    print("수집 완료")
    print(f"전체 수집 건수: {len(all_rows)}")
    print(f"중복 제거 후: {len(unique_rows)}")
    print(f"기존 DB 제외 신규 추가: {len(new_rows)}")
    print(f"저장 파일: {OUTPUT_EXCEL}")
    print(f"이번 수집 백업: {raw_path}")


if __name__ == "__main__":
    main()