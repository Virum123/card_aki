import math
import time
import requests
import pandas as pd

BASE_URL = "https://api.card-gorilla.com:8080/v1/cards"

def top_benefit_to_text(card: dict) -> str:
    tops = card.get("top_benefit") or []
    parts = []
    for b in tops:
        title = (b.get("title") or "").strip()
        tags = [t.strip() for t in (b.get("tags") or []) if t and t.strip()]
        if title and tags:
            parts.append(f"{title}: " + ", ".join(tags))
        elif title:
            parts.append(title)
    return " | ".join(parts)

def fetch_page(p: int, per_page: int, cate: str) -> dict:
    params = {"p": p, "perPage": per_page, "cate": cate}
    r = requests.get(BASE_URL, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

def main():
    cate = "CRD"
    per_page = 50  # 10보다 크게 잡으면 호출 횟수 줄어서 편함(서버가 허용하면)
    sleep_sec = 0.2  # 과도한 호출 방지용(너무 빠르게 돌리지 않기)

    # 1) 1페이지로 total 확인
    first = fetch_page(1, per_page, cate)
    total = int(first.get("total", 0))
    per_page_returned = int(first.get("perPage", per_page))
    last_page = math.ceil(total / per_page_returned) if per_page_returned else 0

    print(f"total={total}, perPage={per_page_returned}, last_page={last_page}")

    # 2) 전체 페이지 순회하며 rows 누적
    rows = []
    seen_idx = set()

    def consume_cards(cards: list[dict]):
        for c in cards:
            idx = c.get("idx")
            if idx in seen_idx:
                continue
            seen_idx.add(idx)

            rows.append({
                "idx": idx,
                "카드명": c.get("name", ""),
                "카드사": c.get("corp_txt", ""),
                "연회비": c.get("annual_fee_basic", ""),
                "전월실적": c.get("pre_month_money", None),
                "혜택(요약)": top_benefit_to_text(c),
                "카드이미지URL": (c.get("card_img") or {}).get("url", ""),
                "상세페이지추정": f"https://www.card-gorilla.com/card/detail/{idx}" if idx else "",
            })

    consume_cards(first.get("data", []))

    for p in range(2, last_page + 1):
        data = fetch_page(p, per_page_returned, cate)
        consume_cards(data.get("data", []))
        if sleep_sec:
            time.sleep(sleep_sec)

    # 3) DataFrame + CSV 저장
    df = pd.DataFrame(rows)

    # 보기 좋게 정렬(선택)
    df = df.sort_values(["카드사", "카드명"], kind="stable").reset_index(drop=True)

    out_path = "cards_CRD_1076.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"저장 완료: {out_path} (rows={len(df)})")
    print(df.head(10).to_string(index=False))

if __name__ == "__main__":
    main()