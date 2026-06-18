"""NLP case parser — fuzzy-matches free text to case studies, falls back to DeepSeek."""
from __future__ import annotations

import asyncio
import difflib
import json
import os
import re
from pathlib import Path
from typing import Any


def _load_cases() -> list[dict]:
    path = Path(__file__).parent.parent / "data" / "case_studies.json"
    return json.loads(path.read_text())["cases"]


def _search_terms(c: dict) -> str:
    drug = c["drugs"][0]["name"].lower() if c.get("drugs") else ""
    herb = c["herbs"][0]["name"].lower() if c.get("herbs") else ""
    title = c["title"].lower()
    aliases = ""
    if "warfarin" in drug:
        aliases += " anticoagulant blood thinner coumadin clotting"
    if "atorvastatin" in drug or "statin" in drug:
        aliases += " statin cholesterol lipitor"
    if "metformin" in drug:
        aliases += " diabetes diabetic sugar glucose"
    if "tacrolimus" in drug or "cyclosporine" in drug:
        aliases += " immunosuppressant transplant organ rejection"
    if "amoxicillin" in drug or "ciprofloxacin" in drug:
        aliases += " antibiotic infection bacteria"
    if "amlodipine" in drug:
        aliases += " antihypertensive blood pressure calcium channel"
    if "aspirin" in drug or "clopidogrel" in drug:
        aliases += " blood thinner antiplatelet"
    if "ashwagandha" in herb:
        aliases += " withania stress adaptogen anxiety"
    if "guggul" in herb:
        aliases += " guggul gugulipid cholesterol"
    if "brahmi" in herb:
        aliases += " bacopa memory cognition"
    if "karela" in herb or "bitter" in herb:
        aliases += " bitter gourd melon blood sugar diabetes"
    if "tulsi" in herb:
        aliases += " holy basil"
    return f"{drug} {herb} {title} {aliases}"


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


async def parse_case(text: str) -> dict[str, Any]:
    cases = _load_cases()
    text_lower = text.lower()
    user_words = _tokens(text_lower)

    best_id: str | None = None
    best_score = 0.0

    for case in cases:
        terms = _search_terms(case)
        term_words = _tokens(terms)

        drug = case["drugs"][0]["name"].lower() if case.get("drugs") else ""
        herb_raw = case["herbs"][0]["name"].lower() if case.get("herbs") else ""
        title = case["title"].lower()

        overlap = len(user_words & term_words)
        drug_hit = bool(drug and drug in text_lower)
        herb_hit = bool(herb_raw and herb_raw in text_lower)
        title_hit = bool(title and title in text_lower)

        if drug_hit and herb_hit:
            score = 0.9
        elif drug_hit or herb_hit:
            score = 0.58
        else:
            score = 0.0

        score += min(0.08, overlap * 0.01)
        if title_hit:
            score += 0.08
        score = min(score, 0.99)

        if score > best_score:
            best_score = score
            best_id = case["id"]

    # Also try difflib against case titles
    titles = [c["title"].lower() for c in cases]
    dl_matches = difflib.get_close_matches(text_lower, titles, n=1, cutoff=0.25)
    if dl_matches:
        dl_title = dl_matches[0]
        dl_case = next((c for c in cases if c["title"].lower() == dl_title), None)
        if dl_case:
            dl_score = difflib.SequenceMatcher(None, text_lower, dl_title).ratio()
            if dl_score > best_score:
                best_score = dl_score
                best_id = dl_case["id"]

    THRESHOLD = 0.28

    if best_score >= THRESHOLD and best_id:
        matched = next(c for c in cases if c["id"] == best_id)
        return {
            "matched_case_id": best_id,
            "extracted": {
                "drug": matched["drugs"][0]["name"] if matched.get("drugs") else None,
                "herb": matched["herbs"][0]["name"] if matched.get("herbs") else None,
                "age": None,
                "sex": None,
                "indication": None,
            },
            "confidence": round(best_score, 3),
            "free_text_message": None,
        }

    extracted = await _extract_with_llm(text)
    return {
        "matched_case_id": None,
        "extracted": extracted,
        "confidence": round(best_score, 3),
        "free_text_message": _build_band_message(extracted),
    }


def _build_band_message(extracted: dict) -> str:
    drug = extracted.get("drug") or "an unidentified drug"
    herb = extracted.get("herb") or "an unidentified herb"
    age = extracted.get("age")
    sex = extracted.get("sex")
    indication = extracted.get("indication")

    patient_parts = []
    if age:
        patient_parts.append(f"{age}-year-old")
    if sex:
        patient_parts.append(str(sex).lower())
    patient = " ".join(patient_parts) if patient_parts else "a patient"
    indication_str = f" for {indication}" if indication else ""

    return (
        f"@Intake @PatientProfile New case: {patient} on {drug}{indication_str} "
        f"has started taking {herb}. Please assess for drug-herb interactions and return a safety risk tier."
    )


async def _extract_with_llm(text: str) -> dict[str, Any]:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return {"drug": None, "herb": None, "age": None, "sex": None,
                "indication": None, "cyp2c9_genotype": None, "cyp3a4_status": None, "egfr": None}

    prompt = (
        "Extract drug name, herb name, patient age, sex, and indication from this text. "
        "Return JSON only with keys: drug, herb, age, sex, indication, cyp2c9_genotype, "
        "cyp3a4_status, egfr. Use null for unknown fields. No markdown — pure JSON.\n"
        f"Text: {text}"
    )

    def _call() -> dict:
        import urllib.request as _req
        payload = json.dumps({
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 256,
            "temperature": 0.1,
        }).encode()
        request = _req.Request(
            "https://api.deepseek.com/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        try:
            with _req.urlopen(request, timeout=15) as resp:
                data = json.loads(resp.read())
                raw = data["choices"][0]["message"]["content"].strip()
                if raw.startswith("```"):
                    raw = raw.split("```", 2)[1]
                    if raw.startswith("json"):
                        raw = raw[4:].lstrip("\n")
                return json.loads(raw)
        except Exception:
            return {"drug": None, "herb": None, "age": None, "sex": None,
                    "indication": None, "cyp2c9_genotype": None, "cyp3a4_status": None, "egfr": None}

    return await asyncio.get_event_loop().run_in_executor(None, _call)


async def parse_case_text(text: str) -> dict[str, Any]:
    return await parse_case(text)
