"""Scoring and filtering logic."""

from __future__ import annotations

import pandas as pd

from app.constants import (
    DETAILED_LABELS,
    FEATURE_MAP,
    INTERNET_BANK_NO_ISSUERS,
    INTERNET_BANK_YES_ISSUERS,
    MILEAGE_KEYWORDS,
    TAG_ALIAS_MAP,
    WEIGHTS,
)

try:
    from app.question_bank import QUESTIONS
except ModuleNotFoundError:
    from question_bank import QUESTIONS


def is_yesno_question(question: dict) -> bool:
    if question.get("type") != "single":
        return False
    values = [str(opt.get("value")) for opt in question.get("options", [])]
    return set(values) == {"yes", "no"}


def answer_meets_visible_rule(answers: dict[str, object], rule: dict, mode: str) -> bool:
    value = answers.get(rule["question_id"])
    expected = rule["equals"]
    if mode == "detailed" and isinstance(value, int) and expected == "yes":
        return value >= 4
    return value == expected


def get_active_questions(answers: dict[str, object], mode: str) -> list[dict]:
    active: list[dict] = []
    for q in QUESTIONS:
        rule = q.get("visible_if")
        if not rule or answer_meets_visible_rule(answers, rule, mode):
            active.append(q)
    return active


def _keyword_match_mask(frame: pd.DataFrame, logical_key: str, fallback_keywords: list[str]) -> pd.Series:
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


def _benefit_strength(frame: pd.DataFrame, logical_key: str, fallback_keywords: list[str]) -> pd.Series:
    values = pd.Series(0.0, index=frame.index)
    for kw in fallback_keywords:
        values += frame["combined_text"].str.contains(str(kw).lower(), na=False).astype(float)
    for tag in TAG_ALIAS_MAP.get(logical_key, []):
        values += frame["benefit_tags"].astype(str).str.contains(tag, na=False).astype(float)
    max_v = float(values.max()) if len(values) else 0.0
    if max_v <= 0:
        return pd.Series(0.0, index=frame.index)
    return (values / max_v).clip(0.0, 1.0)


def _range_preference_score(series: pd.Series, low: float, high: float, unbounded_high: bool) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").fillna(0).astype(float)
    if unbounded_high:
        gap = (low - s).clip(lower=0.0)
        return (1.0 - (gap / max(low, 1.0))).clip(0.0, 1.0)

    inside = s.between(low, high).astype(float)
    dist = (low - s).clip(lower=0.0) + (s - high).clip(lower=0.0)
    width = max(high - low, 1.0)
    outside = (1.0 - (dist / width)).clip(0.0, 1.0)
    return inside.where(inside > 0, outside)


def apply_question_filter(frame: pd.DataFrame, question_id: str, answer, mode: str) -> pd.DataFrame:
    if answer is None:
        return frame

    if question_id == "monthly_spend_level":
        required = pd.to_numeric(frame["min_spend_required_krw"], errors="coerce").fillna(0)
        if answer == "under_300k":
            return frame[required < 300000]
        if answer == "300k_700k":
            return frame[required < 700000]
        if answer == "over_700k":
            return frame

    if question_id == "annual_fee_range":
        if not isinstance(answer, (list, tuple)) or len(answer) != 2:
            return frame
        low, high = float(answer[0]), float(answer[1])
        fee = pd.to_numeric(frame["domestic_annual_fee"], errors="coerce").fillna(0)
        if high >= 110000:
            return frame[fee >= low]
        return frame[fee.between(low, high)]

    if mode != "quick":
        return frame

    if question_id in FEATURE_MAP:
        _, logical_key, keywords = FEATURE_MAP[question_id]
        mask = _keyword_match_mask(frame, logical_key, keywords)
        if answer == "yes":
            return frame[mask]
        if answer == "no":
            return frame[~mask]

    if question_id == "mileage_airline":
        ka_mask = frame["combined_text"].str.contains("대한항공|스카이패스|korean air", na=False)
        if answer == "yes":
            return frame[ka_mask]
        if answer == "no":
            return frame[~ka_mask]

    if question_id == "internet_bank_main":
        if answer == "yes":
            return frame[frame["issuer"].isin(INTERNET_BANK_YES_ISSUERS)]
        if answer == "no":
            return frame[frame["issuer"].isin(INTERNET_BANK_NO_ISSUERS)]

    return frame


