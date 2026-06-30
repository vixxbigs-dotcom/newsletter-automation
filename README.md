📰 HRD Radar
AI 기반 HRD 뉴스레터 자동화 시스템

AI가 HRD 뉴스를 선별하고, 요약하고, HTML 뉴스레터를 생성하여 웹과 이메일로 배포하는 자동화 프로젝트

✨ Preview
<img width="1350" height="1647" alt="_C__Users_MULTICAMPUS_Downloads_github-pages_artifact_index html" src="https://github.com/user-attachments/assets/788f527e-32ff-4e4d-8c63-01041762a033" />

📷 Home Preview
<img width="1350" height="3404" alt="_C__Users_MULTICAMPUS_Downloads_github-pages_artifact_articles_onboarding-001 html" src="https://github.com/user-attachments/assets/76326720-679a-4592-bb33-1599f4b820a5" /> 📷 Article Preview <img width="723" height="2871" alt="_C__Users_MULTICAMPUS_Downloads_github-pages_artifact_newsletter_email html" src="https://github.com/user-attachments/assets/a54bcde0-a7aa-49bf-8f8b-fb31772457b9" /> 📷 Email Preview


🚀 프로젝트 소개

기존 HRD 뉴스레터는

기사 수집
기사 요약
이미지 제작
HTML 제작
메일 발송

을 모두 사람이 직접 수행해야 했습니다.

HRD Radar는 이 과정을 AI와 Python으로 자동화하여

"하루 1개의 HRD 뉴스레터를 자동 생성"

하는 것을 목표로 합니다.
<img width="958" height="694" alt="image" src="https://github.com/user-attachments/assets/e88a6786-f635-46be-b55e-4f263d46178b" />
⚙️ Workflow
📰 뉴스 크롤링
        │
        ▼
🤖 AI 기사 선별
        │
        ▼
✍️ 뉴스레터 재작성
        │
        ▼
🖼 썸네일 자동 추출
        │
        ▼
🌐 HTML 생성
        │
        ├──── Home
        ├──── Article
        └──── Email
        │
        ▼
📤 Email 발송
        │
        ▼
🚀 GitHub Pages 배포
📂 프로젝트 구조
newsletter-automation/

📄 app.py                      # Streamlit 관리자

📁 assets/
 ├── banners/
 ├── thumbnails/
 ├── logos/
 ├── characters/
 └── css/

📁 data/
 ├── newsletters.json
 └── news_db.xlsx

📁 templates/
 ├── home.html
 ├── article.html
 └── email.html

📁 src/
 ├── extract_thumbnail.py
 ├── render_home.py
 ├── render_article.py
 ├── render_email.py
 ├── send_email.py
 └── rewrite_newsletter.py

📁 output/
 ├── index.html
 ├── newsletter_email.html
 ├── articles/
 └── assets/
✨ 주요 기능
📰 HRD 기사 자동 큐레이션
기사 수집
AI 적합성 검토
태그 분류
분야별 분류
🤖 AI 뉴스레터 생성
기사 4~5개 통합
Newneek 스타일 요약
HRD 시사점 작성
우리 부서 적용 아이디어 작성
🖼 이미지 자동 처리
기사 대표 이미지 추출
썸네일 자동 저장
HTML 자동 연결
🌐 웹페이지 생성

자동 생성

✅ Home

✅ Article

✅ Email

📧 HTML 이메일 생성
Outlook
Gmail

지원

🚀 GitHub Pages 자동 배포
git push

↓

GitHub Actions

↓

GitHub Pages
🛠 Tech Stack
Language
🐍 Python
AI
🤖 OpenAI GPT
Web
HTML
CSS
Streamlit
Crawling
BeautifulSoup
Requests
Deployment
GitHub Actions
GitHub Pages
📌 향후 개발 계획
 뉴스레터 HTML 생성
 기사 HTML 생성
 메일 HTML 생성
 GitHub Pages 배포
 Outlook 자동 발송
 Gmail 자동 발송
 GPT 자동 기사 작성
 스케줄러 자동 실행
 뉴스레터 아카이브 구축
📈 자동화 프로세스

뉴스 URL

↓

AI 요약

↓

썸네일 추출

↓

JSON 생성

↓

HTML 생성

↓

메일 생성

↓

GitHub Pages

↓

자동 발송
💡 프로젝트 목표

"매일 5분 안에 HRD 뉴스레터를 발행할 수 있는 자동화 시스템 구축"

⭐ GitHub README를 더 돋보이게 하는 팁

스크린샷을 3장만 넣어도 완성도가 크게 올라갑니다.

🏠 Home 화면
📄 기사 페이지
📧 이메일 화면
