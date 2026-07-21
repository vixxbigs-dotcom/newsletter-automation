from __future__ import annotations


ARTICLE_ANALYSIS_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "articles": {
            "type": "ARRAY",
            "description": "입력 기사 순서를 유지한 기사별 분석 결과",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "title": {
                        "type": "STRING",
                        "description": "기사 원문 제목",
                    },
                    "url": {
                        "type": "STRING",
                        "description": "기사 원문 URL",
                    },
                    "organization": {
                        "type": "STRING",
                        "description": "기사에 등장하는 주요 기업 또는 기관명",
                    },
                    "event": {
                        "type": "STRING",
                        "description": "기사에서 실제로 일어난 일을 한두 문장으로 설명",
                    },
                    "target": {
                        "type": "STRING",
                        "description": "교육 또는 제도의 주요 대상",
                    },
                    "format": {
                        "type": "STRING",
                        "description": "교육 운영 방식 또는 활동 형태",
                    },
                    "duration": {
                        "type": "STRING",
                        "description": "기사에 명시된 교육 기간 또는 시간. 없으면 빈 문자열",
                    },
                    "tools_or_topics": {
                        "type": "ARRAY",
                        "description": "교육에서 다룬 도구나 주제",
                        "items": {
                            "type": "STRING",
                        },
                    },
                    "outcomes": {
                        "type": "ARRAY",
                        "description": "기사에 명시된 결과나 산출물",
                        "items": {
                            "type": "STRING",
                        },
                    },
                    "hrd_meaning": {
                        "type": "STRING",
                        "description": "기사 내용을 바탕으로 도출한 HRD 관점의 의미",
                    },
                    "keywords": {
                        "type": "ARRAY",
                        "description": "기사 핵심 키워드 3~5개",
                        "items": {
                            "type": "STRING",
                        },
                        "minItems": 3,
                        "maxItems": 5,
                    },
                    "evidence": {
                        "type": "ARRAY",
                        "description": "분석의 근거가 된 기사 원문 내용의 요약",
                        "items": {
                            "type": "STRING",
                        },
                    },
                },
                "required": [
                    "title",
                    "url",
                    "organization",
                    "event",
                    "target",
                    "format",
                    "duration",
                    "tools_or_topics",
                    "outcomes",
                    "hrd_meaning",
                    "keywords",
                    "evidence",
                ],
            },
        },
        "shared_theme": {
            "type": "STRING",
            "description": "기사 전체에서 공통으로 확인되는 핵심 주제",
        },
        "background": {
            "type": "STRING",
            "description": "해당 변화가 나타난 배경과 맥락",
        },
        "current_changes": {
            "type": "ARRAY",
            "description": "현재 HRD 현장에서 나타나는 핵심 변화 3개",
            "items": {
                "type": "STRING",
            },
            "minItems": 3,
            "maxItems": 3,
        },
        "differences": {
            "type": "ARRAY",
            "description": "각 기사 사례가 서로 다른 지점",
            "items": {
                "type": "STRING",
            },
        },
        "hrd_implications": {
            "type": "ARRAY",
            "description": "교육 기획자에게 의미 있는 HRD 시사점 3~5개",
            "items": {
                "type": "STRING",
            },
            "minItems": 3,
            "maxItems": 5,
        },
        "risks_or_limits": {
            "type": "ARRAY",
            "description": "교육 적용 시 주의할 점이나 기사 분석의 한계",
            "items": {
                "type": "STRING",
            },
        },
        "candidate_tags": {
            "type": "ARRAY",
            "description": "자연스러운 태그 후보 5~8개. # 기호와 마크다운 기호를 넣지 않음",
            "items": {
                "type": "STRING",
            },
            "minItems": 5,
            "maxItems": 8,
        },
    },
    "required": [
        "articles",
        "shared_theme",
        "background",
        "current_changes",
        "differences",
        "hrd_implications",
        "risks_or_limits",
        "candidate_tags",
    ],
}


NEWSLETTER_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {
            "type": "STRING",
            "description": (
                "뉴스레터 제목. 18~38자. "
                "마크다운 기호 **, *, #, _, 백틱을 사용하지 않음"
            ),
        },
        "summary": {
            "type": "STRING",
            "description": (
                "전체 뉴스레터 한 줄 요약. 1~2문장. "
                "마크다운 기호를 사용하지 않음"
            ),
        },
        "insight": {
            "type": "STRING",
            "description": (
                "기사들을 종합한 HRD 인사이트. "
                "짧고 쉬운 문장으로 작성. "
                "마크다운 기호를 사용하지 않음"
            ),
        },
        "key_points": {
            "type": "ARRAY",
            "description": (
                "핵심 변화 3개. 각 항목에 의미 있는 이모지 1개 사용. "
                "마크다운 기호를 사용하지 않음"
            ),
            "items": {
                "type": "STRING",
            },
            "minItems": 3,
            "maxItems": 3,
        },
        "article_summaries": {
            "type": "ARRAY",
            "description": "입력 기사 순서를 유지한 기사별 요약",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "title": {
                        "type": "STRING",
                        "description": (
                            "기사 제목. 원문 의미를 유지. "
                            "마크다운 기호를 사용하지 않음"
                        ),
                    },
                    "summary": {
                        "type": "STRING",
                        "description": (
                            "기사 요약 2~3문장. "
                            "쉽고 친근한 설명체. "
                            "마크다운 기호를 사용하지 않음"
                        ),
                    },
                },
                "required": [
                    "title",
                    "summary",
                ],
            },
        },
        "conclusion": {
            "type": "STRING",
            "description": (
                "전체 정리 2~3문단. "
                "마지막 문장은 짧고 기억에 남게 작성. "
                "마크다운 기호를 사용하지 않음"
            ),
        },
        "department_apply": {
            "type": "ARRAY",
            "description": (
                "교육 기획할 때 활용할 포인트 3~5개. "
                "각 문장 앞에 '교육 기획할 때'를 반복하지 않음. "
                "마크다운 기호를 사용하지 않음"
            ),
            "items": {
                "type": "STRING",
            },
            "minItems": 3,
            "maxItems": 5,
        },
        "tags": {
            "type": "ARRAY",
            "description": (
                "자연스러운 핵심 키워드 3~4개. "
                "# 기호, **, 공백을 포함한 긴 문장을 사용하지 않음"
            ),
            "items": {
                "type": "STRING",
            },
            "minItems": 3,
            "maxItems": 4,
        },
    },
    "required": [
        "title",
        "summary",
        "insight",
        "key_points",
        "article_summaries",
        "conclusion",
        "department_apply",
        "tags",
    ],
}


FINAL_NEWSLETTER_SCHEMA = NEWSLETTER_SCHEMA