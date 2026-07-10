from pathlib import Path
from datetime import datetime
import json
import os
import subprocess
import sys

import pandas as pd
import streamlit as st

from src.extract_thumbnail import update_newsletters
from src.render_article import render_articles
from src.render_home import render_home
from src.render_email import render_email
from src.collect_news_db import collect_news_to_db
from src.send_email import send_email


# =========================================================
# 기본 경로 및 URL
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


DEFAULT_URLS = """https://www.khrd.co.kr/news/view.php?idx=5057093&sm=w_total&stx=%EC%98%A8%EB%B3%B4%EB%94%A9&stx2=&w_section1=&sdate=&edate=
https://www.khrd.co.kr/news/view.php?idx=5057102&sm=w_total&stx=%EC%8B%A0%EC%9E%85%EC%82%AC%EC%9B%90&stx2=&w_section1=&sdate=&edate=
https://www.khrd.co.kr/news/view.php?idx=5057101&sm=w_total&stx=%EC%8B%A0%EC%9E%85%EC%82%AC%EC%9B%90&stx2=&w_section1=&sdate=&edate=
https://www.khrd.co.kr/news/view.php?idx=5056772&sm=w_total&stx=%EC%98%A8%EB%B3%B4%EB%94%A9&stx2=&w_section1=&sdate=&edate="""


# =========================================================
# Streamlit 기본 설정
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


