"""질문 정의 전용 파일."""

# 지원 타입:
# - single: 단일 선택
# - number: 숫자 입력
#
# visible_if 규칙:
# - {"question_id": "...", "equals": "..."}

QUESTIONS = [
    {
        "id": "monthly_spend_level",
        "title": "월 사용 금액 또는 희망하는 전월실적 수준은 어느 정도인가요?",
        "type": "single",
        "options": [
            {"label": "30만원 미만", "value": "under_300k"},
            {"label": "30만원 이상 70만원 미만", "value": "300k_700k"},
            {"label": "70만원 이상", "value": "over_700k"},
        ],
    },
    {
        "id": "annual_fee_range",
        "title": "연회비 희망 범위를 선택해 주세요. (최대값 끝점은 10만원+ 의미)",
        "type": "range",
        "min": 0,
        "max": 110000,
        "step": 5000,
        "default": [0, 110000],
        "display_unit": "manwon",
    },
    {
        "id": "overseas_yesno",
        "title": "해외여행이나 직구를 자주 하시나요?",
        "type": "single",
        "options": [
            {"label": "예", "value": "yes"},
            {"label": "아니오", "value": "no"},
        ],
    },
    {
        "id": "mileage_interest",
        "title": "비행기 마일리지 적립에 관심이 있으신가요?",
        "type": "single",
        "options": [
            {"label": "예", "value": "yes"},
            {"label": "아니오", "value": "no"},
        ],
    },
    {
        "id": "mileage_airline",
        "title": "대한항공 마일리지를 선호하시나요?",
        "type": "single",
        "options": [
            {"label": "예", "value": "yes"},
            {"label": "아니오", "value": "no"},
        ],
        "visible_if": {"question_id": "mileage_interest", "equals": "yes"},
    },
    {
        "id": "bakery_cafe_yesno",
        "title": "베이커리/카페 혜택이 필요하신가요?",
        "type": "single",
        "options": [{"label": "예", "value": "yes"}, {"label": "아니오", "value": "no"}],
    },
    {
        "id": "dining_delivery_yesno",
        "title": "식당/배달 혜택이 필요하신가요?",
        "type": "single",
        "options": [{"label": "예", "value": "yes"}, {"label": "아니오", "value": "no"}],
    },
    {
        "id": "shopping_yesno",
        "title": "쇼핑(온라인/오프라인) 혜택이 필요하신가요?",
        "type": "single",
        "options": [{"label": "예", "value": "yes"}, {"label": "아니오", "value": "no"}],
    },
    {
        "id": "convenience_yesno",
        "title": "편의점 혜택이 필요하신가요?",
        "type": "single",
        "options": [{"label": "예", "value": "yes"}, {"label": "아니오", "value": "no"}],
    },
    {
        "id": "telecom_yesno",
        "title": "통신요금 할인 혜택이 필요하신가요?",
        "type": "single",
        "options": [{"label": "예", "value": "yes"}, {"label": "아니오", "value": "no"}],
    },
    {
        "id": "ott_streaming_yesno",
        "title": "구독 서비스를 많이 사용하시나요?",
        "type": "single",
        "options": [{"label": "예", "value": "yes"}, {"label": "아니오", "value": "no"}],
    },
    {
        "id": "simplepay_yesno",
        "title": "간편결제(삼성페이/네이버페이/카카오페이) 혜택이 필요하신가요?",
        "type": "single",
        "options": [{"label": "예", "value": "yes"}, {"label": "아니오", "value": "no"}],
    },
    {
        "id": "car_benefit_yesno",
        "title": "자동차 관련 혜택(주유/오토 등)이 필요하신가요?",
        "type": "single",
        "options": [{"label": "예", "value": "yes"}, {"label": "아니오", "value": "no"}],
    },
    {
        "id": "public_transport_yesno",
        "title": "대중교통 혜택이 필요하신가요?",
        "type": "single",
        "options": [{"label": "예", "value": "yes"}, {"label": "아니오", "value": "no"}],
    },
    {
        "id": "internet_bank_main",
        "title": "인터넷전문은행(카카오뱅크/토스뱅크/케이뱅크)을 주거래은행으로 사용하시나요?",
        "type": "single",
        "options": [{"label": "예", "value": "yes"}, {"label": "아니오", "value": "no"}],
    },
]
