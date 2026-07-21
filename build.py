from pathlib import Path
import shutil

from src.extract_thumbnail import update_newsletters
from src.render_article import render_articles
from src.render_home import render_home
from src.render_email import render_email


BASE_DIR = Path(__file__).resolve().parent

ASSETS_SOURCE = BASE_DIR / "assets"
ASSETS_OUTPUT = BASE_DIR / "output" / "assets"


def copy_assets():
    if not ASSETS_SOURCE.exists():
        raise FileNotFoundError(
            f"assets 폴더가 없습니다: {ASSETS_SOURCE}"
        )

    if ASSETS_OUTPUT.exists():
        shutil.rmtree(ASSETS_OUTPUT)

    shutil.copytree(
        ASSETS_SOURCE,
        ASSETS_OUTPUT,
    )

    print(f"assets 복사 완료: {ASSETS_OUTPUT}")


def build_all():
    print("1. 썸네일 추출 시작")
    update_newsletters()

    print("2. 기사 HTML 생성 시작")
    render_articles()

    print("3. 홈 HTML 생성 시작")
    render_home()

    print("4. 메일 HTML 생성 시작")
    render_email()

    print("5. assets 복사 시작")
    copy_assets()

    print("전체 빌드 완료")


if __name__ == "__main__":
    build_all()