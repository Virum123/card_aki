"""UI rendering helpers for Streamlit app."""

from __future__ import annotations

import base64
import io
import time

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

from app.constants import (
    DB_PATH,
    DETAILED_LABELS,
    FAIRY_IMAGE_PATH,
    FEATURE_MAP,
    ISSUER_OFFICIAL_URL_MAP,
    MIN_RECOMMEND_SCORE,
    PERCENT_PATTERN,
    TOP_N_RESULTS,
    WON_PATTERN,
)
from app.scoring import (
    detect_conflict_pair,
    get_active_questions,
    get_scored_cards,
    is_yesno_question,
    requested_features,
)
from app.state import init_session_state, reset_session_state

try:
    from PIL import Image
except ModuleNotFoundError:
    Image = None


def inject_styles() -> None:
    st.markdown(
        """
        <style>
            .fairy-bubble { background: linear-gradient(135deg, #12243f 0%, #1d3b66 100%); color: #f6f8ff; border: 1px solid #4e7abc; border-radius: 18px; padding: 16px 18px; font-size: 1.18rem; font-weight: 700; line-height: 1.45; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.22); }
            .candidate-count { font-size: 1.02rem; color: #98a6b8; margin-bottom: 8px; }
            .card-row { border: 1px solid #1f2d41; border-radius: 16px; background: #0c1420; padding: 14px; margin-bottom: 12px; }
            .rank-gold { border: 2px solid #ffd24d !important; box-shadow: 0 0 0 1px rgba(255,210,77,0.25) inset; }
            .rank-silver { border: 2px solid #cfd5de !important; box-shadow: 0 0 0 1px rgba(207,213,222,0.25) inset; }
            .rank-bronze { border: 2px solid #d09a65 !important; box-shadow: 0 0 0 1px rgba(208,154,101,0.25) inset; }
            .match-badge { display: inline-block; padding: 4px 10px; border-radius: 999px; background: #123c2e; color: #8ef2c8; font-size: 0.82rem; font-weight: 700; margin-bottom: 8px; }
            .card-title { font-size: 1.05rem; font-weight: 800; color: #f3f7ff; margin-bottom: 4px; }
            .card-meta { color: #9fb0c8; font-size: 0.9rem; margin-bottom: 8px; }
            .card-summary { color: #d8e0ef; font-size: 0.92rem; }
            .feat-hit { color: #77f3be; font-weight: 800; margin-right: 8px; }
            .feat-mid { color: #d8e0ef; font-weight: 700; margin-right: 8px; }
            .feat-low { color: #7d8ea7; margin-right: 8px; }
            .likert-guide { color:#9fb0c8; font-size:0.9rem; margin-top:6px; }
            .card-flex { display: flex; gap: 14px; align-items: stretch; }
            .card-image-wrap { width: 280px; min-width: 280px; border-radius: 12px; overflow: hidden; background: #101a2b; border: 1px solid #23344f; }
            .card-image-wrap img { width: 100%; height: 100%; object-fit: contain; display: block; background: #0b1220; }
            .card-info-wrap { flex: 1; min-width: 0; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _format_fee_manwon(value: int) -> str:
    if value % 10000 == 0:
        return f"{value // 10000}만"
    return f"{value / 10000:.1f}만"


@st.cache_data(ttl=3600)
def _prepare_card_image_src(url: str) -> str:
    if not url:
        return ""
    if Image is None:
        return url
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        w, h = img.size
        if h > w:
            img = img.rotate(90, expand=True)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return url


def render_question_input(question: dict, current_answer, mode: str):
    qid = question["id"]
    qtype = question["type"]

    if qtype == "single" and mode == "detailed" and is_yesno_question(question):
        temp_key = f"likert_selected_{qid}"
        if temp_key not in st.session_state:
            st.session_state[temp_key] = int(current_answer) if isinstance(current_answer, int) else 3
        if isinstance(current_answer, int) and st.session_state[temp_key] != int(current_answer):
            st.session_state[temp_key] = int(current_answer)

        selected = int(st.session_state[temp_key])
        cols = st.columns(5)
        for i in range(1, 6):
            clicked = cols[i - 1].button(
                str(i),
                key=f"likert_btn_{qid}_{i}",
                use_container_width=True,
                type="primary" if selected == i else "secondary",
            )
            if clicked:
                st.session_state[temp_key] = i
                selected = i
                st.rerun()
        st.markdown(
            f"<div class='likert-guide'>선택: <b>{selected}점</b> ({DETAILED_LABELS[selected]})</div>",
            unsafe_allow_html=True,
        )
        return int(selected)

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


def render_filtering_animation(before_count: int, after_count: int, card_images: list[str]) -> None:
    safe_images = [img for img in card_images if img][:18]
    images_js = str(safe_images)
    html = f"""
    <div style="width:100%;border-radius:16px;background:#0d1625;padding:16px 18px;border:1px solid #1f2f4d;">
      <div style="display:flex;justify-content:space-between;align-items:center;color:#dbe8ff;">
        <strong>카드 점수 산정 중...</strong>
        <span id="countText" style="color:#8ef2c8;font-weight:700;">{before_count} -> {after_count}</span>
      </div>
      <canvas id="netCanvas" width="980" height="250" style="width:100%;height:250px;margin-top:10px;border-radius:12px;background:#0a1220;"></canvas>
    </div>
    <script>
      const canvas = document.getElementById('netCanvas');
      const ctx = canvas.getContext('2d');
      const countText = document.getElementById('countText');
      const imageUrls = {images_js};
      const loaded = [];
      let progress = 0;
      let shown = {before_count};
      const target = {after_count};
      function initCards() {{
        if (imageUrls.length === 0) return;
        imageUrls.forEach((u, i) => {{
          const img = new Image();
          img.src = u;
          loaded.push({{img:img,x:30 + (i % 9) * 102,y:18 + Math.floor(i / 9) * 90,w:58,h:86,vy:1.0+Math.random()}});
        }});
      }}
      function drawNet(cx, cy, scale) {{
        ctx.save(); ctx.translate(cx, cy); ctx.scale(scale, scale);
        ctx.strokeStyle = '#79b4ff'; ctx.lineWidth = 1.2;
        for (let x=-120; x<=120; x+=24) {{ ctx.beginPath(); ctx.moveTo(x,-70); ctx.lineTo(x,70); ctx.stroke(); }}
        for (let y=-70; y<=70; y+=20) {{ ctx.beginPath(); ctx.moveTo(-120,y); ctx.lineTo(120,y); ctx.stroke(); }}
        ctx.restore();
      }}
      function drawCards() {{
        loaded.forEach((c) => {{
          c.y += c.vy * (0.8 + progress*1.1); if (c.y > 215) c.y = 20;
          ctx.save(); ctx.translate(c.x + c.w/2, c.y + c.h/2); ctx.rotate((progress-0.5)*0.16);
          const x=-c.w/2, y=-c.h/2; ctx.fillStyle='#f4f8ff'; ctx.fillRect(x,y,c.w,c.h);
          if (c.img && c.img.complete) ctx.drawImage(c.img, x+2, y+2, c.w-4, c.h-4);
          ctx.strokeStyle='#7ea4d8'; ctx.lineWidth=1.2; ctx.strokeRect(x,y,c.w,c.h); ctx.restore();
        }});
      }}
      function frame() {{
        progress = Math.min(1, progress + 0.018);
        ctx.clearRect(0,0,canvas.width,canvas.height);
        drawCards(); drawNet(canvas.width/2, 160 - progress*38, 1.0 - progress*0.43);
        if (shown > target) {{ shown = Math.max(target, shown - Math.max(1, Math.ceil((shown-target)*0.12))); countText.innerText=`${{shown}} -> {after_count}`; }}
        if (progress < 1) requestAnimationFrame(frame);
      }}
      initCards(); frame();
    </script>
    """
    components.html(html, height=310)


def _official_card_url(row: pd.Series) -> str:
    issuer = str(row.get("issuer", "") or "").strip()
    base = ISSUER_OFFICIAL_URL_MAP.get(issuer)
    if base:
        return base
    return str(row.get("detail_url", "") or "")


def _extract_offer_text(row: pd.Series, qid: str, label: str) -> str:
    summary = str(row.get("summary", "") or "")
    segments = [seg.strip() for seg in summary.split("|") if seg.strip()]

    lookup_terms = {
        "overseas_yesno": ["해외", "외화", "직구", "travel"],
        "mileage_interest": ["마일", "스카이패스", "대한항공", "아시아나"],
        "mileage_airline": ["대한항공", "스카이패스"],
        "bakery_cafe_yesno": ["카페", "베이커리", "커피"],
        "dining_delivery_yesno": ["외식", "배달", "식당"],
        "shopping_yesno": ["쇼핑", "온라인", "마트", "백화점"],
        "convenience_yesno": ["편의점", "gs25", "cu"],
        "telecom_yesno": ["통신", "skt", "kt", "lg"],
        "ott_streaming_yesno": ["ott", "스트리밍", "구독", "넷플릭스", "유튜브"],
        "simplepay_yesno": ["간편결제", "페이", "삼성페이", "네이버페이", "카카오페이"],
        "car_benefit_yesno": ["주유", "오토", "하이패스", "주차"],
        "public_transport_yesno": ["대중교통", "버스", "지하철", "교통"],
        "internet_bank_main": ["은행", "금융"],
    }
    terms = lookup_terms.get(qid, [label])

    target = ""
    for seg in segments:
        low = seg.lower()
        if any(t.lower() in low for t in terms):
            target = seg
            break
    if not target:
        target = segments[0] if segments else summary

    pct_match = PERCENT_PATTERN.search(target)
    pct = pct_match.group(1) if pct_match else ""
    has_save = "적립" in target
    has_disc = "할인" in target
    if pct:
        if has_save:
            return f"{label} 시 최대 {pct}% 적립"
        if has_disc:
            return f"{label} 시 최대 {pct}% 할인"
        return f"{label} 시 최대 {pct}% 혜택"

    won_match = WON_PATTERN.search(target)
    won = won_match.group(1) if won_match else ""
    if won:
        return f"{label} 관련 {won}원 혜택"

    short = target.replace(":", " ").replace(",", " ").strip()
    short = " ".join(short.split())
    if len(short) > 24:
        short = short[:24] + "..."
    return f"{label} {short}" if short else f"{label} 혜택"


def _feature_html(row: pd.Series, requested: list[tuple[str, str]]) -> str:
    parts: list[str] = []
    for qid, label in requested:
        s = float(row.get(f"strength_{qid}", 0.0))
        offer = _extract_offer_text(row, qid, label)
        if s >= 60:
            parts.append(f"<span class='feat-hit'>{offer}</span>")
        elif s >= 30:
            parts.append(f"<span class='feat-mid'>{offer}</span>")
        else:
            parts.append(f"<span class='feat-low'>{offer}</span>")
    return " ".join(parts)


def render_card_list(cards: pd.DataFrame, answers: dict[str, object], mode: str) -> None:
    if "visible_results" not in st.session_state:
        st.session_state.visible_results = 10

    cards = cards[cards["match_rate"] >= MIN_RECOMMEND_SCORE].head(TOP_N_RESULTS)
    total = len(cards)
    shown = min(st.session_state.visible_results, total)
    requested = requested_features(answers, mode)

    for rank, (_, row) in enumerate(cards.head(shown).iterrows(), start=1):
        rank_class = ""
        medal = ""
        if rank == 1:
            rank_class = "rank-gold"
            medal = "🥇"
        elif rank == 2:
            rank_class = "rank-silver"
            medal = "🥈"
        elif rank == 3:
            rank_class = "rank-bronze"
            medal = "🥉"

        image_src = _prepare_card_image_src(str(row["card_image_url"] or ""))
        feature_line = _feature_html(row, requested)
        official_url = _official_card_url(row)
        image_html = (
            f"<img src=\"{image_src}\" alt=\"{row['name']}\" />"
            if image_src
            else "<div style='height:180px;display:flex;align-items:center;justify-content:center;color:#8fa1ba;'>이미지 없음</div>"
        )
        st.markdown(
            f"""
            <div class=\"card-row {rank_class}\">
              <div class=\"card-flex\">
                <div class=\"card-image-wrap\">{image_html}</div>
                <div class=\"card-info-wrap\">
                  <div class=\"match-badge\">{medal} 총점 {row['match_rate']:.1f}/100</div>
                  <div class=\"card-title\">#{rank} {row['name']}</div>
                  <div class=\"card-meta\">{row['issuer']} | 연회비 {int(row['domestic_annual_fee'] or 0):,}원</div>
                  <div class=\"card-summary\">{row['summary']}</div>
                  <div class=\"card-meta\" style=\"margin-top:8px;\">요청 혜택 충족도: {feature_line}</div>
                  <a href=\"{official_url}\" target=\"_blank\">카드사 페이지 보기</a>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if shown < total and st.button("더보기", use_container_width=True):
        st.session_state.visible_results = min(total, shown + 10)
        st.rerun()


def render_mode_selector() -> str:
    st.subheader("질문 란")
    selected = st.radio("탐색 방식을 선택하세요", ["간편 탐색", "세부 탐색"], horizontal=True)
    return "quick" if selected == "간편 탐색" else "detailed"


def render_wizard(df: pd.DataFrame) -> None:
    init_session_state()

    st.title("카드의요정")
    st.caption("원하는 탐색 방식으로 질문에 답하면 점수 기반으로 카드를 추천합니다.")

    mode = render_mode_selector()
    if mode != st.session_state.explore_mode:
        reset_session_state(mode=mode)
        st.rerun()

    active_questions = get_active_questions(st.session_state.survey_answers, mode)
    total_questions = len(active_questions)
    step = min(st.session_state.survey_step, max(total_questions - 1, 0))

    final_filtered, scored = get_scored_cards(df, st.session_state.survey_answers, mode)

    if st.session_state.survey_phase == "animating":
        st.subheader("질문 종료: 점수 산정 결과")
        render_filtering_animation(
            before_count=len(final_filtered),
            after_count=min(TOP_N_RESULTS, len(scored)),
            card_images=scored["card_image_url"].dropna().tolist()[:18],
        )
        st.caption("질문 기반 가중치를 계산해 상위 카드를 정렬 중입니다...")
        wait_seconds = 2.0
        elapsed = time.time() - float(st.session_state.animation_started_at or 0.0)
        if elapsed < wait_seconds:
            time.sleep(wait_seconds - elapsed)
        st.session_state.survey_phase = "results"
        st.rerun()

    if st.session_state.survey_phase == "results":
        st.subheader("당신에게 맞는 카드")
        st.caption(f"100점 만점 기준 {MIN_RECOMMEND_SCORE:.0f}점 이상 카드 중 상위 {TOP_N_RESULTS}개를 노출합니다.")
        recommended = scored[scored["match_rate"] >= MIN_RECOMMEND_SCORE]

        if len(recommended) == 0:
            st.warning("추천 기준 점수(60점)를 넘는 카드가 없습니다. 질문 답변이나 조건을 조정해보세요.")
        else:
            st.metric("평가 대상 카드 수", len(final_filtered))
            st.metric("노출 카드 수", min(TOP_N_RESULTS, len(recommended)))
            render_card_list(scored, st.session_state.survey_answers, mode)

        if st.button("다시 질문하기", use_container_width=True):
            reset_session_state(mode=mode)
            st.rerun()
        return

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
    answer = render_question_input(question, current_answer, mode)

    preview_answers = dict(st.session_state.survey_answers)
    preview_answers[qid] = answer
    preview_filtered, _ = get_scored_cards(df, preview_answers, mode)
    if mode == "quick":
        st.markdown(
            f"<div class='candidate-count'>일치하는 카드: <strong>{len(preview_filtered)}개</strong></div>",
            unsafe_allow_html=True,
        )

    need_tie_break = False
    if step == total_questions - 1 and mode == "detailed":
        preview_answers_full = dict(st.session_state.survey_answers)
        preview_answers_full[qid] = answer
        final_preview, _ = get_scored_cards(df, preview_answers_full, mode)
        conflict_pair = detect_conflict_pair(final_preview, preview_answers_full, mode)
        st.session_state.tie_break_pair = conflict_pair
        if conflict_pair:
            q1, q2 = conflict_pair
            label1 = FEATURE_MAP[q1][0]
            label2 = FEATURE_MAP[q2][0]
            st.info(f"{label1}과 {label2}를 동시에 강하게 원하셔서 우선순위를 선택해 주세요.")
            tb1, tb2 = st.columns(2)
            if tb1.button(label1, use_container_width=True):
                st.session_state.tie_break_choice = q1
            if tb2.button(label2, use_container_width=True):
                st.session_state.tie_break_choice = q2
            choice = st.session_state.tie_break_choice
            if choice in {q1, q2}:
                st.caption(f"우선 가중치 선택: {FEATURE_MAP[choice][0]}")
            else:
                need_tie_break = True

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
        if c2.button("점수 계산 시작", use_container_width=True):
            if need_tie_break:
                st.warning("우선순위 혜택을 먼저 선택해 주세요.")
                st.stop()
            st.session_state.survey_answers[qid] = answer
            st.session_state.survey_answers["_tie_break_choice"] = st.session_state.tie_break_choice
            st.session_state.visible_results = 10
            st.session_state.survey_phase = "animating"
            st.session_state.animation_started_at = time.time()
            st.rerun()

    if c3.button("처음부터", use_container_width=True):
        reset_session_state(mode=mode)
        st.rerun()
