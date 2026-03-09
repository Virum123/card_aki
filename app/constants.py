"""Shared constants for Card Fairy app."""

from __future__ import annotations

import re
from pathlib import Path

DB_PATH = Path("data/cards.db")
FAIRY_IMAGE_PATH = Path("app/assets/fairy.svg")
TOP_N_RESULTS = 100
MIN_RECOMMEND_SCORE = 60.0

OVERSEAS_KEYWORDS = [
    "외화결제",
    "해외",
    "해외이용",
    "해외결제",
    "직구",
    "travel",
    "공항",
    "라운지",
    "면세",
    "환전",
    "visa",
    "master",
    "amex",
    "jcb",
    "unionpay",
    "유니온페이",
]
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
    "문화",
    "디지털",
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
    "구독": ["문화"],
    "간편결제": ["간편결제"],
    "차": ["오토", "주유", "하이패스"],
    "대중교통": ["대중교통"],
    "해외": ["외화결제", "레저"],
    "마일리지": ["항공마일리지"],
}

FEATURE_MAP: dict[str, tuple[str, str, list[str]]] = {
    "overseas_yesno": ("해외/직구", "해외", OVERSEAS_KEYWORDS),
    "mileage_interest": ("마일리지", "마일리지", MILEAGE_KEYWORDS),
    "bakery_cafe_yesno": ("카페/베이커리", "카페", CAFE_KEYWORDS),
    "dining_delivery_yesno": ("식당/배달", "외식", DINING_KEYWORDS),
    "shopping_yesno": ("쇼핑", "쇼핑", SHOPPING_KEYWORDS),
    "convenience_yesno": ("편의점", "편의점", CONVENIENCE_KEYWORDS),
    "telecom_yesno": ("통신", "통신", TELECOM_KEYWORDS),
    "ott_streaming_yesno": ("구독/스트리밍", "구독", SUBSCRIPTION_KEYWORDS),
    "simplepay_yesno": ("간편결제", "간편결제", SIMPLEPAY_KEYWORDS),
    "car_benefit_yesno": ("자동차", "차", CAR_KEYWORDS),
    "public_transport_yesno": ("대중교통", "대중교통", PUBLIC_TRANSPORT_KEYWORDS),
}

WEIGHTS = {
    "monthly_spend_level": 10,
    "annual_fee_range": 10,
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

DETAILED_LABELS = {
    1: "전혀 필요 없음",
    2: "별로 필요 없음",
    3: "보통",
    4: "필요함",
    5: "매우 필요함",
}

ISSUER_OFFICIAL_URL_MAP = {
    "신한카드": "https://www.shinhancard.com",
    "현대카드": "https://www.hyundaicard.com",
    "삼성카드": "https://www.samsungcard.com",
    "KB국민카드": "https://card.kbcard.com",
    "롯데카드": "https://www.lottecard.co.kr",
    "하나카드": "https://www.hanacard.co.kr",
    "우리카드": "https://pc.wooricard.com",
    "BC": "https://www.bccard.com",
    "BC 바로카드": "https://www.bccard.com",
    "NH농협카드": "https://card.nonghyup.com",
}

PERCENT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%")
WON_PATTERN = re.compile(r"([\d,]+)\s*원")
