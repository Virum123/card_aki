"""Card Akinator Streamlit prototype.

질문(설문) 기반으로 카드 후보를 좁히는 MVP 화면.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    # 프로젝트 루트에서 실행할 때.
    from app.question_bank import QUESTIONS
except ModuleNotFoundError:
    # app 디렉터리 기준으로 실행할 때.
    from question_bank import QUESTIONS

DB_PATH = Path("data/cards.db")
OVERSEAS_KEYWORDS = ["외화결제", "해외", "해외이용", "해외결제", "직구"]
MILEAGE_KEYWORDS = ["항공마일리지", "마일리지", "스카이패스", "대한항공", "아시아나"]
KOREAN_AIR_KEYWORDS = ["대한항공", "스카이패스", "korean air"]
CAFE_KEYWORDS = ["카페", "베이커리", "스타벅스", "투썸", "커피"]
DINING_KEYWORDS = ["외식", "배달", "요기요", "배민", "식당", "레스토랑"]
SHOPPING_KEYWORDS = ["쇼핑", "온라인", "인터넷쇼핑", "백화점", "마트"]
CONVENIENCE_KEYWORDS = ["편의점", "gs25", "cu", "세븐일레븐", "이마트24"]
TELECOM_KEYWORDS = ["통신", "skt", "kt", "lg u+", "알뜰폰"]
OTT_KEYWORDS = [
    "ott",
    "스트리밍",
    "구독",
    "정기결제",
    "멤버십",
    "넷플릭스",
    "유튜브",
    "유튜브프리미엄",
    "디즈니",
    "디즈니플러스",
    "티빙",
    "웨이브",
    "쿠팡플레이",
    "쿠팡와우",
    "네이버플러스",
    "spotify",
    "애플뮤직",
]
SIMPLEPAY_KEYWORDS = ["간편결제", "삼성페이", "네이버페이", "카카오페이", "pay"]
CAR_KEYWORDS = ["오토", "주유", "하이패스", "주차", "차량"]
PUBLIC_TRANSPORT_KEYWORDS = ["대중교통", "버스", "지하철", "교통"]
INTERNET_BANK_YES_ISSUERS = {"현대카드", "삼성카드", "롯데카드", "BC"}
INTERNET_BANK_NO_ISSUERS = {"KB국민카드", "우리카드", "신한카드", "하나카드"}
TAG_ALIAS_MAP = {
    "카페": ["카페/베이커리"],
    "외식": ["외식"],
    "쇼핑": ["쇼핑", "대형마트"],
    "편의점": ["편의점"],
    "통신": ["통신"],
    "ott": [],
    "간편결제": ["간편결제"],
    "차": ["오토", "주유", "하이패스"],
    "대중교통": ["대중교통"],
    "해외": ["외화결제"],
    "마일리지": ["항공마일리지"],
}
WEIGHTS = {
    "overseas_yesno": 10,
    "mileage_interest": 12,
    "mileage_airline": 8,
    "bakery_cafe_yesno": 6,
    "dining_delivery_yesno": 6,
    "shopping_yesno": 6,
    "convenience_yesno": 5,
    "telecom_yesno": 6,
    "ott_streaming_yesno": 6,
    "simplepay_yesno": 6,
    "car_benefit_yesno": 5,
    "public_transport_yesno": 6,
    "internet_bank_main": 8,
}

st.set_page_config(page_title="카드의요정", page_icon="🧚", layout="wide")

st.title("카드의요정")
st.caption("아키네이터형 스무고개 문답 기반 카드 추천")

st.markdown(
    """
**기획 의도**
과거 유행했던 아키네이터처럼 스무고개 방식의 문답을 통해
사용자에게 가장 적합하다고 판단되는 카드상품을 추천하는 시스템입니다.
"""
)

st.markdown(
    """
