from pathlib import Path
import streamlit as st

from src.render_article import render_articles
from src.render_home import render_home


BASE_DIR = Path(__file__).resolve().parent
HOME_PATH = BASE_DIR / "output" / "index.html"
ARTICLE_DIR = BASE_DIR / "output" / "articles"


st.set_page_config(
    page_title="HRD Radar",
    page_icon="🧡",
    layout="wide"
)

# 최초 실행 시 HTML 자동 생성
try:
    render_articles()
    render_home()
except Exception as e:
    st.error(f"HTML 생성 중 오류가 발생했습니다: {e}")


st.markdown(
    """
    <style>
    .block-container {
        padding-top: 0rem;
        padding-left: 0rem;
        padding-right: 0rem;
        max-width: 100%;
    }

    header[data-testid="stHeader"] {
        display: none;
    }

    [data-testid="stToolbar"] {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True
)


view = st.sidebar.radio(
    "보기 선택",
    ["홈페이지", "기사 페이지", "관리자"]
)


def read_html(path):
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


if view == "홈페이지":
    html = read_html(HOME_PATH)

    if html:
        st.components.v1.html(html, height=1200, scrolling=True)
    else:
        st.warning("output/index.html 파일이 없습니다.")

elif view == "기사 페이지":
    article_files = sorted(ARTICLE_DIR.glob("*.html")) if ARTICLE_DIR.exists() else []

    if article_files:
        selected = st.sidebar.selectbox(
            "기사 선택",
            article_files,
            format_func=lambda p: p.name
        )

        html = read_html(selected)
        st.components.v1.html(html, height=1400, scrolling=True)
    else:
        st.warning("생성된 기사 HTML이 없습니다.")

else:
    st.title("🧡 HRD Radar 관리자")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("홈페이지 HTML 다시 생성", use_container_width=True):
            render_home()
            st.success("홈페이지 생성 완료")

    with col2:
        if st.button("기사 HTML 다시 생성", use_container_width=True):
            render_articles()
            st.success("기사 페이지 생성 완료")