"""Card Akinator Streamlit app.

요정 안내형 질문 UI + 조건 필터링 + 매치 점수 기반 추천 결과 화면.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

try:
    from app.question_bank import QUESTIONS
except ModuleNotFoundError:
    from question_bank import QUESTIONS

DB_PATH = Path("data/cards.db")
FAIRY_IMAGE_PATH = Path("app/assets/fairy.svg")

OVERSEAS_KEYWORDS = ["외화결제", "해외", "해외이용", "해외결제", "직구"]
MILEAGE_KEYWORDS = ["항공마일리지", "마일리지", "스카이패스", "대한항공", "아시아나"]
CAFE_KEYWORDS = ["카페", "베이커리", "스타벅스", "투썸", "커피"]
DINING_KEYWORDS = ["외식", "배달", "요기요", "배민", "식당", "레스토랑"]
SHOPPING_KEYWORDS = ["쇼핑", "온라인", "인터넷쇼핑", "백화점", "마트"]
CONVENIENCE_KEYWORDS = ["편의점", "gs25", "cu", "세븐일레븐", "이마트24"]
TELECOM_KEYWORDS = ["통신", "skt", "kt", "lg u+", "알뜰폰"]
SUBSCRIPTION_KEYWORDS = [
    "ott",
    "스트리밍",
    "구독",
    "정기결제",
    "멤버십",
    "넷플릭스",
    "유튜브",
    "디즈니",
    "티빙",
    "웨이브",
    "쿠팡플레이",
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
    "구독": [],
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


def inject_styles() -> None:
    """요정 대화형 화면 스타일."""
    st.markdown(
        """
        <style>
            .fairy-wrap {
                display: flex;
                align-items: flex-start;
                gap: 16px;
                margin: 8px 0 20px 0;
            }
            .fairy-bubble {
                background: linear-gradient(135deg, #12243f 0%, #1d3b66 100%);
                color: #f6f8ff;
                border: 1px solid #4e7abc;
                border-radius: 18px;
                padding: 16px 18px;
                font-size: 1.18rem;
                font-weight: 700;
                line-height: 1.45;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.22);
            }
            .candidate-count {
                font-size: 1.02rem;
                color: #98a6b8;
                margin-bottom: 8px;
            }
            .card-tile {
                border: 1px solid #1f2d41;
                border-radius: 16px;
                background: #0c1420;
                padding: 14px;
                margin-bottom: 12px;
            }
            .match-badge {
                display: inline-block;
                padding: 4px 10px;
                border-radius: 999px;
                background: #123c2e;
                color: #8ef2c8;
                font-size: 0.82rem;
                font-weight: 700;
                margin-bottom: 8px;
            }
            .card-title {
                font-size: 1.05rem;
                font-weight: 800;
                color: #f3f7ff;
                margin-bottom: 4px;
            }
            .card-meta {
                color: #9fb0c8;
                font-size: 0.9rem;
                margin-bottom: 8px;
            }
            .card-summary {
                color: #d8e0ef;
                font-size: 0.92rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=300)
