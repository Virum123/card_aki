# 카드의요정 (Streamlit)

스무고개 문답 방식으로 사용자 소비 성향을 파악하고, 조건에 맞는 카드를 단계적으로 좁혀 추천하는 서비스입니다.

## 핵심 UX
- 요정 캐릭터가 말풍선으로 질문하는 단계형 문답 UI
- 답변할 때마다 충족 카드 수가 줄어드는 흐름 표시
- 질문 종료 후 `카드 망 필터링` 애니메이션 출력
- 상위 10개 카드(이미지 포함) 우선 노출 + `더보기`로 추가 조회

## 데이터 소스
- 네이버 카드검색: https://card-search.naver.com/list
- 수집 방식: GraphQL `smartSearch` 페이지네이션 + 카드 상세 실적 보강

## 저장 데이터
- `data/cards.db` (SQLite)
- `data/cards_snapshot.json` (검증 스냅샷)
- 컬럼 예시: 카드명, 카드사, 요약, 카드 이미지 URL, 최소 실적, 연회비, 혜택 태그, 상세 링크

## 실행 방법
```bash
uv venv .venv
source .venv/bin/activate
UV_CACHE_DIR=.uv-cache uv sync

uv run python crawler/build_card_db.py
uv run streamlit run app/streamlit_app.py
```

기본 링크: http://localhost:8501

## 자동 업데이트 파이프라인
- GitHub Actions: `.github/workflows/update_cards.yml`
- 동작:
  - 매일 03:15 UTC 스케줄 실행
  - 수동 실행(`workflow_dispatch`) 지원
  - 크롤링 후 `data/cards.db`, `data/cards_snapshot.json` 변경 시 자동 커밋/푸시

## 질문 정의 위치
- `app/question_bank.py`
- 질문 타입: `single`, `range`
