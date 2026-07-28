from pathlib import Path
from datetime import datetime
import json
import os
import subprocess
import sys
import shutil
from src.article_parser import fetch_articles
from src.create_newsletter_with_gemini import create_newsletter
import pandas as pd
import streamlit as st

from src.extract_thumbnail import update_newsletters
from src.render_article import render_articles
from src.render_home import render_home
from src.render_email import render_email
from src.collect_news_db import collect_news_to_db
from src.send_email import send_email


# =========================================================
# 기본 설정
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

SITE_URL = "https://vixxbigs-dotcom.github.io/newsletter-automation"
GITHUB_REPO_URL = "https://github.com/vixxbigs-dotcom/newsletter-automation"
GITHUB_ACTIONS_URL = f"{GITHUB_REPO_URL}/actions"

HOME_PATH = BASE_DIR / "output" / "index.html"
EMAIL_PATH = BASE_DIR / "output" / "newsletter_email.html"
ARTICLE_DIR = BASE_DIR / "output" / "articles"

NEWSLETTERS_PATH = BASE_DIR / "data" / "newsletters.json"
SOURCE_URLS_PATH = BASE_DIR / "data" / "source_urls.json"
RECIPIENTS_PATH = BASE_DIR / "data" / "recipients.json"
NEWS_DB_PATH = BASE_DIR / "data" / "news_db.xlsx"
UPLOAD_IMAGE_DIR = BASE_DIR / "assets" / "uploads"


CATEGORIES = [
    "AI/AX 교육",
    "신입사원 교육",
    "승격자 교육",
    "리더 교육",
    "조직활성화 교육",
    "기타",
]

CATEGORY_PREFIXES = {
    "AI/AX 교육": "ai-ax",
    "신입사원 교육": "onboarding",
    "승격자 교육": "promotion",
    "리더 교육": "leadership",
    "조직활성화 교육": "culture",
    "기타": "etc",
}

AGE_OPTIONS = {
    "이번 달": 0,
    "최근 1개월": 1,
    "최근 3개월": 3,
    "최근 6개월": 6,
    "최근 12개월": 12,
    "최근 24개월": 24,
    "최근 36개월": 36,
    "기간 제한 없음": None,
}


DEFAULT_URLS = """https://www.khrd.co.kr/news/view.php?idx=5057093
https://www.khrd.co.kr/news/view.php?idx=5057102
https://www.khrd.co.kr/news/view.php?idx=5057101
https://www.khrd.co.kr/news/view.php?idx=5056772"""


# =========================================================
# Streamlit 설정
# =========================================================

st.set_page_config(
    page_title="HRD Radar 관리자",
    page_icon="🧡",
    layout="wide",
)

st.title("🧡 HRD Radar 관리자")
st.caption(
    "뉴스 수집 → 뉴스레터 생성 → HTML 미리보기 → "
    "메일 발송 → GitHub Pages 배포"
)


if "newsletter_urls_text" not in st.session_state:
    st.session_state["newsletter_urls_text"] = DEFAULT_URLS


# =========================================================
# 공통 파일 함수
# =========================================================

def read_file(path: Path):
    if path.exists():
        return path.read_text(encoding="utf-8")

    return None


def load_json_file(path: Path, default):
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def save_source_urls(data):
    SOURCE_URLS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    SOURCE_URLS_PATH.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def get_next_newsletter_id(category):
    prefix = CATEGORY_PREFIXES.get(
        category,
        "etc",
    )

    newsletters = load_json_file(
        NEWSLETTERS_PATH,
        [],
    )

    max_number = 0

    for newsletter in newsletters:
        newsletter_id = str(
            newsletter.get("id", "")
        )

        if not newsletter_id.startswith(f"{prefix}-"):
            continue

        suffix = newsletter_id.replace(
            f"{prefix}-",
            "",
            1,
        )

        if suffix.isdigit():
            max_number = max(
                max_number,
                int(suffix),
            )

    return f"{prefix}-{max_number + 1:03d}"