def _preference_from_answer(strength: pd.Series, answer, mode: str) -> pd.Series:
    if mode == "quick":
        if answer == "yes":
            return strength
        if answer == "no":
            return 1.0 - strength
        return pd.Series(0.5, index=strength.index)

    if isinstance(answer, int):
        need_degree = max(0.0, min(1.0, (answer - 1) / 4.0))
        return (need_degree * strength).clip(0.0, 1.0)
    return pd.Series(0.5, index=strength.index)


def _importance_weight_from_likert(answer: int) -> float:
    if answer <= 2:
        return 0.0
    if answer == 3:
        return 0.4
    if answer == 4:
        return 0.75
    return 1.0


def apply_match_score(frame: pd.DataFrame, answers: dict[str, object], mode: str) -> pd.DataFrame:
    out = frame.copy()
    out["score_raw"] = 0.0
    total_weight = 0.0

    spend_answer = answers.get("monthly_spend_level")
    if spend_answer in {"under_300k", "300k_700k", "over_700k"}:
        required = pd.to_numeric(out["min_spend_required_krw"], errors="coerce").fillna(0).astype(float)
        if spend_answer == "under_300k":
            pref = pd.Series(0.2, index=out.index)
            pref = pref.where(required >= 700000, 0.6)
            pref = pref.where(required >= 300000, 1.0)
        elif spend_answer == "300k_700k":
            pref = pd.Series(0.4, index=out.index)
            pref = pref.where(required >= 700000, 1.0)
            pref = pref.where(required < 300000, 0.8)
        else:
            pref = pd.Series(0.6, index=out.index)
            pref = pref.where(required < 700000, 1.0)
        w = float(WEIGHTS["monthly_spend_level"])
        out["score_raw"] += pref * w
        total_weight += w

    fee_answer = answers.get("annual_fee_range")
    if isinstance(fee_answer, (list, tuple)) and len(fee_answer) == 2:
        low, high = float(fee_answer[0]), float(fee_answer[1])
        pref = _range_preference_score(
            out["domestic_annual_fee"], low=low, high=high, unbounded_high=(high >= 110000)
        )
        w = float(WEIGHTS["annual_fee_range"])
        out["score_raw"] += pref * w
        total_weight += w

    for qid, (_, logical_key, keywords) in FEATURE_MAP.items():
        ans = answers.get(qid)
        if ans is None:
            continue
        if mode == "quick" and ans not in {"yes", "no"}:
            continue
        if mode == "detailed" and not isinstance(ans, int):
            continue

        strength = _benefit_strength(out, logical_key, keywords)
        out[f"strength_{qid}"] = strength * 100.0
        if mode == "detailed":
            importance_w = _importance_weight_from_likert(int(ans))
            if importance_w <= 0:
                continue
            pref = strength
            w = float(WEIGHTS.get(qid, 6.0)) * importance_w
        else:
            pref = _preference_from_answer(strength, ans, mode)
            w = float(WEIGHTS.get(qid, 6.0))
        out["score_raw"] += pref * w
        total_weight += w

    tie_break_choice = answers.get("_tie_break_choice")
    if isinstance(tie_break_choice, str) and tie_break_choice in FEATURE_MAP:
        _, logical_key, keywords = FEATURE_MAP[tie_break_choice]
        boost_strength = _benefit_strength(out, logical_key, keywords)
        boost_w = 4.0
        out["score_raw"] += boost_strength * boost_w
        total_weight += boost_w

    airline_ans = answers.get("mileage_airline")
    if airline_ans is not None and answers.get("mileage_interest") is not None:
        if (mode == "quick" and airline_ans in {"yes", "no"}) or (mode == "detailed" and isinstance(airline_ans, int)):
            ka_strength = _benefit_strength(out, "마일리지", ["대한항공", "스카이패스", "korean air"])
            out["strength_mileage_airline"] = ka_strength * 100.0
            if mode == "detailed":
                importance_w = _importance_weight_from_likert(int(airline_ans))
                if importance_w > 0:
                    pref = ka_strength
                    w = float(WEIGHTS["mileage_airline"]) * importance_w
                    out["score_raw"] += pref * w
                    total_weight += w
            else:
                pref = _preference_from_answer(ka_strength, airline_ans, mode)
                w = float(WEIGHTS["mileage_airline"])
                out["score_raw"] += pref * w
                total_weight += w

    bank_answer = answers.get("internet_bank_main")
    if bank_answer is not None:
        if mode == "quick":
            if bank_answer == "yes":
                strength = out["issuer"].isin(INTERNET_BANK_YES_ISSUERS).astype(float)
            elif bank_answer == "no":
                strength = out["issuer"].isin(INTERNET_BANK_NO_ISSUERS).astype(float)
            else:
                strength = pd.Series(0.5, index=out.index)
        else:
            strength = out["issuer"].isin(INTERNET_BANK_YES_ISSUERS).astype(float)

        out["strength_internet_bank_main"] = strength * 100.0
        if mode == "detailed" and isinstance(bank_answer, int):
            importance_w = _importance_weight_from_likert(int(bank_answer))
            if importance_w > 0:
                pref = strength
                w = float(WEIGHTS["internet_bank_main"]) * importance_w
                out["score_raw"] += pref * w
                total_weight += w
        else:
            pref = _preference_from_answer(strength, bank_answer, mode)
            w = float(WEIGHTS["internet_bank_main"])
            out["score_raw"] += pref * w
            total_weight += w

    out["max_score"] = total_weight
    out["match_rate"] = 0.0 if total_weight <= 0 else (out["score_raw"] / total_weight) * 100.0

    return out.sort_values(by=["match_rate", "domestic_annual_fee", "card_ad_id"], ascending=[False, True, True])


