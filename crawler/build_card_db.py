"""Naver card list crawler -> SQLite builder.

주요 목적:
1) 네이버 카드 검색의 더보기 동작(GraphQL smartSearch)을 페이지 단위로 반복 호출
2) 전체 카드 목록을 SQLite DB(data/cards.db)에 저장
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests

GRAPHQL_URL = "https://card-search.naver.com/graphql"
DB_PATH = Path("data/cards.db")
TIMEOUT_SECONDS = 20
PAGE_SIZE = 10

# 네이버 번들에서 사용하는 기본 쿼리명/변수와 동일하게 유지한다.
SMART_SEARCH_QUERY = """
query smartSearch(
  $cardAdIds: [Int]
  $companyCode: [String]
  $brandNames: [String]
  $benefitCategoryIds: [Int]
  $subBenefitCategoryIds: [Int]
  $affiliateIds: [Int]
  $maxAnnualFee: Int
  $minAnnualFee: Int
  $basePayment: Int
  $pageNo: Int = 1
  $pageSize: Int = 10
  $device: AdDeviceType
  $sortMethod: SortMethod
  $where: String
  $isRefetch: Boolean
  $bizType: BizType
  $searchedAgeGroup: Int
  $searchedGender: String
) {
  cardAdList(
    cardAdIds: $cardAdIds
    companyCode: $companyCode
    brandNames: $brandNames
    benefitCategoryIds: $benefitCategoryIds
    subBenefitCategoryIds: $subBenefitCategoryIds
    affiliateIds: $affiliateIds
    maxAnnualFee: $maxAnnualFee
    minAnnualFee: $minAnnualFee
    basePayment: $basePayment
    pageNo: $pageNo
    pageSize: $pageSize
    device: $device
    sortMethod: $sortMethod
    where: $where
    isRefetch: $isRefetch
    bizType: $bizType
    searchedAgeGroup: $searchedAgeGroup
    searchedGender: $searchedGender
  ) {
    cardAds {
      cardAdId
      cardName
      cardImage
      cardImageUrl
      companyCode
      titleDescription
      domesticAnnualFee
      foreignAnnualFee
      familyAnnualFee
      benefits {
        rootBenefitCategoryIdName
      }
    }
    totalSize
  }
}
"""

COMPANY_CODE_TO_ISSUER = {
    "SH": "신한카드",
    "HD": "현대카드",
    "SS": "삼성카드",
    "KB": "KB국민카드",
    "LO": "롯데카드",
    "SK": "하나카드",
    "WR": "우리카드",
    "NH": "NH농협카드",
    "IB": "IBK기업은행",
}


@dataclass
class CardRow:
    # DB에 저장할 카드 속성(연회비/혜택 포함).
    card_ad_id: int
    name: str
    issuer: str
    summary: str
    card_image_url: str
    min_spend_required_krw: int | None
    domestic_annual_fee: int | None
    foreign_annual_fee: int | None
    family_annual_fee: int | None
    benefit_tags: str
    detail_url: str
    source: str = "naver_card_search"


def _build_session() -> requests.Session:
    """요청 세션 생성."""
    session = requests.Session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Content-Type": "application/json",
        "Origin": "https://card-search.naver.com",
        "Referer": "https://card-search.naver.com/list",
    }
    session.headers.update(headers)
    return session


def fetch_page(session: requests.Session, page_no: int) -> tuple[list[dict], int]:
    """smartSearch로 특정 페이지 카드를 조회한다."""
    payload = {
        "operationName": "smartSearch",
        "query": SMART_SEARCH_QUERY,
        "variables": {
            "minAnnualFee": 0,
            "maxAnnualFee": 0,
            "basePayment": 0,
            "device": "pc",
            "pageSize": PAGE_SIZE,
            "pageNo": page_no,
            "sortMethod": "ri",
            "bizType": "CPC",
        },
    }
    response = session.post(GRAPHQL_URL, json=payload, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()

    payload_json = response.json()
    card_list = payload_json["data"]["cardAdList"]
    return card_list["cardAds"], card_list["totalSize"]


def fetch_card_min_spend(session: requests.Session, card_ad_id: int) -> int | None:
    """카드 상세 페이지에서 혜택 최소 전월실적(원) 추출."""
    url = f"https://card-search.naver.com/item?cardAdId={card_ad_id}"
    response = session.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    html = response.text

    # 상세 JSON(baseRecord.valueFrom) 우선.
    match = re.search(r'"baseRecord":\{.*?"valueFrom":(\d+)', html, flags=re.DOTALL)
    if match:
        return int(match.group(1))

    # 텍스트 fallback (예: "30만원 이상").
    text_match = re.search(r"기준실적.*?([0-9]+)\s*만원", html, flags=re.DOTALL)
    if text_match:
        return int(text_match.group(1)) * 10000

    return None


def _to_card_row(raw: dict) -> CardRow:
    card_ad_id = int(raw["cardAdId"])
    company_code = str(raw.get("companyCode", "")).strip()
    issuer = COMPANY_CODE_TO_ISSUER.get(company_code, company_code)

    benefit_names: list[str] = []
    for benefit in raw.get("benefits") or []:
        raw_name = str(benefit.get("rootBenefitCategoryIdName", "")).strip()
        # 예: "15|대중교통" 형태에서 카테고리명만 보관.
        parsed_name = raw_name.split("|", 1)[1] if "|" in raw_name else raw_name
        if parsed_name and parsed_name not in benefit_names:
            benefit_names.append(parsed_name)

    image_url = str(raw.get("cardImageUrl") or "").strip()
    if not image_url:
        # cardImage 상대 경로를 절대 URL로 보정한다.
        image_path = str(raw.get("cardImage") or "").strip()
        if image_path.startswith("//"):
            image_url = f"https:{image_path}"
        elif image_path.startswith("/"):
            image_url = f"https://card-search.naver.com{image_path}"
        else:
            image_url = image_path

    return CardRow(
        card_ad_id=card_ad_id,
        name=str(raw.get("cardName", "")).strip(),
        issuer=issuer,
        summary=str(raw.get("titleDescription", "")).strip(),
        card_image_url=image_url,
        min_spend_required_krw=None,
        domestic_annual_fee=raw.get("domesticAnnualFee"),
        foreign_annual_fee=raw.get("foreignAnnualFee"),
        family_annual_fee=raw.get("familyAnnualFee"),
        benefit_tags=", ".join(benefit_names),
        detail_url=f"https://card-search.naver.com/item?cardAdId={card_ad_id}",
    )


def deduplicate(rows: Iterable[CardRow]) -> list[CardRow]:
    """중복 cardAdId 제거."""
    seen: set[int] = set()
    unique_rows: list[CardRow] = []

    for row in rows:
        if row.card_ad_id in seen:
            continue
        seen.add(row.card_ad_id)
        unique_rows.append(row)

    return unique_rows


def init_db(conn: sqlite3.Connection) -> None:
    """카드 테이블 생성.

    스키마 변경 추적을 단순화하기 위해 매 실행 시 재생성한다.
    """
    conn.execute("DROP TABLE IF EXISTS cards")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_ad_id INTEGER NOT NULL UNIQUE,
            name TEXT NOT NULL,
            issuer TEXT,
            summary TEXT,
            card_image_url TEXT,
            min_spend_required_krw INTEGER,
            domestic_annual_fee INTEGER,
            foreign_annual_fee INTEGER,
            family_annual_fee INTEGER,
            benefit_tags TEXT,
            detail_url TEXT,
            source TEXT NOT NULL,
            crawled_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def replace_cards(conn: sqlite3.Connection, rows: list[CardRow]) -> None:
    """재실행 시 최신 스냅샷으로 교체한다."""
    conn.execute("DELETE FROM cards")
    conn.executemany(
        """
        INSERT INTO cards (
            card_ad_id,
            name,
            issuer,
            summary,
            card_image_url,
            min_spend_required_krw,
            domestic_annual_fee,
            foreign_annual_fee,
            family_annual_fee,
            benefit_tags,
            detail_url,
            source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                r.card_ad_id,
                r.name,
                r.issuer,
                r.summary,
                r.card_image_url,
                r.min_spend_required_krw,
                r.domestic_annual_fee,
                r.foreign_annual_fee,
                r.family_annual_fee,
                r.benefit_tags,
                r.detail_url,
                r.source,
            )
            for r in rows
        ],
    )


