from pathlib import Path
import json
import subprocess
import streamlit as st

from src.extract_thumbnail import update_newsletters
from src.render_article import render_articles
from src.render_home import render_home
from src.render_email import render_email
from src.send_email import send_email


BASE_DIR = Path(__file__).resolve().parent
SITE_URL = "https://vixxbigs-dotcom.github.io/newsletter-automation"

HOME_PATH = BASE_DIR / "output" / "index.html"
EMAIL_PATH = BASE_DIR / "output" / "newsletter_email.html"
ARTICLE_DIR = BASE_DIR / "output" / "articles"
NEWSLETTERS_PATH = BASE_DIR / "data" / "newsletters.json"
SOURCE_URLS_PATH = BASE_DIR / "data" / "source_urls.json"


st.set_page_config(
    page_title="HRD Radar 관리자",
    page_icon="🧡",
    layout="wide"
)

st.title("🧡 HRD Radar 관리자")
st.caption("URL 입력 → 뉴스레터 생성 → HTML 미리보기 → 메일 발송")


def read_file(path):
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def save_source_urls(data):
    SOURCE_URLS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SOURCE_URLS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_all():
    result = subprocess.run(
        ["python", "build.py"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    return result.stdout


st.markdown("## 1️⃣ 뉴스레터 기본 정보 입력")

with st.form("source_url_form"):
    col1, col2 = st.columns(2)

    with col1:
        newsletter_id = st.text_input("뉴스레터 ID", value="onboarding-001")
        category = st.selectbox(
            "카테고리",
            ["AI/AX 교육", "신입사원 교육", "승격자 교육", "리더 교육", "조직활성화 교육"]
        )
        title = st.text_input("뉴스레터 제목", value="신입사원 교육, 이제 ‘적응’만으로는 부족해요 👀")

    with col2:
        issue = st.text_input("발행호수", value="HRD Trend Newsletter 1호")
        date = st.text_input("발행일", value="2026.06.29")
        read_time = st.text_input("읽는 시간", value="4분 읽기")

    summary = st.text_area(
        "한 줄 요약",
        value="요즘 온보딩은 회사 소개를 넘어 AI 활용력·협업 경험·현장 적응력까지 함께 키우는 방향으로 바뀌고 있어요.",
        height=80
    )

    urls_text = st.text_area(
        "기사 URL 4개 입력",
        value="""https://www.khrd.co.kr/news/view.php?idx=5057093&sm=w_total&stx=%EC%98%A8%EB%B3%B4%EB%94%A9&stx2=&w_section1=&sdate=&edate=
https://www.khrd.co.kr/news/view.php?idx=5057102&sm=w_total&stx=%EC%8B%A0%EC%9E%85%EC%82%AC%EC%9B%90&stx2=&w_section1=&sdate=&edate=
https://www.khrd.co.kr/news/view.php?idx=5057101&sm=w_total&stx=%EC%8B%A0%EC%9E%85%EC%82%AC%EC%9B%90&stx2=&w_section1=&sdate=&edate=
https://www.khrd.co.kr/news/view.php?idx=5056772&sm=w_total&stx=%EC%98%A8%EB%B3%B4%EB%94%A9&stx2=&w_section1=&sdate=&edate=""",
        height=160
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
            "urls": urls
        }

        save_source_urls(data)
        st.success("data/source_urls.json 저장 완료")


st.markdown("## 2️⃣ 생성 관리")

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


st.divider()

tab1, tab2, tab3, tab4 = st.tabs(
    ["🏠 홈 미리보기", "📄 기사 미리보기", "📧 메일 미리보기", "🧾 JSON 확인"]
)

with tab1:
    st.subheader("홈페이지 미리보기")
    st.link_button("🌐 새 창에서 홈 보기", SITE_URL, use_container_width=True)
    st.components.v1.iframe(SITE_URL, height=900, scrolling=True)

with tab2:
    st.subheader("기사 페이지 미리보기")

    article_files = sorted(ARTICLE_DIR.glob("*.html")) if ARTICLE_DIR.exists() else []

    if article_files:
        selected_article = st.selectbox(
            "미리볼 기사 선택",
            article_files,
            format_func=lambda path: path.name
        )

        article_url = f"{SITE_URL}/articles/{selected_article.name}"
        st.link_button("🌐 새 창에서 기사 보기", article_url, use_container_width=True)
        st.components.v1.iframe(article_url, height=1200, scrolling=True)
    else:
        st.warning("아직 생성된 기사 HTML이 없습니다.")

with tab3:
    st.subheader("메일 HTML 미리보기")

    html = read_file(EMAIL_PATH)

    if html:
        st.components.v1.html(html, height=1200, scrolling=True)

        with open(EMAIL_PATH, "rb") as f:
            st.download_button(
                label="⬇️ 메일 HTML 다운로드",
                data=f,
                file_name="newsletter_email.html",
                mime="text/html"
            )

        subject = st.text_input("메일 제목", value="HRD Radar 뉴스레터")

        if st.button("📤 Gmail 테스트 발송", use_container_width=True):
            try:
                send_email(subject=subject)
                st.success("메일 발송 완료")
            except Exception as e:
                st.error(f"메일 발송 실패: {e}")
    else:
        st.warning("아직 output/newsletter_email.html 파일이 없습니다.")

with tab4:
    st.subheader("source_urls.json")
    source_text = read_file(SOURCE_URLS_PATH)
    st.code(source_text or "source_urls.json 없음", language="json")

    st.subheader("newsletters.json")
    newsletter_text = read_file(NEWSLETTERS_PATH)
    st.code(newsletter_text or "newsletters.json 없음", language="json")