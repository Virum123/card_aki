# 카드의요정 구현 가이드 (주니어 데이터 분석가용)

이 문서는 현재 프로젝트를 처음부터 직접 재현하면서, 데이터 분석 포트폴리오로 연결하는 실습 가이드입니다.

## 1. 이 프로젝트를 데이터 분석 포트폴리오로 쓰는 방법

이 프로젝트는 추천 서비스 형태이지만, 분석 직무에서는 아래 역량을 보여줄 수 있습니다.

1. 데이터 수집/적재: 웹 수집 → DB 저장
2. 데이터 품질 점검: 결측, 중복, 태그 커버리지 확인
3. 지표 설계: 질문별 후보 감소율, 매칭율 분포
4. SQL/전처리: 조건 필터링, 텍스트 기반 피처화
5. 개선 실험: 필터 룰 변경 전후 비교

## 2. 목표 정의

최종적으로 아래 7개를 완성합니다.

1. 카드 데이터 수집
2. SQLite DB 구성
3. SQL 검증 쿼리 작성
4. pandas 전처리
5. 질문 기반 필터링 엔진
6. Streamlit UI 연결
7. 개선 로그/결과 문서화

## 3. 개발 환경 세팅

프로젝트 폴더에서 실행:

```bash
uv venv .venv
source .venv/bin/activate
UV_CACHE_DIR=.uv-cache uv sync
```

앱 실행:

```bash
UV_CACHE_DIR=.uv-cache uv run streamlit run app/streamlit_app.py
```

크롤링 + DB 재생성:

```bash
UV_CACHE_DIR=.uv-cache uv run python crawler/build_card_db.py
```

## 4. 프로젝트 구조 이해

- `crawler/build_card_db.py`: 수집/DB 생성
- `data/cards.db`: SQLite DB
- `data/cards_snapshot.json`: 수집 스냅샷
- `app/question_bank.py`: 질문 정의
- `app/streamlit_app.py`: 질문/필터/추천 UI
- `IMPORTANT_CHANGES.md`: 주요 변경 이력

## 5. DB 구성 및 핵심 컬럼

현재 핵심 컬럼:

- `card_ad_id`: 카드 고유 ID
- `name`, `issuer`, `summary`
- `card_image_url`
- `min_spend_required_krw`
- `domestic_annual_fee`, `foreign_annual_fee`
- `benefit_tags`
- `detail_url`, `crawled_at`

## 6. SQL로 데이터 품질 점검 (실무 핵심)

### 6-1. 전체 카드 수

```sql
SELECT COUNT(*) AS total_cards FROM cards;
```

### 6-2. 결측 확인

```sql
SELECT
  SUM(CASE WHEN min_spend_required_krw IS NULL THEN 1 ELSE 0 END) AS null_spend,
  SUM(CASE WHEN card_image_url IS NULL OR card_image_url='' THEN 1 ELSE 0 END) AS null_image
FROM cards;
```

### 6-3. 카드사 분포

```sql
SELECT issuer, COUNT(*) AS cnt
FROM cards
GROUP BY issuer
ORDER BY cnt DESC;
```

### 6-4. 해외/마일리지/구독 관련 카드 수 점검

```sql
-- 해외/직구/트래블
SELECT COUNT(*)
FROM cards
WHERE LOWER(name||' '||summary||' '||benefit_tags)
REGEXP '외화결제|해외|직구|travel|공항|라운지|면세|환전|visa|master|amex|jcb|unionpay|유니온페이';

-- 마일리지
SELECT COUNT(*)
FROM cards
WHERE LOWER(name||' '||summary||' '||benefit_tags)
REGEXP '항공마일리지|마일리지|스카이패스|대한항공|아시아나|마일';

-- 구독/디지털
SELECT COUNT(*)
FROM cards
WHERE LOWER(name||' '||summary||' '||benefit_tags)
REGEXP 'ott|스트리밍|구독|정기결제|멤버십|넷플릭스|유튜브|디즈니|티빙|웨이브|쿠팡플레이|spotify|애플뮤직|문화|디지털';
```

## 7. 전처리 (pandas) 최소 필수

핵심은 문자열 결합 컬럼(`combined_text`)을 만드는 것입니다.

```python
df["combined_text"] = (
    df["name"].fillna("").astype(str)
    + " " + df["summary"].fillna("").astype(str)
    + " " + df["benefit_tags"].fillna("").astype(str)
).str.lower()
```

이후 `키워드 포함 여부`로 파생 변수 생성:

```python
overseas_kw = ["외화결제", "해외", "직구", "travel", "공항", "라운지"]
df["is_overseas"] = df["combined_text"].apply(lambda t: any(k in t for k in overseas_kw))
```

## 8. 질문 필터 로직 이해

필터는 2단계입니다.

1. 하드 필터: 실적/연회비/yes-no 질문으로 후보 자체를 줄임
2. 소프트 점수: 남은 후보를 점수로 정렬

현재 개선된 포인트:

- 해외/구독 키워드 확장으로 과필터링 완화
- 마일리지 후속 질문을 `대한항공 선호 예/아니오`로 단순화
- 질문 완료 후 `애니메이션 화면 -> 결과 화면` 전환

## 9. 직접 재현 순서 (초보자용)

### Step 1) DB 만들기

```bash
UV_CACHE_DIR=.uv-cache uv run python crawler/build_card_db.py
```

완료 확인:

```bash
sqlite3 data/cards.db "SELECT COUNT(*) FROM cards;"
```

### Step 2) SQL 점검하기

위 6장 쿼리를 그대로 실행해서 품질 점검.

### Step 3) 질문 문구 수정해보기

`app/question_bank.py`에서 질문 문구/옵션 수정.

예시:
- "대한항공 마일리지를 선호하시나요?" (예/아니오)

### Step 4) 필터 룰 수정해보기

`app/streamlit_app.py`에서
- `OVERSEAS_KEYWORDS`, `SUBSCRIPTION_KEYWORDS` 조정
- `apply_question_filter()` 조건 확인

### Step 5) 앱 실행 후 확인

```bash
UV_CACHE_DIR=.uv-cache uv run streamlit run app/streamlit_app.py --server.headless true --server.port 8510
```

브라우저: `http://localhost:8510`

### Step 6) 개선 전/후 기록

`IMPORTANT_CHANGES.md`에 아래 형식으로 기록:

- 문제: 특정 질문에서 후보 급감
- 가설: 키워드 누락
- 수정: 키워드/태그 alias 확장
- 결과: 질문별 후보 수 변화

## 10. 데이터 분석 면접에서 설명하는 방법

면접에서는 아래 순서로 설명하면 좋습니다.

1. 문제 정의: 카드 추천에서 필터 급감 이슈 발견
2. 데이터 진단: SQL로 태그/텍스트 커버리지 검증
3. 개선: 키워드/룰 조정
4. 결과: 잔존 카드 수와 추천 품질 개선
5. 운영: GitHub Actions로 DB 자동 업데이트

## 11. 다음 확장 과제 (추천)

1. 질문별 통과율 대시보드(막대그래프)
2. 카드사 편중도 지표(엔트로피, Top-N 비중)
3. 사용자 응답 로그 테이블 추가 후 퍼널 분석
4. 규칙 기반 추천과 점수 기반 추천 성능 비교

---

필요하면 다음 문서로 이어서 작성하세요:
- `docs/SQL_PRACTICE_SET.md` (실전 SQL 문제 20개)
- `docs/FEATURE_ENGINEERING_NOTE.md` (피처 설계 노트)
- `docs/ANALYSIS_REPORT_TEMPLATE.md` (보고서 템플릿)
