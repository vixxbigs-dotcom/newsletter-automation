from pathlib import Path
import shutil

from src.create_newsletter_from_urls import create_newsletter
from src.extract_thumbnail import update_newsletters
from src.render_article import render_articles
from src.render_home import render_home
from src.render_email import render_email


BASE_DIR = Path(__file__).resolve().parent
ASSETS_SRC = BASE_DIR / "assets"
ASSETS_DST = BASE_DIR / "output" / "assets"


def copy_assets():
    if ASSETS_DST.exists():
        shutil.rmtree(ASSETS_DST)

    shutil.copytree(ASSETS_SRC, ASSETS_DST)
    print(f"assets 복사 완료: {ASSETS_DST}")


def build_all():
    print("1. URL 기반 뉴스레터 초안 생성 시작")
    create_newsletter()

    print("2. 썸네일 추출 시작")
    update_newsletters()

    print("3. 기사 HTML 생성 시작")
    render_articles()

    print("4. 홈 HTML 생성 시작")
    render_home()

    print("5. 메일 HTML 생성 시작")
    render_email()

    print("6. assets 복사 시작")
    copy_assets()

    print("전체 빌드 완료")


if __name__ == "__main__":
    build_all()