def crawl_cards() -> list[CardRow]:
    session = _build_session()
    rows: list[CardRow] = []
    page_no = 1
    total_size = None

    # 더보기 동작을 pageNo 증가로 재현한다.
    while True:
        card_ads, fetched_total_size = fetch_page(session, page_no)
        if total_size is None:
            total_size = fetched_total_size

        if not card_ads:
            break

        rows.extend(_to_card_row(raw) for raw in card_ads)
        unique_rows = deduplicate(rows)

        print(f"Fetched page={page_no} page_items={len(card_ads)} unique_items={len(unique_rows)}")

        # 전체 개수에 도달하면 즉시 중단한다.
        if len(unique_rows) >= total_size:
            rows = unique_rows
            break

        rows = unique_rows
        page_no += 1

    rows = deduplicate(rows)

    # 카드 상세 페이지를 순회하며 최소 실적을 보강한다.
    for idx, row in enumerate(rows, start=1):
        try:
            row.min_spend_required_krw = fetch_card_min_spend(session, row.card_ad_id)
        except requests.RequestException:
            row.min_spend_required_krw = None
        if idx % 30 == 0 or idx == len(rows):
            print(f"Enriched min spend {idx}/{len(rows)}")

    return rows


def save_debug_snapshot(rows: list[CardRow]) -> None:
    """수집 결과를 검증하기 위한 JSON 스냅샷 저장."""
    Path("data").mkdir(parents=True, exist_ok=True)
    payload = [row.__dict__ for row in rows]
    Path("data/cards_snapshot.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = crawl_cards()

    if not rows:
        raise RuntimeError("카드 데이터를 수집하지 못했습니다. 페이지 구조 변경 여부를 확인하세요.")

    save_debug_snapshot(rows)

    with sqlite3.connect(DB_PATH) as conn:
        init_db(conn)
        replace_cards(conn, rows)
        conn.commit()

    print(f"Saved {len(rows)} cards to {DB_PATH}")


if __name__ == "__main__":
    main()
