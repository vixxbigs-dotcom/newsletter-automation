from pathlib import Path
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


st.set_page_config(
    page_title="HRD Radar 관리자",
    page_icon="🧡",
    layout="wide"
)

st.title("🧡 HRD Radar 관리자")
st.caption("HRD 뉴스레터 생성 · 미리보기 · 메일 발송 관리 화면")


def read_file(path):
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def build_all():
    update_newsletters()
    render_articles()
    render_home()
    render_email()


st.markdown("## ⚙️ 생성 관리")

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("🖼 썸네일 추출", use_container_width=True):
        update_newsletters()
        st.success("썸네일 추출 완료")

with col2:
    if st.button("📄 기사 HTML 생성", use_container_width=True):
        render_articles()
        st.success("기사 HTML 생성 완료")

with col3:
    if st.button("🏠 홈 HTML 생성", use_container_width=True):
        render_home()
        st.success("홈 HTML 생성 완료")

with col4:
    if st.button("📧 메일 HTML 생성", use_container_width=True):
        render_email()
        st.success("메일 HTML 생성 완료")

if st.button("🚀 전체 생성", use_container_width=True):
    build_all()
    st.success("전체 생성 완료")

st.divider()

tab1, tab2, tab3, tab4 = st.tabs(
    ["🏠 홈 미리보기", "📄 기사 미리보기", "📧 메일 미리보기", "🧾 JSON 확인"]
)

with tab1:
    st.subheader("홈페이지 미리보기")

    st.link_button("🌐 새 창에서 홈 보기", SITE_URL, use_container_width=True)

    st.components.v1.iframe(
        SITE_URL,
        height=900,
        scrolling=True
    )

    if HOME_PATH.exists():
        with open(HOME_PATH, "rb") as f:
            st.download_button(
                label="⬇️ index.html 다운로드",
                data=f,
                file_name="index.html",
                mime="text/html"
            )

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

        st.components.v1.iframe(
            article_url,
            height=1200,
            scrolling=True
        )

        with open(selected_article, "rb") as f:
            st.download_button(
                label="⬇️ 기사 HTML 다운로드",
                data=f,
                file_name=selected_article.name,
                mime="text/html"
            )
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

        st.markdown("### Gmail 테스트 발송")

        subject = st.text_input(
            "메일 제목",
            value="HRD Radar 뉴스레터"
        )

        if st.button("📤 Gmail 테스트 발송", use_container_width=True):
            try:
                send_email(subject=subject)
                st.success("메일 발송 완료")
            except Exception as e:
                st.error(f"메일 발송 실패: {e}")
                st.info(
                    "회사 네트워크에서 Gmail SMTP가 차단됐을 수 있습니다. "
                    "휴대폰 핫스팟 또는 외부 네트워크에서 다시 테스트해보세요."
                )
    else:
        st.warning("아직 output/newsletter_email.html 파일이 없습니다.")

with tab4:
    st.subheader("newsletters.json")

    json_text = read_file(NEWSLETTERS_PATH)

    if json_text:
        st.code(json_text, language="json")
    else:
        st.warning("data/newsletters.json 파일이 없습니다.")