def save_generated_newsletter(newsletter):
    """생성된 뉴스레터를 data/newsletters.json에 저장합니다."""
    NEWSLETTERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    newsletters = load_json_file(NEWSLETTERS_PATH, [])
    if not isinstance(newsletters, list):
        newsletters = []

    clean_newsletter = {
        key: value
        for key, value in newsletter.items()
        if not str(key).startswith("_")
    }

    newsletter_id = str(clean_newsletter.get("id", "")).strip()
    replaced = False

    for index, existing in enumerate(newsletters):
        if str(existing.get("id", "")).strip() == newsletter_id:
            newsletters[index] = clean_newsletter
            replaced = True
            break

    if not replaced:
        newsletters.append(clean_newsletter)

    NEWSLETTERS_PATH.write_text(
        json.dumps(newsletters, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def delete_newsletter(newsletter_id):
    newsletter_id = str(newsletter_id).strip()
    newsletters = load_json_file(NEWSLETTERS_PATH, [])
    remaining = [item for item in newsletters if str(item.get("id", "")).strip() != newsletter_id]
    if len(remaining) == len(newsletters):
        raise ValueError("삭제할 뉴스레터를 찾지 못했습니다.")
    NEWSLETTERS_PATH.write_text(json.dumps(remaining, ensure_ascii=False, indent=2), encoding="utf-8")
    article_path = ARTICLE_DIR / f"{newsletter_id}.html"
    if article_path.exists():
        article_path.unlink()
    return len(remaining)


def update_newsletter(newsletter_id, updates):
    newsletters = load_json_file(NEWSLETTERS_PATH, [])
    if not isinstance(newsletters, list):
        raise ValueError("newsletters.json 형식이 올바르지 않습니다.")

    found = False
    for index, item in enumerate(newsletters):
        if str(item.get("id", "")).strip() == str(newsletter_id).strip():
            updated = dict(item)
            updated.update(updates)
            newsletters[index] = updated
            found = True
            break

    if not found:
        raise ValueError("수정할 뉴스레터를 찾지 못했습니다.")

    NEWSLETTERS_PATH.write_text(
        json.dumps(newsletters, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return newsletters[index]


def save_uploaded_hero_image(uploaded_file, newsletter_id):
    if uploaded_file is None:
        return None

    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("PNG, JPG, JPEG, WEBP 이미지만 업로드할 수 있습니다.")

    UPLOAD_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    target = UPLOAD_IMAGE_DIR / f"{newsletter_id}-hero{suffix}"
    target.write_bytes(uploaded_file.getbuffer())
    return f"assets/uploads/{target.name}"


def split_lines(text):
    return [line.strip() for line in str(text).splitlines() if line.strip()]


def resolve_streamlit_image(image_value):
    """Streamlit 미리보기용 이미지 경로를 안전하게 변환합니다."""
    value = str(image_value or "").strip()
    if not value:
        return None

    if value.startswith(("http://", "https://")):
        return value

    normalized = value.replace("\\", "/")

    candidates = []
    raw_path = Path(normalized)
    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        candidates.extend([
            BASE_DIR / normalized,
            BASE_DIR / normalized.lstrip("./"),
            BASE_DIR / "output" / normalized,
        ])

        if normalized.startswith("../assets/"):
            candidates.append(BASE_DIR / normalized.replace("../assets/", "assets/", 1))
        elif normalized.startswith("../../assets/"):
            candidates.append(BASE_DIR / normalized.replace("../../assets/", "assets/", 1))

    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file():
                return str(candidate.resolve())
        except OSError:
            continue

    return None


def show_streamlit_image(image_value, caption=None, use_container_width=True):
    resolved = resolve_streamlit_image(image_value)
    if resolved:
        st.image(
            resolved,
            caption=caption,
            use_container_width=use_container_width,
        )
        return True

    if str(image_value or "").strip():
        st.caption(
            f"이미지 파일을 찾지 못했습니다: {image_value}"
        )
    return False




# =========================================================
# 뉴스 DB 함수
# =========================================================

def load_news_db():
    if NEWS_DB_PATH.exists():
        return pd.read_excel(NEWS_DB_PATH)

    return pd.DataFrame()


def ensure_news_db_columns(df):
    required_columns = [
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

    for column in required_columns:
        if column not in df.columns:
            if column == "뉴스레터 반영 여부":
                df[column] = False
            else:
                df[column] = ""

    df["뉴스레터 반영 여부"] = (
        df["뉴스레터 반영 여부"]
        .fillna(False)
        .replace("", False)
        .astype(bool)
    )

    return df[required_columns]


def filter_news_db(df):
    filtered_df = df.copy()

    with st.expander(
        "🔎 필터 열기/닫기",
        expanded=False,
    ):
        column1, column2, column3 = st.columns(3)

        with column1:
            keyword_filter = st.text_input(
                "키워드 검색",
                key="news_db_keyword_filter",
            )

        with column2:
            topic_options = ["전체"]

            topics = [
                str(value)
                for value in df["뉴스레터 주제"]
                .dropna()
                .unique()
                if str(value).strip()
            ]

            topic_options += sorted(set(topics))

            selected_topic = st.selectbox(
                "뉴스레터 주제",
                topic_options,
                key="news_db_topic_filter",
            )

        with column3:
            reflect_filter = st.selectbox(
                "뉴스레터 반영 여부",
                ["전체", "반영", "미반영"],
                key="news_db_reflect_filter",
            )

    if keyword_filter:
        searchable_columns = [
            "키워드",
            "자료 제목",
            "핵심 내용",
            "URL",
        ]

        mask = pd.Series(
            False,
            index=filtered_df.index,
        )

        for column in searchable_columns:
            if column not in filtered_df.columns:
                continue

            mask = mask | (
                filtered_df[column]
                .fillna("")
                .astype(str)
                .str.contains(
                    keyword_filter,
                    case=False,
                    na=False,
                )
            )

        filtered_df = filtered_df[mask]

    if selected_topic != "전체":
        filtered_df = filtered_df[
            filtered_df["뉴스레터 주제"]
            .fillna("")
            .astype(str)
            == selected_topic
        ]

    if reflect_filter != "전체":
        boolean_series = (
            filtered_df["뉴스레터 반영 여부"]
            .fillna(False)
            .astype(bool)
        )

        if reflect_filter == "반영":
            filtered_df = filtered_df[boolean_series]
        else:
            filtered_df = filtered_df[~boolean_series]

    return filtered_df


def apply_filtered_edits(original_df, edited_df):
    if "_row_id" not in edited_df.columns:
        return original_df

    updated_df = original_df.copy()

    for _, row in edited_df.iterrows():
        row_id = row["_row_id"]

        if pd.isna(row_id):
            continue

        row_id = int(row_id)

        if row_id not in updated_df.index:
            continue

        for column in edited_df.columns:
            if column == "_row_id":
                continue

            if column in updated_df.columns:
                updated_df.loc[row_id, column] = row[column]

    return updated_df


# =========================================================
# 수신자 함수
# =========================================================

def load_recipients_df():
    data = load_json_file(
        RECIPIENTS_PATH,
        [],
    )

    if not isinstance(data, list):
        data = []

    df = pd.DataFrame(data)

    required_columns = [
        "name",
        "email",
        "group",
        "send",
    ]

    for column in required_columns:
        if column not in df.columns:
            if column == "send":
                df[column] = False
            else:
                df[column] = ""

    df = df[required_columns]

    if df.empty:
        df = pd.DataFrame(
            [
                {
                    "name": "",
                    "email": "",
                    "group": "",
                    "send": False,
                }
            ]
        )

    df["send"] = (
        df["send"]
        .fillna(False)
        .astype(bool)
    )

    return df


def save_recipients_df(df):
    clean_df = df.copy()

    for column in ["name", "email", "group"]:
        clean_df[column] = (
            clean_df[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    clean_df["send"] = (
        clean_df["send"]
        .fillna(False)
        .astype(bool)
    )

    clean_df = clean_df[
        (clean_df["email"] != "")
        | (clean_df["name"] != "")
        | (clean_df["group"] != "")
    ]

    RECIPIENTS_PATH.write_text(
        json.dumps(
            clean_df.to_dict(orient="records"),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def get_selected_recipient_emails():
    df = load_recipients_df()

    selected_df = df[
        (df["send"] == True)
        & (
            df["email"]
            .fillna("")
            .astype(str)
            .str.strip()
            != ""
        )
    ]

    return (
        selected_df["email"]
        .astype(str)
        .str.strip()
        .tolist()
    )


def normalize_email_list(text):
    emails = []

    for item in str(text).replace(",", "\n").splitlines():
        email = item.strip()

        if email:
            emails.append(email)

    return list(dict.fromkeys(emails))


# =========================================================
# 빌드 및 Git 함수
# =========================================================

def run_command(command, timeout=180):
    environment = os.environ.copy()

    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        command,
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=environment,
    )

    output = "\n".join(
        part.strip()
        for part in [
            result.stdout,
            result.stderr,
        ]
        if part and part.strip()
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"명령 실행 실패\n\n"
            f"명령어: {' '.join(map(str, command))}\n\n"
            f"{output}"
        )

    return output


def build_all():
    return run_command(
        [sys.executable, "build.py"],
        timeout=300,
    )


def deploy_to_github(commit_message):
    logs = []

    logs.append("===== 전체 빌드 =====")
    logs.append(build_all())

    branch = run_command(
        ["git", "branch", "--show-current"],
        timeout=30,
    ).strip()

    changes = run_command(
        ["git", "status", "--porcelain"],
        timeout=30,
    ).strip()

    if not changes:
        logs.append("변경사항이 없습니다.")
        return "\n".join(logs), False

    logs.append("===== 변경 파일 =====")
    logs.append(changes)

    run_command(
        ["git", "add", "."],
        timeout=60,
    )

    staged = run_command(
        ["git", "diff", "--cached", "--name-status"],
        timeout=30,
    ).strip()

    if not staged:
        logs.append("커밋할 파일이 없습니다.")
        return "\n".join(logs), False

    logs.append("===== 커밋 파일 =====")
    logs.append(staged)

    logs.append(
        run_command(
            [
                "git",
                "commit",
                "-m",
                commit_message,
            ],
            timeout=60,
        )
    )

    logs.append(
        run_command(
            [
                "git",
                "push",
                "origin",
                branch,
            ],
            timeout=180,
        )
    )

    return "\n".join(logs), True


# =========================================================
# 탭
# =========================================================

(
    tab_home,
    tab_article,
    tab_email,
    tab_db,
    tab_create,
    tab_manage,
) = st.tabs(
    [
        "🏠 홈 미리보기",
        "📄 기사 미리보기",
        "📧 메일 발송",
        "📊 뉴스 DB",
        "📝 뉴스레터 생성",
        "🛠️ 기사 관리",
    ]
)


# =========================================================
# 홈 미리보기
# =========================================================

with tab_home:
    st.subheader("홈페이지 미리보기")

    st.link_button(
        "🌐 새 창에서 홈 보기",
        SITE_URL,
        use_container_width=True,
    )

    st.components.v1.iframe(
        SITE_URL,
        height=900,
        scrolling=True,
    )


# =========================================================
# 기사 미리보기
# =========================================================

with tab_article:
    st.subheader("기사 페이지 미리보기")

    article_files = (
        sorted(ARTICLE_DIR.glob("*.html"))
        if ARTICLE_DIR.exists()
        else []
    )

    if article_files:
        selected_article = st.selectbox(
            "미리볼 기사 선택",
            article_files,
            format_func=lambda path: path.name,
        )

        article_url = (
            f"{SITE_URL}/articles/{selected_article.name}"
        )

        st.link_button(
            "🌐 새 창에서 기사 보기",
            article_url,
            use_container_width=True,
        )

        st.components.v1.iframe(
            article_url,
            height=1200,
            scrolling=True,
        )

    else:
        st.warning("생성된 기사 HTML이 없습니다.")


# =========================================================
# 메일 발송
# =========================================================

with tab_email:
    st.subheader("보낼 기사 선택")

    email_newsletters = load_json_file(NEWSLETTERS_PATH, [])
    email_newsletters = email_newsletters if isinstance(email_newsletters, list) else []

    if not email_newsletters:
        st.warning("발송할 뉴스레터가 없습니다.")
    else:
        email_ids = [
            str(item.get("id", "")).strip()
            for item in email_newsletters
            if str(item.get("id", "")).strip()
        ]

        selected_email_id = st.selectbox(
            "메일로 보낼 기사",
            email_ids,
            format_func=lambda newsletter_id: next(
                (
                    f"{item.get('title', '제목 없음')} "
                    f"({item.get('category', '카테고리 없음')} · {newsletter_id})"
                    for item in email_newsletters
                    if str(item.get("id", "")).strip() == newsletter_id
                ),
                newsletter_id,
            ),
            key="selected_email_newsletter_id",
        )

        if st.button(
            "📧 선택한 기사로 메일 HTML 만들기",
            use_container_width=True,
        ):
            try:
                render_email(newsletter_id=selected_email_id)
                st.success("선택한 기사로 메일 HTML을 생성했습니다.")
                st.rerun()
            except Exception as error:
                st.error(f"메일 HTML 생성 실패: {error}")

        st.subheader("메일 HTML 미리보기")
        email_html = read_file(EMAIL_PATH)

        if email_html:
            st.components.v1.html(email_html, height=850, scrolling=True)
            with open(EMAIL_PATH, "rb") as file:
                st.download_button(
                    "⬇️ 메일 HTML 다운로드",
                    data=file,
                    file_name=f"newsletter_email_{selected_email_id}.html",
                    mime="text/html",
                    use_container_width=True,
                )
        else:
            st.info("위 버튼을 눌러 선택한 기사의 메일 HTML을 생성해주세요.")

        st.divider()
        st.subheader("수신자 표 관리")

        recipients_df = load_recipients_df()
        edited_recipients_df = st.data_editor(
            recipients_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "name": st.column_config.TextColumn("이름"),
                "email": st.column_config.TextColumn("이메일"),
                "group": st.column_config.TextColumn("그룹"),
                "send": st.column_config.CheckboxColumn("발송대상", default=False),
            },
            hide_index=True,
            key="recipient_editor",
        )

        if st.button("💾 수신자 표 저장", use_container_width=True):
            save_recipients_df(edited_recipients_df)
            st.success("수신자 표 저장 완료")
            st.rerun()

        st.divider()
        st.subheader("Gmail 발송")
        selected_emails = get_selected_recipient_emails()
        receiver_email = st.text_area(
            "받는 사람(To)",
            value=", ".join(selected_emails),
            height=90,
        )
        cc_email = st.text_input("참조(CC)")
        selected_email_item = next(
            (item for item in email_newsletters if str(item.get("id", "")).strip() == selected_email_id),
            {},
        )
        subject = st.text_input(
            "메일 제목",
            value=selected_email_item.get("title", "HRD Radar 뉴스레터"),
        )

        if st.button("📤 선택한 기사 Gmail 발송", use_container_width=True):
            to_list = normalize_email_list(receiver_email)
            cc_list = normalize_email_list(cc_email)
            if not to_list:
                st.warning("받는 사람을 입력해주세요.")
            else:
                try:
                    render_email(newsletter_id=selected_email_id)
                    send_email(
                        receiver_email=", ".join(to_list),
                        subject=subject,
                        cc_email=", ".join(cc_list),
                    )
                    st.success(f"메일 발송 완료: {len(to_list)}명")
                except Exception as error:
                    st.error(f"메일 발송 실패: {error}")


# =========================================================
# 뉴스 DB
# =========================================================

with tab_db:
    st.subheader("뉴스 수집")

    with st.form("collect_news_form"):
        column1, column2, column3 = st.columns(3)

        with column1:
            collect_topic = st.selectbox(
                "뉴스레터 주제",
                CATEGORIES,
                key="collect_topic",
            )

            collect_keyword = st.text_input(
                "검색 키워드",
                value="온보딩",
            )

        with column2:
            collect_issue = st.text_input(
                "발행호수",
                value="HRD Trend Newsletter",
            )

            selected_age_label = st.selectbox(
                "수집 기간",
                list(AGE_OPTIONS.keys()),
                index=4,
            )

        with column3:
            st.text_input(
                "출처",
                value="월간HRD",
                disabled=True,
            )

            collect_count = st.number_input(
                "수집 개수",
                min_value=1,
                max_value=30,
                value=10,
            )

        collect_submitted = st.form_submit_button(
            "📰 뉴스 DB에 기사 수집",
            use_container_width=True,
        )

        if collect_submitted:
            try:
                result_df, new_count = collect_news_to_db(
                    newsletter_topic=collect_topic,
                    keyword=collect_keyword,
                    issue=collect_issue,
                    source="월간HRD",
                    max_count=int(collect_count),
                    max_age_months=AGE_OPTIONS[
                        selected_age_label
                    ],
                )

                st.success(
                    f"신규 기사 {new_count}건 수집 완료 · "
                    f"DB 전체 {len(result_df)}건"
                )

            except Exception as error:
                st.error(f"뉴스 수집 실패: {error}")

    st.divider()
    st.subheader("뉴스 DB 미리보기")

    news_df = load_news_db()

    if news_df.empty:
        st.info("수집된 기사가 없습니다.")

    else:
        news_df = ensure_news_db_columns(news_df)
        news_df = news_df.reset_index(drop=True)
        news_df["_row_id"] = news_df.index

        filtered_df = filter_news_db(news_df)

        st.caption(
            f"전체 {len(news_df)}건 중 "
            f"{len(filtered_df)}건 표시"
        )

        edited_news_df = st.data_editor(
            filtered_df,
            num_rows="fixed",
            use_container_width=True,
            column_config={
                "뉴스레터 반영 여부":
                    st.column_config.CheckboxColumn(
                        "뉴스레터 반영 여부",
                        default=False,
                    ),
                "활용 점수":
                    st.column_config.NumberColumn(
                        "활용 점수",
                        min_value=0,
                        max_value=100,
                    ),
                "URL":
                    st.column_config.LinkColumn("URL"),
                "_row_id": None,
            },
            hide_index=True,
            key="news_db_editor",
        )

        if st.button(
            "💾 뉴스 DB 저장",
            use_container_width=True,
        ):
            updated_df = apply_filtered_edits(
                news_df,
                edited_news_df,
            )

            updated_df = updated_df.drop(
                columns=["_row_id"],
                errors="ignore",
            )

            updated_df.to_excel(
                NEWS_DB_PATH,
                index=False,
            )

            st.success("뉴스 DB 저장 완료")
            st.rerun()

        with open(NEWS_DB_PATH, "rb") as file:
            st.download_button(
                "⬇️ news_db.xlsx 다운로드",
                data=file,
                file_name="news_db.xlsx",
                mime=(
                    "application/vnd.openxmlformats-"
                    "officedocument.spreadsheetml.sheet"
                ),
                use_container_width=True,
            )


# =========================================================
# 뉴스레터 생성
# =========================================================

with tab_create:
    st.subheader("뉴스레터 기본 정보 입력")

    selected_category = st.selectbox(
        "카테고리",
        CATEGORIES,
        key="newsletter_category",
    )

    automatic_newsletter_id = get_next_newsletter_id(
        selected_category
    )

    st.text_input(
        "뉴스레터 ID",
        value=automatic_newsletter_id,
        disabled=True,
        help=(
            "선택한 카테고리와 기존 발행 번호를 기준으로 "
            "자동 생성됩니다."
        ),
    )

    with st.form("source_url_form"):
        column1, column2 = st.columns(2)

        with column1:
            title = st.text_input(
                "뉴스레터 제목",
                value="새 뉴스레터 제목",
            )

            summary = st.text_area(
                "한 줄 요약",
                height=100,
            )

        with column2:
            issue = st.text_input(
                "발행호수",
                value="HRD Trend Newsletter",
            )

            publish_date = st.text_input(
                "발행일",
                value=datetime.now().strftime("%Y.%m.%d"),
            )

            st.text_input(
                "읽는 시간",
                value="5분 뉴스",
                disabled=True,
            )

        urls_text = st.text_area(
            "기사 URL 4개 입력",
            key="newsletter_urls_text",
            height=160,
        )

        submitted = st.form_submit_button(
            "💾 URL 및 기본 정보 저장",
            use_container_width=True,
        )

        if submitted:
            urls = [
                line.strip()
                for line in urls_text.splitlines()
                if line.strip()
            ]

            if not urls:
                st.warning("기사 URL을 입력해주세요.")
            else:
                save_source_urls(
                    {
                        "newsletter_id": automatic_newsletter_id,
                        "issue": issue.strip(),
                        "category": selected_category,
                        "title": title.strip(),
                        "date": publish_date.strip(),
                        "read_time": "5분 뉴스",
                        "summary": summary.strip(),
                        "urls": urls,
                    }
                )
                st.session_state["gemini_preview_articles"] = []
                st.session_state["gemini_preview_failures"] = []
                st.success(
                    f"{automatic_newsletter_id} 기본 정보 저장 완료"
                )

    st.divider()
    st.subheader("기사 작성 및 생성")
    st.markdown("### 🔍 기사 원문 확인")

    if st.button(
        "🔍 입력한 URL 기사 원문 불러오기",
        use_container_width=True,
    ):
        source_data = load_json_file(SOURCE_URLS_PATH, {})
        source_urls = source_data.get("urls", [])

        if not source_urls:
            st.warning("먼저 URL 및 기본 정보를 저장해주세요.")
        else:
            try:
                with st.spinner(
                    "기사 제목과 본문을 불러오고 있습니다..."
                ):
                    preview_articles, preview_failures = fetch_articles(
                        source_urls
                    )

                st.session_state["gemini_preview_articles"] = preview_articles
                st.session_state["gemini_preview_failures"] = preview_failures
                st.success(
                    f"기사 {len(preview_articles)}개를 불러왔습니다."
                )
            except Exception as error:
                st.error(f"기사 원문 수집 실패: {error}")

    preview_articles = st.session_state.get(
        "gemini_preview_articles",
        [],
    )
    preview_failures = st.session_state.get(
        "gemini_preview_failures",
        [],
    )

    if preview_failures:
        st.error("일부 기사 본문 수집에 실패했습니다.")
        for failure in preview_failures:
            st.write(f"- {failure['url']}: {failure['error']}")

    if preview_articles:
        for index, article in enumerate(preview_articles, start=1):
            with st.expander(
                f"기사 {index}. {article['title']}",
                expanded=False,
            ):
                st.write(
                    f"**발행일:** "
                    f"{article.get('published_at') or '확인 불가'}"
                )
                st.write(f"**URL:** {article['url']}")
                st.write(article["preview"])

    article_confirmed = st.checkbox(
        "기사 제목과 본문 수집 결과를 확인했습니다.",
        value=False,
        disabled=not bool(preview_articles),
    )

    if st.button(
        "✨ Gemini API로 기사 작성하기",
        type="primary",
        use_container_width=True,
        disabled=(
            not article_confirmed
            or not bool(preview_articles)
        ),
    ):
        try:
            source_data = load_json_file(SOURCE_URLS_PATH, {})
            article_urls = [
                article["url"]
                for article in preview_articles
                if article.get("url")
            ]

            if not article_urls:
                raise ValueError(
                    "뉴스레터로 작성할 기사 URL이 없습니다. "
                    "먼저 기사 원문을 불러와 확인해주세요."
                )

            category = (
                str(source_data.get("category", selected_category)).strip()
                or "HRD 트렌드"
            )
            newsletter_id = (
                str(
                    source_data.get(
                        "newsletter_id",
                        automatic_newsletter_id,
                    )
                ).strip()
                or automatic_newsletter_id
            )

            with st.spinner(
                "Editor 분석 → Writer 작성 → Reviewer 검수를 "
                "진행하고 있습니다..."
            ):
                generated_newsletter = create_newsletter(
                    urls=article_urls,
                    category=category,
                    newsletter_id=newsletter_id,
                    save=False,
                )
                generated_newsletter["category"] = category
                generated_newsletter["issue"] = str(source_data.get("issue", "")).strip()
                generated_newsletter["date"] = str(source_data.get("date", "")).strip()
                generated_newsletter["read_time"] = str(source_data.get("read_time", "5분 뉴스")).strip() or "5분 뉴스"
                generated_newsletter.setdefault("insight_title", "통합되는 인사이트")
                save_generated_newsletter(generated_newsletter)

            st.session_state["generated_newsletter"] = (
                generated_newsletter
            )
            st.success(
                f"{generated_newsletter['id']} "
                "뉴스레터 초안 작성 및 저장 완료"
            )

        except Exception as error:
            st.error(f"Gemini 기사 작성 실패: {error}")
            st.exception(error)

    generated_newsletter = st.session_state.get(
        "generated_newsletter"
    )

    if generated_newsletter:
        st.markdown("### ✨ 생성 결과")

        review_score = generated_newsletter.get("_review_score")
        if review_score is not None:
            st.info(f"Reviewer 검수 점수: {review_score}점")

        st.write(
            f"**제목:** {generated_newsletter.get('title', '')}"
        )
        st.write(
            f"**한 줄 요약:** "
            f"{generated_newsletter.get('summary', '')}"
        )
        st.write(
            f"**HRD 인사이트:** "
            f"{generated_newsletter.get('insight', '')}"
        )

        st.write("**교육 기획할 때 활용할 포인트**")
        for point in generated_newsletter.get("department_apply", []):
            st.write(f"- {point}")

        tags = generated_newsletter.get("tags", [])
        if tags:
            st.write("**키워드:** " + ", ".join(tags))

        hero_image = generated_newsletter.get("hero_image")
        if hero_image:
            st.write("**대표 썸네일:** 첫 번째 기사 이미지")
            show_streamlit_image(hero_image, use_container_width=True)

        st.info(
            "생성 결과는 data/newsletters.json에 저장됐습니다. "
            "아래 전체 빌드를 누르면 로컬 HTML에 반영됩니다."
        )

    if st.button(
        "🚀 전체 빌드",
        type="primary",
        use_container_width=True,
    ):
        try:
            with st.spinner(
                "뉴스레터 HTML을 생성하고 있습니다..."
            ):
                build_log = build_all()

            st.success("전체 빌드 완료")
            st.code(
                build_log or "빌드가 완료됐습니다.",
                language="text",
            )
            st.link_button(
                "🌐 로컬 홈페이지 열기",
                "http://localhost:8000",
                use_container_width=True,
            )
        except Exception as error:
            st.error(f"전체 빌드 실패: {error}")
            st.exception(error)

    with st.expander("🛠 고급 생성 도구", expanded=False):
        advanced_column1, advanced_column2 = st.columns(2)

        with advanced_column1:
            if st.button(
                "🖼 썸네일만 추출",
                use_container_width=True,
            ):
                update_newsletters()
                st.success("썸네일 추출 완료")

            if st.button(
                "📄 기사 HTML만 생성",
                use_container_width=True,
            ):
                render_articles()
                st.success("기사 HTML 생성 완료")

        with advanced_column2:
            if st.button(
                "🏠 홈 HTML만 생성",
                use_container_width=True,
            ):
                render_home()
                st.success("홈 HTML 생성 완료")

            if st.button(
                "📧 메일 HTML만 생성",
                use_container_width=True,
            ):
                render_email()
                st.success("메일 HTML 생성 완료")

    st.divider()
    st.subheader("☁️ GitHub Pages 배포")

    commit_message = st.text_input(
        "Git 커밋 메시지",
        value=f"Publish {automatic_newsletter_id}",
    )

    confirm_deploy = st.checkbox(
        "전체 빌드 결과를 GitHub에 커밋하고 배포합니다."
    )

    if st.button(
        "🚀 전체 빌드 & GitHub Pages 배포",
        type="primary",
        use_container_width=True,
        disabled=not confirm_deploy,
    ):
        try:
            with st.spinner(
                "빌드 후 GitHub에 push하고 있습니다..."
            ):
                deploy_log, pushed = deploy_to_github(
                    commit_message.strip()
                )

            st.code(deploy_log, language="text")

            if pushed:
                st.success(
                    "GitHub push 완료. "
                    "Actions 완료 후 Pages에 반영됩니다."
                )

                link_column1, link_column2 = st.columns(2)
                with link_column1:
                    st.link_button(
                        "⚙️ GitHub Actions 확인",
                        GITHUB_ACTIONS_URL,
                        use_container_width=True,
                    )
                with link_column2:
                    st.link_button(
                        "🌐 GitHub Pages 열기",
                        SITE_URL,
                        use_container_width=True,
                    )
            else:
                st.info("새로 커밋할 변경사항이 없습니다.")

        except Exception as error:
            st.error(f"GitHub 배포 실패: {error}")
            st.exception(error)


# =========================================================
# 기사 관리
# =========================================================

with tab_manage:
    st.subheader("발행 기사 관리")
    published_newsletters = load_json_file(NEWSLETTERS_PATH, [])
    published_newsletters = published_newsletters if isinstance(published_newsletters, list) else []

    if not published_newsletters:
        st.info("현재 저장된 뉴스레터가 없습니다.")
    else:
        ids = [
            str(item.get("id", "")).strip()
            for item in published_newsletters
            if str(item.get("id", "")).strip()
        ]
        selected_manage_id = st.selectbox(
            "관리할 기사",
            ids,
            format_func=lambda newsletter_id: next(
                (
                    f"{item.get('title', '제목 없음')} "
                    f"({item.get('category', '카테고리 없음')} · {newsletter_id})"
                    for item in published_newsletters
                    if str(item.get("id", "")).strip() == newsletter_id
                ),
                newsletter_id,
            ),
            key="manage_newsletter_id",
        )
        selected_item = next(
            (
                item for item in published_newsletters
                if str(item.get("id", "")).strip() == selected_manage_id
            ),
            {},
        )

        st.markdown("### 기사 미리보기")
        article_preview_url = f"{SITE_URL}/articles/{selected_manage_id}.html"
        st.components.v1.iframe(
            article_preview_url,
            height=900,
            scrolling=True,
        )

        st.divider()
        st.markdown("### 기사 내용 및 대표 썸네일 수정")

        with st.form("newsletter_edit_form"):
            column1, column2 = st.columns(2)
            with column1:
                edit_title = st.text_input("제목", value=selected_item.get("title", ""))
                edit_category = st.selectbox(
                    "카테고리",
                    CATEGORIES,
                    index=(
                        CATEGORIES.index(selected_item.get("category"))
                        if selected_item.get("category") in CATEGORIES
                        else len(CATEGORIES) - 1
                    ),
                )
                edit_date = st.text_input("발행일", value=selected_item.get("date", ""))
                edit_read_time = st.text_input("읽는 시간", value=selected_item.get("read_time", "5분 뉴스"))
            with column2:
                edit_hero_url = st.text_input(
                    "대표 썸네일 URL 또는 경로",
                    value=selected_item.get("hero_image", ""),
                    help="외부 이미지 URL 또는 assets/... 경로를 입력할 수 있습니다.",
                )
                uploaded_hero = st.file_uploader(
                    "새 대표 썸네일 업로드",
                    type=["png", "jpg", "jpeg", "webp"],
                )
                if selected_item.get("hero_image"):
                    show_streamlit_image(
                        selected_item.get("hero_image"),
                        caption="현재 대표 썸네일",
                    )

            edit_summary = st.text_area("한 줄 요약", value=selected_item.get("summary", ""), height=100)
            edit_insight_title = st.text_input("인사이트 제목", value=selected_item.get("insight_title", "통합되는 인사이트"))
            edit_insight = st.text_area("통합 인사이트", value=selected_item.get("insight", ""), height=180)
            edit_key_points = st.text_area(
                "핵심 포인트 · 한 줄에 하나",
                value="\n".join(selected_item.get("key_points", [])),
                height=150,
            )
            edit_conclusion = st.text_area("정리 문장", value=selected_item.get("conclusion", ""), height=150)
            edit_department_apply = st.text_area(
                "교육 기획 활용 포인트 · 한 줄에 하나",
                value="\n".join(selected_item.get("department_apply", [])),
                height=150,
            )
            edit_tags = st.text_input(
                "태그 · 쉼표로 구분",
                value=", ".join(selected_item.get("tags", [])),
            )

            save_edits = st.form_submit_button(
                "💾 수정 내용 저장 후 전체 빌드",
                use_container_width=True,
            )

        if save_edits:
            try:
                uploaded_path = save_uploaded_hero_image(uploaded_hero, selected_manage_id)
                hero_image = uploaded_path or edit_hero_url.strip()
                updates = {
                    "title": edit_title.strip(),
                    "category": edit_category,
                    "date": edit_date.strip(),
                    "read_time": edit_read_time.strip(),
                    "hero_image": hero_image,
                    "summary": edit_summary.strip(),
                    "insight_title": edit_insight_title.strip(),
                    "insight": edit_insight.strip(),
                    "key_points": split_lines(edit_key_points),
                    "conclusion": edit_conclusion.strip(),
                    "department_apply": split_lines(edit_department_apply),
                    "tags": [tag.strip().lstrip("#") for tag in edit_tags.split(",") if tag.strip()],
                }
                update_newsletter(selected_manage_id, updates)
                with st.spinner("수정 내용을 반영해 전체 HTML을 다시 생성하고 있습니다..."):
                    build_all()
                st.success("기사 수정 및 전체 빌드가 완료됐습니다.")
                st.rerun()
            except Exception as error:
                st.error(f"기사 수정 실패: {error}")
                st.exception(error)

        st.divider()
        st.markdown("### 기사 삭제")
        confirm_delete = st.checkbox(
            "이 기사를 영구 삭제하는 것에 동의합니다.",
            key="confirm_manage_delete",
        )
        if st.button(
            "🗑️ 선택한 기사 삭제",
            type="primary",
            use_container_width=True,
            disabled=not confirm_delete,
        ):
            try:
                remaining_count = delete_newsletter(selected_manage_id)
                with st.spinner("홈·기사·메일 HTML을 다시 생성하고 있습니다..."):
                    build_all()
                st.session_state.pop("generated_newsletter", None)
                st.success(f"삭제 완료 · 남은 뉴스레터 {remaining_count}건")
                st.rerun()
            except Exception as error:
                st.error(f"기사 삭제 실패: {error}")
                st.exception(error)