def filter_by_answers(df: pd.DataFrame, answers: dict[str, object], mode: str, upto_step: int | None = None) -> pd.DataFrame:
    filtered = df.copy()
    active_questions = get_active_questions(answers, mode)
    scope = active_questions if upto_step is None else active_questions[: upto_step + 1]
    for q in scope:
        filtered = apply_question_filter(filtered, q["id"], answers.get(q["id"]), mode)
    return filtered


def get_scored_cards(df: pd.DataFrame, answers: dict[str, object], mode: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    filtered = filter_by_answers(df, answers, mode)
    scored = apply_match_score(filtered, answers, mode)
    return filtered, scored


def requested_features(answers: dict[str, object], mode: str) -> list[tuple[str, str]]:
    scored: list[tuple[float, str, str]] = []
    for qid, (label, _, _) in FEATURE_MAP.items():
        ans = answers.get(qid)
        if mode == "quick":
            if ans == "yes":
                scored.append((float(WEIGHTS.get(qid, 5)), qid, label))
        else:
            if isinstance(ans, int):
                scored.append((float(ans) * float(WEIGHTS.get(qid, 5)), qid, label))

    ma = answers.get("mileage_airline")
    if mode == "quick":
        if ma == "yes":
            scored.append((float(WEIGHTS["mileage_airline"]), "mileage_airline", "대한항공 마일리지"))
    else:
        if isinstance(ma, int):
            scored.append((float(ma) * float(WEIGHTS["mileage_airline"]), "mileage_airline", "대한항공 마일리지"))

    scored.sort(key=lambda x: x[0], reverse=True)
    picked = [(qid, label) for _, qid, label in scored[:3]]
    if not picked:
        defaults = list(FEATURE_MAP.items())[:3]
        picked = [(qid, label) for qid, (label, _, _) in defaults]
    return picked


def detect_conflict_pair(frame: pd.DataFrame, answers: dict[str, object], mode: str) -> tuple[str, str] | None:
    if mode != "detailed" or len(frame) == 0:
        return None

    top_demands: list[tuple[float, str, str, list[str]]] = []
    for qid, (_, logical_key, keywords) in FEATURE_MAP.items():
        ans = answers.get(qid)
        if isinstance(ans, int) and ans >= 5:
            top_demands.append((float(WEIGHTS.get(qid, 5)), qid, logical_key, keywords))
    if len(top_demands) < 2:
        return None

    top_demands.sort(key=lambda x: x[0], reverse=True)
    first = top_demands[0]
    second = top_demands[1]
    s1 = _benefit_strength(frame, first[2], first[3])
    s2 = _benefit_strength(frame, second[2], second[3])
    overlap = ((s1 >= 0.6) & (s2 >= 0.6)).sum()
    if overlap < 3:
        return first[1], second[1]
    return None