**유사 서비스 참고**
- 카드고릴라 1분 카드 매칭: https://www.card-gorilla.com/test/intro
- 본 서비스는 특정 발급 채널 유도보다 사용자 적합성 중심 추천을 지향합니다.
"""
)

if not DB_PATH.exists():
    st.error("DB 파일이 없습니다. 먼저 `uv run python crawler/build_card_db.py`를 실행하세요.")
    st.stop()


@st.cache_data(ttl=300)
def load_cards() -> pd.DataFrame:
    """DB에서 카드 목록을 읽어 DataFrame으로 변환."""
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            """
            SELECT
                id,
                card_ad_id,
                name,
                COALESCE(NULLIF(issuer, ''), '미상') AS issuer,
                COALESCE(NULLIF(summary, ''), '-') AS summary,
                min_spend_required_krw,
                domestic_annual_fee,
                foreign_annual_fee,
                family_annual_fee,
                COALESCE(NULLIF(benefit_tags, ''), '-') AS benefit_tags,
                detail_url,
                source,
                crawled_at
            FROM cards
            ORDER BY id DESC
            """,
            conn,
        )
    # 혜택 키워드 매칭용 통합 텍스트 컬럼.
    df["combined_text"] = (
        df["name"].fillna("").astype(str)
        + " "
        + df["summary"].fillna("").astype(str)
        + " "
        + df["benefit_tags"].fillna("").astype(str)
    ).str.lower()
    return df


def _contains_any(frame: pd.DataFrame, keywords: list[str]) -> pd.DataFrame:
    if not keywords:
        return frame
    mask = pd.Series(False, index=frame.index)
    for kw in keywords:
        mask = mask | frame["combined_text"].str.contains(str(kw).lower(), na=False)
    return frame[mask]


def _contains_benefit_tag(frame: pd.DataFrame, logical_key: str, fallback_keywords: list[str]) -> pd.DataFrame:
    """benefit_tags 우선 매칭 + fallback 키워드 매칭."""
    tag_aliases = TAG_ALIAS_MAP.get(logical_key, [])
    if tag_aliases:
        tag_mask = pd.Series(False, index=frame.index)
        for tag in tag_aliases:
            tag_mask = tag_mask | frame["benefit_tags"].astype(str).str.contains(tag, na=False)
        matched = frame[tag_mask]
        if len(matched) > 0:
            return matched
    return _contains_any(frame, fallback_keywords)


def apply_question_filter(frame: pd.DataFrame, question_id: str, answer, answers: dict[str, object]) -> pd.DataFrame:
    """질문 ID별 하드 필터 규칙 적용."""
    if answer is None:
        return frame

    # 하드 필터는 실적/연회비만 적용한다.
    if question_id == "monthly_spend_level":
        required = pd.to_numeric(frame["min_spend_required_krw"], errors="coerce").fillna(0)
        if answer == "under_300k":
            return frame[required < 300000]
        if answer == "300k_700k":
            return frame[required < 700000]
        if answer == "over_700k":
            return frame
        return frame

    if question_id == "annual_fee_range":
        if not isinstance(answer, (list, tuple)) or len(answer) != 2:
            return frame
        low, high = float(answer[0]), float(answer[1])
        fee = pd.to_numeric(frame["domestic_annual_fee"], errors="coerce").fillna(0)
        # 슬라이더 최대 끝(110000)은 "10만원 이상 포함(상한 없음)"으로 처리.
        if high >= 110000:
            return frame[fee >= low]
        return frame[fee.between(low, high)]

    return frame


def _keyword_match_mask(frame: pd.DataFrame, logical_key: str, fallback_keywords: list[str]) -> pd.Series:
    """카드별 혜택 매칭 여부를 bool mask로 반환."""
    tag_aliases = TAG_ALIAS_MAP.get(logical_key, [])
    if tag_aliases:
        tag_mask = pd.Series(False, index=frame.index)
        for tag in tag_aliases:
            tag_mask = tag_mask | frame["benefit_tags"].astype(str).str.contains(tag, na=False)
        if tag_mask.any():
            return tag_mask
    text_mask = pd.Series(False, index=frame.index)
    for kw in fallback_keywords:
        text_mask = text_mask | frame["combined_text"].str.contains(str(kw).lower(), na=False)
    return text_mask


def apply_match_score(frame: pd.DataFrame, answers: dict[str, object]) -> pd.DataFrame:
    """선호 기반 매치 점수/매치율 계산."""
    out = frame.copy()
    out["match_score"] = 0.0
    out["max_score"] = 0.0

    def add_scored_match(question_id: str, logical_key: str, fallback_keywords: list[str]) -> None:
        if answers.get(question_id) != "yes":
            return
        weight = WEIGHTS[question_id]
        mask = _keyword_match_mask(out, logical_key, fallback_keywords)
        out["max_score"] += weight
        out.loc[mask, "match_score"] += weight

    add_scored_match("overseas_yesno", "해외", OVERSEAS_KEYWORDS)
    add_scored_match("mileage_interest", "마일리지", MILEAGE_KEYWORDS)
    add_scored_match("bakery_cafe_yesno", "카페", CAFE_KEYWORDS)
    add_scored_match("dining_delivery_yesno", "외식", DINING_KEYWORDS)
    add_scored_match("shopping_yesno", "쇼핑", SHOPPING_KEYWORDS)
    add_scored_match("convenience_yesno", "편의점", CONVENIENCE_KEYWORDS)
    add_scored_match("telecom_yesno", "통신", TELECOM_KEYWORDS)
    add_scored_match("ott_streaming_yesno", "ott", OTT_KEYWORDS)
    add_scored_match("simplepay_yesno", "간편결제", SIMPLEPAY_KEYWORDS)
    add_scored_match("car_benefit_yesno", "차", CAR_KEYWORDS)
    add_scored_match("public_transport_yesno", "대중교통", PUBLIC_TRANSPORT_KEYWORDS)

    # 마일리지 항공사 분기는 가점(소프트 규칙)으로 처리한다.
    if answers.get("mileage_interest") == "yes":
        airline_answer = answers.get("mileage_airline")
        if airline_answer == "korean_air":
            weight = WEIGHTS["mileage_airline"]
            ka_mask = _contains_any(out, KOREAN_AIR_KEYWORDS).index.isin(out.index)
            # above returns filtered frame; rebuild boolean mask directly:
            ka_mask = out["combined_text"].str.contains("대한항공|스카이패스|korean air", na=False)
            out["max_score"] += weight
            out.loc[ka_mask, "match_score"] += weight
        elif airline_answer == "others":
            weight = WEIGHTS["mileage_airline"]
            mileage_mask = _keyword_match_mask(out, "마일리지", MILEAGE_KEYWORDS)
            ka_mask = out["combined_text"].str.contains("대한항공|스카이패스|korean air", na=False)
            out["max_score"] += weight
            out.loc[mileage_mask & (~ka_mask), "match_score"] += weight

    # 주거래은행 질문은 매치율 계산에 가점으로 반영.
    bank_answer = answers.get("internet_bank_main")
    if bank_answer == "yes":
        weight = WEIGHTS["internet_bank_main"]
        out["max_score"] += weight
        out.loc[out["issuer"].isin(INTERNET_BANK_YES_ISSUERS), "match_score"] += weight
    elif bank_answer == "no":
        weight = WEIGHTS["internet_bank_main"]
        out["max_score"] += weight
        out.loc[out["issuer"].isin(INTERNET_BANK_NO_ISSUERS), "match_score"] += weight

    out["match_rate"] = 0.0
    valid = out["max_score"] > 0
    out.loc[valid, "match_rate"] = (out.loc[valid, "match_score"] / out.loc[valid, "max_score"]) * 100

    return out.sort_values(
        by=["match_rate", "match_score", "domestic_annual_fee", "card_ad_id"],
        ascending=[False, False, True, True],
    )


def get_active_questions(answers: dict[str, object]) -> list[dict]:
    """조건부 질문(visible_if)을 반영한 실제 질문 흐름."""
    active: list[dict] = []
    for q in QUESTIONS:
        rule = q.get("visible_if")
        if not rule:
            active.append(q)
            continue
        if answers.get(rule["question_id"]) == rule["equals"]:
            active.append(q)
    return active


def filter_by_answers(df: pd.DataFrame, answers: dict[str, object], upto_step: int | None = None) -> pd.DataFrame:
    """저장된 응답으로 카드 후보를 순차 필터링한다."""
    filtered = df.copy()
    active_questions = get_active_questions(answers)
    questions_scope = active_questions if upto_step is None else active_questions[: upto_step + 1]
    for q in questions_scope:
        saved_answer = answers.get(q["id"])
        filtered = apply_question_filter(filtered, q["id"], saved_answer, answers)
    return filtered


def _render_question_input(question: dict, current_answer):
    """질문 타입에 맞는 입력 컴포넌트를 렌더링하고 현재 답변을 반환한다."""
    def format_manwon(value: int) -> str:
        if value % 10000 == 0:
            return f"{value // 10000}만"
        return f"{value / 10000:.1f}만"

    qid = question["id"]
    qtype = question["type"]
    title = question["title"]

    if qtype == "single":
        options = question.get("options", [])
        labels = [opt["label"] for opt in options]
        label_to_value = {opt["label"]: opt["value"] for opt in options}
        value_to_label = {opt["value"]: opt["label"] for opt in options}
        default_label = value_to_label.get(current_answer, labels[0] if labels else "")
        selected_label = st.radio(
            title,
            labels,
            index=labels.index(default_label) if default_label in labels else 0,
            key=f"input_{qid}",
        )
        return label_to_value.get(selected_label)

    if qtype == "multi":
        options = question.get("options", [])
        labels = [opt["label"] for opt in options]
        label_to_value = {opt["label"]: opt["value"] for opt in options}
        value_to_label = {opt["value"]: opt["label"] for opt in options}
        default_labels = [value_to_label[x] for x in (current_answer or []) if x in value_to_label]
        selected_labels = st.multiselect(title, labels, default=default_labels, key=f"input_{qid}")
        return [label_to_value[x] for x in selected_labels]

    if qtype == "text":
        return st.text_input(title, value=str(current_answer or ""), key=f"input_{qid}")

    if qtype == "range":
        min_value = int(question.get("min", 0))
        max_value = int(question.get("max", 100000))
        step = int(question.get("step", 1000))
        default_value = current_answer if current_answer else (min_value, max_value)
        if question.get("display_unit") == "manwon":
            # 화면 표시는 만원 단위, 이동 단위는 0.5만원(=5,000원)으로 유지.
            min_m = min_value / 10000
            max_m = max_value / 10000
            step_m = step / 10000
            default_m = (default_value[0] / 10000, default_value[1] / 10000)
            selected_m = st.slider(
                title,
                min_value=float(min_m),
                max_value=float(max_m),
                value=(float(default_m[0]), float(default_m[1])),
                step=float(step_m),
                format="%.1f만",
                key=f"input_{qid}",
            )
            low = int(selected_m[0] * 10000)
            high = int(selected_m[1] * 10000)
            high_text = "10만+" if high >= max_value else format_manwon(high)
            st.caption(f"선택 범위: {format_manwon(low)} ~ {high_text}")
            return (low, high)

        selected_range = st.slider(
            title,
            min_value=min_value,
            max_value=max_value,
            value=default_value,
            step=step,
            key=f"input_{qid}",
        )
        return selected_range

    if qtype == "number":
        min_value = int(question.get("min", 0))
        max_value = int(question.get("max", 100000))
        step = int(question.get("step", 1000))
        default_value = int(current_answer if current_answer is not None else question.get("default", min_value))
        return st.number_input(
            title,
            min_value=min_value,
            max_value=max_value,
            step=step,
            value=default_value,
            key=f"input_{qid}",
        )

    return current_answer


def render_questions_and_filter(df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """안내원 형식으로 질문을 단계별 렌더링하고 응답 기반 결과를 반환한다."""
    if not QUESTIONS:
        st.warning("질문이 아직 등록되지 않았습니다. `app/question_bank.py`에 QUESTIONS를 입력하세요.")
        return df, False

    if "survey_step" not in st.session_state:
        st.session_state.survey_step = 0
    if "survey_answers" not in st.session_state:
        st.session_state.survey_answers = {}
    if "survey_submitted" not in st.session_state:
        st.session_state.survey_submitted = False

    active_questions = get_active_questions(st.session_state.survey_answers)
    total_questions = len(active_questions)
    if total_questions == 0:
        return df, False

    if st.session_state.survey_step >= total_questions:
        st.session_state.survey_step = total_questions - 1

    step = st.session_state.survey_step
    question = active_questions[step]
    qid = question["id"]

    st.subheader("문답 진행")
    st.progress((step + 1) / total_questions, text=f"{step + 1} / {total_questions}")
    st.caption(f"전체 카드 {len(df)}개에서 답변 조건으로 점점 좁혀집니다.")

    # 안내원 채팅 버블 스타일로 질문을 보여준다.
    with st.chat_message("assistant", avatar="🧚"):
        st.markdown(f"안녕하세요, 카드의요정입니다. {step + 1}번째 질문 드릴게요.")
        st.markdown(f"### {question['title']}")

    current_answer = st.session_state.survey_answers.get(qid)
    answer = _render_question_input(question, current_answer)

    # 현재 질문 답변까지 반영한 임시 후보 수를 실시간으로 계산한다.
    preview_answers = dict(st.session_state.survey_answers)
    preview_answers[qid] = answer
    preview_filtered = filter_by_answers(df, preview_answers, upto_step=step)
    st.metric("현재 조건 충족 카드 수", len(preview_filtered))
    overseas_count = len(_contains_any(preview_filtered, OVERSEAS_KEYWORDS))
    st.caption(f"현재 후보 중 해외결제 혜택 보유 카드: {overseas_count}개")

    if len(preview_filtered) > 0:
        st.caption("현재 조건 기준 상위 3개 미리보기")
        st.dataframe(
            preview_filtered[["name", "issuer", "domestic_annual_fee", "benefit_tags"]].head(3),
            use_container_width=True,
            hide_index=True,
        )

    col_prev, col_next, col_finish, col_reset = st.columns(4)

    if col_prev.button("이전", disabled=step == 0, use_container_width=True):
        st.session_state.survey_answers[qid] = answer
        st.session_state.survey_step = max(0, step - 1)
        st.rerun()

    if step < total_questions - 1:
        if col_next.button("다음", use_container_width=True):
            st.session_state.survey_answers[qid] = answer
            st.session_state.survey_step = min(total_questions - 1, step + 1)
            st.rerun()
    else:
        if col_finish.button("결과 보기", use_container_width=True):
            st.session_state.survey_answers[qid] = answer
            st.session_state.survey_submitted = True
            st.rerun()

    if col_reset.button("처음부터", use_container_width=True):
        st.session_state.survey_step = 0
        st.session_state.survey_answers = {}
        st.session_state.survey_submitted = False
        st.rerun()

    if not st.session_state.survey_submitted:
        st.info("안내원의 질문에 답하면서 `다음`으로 진행하고, 마지막에 `결과 보기`를 눌러주세요.")
        return df.head(0), False

    filtered = filter_by_answers(df, st.session_state.survey_answers)
    filtered = apply_match_score(filtered, st.session_state.survey_answers)

    return filtered, True


df = load_cards()
filtered, submitted = render_questions_and_filter(df)

st.subheader("추천 결과")
st.metric("추천 카드 수", len(filtered))
if submitted:
    st.dataframe(
        filtered[
            [
                "match_rate",
                "match_score",
                "card_ad_id",
                "name",
                "issuer",
                "summary",
                "min_spend_required_krw",
                "domestic_annual_fee",
                "foreign_annual_fee",
                "benefit_tags",
                "detail_url",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

st.divider()
with st.expander("실행 가이드", expanded=False):
    st.code(
        """uv run python crawler/build_card_db.py
uv run streamlit run app/streamlit_app.py""",
        language="bash",
    )

with st.expander("질문 작성 위치", expanded=False):
    st.code("app/question_bank.py", language="text")
    st.caption("질문은 위 파일의 `QUESTIONS` 리스트에 추가/수정하면 됩니다.")