def load_cards() -> pd.DataFrame:
    """DB에서 카드 목록을 DataFrame으로 로드."""
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            """
            SELECT
                id,
                card_ad_id,
                name,
                COALESCE(NULLIF(issuer, ''), '미상') AS issuer,
                COALESCE(NULLIF(summary, ''), '-') AS summary,
                COALESCE(NULLIF(card_image_url, ''), '') AS card_image_url,
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

    # 혜택 텍스트 매칭을 위한 통합 텍스트.
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


def _keyword_match_mask(frame: pd.DataFrame, logical_key: str, fallback_keywords: list[str]) -> pd.Series:
    """benefit_tags 우선 매칭 후 텍스트 fallback."""
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


def apply_question_filter(frame: pd.DataFrame, question_id: str, answer) -> pd.DataFrame:
    """하드 필터: 실적/연회비."""
    if answer is None:
        return frame

    if question_id == "monthly_spend_level":
        required = pd.to_numeric(frame["min_spend_required_krw"], errors="coerce").fillna(0)
        if answer == "under_300k":
            return frame[required < 300000]
        if answer == "300k_700k":
            # 포함형 규칙: 30~70 선택 시 70 미만 카드 포함.
            return frame[required < 700000]
        if answer == "over_700k":
            # 포함형 규칙: 70+ 선택 시 전체 포함.
            return frame

    if question_id == "annual_fee_range":
        if not isinstance(answer, (list, tuple)) or len(answer) != 2:
            return frame
        low, high = float(answer[0]), float(answer[1])
        fee = pd.to_numeric(frame["domestic_annual_fee"], errors="coerce").fillna(0)
        if high >= 110000:
            return frame[fee >= low]
        return frame[fee.between(low, high)]

    return frame


def apply_match_score(frame: pd.DataFrame, answers: dict[str, object]) -> pd.DataFrame:
    """소프트 매칭 점수 계산."""
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
    add_scored_match("ott_streaming_yesno", "구독", SUBSCRIPTION_KEYWORDS)
    add_scored_match("simplepay_yesno", "간편결제", SIMPLEPAY_KEYWORDS)
    add_scored_match("car_benefit_yesno", "차", CAR_KEYWORDS)
    add_scored_match("public_transport_yesno", "대중교통", PUBLIC_TRANSPORT_KEYWORDS)

    # 마일리지 항공사 선호는 하드 필터 대신 가중치만 적용한다.
    if answers.get("mileage_interest") == "yes":
        airline = answers.get("mileage_airline")
        if airline in {"korean_air", "others"}:
            weight = WEIGHTS["mileage_airline"]
            ka_mask = out["combined_text"].str.contains("대한항공|스카이패스|korean air", na=False)
            mileage_mask = _keyword_match_mask(out, "마일리지", MILEAGE_KEYWORDS)
            out["max_score"] += weight
            if airline == "korean_air":
                out.loc[ka_mask, "match_score"] += weight
            else:
                out.loc[mileage_mask & (~ka_mask), "match_score"] += weight

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
    active: list[dict] = []
    for q in QUESTIONS:
        rule = q.get("visible_if")
        if not rule or answers.get(rule["question_id"]) == rule["equals"]:
            active.append(q)
    return active


def filter_by_answers(df: pd.DataFrame, answers: dict[str, object], upto_step: int | None = None) -> pd.DataFrame:
    filtered = df.copy()
    active_questions = get_active_questions(answers)
    scope = active_questions if upto_step is None else active_questions[: upto_step + 1]
    for q in scope:
        filtered = apply_question_filter(filtered, q["id"], answers.get(q["id"]))
    return filtered


def _format_fee_manwon(value: int) -> str:
    if value % 10000 == 0:
        return f"{value // 10000}만"
    return f"{value / 10000:.1f}만"


def render_question_input(question: dict, current_answer):
    qid = question["id"]
    qtype = question["type"]

    if qtype == "single":
        options = question.get("options", [])
        labels = [opt["label"] for opt in options]
        label_to_value = {opt["label"]: opt["value"] for opt in options}
        value_to_label = {opt["value"]: opt["label"] for opt in options}
        default = value_to_label.get(current_answer, labels[0] if labels else "")
        selected = st.radio(
            "",
            labels,
            index=labels.index(default) if default in labels else 0,
            key=f"input_{qid}",
            label_visibility="collapsed",
        )
        return label_to_value.get(selected)

    if qtype == "range":
        min_value = int(question.get("min", 0))
        max_value = int(question.get("max", 100000))
        step = int(question.get("step", 1000))
        default_value = current_answer if current_answer else (min_value, max_value)

        if question.get("display_unit") == "manwon":
            selected = st.slider(
                "",
                min_value=float(min_value / 10000),
                max_value=float(max_value / 10000),
                value=(float(default_value[0] / 10000), float(default_value[1] / 10000)),
                step=float(step / 10000),
                format="%.1f만",
                key=f"input_{qid}",
                label_visibility="collapsed",
            )
            low = int(selected[0] * 10000)
            high = int(selected[1] * 10000)
            high_text = "10만+" if high >= max_value else _format_fee_manwon(high)
            st.caption(f"선택 범위: {_format_fee_manwon(low)} ~ {high_text}")
            return (low, high)

    return current_answer


def render_filtering_animation(before_count: int, after_count: int) -> None:
    """질문 완료 후 카드가 망으로 걸러지는 효과를 출력."""
    html = f"""
    <div style=\"width:100%;border-radius:16px;background:#0d1625;padding:16px 18px;border:1px solid #1f2f4d;\">
      <div style=\"display:flex;justify-content:space-between;align-items:center;color:#dbe8ff;\">
        <strong>카드 망 필터링 진행 중...</strong>
        <span id=\"countText\" style=\"color:#8ef2c8;font-weight:700;\">{before_count} -> {after_count}</span>
      </div>
      <canvas id=\"netCanvas\" width=\"980\" height=\"180\" style=\"width:100%;height:180px;margin-top:10px;\"></canvas>
    </div>
    <script>
      const canvas = document.getElementById('netCanvas');
      const ctx = canvas.getContext('2d');
      let progress = 0;
      let shown = {before_count};
      const target = {after_count};
      const countText = document.getElementById('countText');
      function draw() {{
        ctx.clearRect(0,0,canvas.width,canvas.height);
        const rows = 7;
        const cols = 14;
        const shrink = 1 - (progress * 0.72);
        const offsetX = (canvas.width * (1 - shrink)) / 2;
        const offsetY = (canvas.height * (1 - shrink)) / 2;

        ctx.strokeStyle = '#63a7ff';
        ctx.lineWidth = 1.1;

        for (let r=0; r<rows; r++) {{
          for (let c=0; c<cols; c++) {{
            const x = offsetX + (c / (cols-1)) * canvas.width * shrink;
            const y = offsetY + (r / (rows-1)) * canvas.height * shrink;
            if (c < cols-1) {{
              const nx = offsetX + ((c+1) / (cols-1)) * canvas.width * shrink;
              ctx.beginPath();
              ctx.moveTo(x,y);
              ctx.lineTo(nx,y);
              ctx.stroke();
            }}
            if (r < rows-1) {{
              const ny = offsetY + ((r+1) / (rows-1)) * canvas.height * shrink;
              ctx.beginPath();
              ctx.moveTo(x,y);
              ctx.lineTo(x,ny);
              ctx.stroke();
            }}
          }}
        }}

        ctx.fillStyle = '#ffde8a';
        ctx.beginPath();
        ctx.arc(canvas.width/2, canvas.height/2, 9, 0, Math.PI*2);
        ctx.fill();
      }}

      const timer = setInterval(() => {{
        progress += 0.035;
        if (shown > target) {{
          shown = Math.max(target, shown - Math.max(1, Math.ceil((shown - target) * 0.14)));
          countText.innerText = `${{shown}} -> {after_count}`;
        }}
        draw();
        if (progress >= 1) {{
          clearInterval(timer);
          countText.innerText = '{before_count} -> {after_count} (완료)';
        }}
      }}, 35);
      draw();
    </script>
    """
    components.html(html, height=240)


def render_card_list(cards: pd.DataFrame) -> None:
    """상위 10개 + 더보기 목록."""
    if "visible_results" not in st.session_state:
        st.session_state.visible_results = 10

    total = len(cards)
    shown = min(st.session_state.visible_results, total)

    for _, row in cards.head(shown).iterrows():
        left, right = st.columns([1, 3])
        with left:
            if row["card_image_url"]:
                st.image(row["card_image_url"], use_container_width=True)
            else:
                st.markdown("<div class='card-tile' style='height:160px;display:flex;align-items:center;justify-content:center;color:#8fa1ba;'>이미지 없음</div>", unsafe_allow_html=True)
        with right:
            st.markdown(
                f"""
                <div class=\"card-tile\">
                  <div class=\"match-badge\">매치율 {row['match_rate']:.1f}%</div>
                  <div class=\"card-title\">{row['name']}</div>
                  <div class=\"card-meta\">{row['issuer']} | 연회비 {int(row['domestic_annual_fee'] or 0):,}원</div>
                  <div class=\"card-summary\">{row['summary']}</div>
                  <div class=\"card-meta\" style=\"margin-top:8px;\">최소 실적: {int(row['min_spend_required_krw'] or 0):,}원</div>
                  <a href=\"{row['detail_url']}\" target=\"_blank\">카드 상세 보기</a>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if shown < total and st.button("더보기", use_container_width=True):
        st.session_state.visible_results = min(total, shown + 10)
        st.rerun()


