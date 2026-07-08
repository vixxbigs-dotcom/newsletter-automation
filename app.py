from pathlib import Path
import json
import subprocess

import pandas as pd
import streamlit as st

from src.extract_thumbnail import update_newsletters
from src.render_article import render_articles
from src.render_home import render_home
from src.render_email import render_email
from src.collect_news_db import collect_news_to_db
from src.send_email import send_email


BASE_DIR = Path(__file__).resolve().parent
SITE_URL = "https://vixxbigs-dotcom.github.io/newsletter-automation"

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


st.set_page_config(
    page_title="HRD Radar 관리자",
    page_icon="🧡",
    layout="wide",
)

st.title("🧡 HRD Radar 관리자")
st.caption("뉴스 수집 → 뉴스레터 생성 → HTML 미리보기 → 메일 발송")


if "newsletter_urls_text" not in st.session_state:
    st.session_state["newsletter_urls_text"] = DEFAULT_URLS


def read_file(path: Path):
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def save_source_urls(data):
    SOURCE_URLS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SOURCE_URLS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_news_db():
    if NEWS_DB_PATH.exists():
        return pd.read_excel(NEWS_DB_PATH)
    return pd.DataFrame()


def load_recipients_df():
    if RECIPIENTS_PATH.exists():
        try:
            data = json.loads(RECIPIENTS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = []
    else:
        data = []

    if not isinstance(data, list):
        data = []

    df = pd.DataFrame(data)

    required_columns = ["name", "email", "group", "send"]

    for col in required_columns:
        if col not in df.columns:
            df[col] = True if col == "send" else ""

    df = df[required_columns]

    if df.empty:
        df = pd.DataFrame([{"name": "", "email": "", "group": "", "send": True}])

    df["send"] = df["send"].fillna(False).astype(bool)
    return df


def save_recipients_df(df: pd.DataFrame):
    clean_df = df.copy()

    for col in ["name", "email", "group"]:
        clean_df[col] = clean_df[col].fillna("").astype(str).str.strip()

    clean_df["send"] = clean_df["send"].fillna(False).astype(bool)

    clean_df = clean_df[
        (clean_df["email"] != "")
        | (clean_df["name"] != "")
        | (clean_df["group"] != "")
    ]

    RECIPIENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECIPIENTS_PATH.write_text(
        json.dumps(clean_df.to_dict(orient="records"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_selected_recipient_emails():
    df = load_recipients_df()

    selected = df[
        (df["send"] == True)
        & (df["email"].fillna("").astype(str).str.strip() != "")
    ]

    return selected["email"].astype(str).str.strip().tolist()


def normalize_email_list(text):
    emails = []
    for item in str(text).replace(",", "\n").splitlines():
        email = item.strip()
        if email:
            emails.append(email)
    return emails


def build_all():
    result = subprocess.run(
        ["python", "build.py"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    return result.stdout


def filter_news_db(df: pd.DataFrame):
    filtered_df = df.copy()

    with st.expander("🔎 필터 열기/닫기", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            keyword_filter = st.text_input("키워드 검색", value="")

        with col2:
            topic_options = ["전체"]
            if "뉴스레터 주제" in df.columns:
                topic_options += sorted(
                    [str(x) for x in df["뉴스레터 주제"].dropna().unique() if str(x).strip()]
                )

            selected_topic = st.selectbox("뉴스레터 주제", topic_options)

        with col3:
            reflect_filter = st.selectbox(
                "뉴스레터 반영 여부",
                ["전체", "반영", "미반영"],
            )

    if keyword_filter:
        keyword_cols = ["키워드", "자료 제목", "핵심 내용", "URL"]
        available_cols = [col for col in keyword_cols if col in filtered_df.columns]

        mask = False
        for col in available_cols:
            mask = mask | filtered_df[col].fillna("").astype(str).str.contains(
                keyword_filter,
                case=False,
                na=False,
            )

        filtered_df = filtered_df[mask]

    if selected_topic != "전체" and "뉴스레터 주제" in filtered_df.columns:
        filtered_df = filtered_df[
            filtered_df["뉴스레터 주제"].fillna("").astype(str) == selected_topic
        ]

    if reflect_filter != "전체" and "뉴스레터 반영 여부" in filtered_df.columns:
        bool_series = filtered_df["뉴스레터 반영 여부"].fillna(False).astype(bool)

        if reflect_filter == "반영":
            filtered_df = filtered_df[bool_series]
        else:
            filtered_df = filtered_df[~bool_series]

    return filtered_df


def ensure_news_db_columns(df: pd.DataFrame):
    required = [
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

    for col in required:
        if col not in df.columns:
            df[col] = ""

    if "뉴스레터 반영 여부" in df.columns:
        df["뉴스레터 반영 여부"] = (
            df["뉴스레터 반영 여부"]
            .fillna(False)
            .replace("", False)
            .astype(bool)
        )

    return df[required]


def apply_filtered_edits(original_df: pd.DataFrame, edited_df: pd.DataFrame):
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

        for col in edited_df.columns:
            if col == "_row_id":
                continue

            if col in updated_df.columns:
                updated_df.loc[row_id, col] = row[col]

    return updated_df


tab_home, tab_article, tab_email, tab_db, tab_create, tab_json = st.tabs(
    ["🏠 홈 미리보기", "📄 기사 미리보기", "📧 메일 발송", "📊 뉴스 DB", "📝 뉴스레터 생성", "🧾 JSON 미리보기"]
)


with tab_home:
    st.subheader("홈페이지 미리보기")
    st.link_button("🌐 새 창에서 홈 보기", SITE_URL, use_container_width=True)
    st.components.v1.iframe(SITE_URL, height=900, scrolling=True)


with tab_article:
    st.subheader("기사 페이지 미리보기")

    article_files = sorted(ARTICLE_DIR.glob("*.html")) if ARTICLE_DIR.exists() else []

    if article_files:
        selected_article = st.selectbox(
            "미리볼 기사 선택",
            article_files,
            format_func=lambda path: path.name,
        )

        article_url = f"{SITE_URL}/articles/{selected_article.name}"
        st.link_button("🌐 새 창에서 기사 보기", article_url, use_container_width=True)
        st.components.v1.iframe(article_url, height=1200, scrolling=True)
    else:
        st.warning("아직 생성된 기사 HTML이 없습니다.")


with tab_email:
    st.subheader("메일 HTML 미리보기")

    html = read_file(EMAIL_PATH)

    if html:
        st.components.v1.html(html, height=850, scrolling=True)

        with open(EMAIL_PATH, "rb") as f:
            st.download_button(
                label="⬇️ 메일 HTML 다운로드",
                data=f,
                file_name="newsletter_email.html",
                mime="text/html",
                use_container_width=True,
            )
    else:
        st.warning("아직 output/newsletter_email.html 파일이 없습니다.")

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
            "send": st.column_config.CheckboxColumn("발송대상"),
        },
        hide_index=True,
    )

    if st.button("💾 수신자 표 저장", use_container_width=True):
        save_recipients_df(edited_recipients_df)
        st.success("수신자 표 저장 완료")
        st.rerun()

    st.divider()
    st.subheader("Gmail 발송")

    selected_emails = get_selected_recipient_emails()
    selected_email_text = ", ".join(selected_emails)

    st.info(f"현재 발송대상 체크된 수신자: {len(selected_emails)}명")

    receiver_email = st.text_area(
        "받는 사람(To)",
        value=selected_email_text,
        placeholder="수신자 표에서 send 체크한 이메일이 자동 입력됩니다. 직접 수정 가능.",
        height=90,
    )

    cc_email = st.text_input(
        "참조(CC)",
        value="",
        placeholder="선택 입력. 여러 명은 쉼표로 구분.",
    )

    subject = st.text_input(
        "메일 제목",
        value="HRD Radar 뉴스레터",
    )

    if st.button("📤 Gmail 테스트 발송", use_container_width=True):
        to_list = normalize_email_list(receiver_email)
        cc_list = normalize_email_list(cc_email)

        if not to_list:
            st.warning("받는 사람 이메일을 입력하거나 수신자 표에서 발송대상을 체크해주세요.")
        else:
            try:
                send_email(
                    receiver_email=", ".join(to_list),
                    subject=subject,
                    cc_email=", ".join(cc_list),
                )
                st.success(f"메일 발송 완료: {len(to_list)}명")
            except Exception as e:
                st.error(f"메일 발송 실패: {e}")
                st.info("회사망에서는 Gmail SMTP가 차단될 수 있습니다. 실패하면 핫스팟으로 다시 시도하세요.")


with tab_db:
    st.subheader("뉴스 수집")

    with st.form("collect_news_form"):
        col1, col2, col3 = st.columns(3)

        with col1:
            collect_topic = st.text_input("뉴스레터 주제", value="신입사원 교육")
            collect_keyword = st.text_input("검색 키워드", value="온보딩")

        with col2:
            collect_issue = st.text_input("발행호수", value="HRD Trend Newsletter 1호")
            collect_section = st.text_input("섹션 구분", value="뉴스")

        with col3:
            collect_source = st.selectbox("출처", ["월간HRD"])
            collect_count = st.number_input("수집 개수", min_value=1, max_value=30, value=10)

        collect_submitted = st.form_submit_button("📰 뉴스 DB에 기사 수집", use_container_width=True)

        if collect_submitted:
            try:
                df = collect_news_to_db(
                    newsletter_topic=collect_topic,
                    keyword=collect_keyword,
                    issue=collect_issue,
                    section=collect_section,
                    source=collect_source,
                    max_count=int(collect_count),
                )
                st.success(f"뉴스 수집 완료: 총 {len(df)}건 저장")
            except Exception as e:
                st.error(f"뉴스 수집 실패: {e}")

    st.divider()
    st.subheader("뉴스 DB 미리보기")

    df = load_news_db()

    if df.empty:
        st.info("아직 news_db.xlsx에 수집된 기사가 없습니다.")
    else:
        df = ensure_news_db_columns(df)
        df = df.reset_index(drop=True)
        df["_row_id"] = df.index

        filtered_df = filter_news_db(df)

        st.caption(f"전체 {len(df)}건 중 현재 {len(filtered_df)}건 표시")

        edited_df = st.data_editor(
            filtered_df,
            num_rows="fixed",
            use_container_width=True,
            column_config={
                "뉴스레터 반영 여부": st.column_config.CheckboxColumn("뉴스레터 반영 여부"),
                "활용 점수": st.column_config.NumberColumn("활용 점수", min_value=0, max_value=100),
                "URL": st.column_config.LinkColumn("URL"),
                "_row_id": None,
            },
            hide_index=True,
        )

        if st.button("💾 뉴스 DB 저장", use_container_width=True):
            updated_df = apply_filtered_edits(df, edited_df)
            updated_df = updated_df.drop(columns=["_row_id"], errors="ignore")
            updated_df.to_excel(NEWS_DB_PATH, index=False)
            st.success("news_db.xlsx 저장 완료")
            st.rerun()

        with open(NEWS_DB_PATH, "rb") as f:
            st.download_button(
                label="⬇️ news_db.xlsx 다운로드",
                data=f,
                file_name="news_db.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )


with tab_create:
    st.subheader("뉴스레터 기본 정보 입력")

    with st.form("source_url_form"):
        col1, col2 = st.columns(2)

        with col1:
            newsletter_id = st.text_input("뉴스레터 ID", value="onboarding-001")
            category = st.selectbox(
                "카테고리",
                ["AI/AX 교육", "신입사원 교육", "승격자 교육", "리더 교육", "조직활성화 교육"],
            )
            title = st.text_input("뉴스레터 제목", value="신입사원 교육, 이제 ‘적응’만으로는 부족해요 👀")

        with col2:
            issue = st.text_input("발행호수", value="HRD Trend Newsletter 1호")
            date = st.text_input("발행일", value="2026.06.29")
            read_time = st.text_input("읽는 시간", value="4분 읽기")

        summary = st.text_area(
            "한 줄 요약",
            value="요즘 온보딩은 회사 소개를 넘어 AI 활용력·협업 경험·현장 적응력까지 함께 키우는 방향으로 바뀌고 있어요.",
            height=80,
        )

        urls_text = st.text_area(
            "기사 URL 4개 입력",
            key="newsletter_urls_text",
            height=160,
        )

        submitted = st.form_submit_button("💾 URL 저장하기", use_container_width=True)

        if submitted:
            urls = [line.strip() for line in urls_text.splitlines() if line.strip()]

            data = {
                "newsletter_id": newsletter_id,
                "issue": issue,
                "category": category,
                "title": title,
                "date": date,
                "read_time": read_time,
                "summary": summary,
                "urls": urls,
            }

            save_source_urls(data)
            st.success("data/source_urls.json 저장 완료")

    st.divider()
    st.subheader("생성 관리")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        if st.button("🖼 썸네일 추출", use_container_width=True):
            update_newsletters()
            st.success("썸네일 추출 완료")

    with col2:
        if st.button("📄 기사 HTML", use_container_width=True):
            render_articles()
            st.success("기사 HTML 생성 완료")

    with col3:
        if st.button("🏠 홈 HTML", use_container_width=True):
            render_home()
            st.success("홈 HTML 생성 완료")

    with col4:
        if st.button("📧 메일 HTML", use_container_width=True):
            render_email()
            st.success("메일 HTML 생성 완료")

    with col5:
        if st.button("🚀 전체 빌드", use_container_width=True):
            try:
                log = build_all()
                st.success("전체 빌드 완료")
                st.code(log)
            except Exception as e:
                st.error(f"빌드 실패: {e}")


with tab_json:
    st.subheader("source_urls.json")
    source_text = read_file(SOURCE_URLS_PATH)
    st.code(source_text or "source_urls.json 없음", language="json")

    st.subheader("newsletters.json")
    newsletter_text = read_file(NEWSLETTERS_PATH)
    st.code(newsletter_text or "newsletters.json 없음", language="json")

    st.subheader("recipients.json")
    recipients_text = read_file(RECIPIENTS_PATH)
    st.code(recipients_text or "recipients.json 없음", language="json")