def save_source_urls(data):
    SOURCE_URLS_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(SOURCE_URLS_PATH, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


# =========================================================
# 뉴스 DB 함수
# =========================================================

def load_news_db():
    if NEWS_DB_PATH.exists():
        return pd.read_excel(NEWS_DB_PATH)

    return pd.DataFrame()


def ensure_news_db_columns(df: pd.DataFrame):
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


def filter_news_db(df: pd.DataFrame):
    filtered_df = df.copy()

    with st.expander("🔎 필터 열기/닫기", expanded=False):
        column1, column2, column3 = st.columns(3)

        with column1:
            keyword_filter = st.text_input(
                "키워드 검색",
                value="",
                key="news_db_keyword_filter",
            )

        with column2:
            topic_options = ["전체"]

            if "뉴스레터 주제" in df.columns:
                topics = [
                    str(value)
                    for value in df["뉴스레터 주제"].dropna().unique()
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

        available_columns = [
            column
            for column in searchable_columns
            if column in filtered_df.columns
        ]

        mask = pd.Series(False, index=filtered_df.index)

        for column in available_columns:
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

    if (
        selected_topic != "전체"
        and "뉴스레터 주제" in filtered_df.columns
    ):
        filtered_df = filtered_df[
            filtered_df["뉴스레터 주제"]
            .fillna("")
            .astype(str)
            == selected_topic
        ]

    if (
        reflect_filter != "전체"
        and "뉴스레터 반영 여부" in filtered_df.columns
    ):
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


def apply_filtered_edits(
    original_df: pd.DataFrame,
    edited_df: pd.DataFrame,
):
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
# 수신자 관리 함수
# =========================================================

def load_recipients_df():
    if RECIPIENTS_PATH.exists():
        try:
            data = json.loads(
                RECIPIENTS_PATH.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            data = []
    else:
        data = []

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

    df["send"] = df["send"].fillna(False).astype(bool)

    return df


def save_recipients_df(df: pd.DataFrame):
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

    RECIPIENTS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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
# 명령어 및 빌드 함수
# =========================================================

def run_command(command, timeout=180):
    env = os.environ.copy()

    # 인증 요청 창으로 프로세스가 멈추는 것을 방지
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        command,
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
    )

    output_parts = []

    if result.stdout and result.stdout.strip():
        output_parts.append(result.stdout.strip())

    if result.stderr and result.stderr.strip():
        output_parts.append(result.stderr.strip())

    output = "\n".join(output_parts)

    if result.returncode != 0:
        command_text = " ".join(str(item) for item in command)

        raise RuntimeError(
            "명령 실행에 실패했습니다.\n\n"
            f"명령어: {command_text}\n\n"
            f"{output or '상세 오류 메시지가 없습니다.'}"
        )

    return output


def build_all():
    return run_command(
        [sys.executable, "build.py"],
        timeout=300,
    )


def get_current_branch():
    branch = run_command(
        ["git", "branch", "--show-current"],
        timeout=30,
    ).strip()

    if not branch:
        raise RuntimeError(
            "현재 Git 브랜치를 확인하지 못했습니다."
        )

    return branch


def get_git_changes():
    return run_command(
        ["git", "status", "--porcelain"],
        timeout=30,
    ).strip()


def deploy_to_github(commit_message):
    logs = []

    logs.append("===== 1. 전체 빌드 =====")

    build_log = build_all()

    if build_log:
        logs.append(build_log)
    else:
        logs.append("전체 빌드 완료")

    branch = get_current_branch()

    logs.append("")
    logs.append(f"현재 브랜치: {branch}")

    changes = get_git_changes()

    if not changes:
        logs.append("")
        logs.append("Git에 반영할 변경사항이 없습니다.")

        return "\n".join(logs), False

    logs.append("")
    logs.append("===== 2. 변경 파일 =====")
    logs.append(changes)

    logs.append("")
    logs.append("===== 3. Git add =====")

    add_log = run_command(
        ["git", "add", "."],
        timeout=60,
    )

    logs.append(add_log or "git add 완료")

    staged_changes = run_command(
        ["git", "diff", "--cached", "--name-status"],
        timeout=30,
    ).strip()

    if not staged_changes:
        logs.append("")
        logs.append(
            "스테이징된 변경사항이 없어 커밋하지 않았습니다."
        )

        return "\n".join(logs), False

    logs.append("")
    logs.append("===== 4. 커밋 대상 =====")
    logs.append(staged_changes)

    logs.append("")
    logs.append("===== 5. Git commit =====")

    commit_log = run_command(
        [
            "git",
            "commit",
            "-m",
            commit_message,
        ],
        timeout=60,
    )

    logs.append(commit_log)

    logs.append("")
    logs.append(f"===== 6. Git push origin {branch} =====")

    push_log = run_command(
        [
            "git",
            "push",
            "origin",
            branch,
        ],
        timeout=180,
    )

    logs.append(push_log)

    logs.append("")
    logs.append(
        "GitHub push 완료. "
        "이후 GitHub Actions에서 Pages 배포가 진행됩니다."
    )

    return "\n".join(logs), True


# =========================================================
# 탭 구성
# =========================================================

(
    tab_home,
    tab_article,
    tab_email,
    tab_db,
    tab_create,
    tab_json,
) = st.tabs(
    [
        "🏠 홈 미리보기",
        "📄 기사 미리보기",
        "📧 메일 발송",
        "📊 뉴스 DB",
        "📝 뉴스레터 생성",
        "🧾 JSON 미리보기",
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
            f"{SITE_URL}/articles/"
            f"{selected_article.name}"
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

        st.caption(
            "새로 생성한 기사가 404라면 아직 GitHub Pages에 "
            "배포되지 않은 상태입니다."
        )

    else:
        st.warning(
            "아직 생성된 기사 HTML이 없습니다."
        )


# =========================================================
# 메일 발송
# =========================================================

with tab_email:
    st.subheader("메일 HTML 미리보기")

    email_html = read_file(EMAIL_PATH)

    if email_html:
        st.components.v1.html(
            email_html,
            height=850,
            scrolling=True,
        )

        with open(EMAIL_PATH, "rb") as file:
            st.download_button(
                label="⬇️ 메일 HTML 다운로드",
                data=file,
                file_name="newsletter_email.html",
                mime="text/html",
                use_container_width=True,
            )

    else:
        st.warning(
            "아직 output/newsletter_email.html 파일이 없습니다."
        )

    st.divider()
    st.subheader("수신자 표 관리")

    recipients_df = load_recipients_df()

    edited_recipients_df = st.data_editor(
        recipients_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "name": st.column_config.TextColumn(
                "이름",
            ),
            "email": st.column_config.TextColumn(
                "이메일",
            ),
            "group": st.column_config.TextColumn(
                "그룹",
            ),
            "send": st.column_config.CheckboxColumn(
                "발송대상",
                default=False,
            ),
        },
        hide_index=True,
        key="recipient_data_editor",
    )

    if st.button(
        "💾 수신자 표 저장",
        use_container_width=True,
    ):
        save_recipients_df(edited_recipients_df)

        st.success(
            "수신자 표 저장 완료"
        )

        st.rerun()

    st.divider()
    st.subheader("Gmail 발송")

    selected_emails = get_selected_recipient_emails()
    selected_email_text = ", ".join(selected_emails)

    st.info(
        f"현재 발송대상 체크 수신자: "
        f"{len(selected_emails)}명"
    )

    receiver_email = st.text_area(
        "받는 사람(To)",
        value=selected_email_text,
        placeholder=(
            "수신자 표에서 발송대상을 체크한 이메일이 "
            "자동 입력됩니다. 직접 입력도 가능합니다."
        ),
        height=90,
    )

    cc_email = st.text_input(
        "참조(CC)",
        value="",
        placeholder=(
            "선택 입력. 여러 명은 쉼표 또는 줄바꿈으로 구분하세요."
        ),
    )

    subject = st.text_input(
        "메일 제목",
        value="HRD Radar 뉴스레터",
    )

    if st.button(
        "📤 Gmail 테스트 발송",
        use_container_width=True,
    ):
        to_list = normalize_email_list(
            receiver_email
        )

        cc_list = normalize_email_list(
            cc_email
        )

        if not to_list:
            st.warning(
                "받는 사람 이메일을 입력하거나 "
                "수신자 표에서 발송대상을 체크해주세요."
            )

        elif not EMAIL_PATH.exists():
            st.warning(
                "메일 HTML이 없습니다. "
                "먼저 뉴스레터 생성 탭에서 메일 HTML을 생성해주세요."
            )

        else:
            try:
                with st.spinner(
                    "메일을 발송하고 있습니다..."
                ):
                    send_email(
                        receiver_email=", ".join(to_list),
                        subject=subject.strip()
                        or "HRD Radar 뉴스레터",
                        cc_email=", ".join(cc_list),
                    )

                st.success(
                    f"메일 발송 완료: {len(to_list)}명"
                )

            except Exception as error:
                st.error(
                    f"메일 발송 실패: {error}"
                )

                st.info(
                    "회사망에서는 Gmail SMTP가 차단될 수 있습니다. "
                    "실패하면 휴대폰 핫스팟으로 다시 시도하세요."
                )


# =========================================================
# 뉴스 DB
# =========================================================

with tab_db:
    st.subheader("뉴스 수집")

    with st.form("collect_news_form"):
        column1, column2, column3 = st.columns(3)

        with column1:
            collect_topic = st.text_input(
                "뉴스레터 주제",
                value="신입사원 교육",
            )

            collect_keyword = st.text_input(
                "검색 키워드",
                value="온보딩",
            )

        with column2:
            collect_issue = st.text_input(
                "발행호수",
                value="HRD Trend Newsletter 1호",
            )

            collect_section = st.text_input(
                "섹션 구분",
                value="뉴스",
            )

        with column3:
            collect_source = st.selectbox(
                "출처",
                ["월간HRD"],
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
                with st.spinner(
                    "뉴스 기사를 수집하고 있습니다..."
                ):
                    collected_df = collect_news_to_db(
                        newsletter_topic=collect_topic,
                        keyword=collect_keyword,
                        issue=collect_issue,
                        section=collect_section,
                        source=collect_source,
                        max_count=int(collect_count),
                    )

                st.success(
                    f"뉴스 수집 완료: 총 {len(collected_df)}건 저장"
                )

            except Exception as error:
                st.error(
                    f"뉴스 수집 실패: {error}"
                )

    st.divider()
    st.subheader("뉴스 DB 미리보기")

    news_df = load_news_db()

    if news_df.empty:
        st.info(
            "아직 news_db.xlsx에 수집된 기사가 없습니다."
        )

    else:
        news_df = ensure_news_db_columns(
            news_df
        )

        news_df = news_df.reset_index(
            drop=True
        )

        news_df["_row_id"] = news_df.index

        filtered_df = filter_news_db(
            news_df
        )

        st.caption(
            f"전체 {len(news_df)}건 중 "
            f"현재 {len(filtered_df)}건 표시"
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
                    st.column_config.LinkColumn(
                        "URL",
                    ),
                "_row_id": None,
            },
            hide_index=True,
            key="news_db_data_editor",
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

            st.success(
                "news_db.xlsx 저장 완료"
            )

            st.rerun()

        with open(NEWS_DB_PATH, "rb") as file:
            st.download_button(
                label="⬇️ news_db.xlsx 다운로드",
                data=file,
                file_name="news_db.xlsx",
                mime=(
                    "application/vnd.openxmlformats-"
                    "officedocument.spreadsheetml.sheet"
                ),
                use_container_width=True,
            )


# =========================================================
# 뉴스레터 생성 및 GitHub 배포
# =========================================================

with tab_create:
    st.subheader("뉴스레터 기본 정보 입력")

    with st.form("source_url_form"):
        column1, column2 = st.columns(2)

        with column1:
            newsletter_id = st.text_input(
                "뉴스레터 ID",
                value="onboarding-001",
            )

            category = st.selectbox(
                "카테고리",
                [
                    "AI/AX 교육",
                    "신입사원 교육",
                    "승격자 교육",
                    "리더 교육",
                    "조직활성화 교육",
                ],
            )

            title = st.text_input(
                "뉴스레터 제목",
                value=(
                    "신입사원 교육, 이제 ‘적응’만으로는 "
                    "부족해요 👀"
                ),
            )

        with column2:
            issue = st.text_input(
                "발행호수",
                value="HRD Trend Newsletter 1호",
            )

            publish_date = st.text_input(
                "발행일",
                value=datetime.now().strftime("%Y.%m.%d"),
            )

            read_time = st.text_input(
                "읽는 시간",
                value="4분 읽기",
            )

        summary = st.text_area(
            "한 줄 요약",
            value=(
                "요즘 온보딩은 회사 소개를 넘어 "
                "AI 활용력·협업 경험·현장 적응력까지 "
                "함께 키우는 방향으로 바뀌고 있어요."
            ),
            height=80,
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

            if not newsletter_id.strip():
                st.warning(
                    "뉴스레터 ID를 입력해주세요."
                )

            elif not title.strip():
                st.warning(
                    "뉴스레터 제목을 입력해주세요."
                )

            elif not urls:
                st.warning(
                    "기사 URL을 1개 이상 입력해주세요."
                )

            else:
                source_data = {
                    "newsletter_id":
                        newsletter_id.strip(),
                    "issue":
                        issue.strip(),
                    "category":
                        category,
                    "title":
                        title.strip(),
                    "date":
                        publish_date.strip(),
                    "read_time":
                        read_time.strip(),
                    "summary":
                        summary.strip(),
                    "urls":
                        urls,
                }

                save_source_urls(
                    source_data
                )

                st.success(
                    "data/source_urls.json 저장 완료"
                )

    st.divider()
    st.subheader("생성 관리")

    column1, column2, column3, column4, column5 = st.columns(5)

    with column1:
        if st.button(
            "🖼 썸네일 추출",
            use_container_width=True,
        ):
            try:
                with st.spinner(
                    "썸네일을 추출하고 있습니다..."
                ):
                    update_newsletters()

                st.success(
                    "썸네일 추출 완료"
                )

            except Exception as error:
                st.error(
                    f"썸네일 추출 실패: {error}"
                )

    with column2:
        if st.button(
            "📄 기사 HTML",
            use_container_width=True,
        ):
            try:
                render_articles()

                st.success(
                    "기사 HTML 생성 완료"
                )

            except Exception as error:
                st.error(
                    f"기사 HTML 생성 실패: {error}"
                )

    with column3:
        if st.button(
            "🏠 홈 HTML",
            use_container_width=True,
        ):
            try:
                render_home()

                st.success(
                    "홈 HTML 생성 완료"
                )

            except Exception as error:
                st.error(
                    f"홈 HTML 생성 실패: {error}"
                )

    with column4:
        if st.button(
            "📧 메일 HTML",
            use_container_width=True,
        ):
            try:
                render_email()

                st.success(
                    "메일 HTML 생성 완료"
                )

            except Exception as error:
                st.error(
                    f"메일 HTML 생성 실패: {error}"
                )

    with column5:
        if st.button(
            "🚀 전체 빌드",
            use_container_width=True,
        ):
            try:
                with st.spinner(
                    "전체 HTML을 생성하고 있습니다..."
                ):
                    build_log = build_all()

                st.success(
                    "전체 빌드 완료"
                )

                st.code(
                    build_log or "전체 빌드 완료",
                    language="text",
                )

            except Exception as error:
                st.error(
                    f"전체 빌드 실패: {error}"
                )

    st.divider()
    st.subheader("☁️ GitHub Pages 배포")

    default_commit_message = (
        f"Publish {newsletter_id.strip()}"
        if newsletter_id.strip()
        else (
            f"Publish newsletter "
            f"{datetime.now():%Y-%m-%d}"
        )
    )

    commit_message = st.text_input(
        "Git 커밋 메시지",
        value=default_commit_message,
        help=(
            "GitHub 저장소에 기록될 변경 이력입니다. "
            "예: Publish onboarding-002"
        ),
    )

    st.warning(
        "이 기능은 로컬 PC에서 실행한 Streamlit 관리자에서만 "
        "사용하세요. 전체 빌드 후 변경 파일을 GitHub에 "
        "커밋하고 push합니다."
    )

    confirm_deploy = st.checkbox(
        "현재 변경사항을 GitHub에 커밋하고 Pages에 배포합니다.",
        value=False,
    )

    if st.button(
        "🚀 전체 빌드 & GitHub Pages 배포",
        type="primary",
        use_container_width=True,
        disabled=not confirm_deploy,
    ):
        if not commit_message.strip():
            st.warning(
                "Git 커밋 메시지를 입력해주세요."
            )

        else:
            try:
                with st.spinner(
                    "전체 빌드 후 GitHub에 push하고 있습니다. "
                    "창을 닫지 마세요..."
                ):
                    deploy_log, pushed = deploy_to_github(
                        commit_message.strip()
                    )

                st.code(
                    deploy_log,
                    language="text",
                )

                if pushed:
                    st.success(
                        "GitHub push가 완료되었습니다. "
                        "GitHub Actions가 끝나면 Pages에 반영됩니다."
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
                    st.info(
                        "새로 커밋할 변경사항이 없습니다."
                    )

            except subprocess.TimeoutExpired:
                st.error(
                    "명령 실행 시간이 초과되었습니다. "
                    "네트워크 또는 GitHub 인증 상태를 확인해주세요."
                )

            except Exception as error:
                st.error(
                    f"GitHub 배포 실패:\n\n{error}"
                )

                st.info(
                    "Git Bash에서 git status와 git push가 "
                    "정상 작동하는지 먼저 확인해주세요."
                )


# =========================================================
# JSON 미리보기
# =========================================================

with tab_json:
    st.subheader("source_urls.json")

    source_text = read_file(
        SOURCE_URLS_PATH
    )

    st.code(
        source_text or "source_urls.json 없음",
        language="json",
    )

    st.subheader("newsletters.json")

    newsletter_text = read_file(
        NEWSLETTERS_PATH
    )

    st.code(
        newsletter_text or "newsletters.json 없음",
        language="json",
    )

    st.subheader("recipients.json")

    recipients_text = read_file(
        RECIPIENTS_PATH
    )

    st.code(
        recipients_text or "recipients.json 없음",
        language="json",
    )