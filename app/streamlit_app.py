"""Card Akinator Streamlit entrypoint."""

from __future__ import annotations

import sqlite3

import pandas as pd
import streamlit as st

from app.constants import DB_PATH
from app.ui import inject_styles, render_wizard

st.set_page_config(page_title="카드의요정", page_icon="🧚", layout="wide")


@st.cache_data(ttl=300)
def load_cards() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            """
            SELECT
                id,
                card_ad_id,
                COALESCE(NULLIF(name, ''), '-') AS name,
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

    df["combined_text"] = (
        df["name"].fillna("").astype(str)
        + " "
        + df["summary"].fillna("").astype(str)
        + " "
        + df["benefit_tags"].fillna("").astype(str)
    ).str.lower()
    return df


inject_styles()

if not DB_PATH.exists():
    st.error("DB 파일이 없습니다. 먼저 `uv run python crawler/build_card_db.py`를 실행하세요.")
    st.stop()

cards_df = load_cards()
render_wizard(cards_df)

with st.expander("실행 가이드", expanded=False):
    st.markdown(
        """
1. 질문 란에서 `간편 탐색` 또는 `세부 탐색`을 선택하세요.
2. 간편 탐색은 Y/N 중심, 세부 탐색은 5점 척도로 선호도를 입력합니다.
3. 질문 완료 후 100점 만점 상위 100개 카드가 추천됩니다.
        """
    )
