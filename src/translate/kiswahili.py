"""Kiswahili fallback translation tables (used when LLM is disabled)."""

from __future__ import annotations

import re
from typing import List, Tuple


def _is_kiswahili(language: str | None) -> bool:
    lang = (language or "").strip().lower()
    return lang in ("kiswahili", "swahili")


def _to_kiswahili(text: str) -> str:
    """Lightweight phrase/word replacement to Kiswahili.

    Used only in non-LLM fallback mode. Favors clarity over perfect grammar.
    """
    if not text:
        return ""

    repl_phrase: List[Tuple[str, str]] = [
        ("urine system", "mfumo wa mkojo"),
        ("urine tube", "mrija wa mkojo"),
        ("urine tubes", "mirija ya mkojo"),
        ("womb (uterus)", "mfuko wa uzazi (uterasi)"),
        ("womb", "mfuko wa uzazi"),
        ("hydronephrosis (severe urine backup)", "hidronefrosisi (kuziba kwa mkojo kwa kiwango kikubwa)"),
        ("widened/swollen", "imepanuka/imevimba"),
        ("iodine dye", "dawa ya rangi (iodini)"),
        ("spread of the cancer", "kusambaa kwa saratani"),
        ("abnormal spot", "eneo lisilo la kawaida"),
        ("You have", "Una"),
        ("you have", "una"),
        ("There is", "Kuna"),
        ("there is", "kuna"),
        ("This needs", "Hii inahitaji"),
        ("Go to the hospital now if", "Nenda hospitali sasa ikiwa"),
        ("See a neurosurgeon urgently", "Muone daktari wa upasuaji wa ubongo haraka"),
        ("brain shift", "mchepuko wa ubongo"),
        ("mass effect", "shinikizo la uvimbe"),
        ("fronto-parietal", "fronto-parietal (eneo la mbele na upande wa kati)"),
        ("outside the brain tissue but inside the skull", "nje ya tishu za ubongo lakini ndani ya fuvu"),
        ("thin slices", "vipande vyembamba"),
        ("Contrast dye", "Dawa ya rangi"),
        ("contrast dye", "dawa ya rangi"),
        ("was done", "ilifanyika"),
        ("were done", "zilifanyika"),
        ("No evidence of", "Hakuna ushahidi wa"),
        ("No significant", "Hakuna kilicho kikubwa"),
        ("pleural effusion", "majimaji kwenye ganda la mapafu"),
        ("midline shift", "mchepuko wa mstari wa kati"),
        ("subfalcine herniation", "kuingia kwa ubongo chini ya pindo la kati"),
        ("herniation", "kuingia kwa tishu mahali pasipo"),
        ("lymph nodes", "tezi za limfu"),
        ("lymph node", "tezi ya limfu"),
        ("pulmonary embolism", "gandu la damu kwenye mshipa wa mapafu"),
        ("pulmonary edema", "uvimbe wa maji kwenye mapafu"),
        ("atelectasis", "kupungua kwa upanuzi wa sehemu ya pafu"),
        ("consolidation", "muungano wa tishu za pafu"),
        ("enhancement", "kuonekana zaidi baada ya dawa ya rangi"),
        ("enhances", "huonekana zaidi baada ya dawa ya rangi"),
        ("enhanced", "imeonekana zaidi baada ya dawa ya rangi"),
        ("nodule", "kijivimbe"),
        ("calcification", "ugumu wa chokaa"),
        ("metastatic", "iliyosanbaa"),
    ]

    repl_word: List[Tuple[str, str]] = [
        ("tummy", "tumbo"),
        ("abdomen", "tumbo"),
        ("abdominal", "tumboni"),
        ("ureter", "mrija wa mkojo"),
        ("ureters", "mirija ya mkojo"),
        ("kidneys", "figo"),
        ("kidney", "figo"),
        ("bladder", "kibofu"),
        ("liver", "ini"),
        ("brain", "ubongo"),
        ("head", "kichwa"),
        ("skull", "fuvu"),
        ("lung", "pafu"),
        ("lungs", "mapafu"),
        ("cervix", "seviksi"),
        ("lesions", "maeneo yasiyo ya kawaida"),
        ("lesion", "eneo lisilo la kawaida"),
        ("mass", "uvimbe"),
        ("lump", "uvimbe"),
        ("benign", "siyo saratani"),
        ("malignant", "saratani"),
        ("cancer", "saratani"),
        ("metastases", "maeneo ya saratani iliyosambaa"),
        ("metastasis", "kusambaa kwa saratani"),
        ("indeterminate", "haijabainika"),
        ("dilated", "imepanuka"),
        ("dilation", "upanuzi"),
        ("stenosis", "kubana"),
        ("contrast", "dawa ya rangi"),
        ("shows", "inaonyesha"),
        ("spreads", "inasambaa"),
        ("blocks", "inaziba"),
        ("blocked", "imeziba"),
        ("likely", "huenda"),
        ("scan", "skani"),
        ("treatment", "matibabu"),
        ("surgery", "upasuaji"),
        ("neurosurgeon", "daktari wa upasuaji wa ubongo"),
        ("headaches", "maumivu ya kichwa"),
        ("weakness", "udhaifu"),
        ("confusion", "kuchanganyikiwa"),
        ("right", "kulia"),
        ("left", "kushoto"),
        ("area", "eneo"),
        ("upper", "juu"),
        ("lower", "chini"),
        ("anterior", "ya mbele"),
        ("posterior", "ya nyuma"),
        ("superior", "ya juu"),
        ("inferior", "ya chini"),
        ("lobe", "sehemu"),
        ("segment", "sehemu"),
    ]

    out = text
    out = out.replace("’", "'")

    for a, b in repl_phrase:
        out = re.sub(rf"\b{re.escape(a)}\b", b, out, flags=re.I)
    for a, b in repl_word:
        out = re.sub(rf"\b{re.escape(a)}\b", b, out, flags=re.I)

    out = re.sub(r"\byour\b", "yako", out, flags=re.I)
    out = re.sub(r"\byou\b", "wewe", out, flags=re.I)
    out = re.sub(r"(?m)^\s*-\s+No\b", "- Hakuna", out, flags=re.I)
    out = re.sub(r"\bNo\b", "Hakuna", out, flags=re.I)

    out = re.sub(r"\s+", " ", out).strip()
    return out