def render_wizard(df: pd.DataFrame) -> None:
    if "survey_step" not in st.session_state:
        st.session_state.survey_step = 0
    if "survey_answers" not in st.session_state:
        st.session_state.survey_answers = {}
    if "survey_submitted" not in st.session_state:
        st.session_state.survey_submitted = False
    if "visible_results" not in st.session_state:
        st.session_state.visible_results = 10

    active_questions = get_active_questions(st.session_state.survey_answers)
    total_questions = len(active_questions)
    step = min(st.session_state.survey_step, max(total_questions - 1, 0))

    st.title("카드의요정")
    st.caption("요정과 대화하듯 질문에 답하면 조건에 맞는 카드만 남깁니다.")

    if total_questions == 0:
        st.warning("질문 정의가 비어 있습니다. app/question_bank.py를 확인해 주세요.")
        return

    question = active_questions[step]
    qid = question["id"]
    current_answer = st.session_state.survey_answers.get(qid)

    left, right = st.columns([1, 5])
    with left:
        if FAIRY_IMAGE_PATH.exists():
            st.image(str(FAIRY_IMAGE_PATH), use_container_width=True)
        else:
            st.image("https://placehold.co/280x280?text=Fairy", use_container_width=True)
    with right:
        st.markdown(
            f"""
            <div class=\"fairy-bubble\">
              안녕하세요, 카드의요정입니다. {step + 1}번째 질문이에요.<br>
              {question['title']}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.progress((step + 1) / total_questions, text=f"질문 진행 {step + 1} / {total_questions}")

    answer = render_question_input(question, current_answer)
    preview_answers = dict(st.session_state.survey_answers)
    preview_answers[qid] = answer
    preview_filtered = filter_by_answers(df, preview_answers, upto_step=step)

    st.markdown(f"<div class='candidate-count'>현재 조건 충족 카드 수: <strong>{len(preview_filtered)}개</strong></div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    if c1.button("이전", disabled=step == 0, use_container_width=True):
        st.session_state.survey_answers[qid] = answer
        st.session_state.survey_step = max(0, step - 1)
        st.rerun()

    if step < total_questions - 1:
        if c2.button("다음", use_container_width=True):
            st.session_state.survey_answers[qid] = answer
            st.session_state.survey_step = step + 1
            st.rerun()
    else:
        if c2.button("결과 보기", use_container_width=True):
            st.session_state.survey_answers[qid] = answer
            st.session_state.survey_submitted = True
            st.session_state.visible_results = 10
            st.rerun()

    if c3.button("처음부터", use_container_width=True):
        st.session_state.survey_step = 0
        st.session_state.survey_answers = {}
        st.session_state.survey_submitted = False
        st.session_state.visible_results = 10
        st.rerun()

    if not st.session_state.survey_submitted:
        return

    final_filtered = filter_by_answers(df, st.session_state.survey_answers)
    scored = apply_match_score(final_filtered, st.session_state.survey_answers)

    st.divider()
    st.subheader("질문 종료: 카드 망 필터링 결과")
    render_filtering_animation(before_count=len(df), after_count=len(scored))

    st.subheader("당신에게 맞는 카드")
    st.caption("상위 10개를 먼저 보여주고, 더보기로 남은 카드를 확인할 수 있습니다.")
    if len(scored) == 0:
        st.warning("조건을 모두 충족하는 카드가 없습니다. 연회비/실적 범위를 넓혀보세요.")
        return

    render_card_list(scored)


inject_styles()

if not DB_PATH.exists():
    st.error("DB 파일이 없습니다. 먼저 `uv run python crawler/build_card_db.py`를 실행하세요.")
    st.stop()

cards_df = load_cards()
render_wizard(cards_df)

with st.expander("실행 가이드", expanded=False):
    st.code(
        """uv run python crawler/build_card_db.py
uv run streamlit run app/streamlit_app.py""",
        language="bash",
    )
