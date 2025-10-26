"""
Patient-friendly translation and structuring for radiology reports.

This module builds a simple, sectioned summary suitable for templates/result.html.
It uses GPT‑5 via the OpenAI Responses API (when allowed) to rewrite the
extracted report content into short, clear bullet points with the same tone and
length as the provided reference style. Dashes ("-") from the model output are
rendered as HTML bullet lists so they appear as bullets in result.html.
"""

from __future__ import annotations

import os
import re
import csv
import html
import logging
import json
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

from .parse import parse_metadata, sections_from_text

logger = logging.getLogger("insideimaging.translate")


# ------------------------------------------------------------
# Minimal glossary support (optional CSV at data/glossary.csv)
# ------------------------------------------------------------
@dataclass
class Glossary:
    terms: Dict[str, str]

    @classmethod
    def load(cls, path: str) -> "Glossary":
        terms: Dict[str, str] = {}
        try:
            with open(path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    term = (row.get("term") or row.get("Term") or "").strip()
                    definition = (row.get("definition") or row.get("Definition") or "").strip()
                    if term:
                        terms[term.lower()] = definition
        except Exception:
            logger.exception("Failed to load glossary from %s", path)
        return cls(terms)


# -----------------------
# HTML helper functions
# -----------------------
_DASH_LINE_RX = re.compile(r"^\s*[-•]\s+(.+?)\s*$")


def _dashes_to_ul(text: str) -> str:
    """Convert dash/•-prefixed lines to a <ul> list.

    If there are no dash bullets, return text as-is (HTML-escaped).
    """
    if not text:
        return ""

    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    items: List[str] = []
    for ln in lines:
        m = _DASH_LINE_RX.match(ln)
        if m:   
            items.append(m.group(1).strip())

    if not items:
        # No bullets detected; return safe paragraph text
        return html.escape(text)

    lis = "".join(f"<li>{html.escape(it)}</li>" for it in items if it)
    return f"<ul>{lis}</ul>"


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s or "").strip()

# Accept only standard dash bullets to avoid non-ASCII issues
_DASH_LINE_RX = re.compile(r"^\s*-\s+(.+?)\s*$")


def _simplify_for_layperson(text: str) -> str:
    """Very lightweight jargon simplifier for fallback mode (English only)."""
    repl = [
        # Spinal anatomy - specific levels first
        (r"\bL5/S1\b", "between the lowest back bone and tailbone"),
        (r"\bL4/L5\b", "between the 4th and 5th bones in your lower back"),
        (r"\bL3/L4\b", "between the 3rd and 4th bones in your lower back"),
        (r"\bL2/L3\b", "between the 2nd and 3rd bones in your lower back"),
        (r"\bL1/L2\b", "between the 1st and 2nd bones in your lower back"),
        (r"\bC6/C7\b", "between the 6th and 7th bones in your neck"),
        (r"\bC5/C6\b", "between the 5th and 6th bones in your neck"),
        (r"\bC4/C5\b", "between the 4th and 5th bones in your neck"),
        (r"\bC3/C4\b", "between the 3rd and 4th bones in your neck"),
        (r"\bT\d+/T\d+\b", "between bones in your mid-back"),
        (r"\bL\d+/L\d+\b", "between bones in your lower back"),
        (r"\bC\d+/C\d+\b", "between bones in your neck"),
        # General spinal terms
        (r"\blumbar spine\b", "lower back"),
        (r"\bthoracic spine\b", "mid-back"),
        (r"\bcervical spine\b", "neck"),
        (r"\bvertebrae\b", "bones in the spine"),
        (r"\bvertebra\b", "bone in the spine"),
        (r"\bforamina\b", "nerve tunnels"),
        (r"\bforamen\b", "nerve tunnel"),
        (r"\bdisc herniation\b", "slipped disc"),
        (r"\bherniated disc\b", "slipped disc"),
        (r"\bspinal canal\b", "main channel in the spine"),
        (r"\bnerve root\b", "nerve branch"),
        (r"\bspinal cord\b", "main nerve bundle in the spine"),
        # Lymph and glands
        (r"\badenopathy\b", "swollen glands"),
        (r"\blymphadenopathy\b", "swollen glands"),
        (r"\blymph nodes\b", "infection-fighting glands"),
        (r"\blymph node\b", "infection-fighting gland"),
        # Fluid and swelling
        (r"\bedema\b", "swelling"),
        (r"\beffusion\b", "fluid buildup"),
        (r"\bpleural effusion\b", "fluid around the lung"),
        (r"\bascites\b", "fluid in the belly"),
        # Body regions
        (r"\babdomen(al)?\b", "tummy"),
        (r"\burinary tract\b", "urine system"),
        (r"\bureters\b", "urine tubes"),
        (r"\bureter\b", "urine tube"),
        # Abnormalities
        (r"\blesions\b", "abnormal spots"),
        (r"\blesion\b", "abnormal spot"),
        (r"\bmass(es)?\b", "lump"),
        (r"\bneoplasm(s)?\b", "cancer"),
        # Organs
        (r"\bhepatic\b", "liver"),
        (r"\brenal\b", "kidney"),
        (r"\bpulmonary\b", "lung"),
        (r"\bcervix\b", "neck of the womb"),
        # Conditions
        (r"\bhydronephrosis\b", "severe urine backup"),
        (r"\bstenosis\b", "narrowing"),
        (r"\bdilat(e|ed|ation)\b", "widened"),
        # Procedures
        (r"\bintravenous contrast\b", "dye through a vein"),
        (r"\bcontrast\b", "dye"),
        # Cancer terms
        (r"\bmetastases\b", "spread of the cancer"),
        (r"\bmetastasis\b", "spread of the cancer"),
        (r"\bmalignant\b", "cancer"),
        (r"\bcarcinoma\b", "cancer"),
        (r"\bbenign\b", "non-cancer"),
        # Other
        (r"\bindeterminate\b", "unclear"),
        (r"\batelectasis\b", "partially collapsed lung"),
        (r"\bconsolidation\b", "filled airspaces in the lung"),
        (r"\bnodule(s)?\b", "small lump"),
    ]
    out = text or ""
    for rx, rep in repl:
        out = re.sub(rx, rep, out, flags=re.IGNORECASE)
    return out


# -----------------------
# Kiswahili fallback
# -----------------------
def _is_kiswahili(language: str | None) -> bool:
    lang = (language or "").strip().lower()
    return lang in ("kiswahili", "swahili")


def _to_kiswahili(text: str) -> str:
    """Very lightweight phrase/word replacement to Kiswahili.

    This is used only in non-LLM fallback mode to keep parity of behavior
    when the user selects Kiswahili. It intentionally favors clarity over
    perfect grammar.
    """
    if not text:
        return ""

    # Phrase-level replacements first (order matters)
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

    # Single-word/shorter token replacements
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
    # Normalize simple ASCII quotes to avoid oddities
    out = out.replace("\u2019", "'")

    for a, b in repl_phrase:
        out = re.sub(rf"\b{re.escape(a)}\b", b, out, flags=re.I)

    for a, b in repl_word:
        out = re.sub(rf"\b{re.escape(a)}\b", b, out, flags=re.I)

    # Very light pronoun/tense shifts when present
    out = re.sub(r"\byour\b", "yako", out, flags=re.I)
    out = re.sub(r"\byou\b", "wewe", out, flags=re.I)
    out = re.sub(r"(?m)^\s*-\s+No\b", "- Hakuna", out, flags=re.I)
    out = re.sub(r"\bNo\b", "Hakuna", out, flags=re.I)

    # Clean extra spaces produced by replacements
    out = re.sub(r"\s+", " ", out).strip()
    return out


# -----------------------
# GPT‑5 call + parsing
# -----------------------
REFERENCE_STYLE = (
    "For the reason for scan section: -You had blood in the urine, so the doctors needed clear "
    "pictures to look for growths or blockages in the bladder, ureters and kidneys. "
    "Procedure details section: -A CT machine took many thin pictures of your tummy before and after iodine dye "
    "was injected, giving sharp views of the urine system. "
    "Important Findings section: -A lump about 6 × 5 × 4½ cm (chicken-egg sized) grows from the left side of the bladder, "
    "both inside and outside the bladder wall. -The lump spreads into the lower part of the left urine tube (ureter), "
    "causing severe swelling of that tube and the left kidney (grade 5 hydronephrosis). -The same lump has also grown into "
    "the neck of the womb (cervix). -Several small spots are seen in both lower lungs; these likely show the cancer has spread. "
    "-Liver, spleen, pancreas, adrenal glands, bowel and big blood vessels look normal; spine shows age-related wear. "
    "CONCLUSION section: -Large bladder cancer has broken through the bladder wall, blocked the left ureter, invaded the cervix, "
    "and has probably spread to the lungs. NOTE OF CONCERN section: -See a urologist and cancer specialist urgently to plan biopsy, "
    "staging and treatment such as surgery, chemotherapy or immunotherapy. -The swollen kidney may need a stent or tube (nephrostomy) "
    "to drain urine and prevent damage. -Go to hospital fast if you get fever, severe side pain, cannot pass urine, or feel breathless."
)


# Override to ensure a layperson-friendly style reference
REFERENCE_STYLE = (
    "You convert radiology reports into a kind, patient-facing summary. "
    "Use second person (you/your). Be confident and plain. Avoid hedging. "
    "Short to medium sentences (8–22 words) with everyday words. Define medical terms in brackets. "
    "Keep numbers; add simple size comparisons when helpful. Use direct verbs: shows, spreads into, blocks, likely spread."
)


def _compose_prompt(meta: Dict[str, str], secs: Dict[str, str], language: str) -> List[dict]:
    """Build a Responses API input payload requesting strict JSON with required keys."""
    # Build minimal, PHI-free context
    study = (meta.get("study") or "").strip()
    hospital = (meta.get("hospital") or "").strip()
    if hospital:
        # keep institution name generic—do not surface PHI
        hospital = "a hospital"

    context = {
        "study": study,
        "hospital": hospital,
        "reason": secs.get("reason", ""),
        "technique": secs.get("technique", ""),
        "findings": secs.get("findings", ""),
        "impression": secs.get("impression", ""),
    }

    system = (
        "You convert radiology reports into a kind, patient-facing summary. "
        "Write ALL output ONLY in {language}. Do not include any personal identifiers."
    ).replace("{language}", language or "English")

    # When Kiswahili is selected, strongly forbid mixed language output
    if _is_kiswahili(language):
        system += (
            " Use pure, everyday East African Kiswahili. Do NOT mix with English. "
            "Avoid English words entirely. You may keep standard acronyms (CT, MRI, IV, X-ray) "
            "but explain them once in Kiswahili in brackets the first time they appear."
        )

    developer = (
        "Return ONLY a JSON object with keys: reason, technique, findings, conclusion, concern.\n"
        "Use second person (you/your). Be confident and plain. Avoid hedging.\n"
        "Explain as if to someone with no medical background (about grade 6 reading level).\n"
        "Use a kind, calm, supportive tone.\n\n"
        "CRITICAL SIMPLIFICATION RULES\n"
        "- NEVER use medical terms alone. ALWAYS explain them immediately in brackets.\n"
        "- Bad: 'enlarged lymph nodes' or 'adenopathy'\n"
        "- Good: 'swollen infection-fighting glands (lymph nodes)' or 'swollen glands in the neck'\n"
        "- Bad: 'Many enlarged neck lymph nodes (adenopathy). Both sides are involved, worse on the left.'\n"
        "- Good: 'Many swollen glands in the neck (lymph nodes that fight infection). Both sides are swollen, worse on the left.'\n"
        "- Bad: 'At L4/5, a broad disc herniation (slipped disc) pushes back and center.'\n"
        "- Good: 'Between the 4th and 5th bones in your lower back, a slipped disc pushes backward.'\n"
        "- Replace ALL medical jargon and anatomy codes with everyday words + explanations.\n"
        "- ALWAYS explain anatomy locations in simple terms:\n"
        "  * L1-L5 → bones in the lower back (lumbar spine)\n"
        "  * T1-T12 → bones in the mid-back (thoracic spine)\n"
        "  * C1-C7 → bones in the neck (cervical spine)\n"
        "  * Foramina → nerve tunnels or side openings\n"
        "  * Vertebrae → bones in the spine\n"
        "  * Disc herniation → slipped disc\n\n"
        "STYLE & LENGTH\n"
        "- Short to medium sentences (8–22 words). Use everyday words.\n"
        "- Define any medical word immediately in brackets: 'hydronephrosis (severe urine backup)'.\n"
        "- Replace difficult words with plain ones FIRST, then optionally add medical term in brackets:\n"
        "  * abdomen → tummy\n"
        "  * lesion → abnormal spot\n"
        "  * mass → lump\n"
        "  * lymph nodes → infection-fighting glands (lymph nodes) OR swollen glands\n"
        "  * adenopathy → swollen glands\n"
        "  * edema → swelling\n"
        "  * effusion → fluid buildup\n"
        "- No acronyms without a plain explanation the first time: CT (special x-ray), MRI (magnet pictures), IV (through a vein).\n"
        "- Keep numbers from the report. Add a simple size comparison in brackets when helpful.\n"
        "- Use direct verbs: shows, spreads into, blocks, has likely spread.\n"
        "- Do not use phrases like 'clinical correlation recommended' or 'please correlate'.\n\n"
        "READABILITY RULES\n"
        "- Prefer common words: urinary tract → urine system; ureter → urine tube; hydronephrosis → severe urine backup.\n"
        "- Avoid ALL jargon: attenuation, morphology, heterogeneous, signal, density, adenopathy, lymphadenopathy.\n"
        "- Use simple alternatives or define in brackets.\n"
        "- Avoid fear language. Be honest but reassuring.\n\n"
        "MAP EACH FIELD TO THIS EXACT CONTENT\n\n"
        "reason:\n"
        "- 1–2 sentences (100–150 chars). Explain why the scan was ordered in simple words.\n"
        "- Start with the patient's symptom or trigger.\n"
        "- Name body area(s) to check and for what (growths, blockages, bleeding).\n\n"
        "technique:\n"
        "- 1–2 sentences (100–180 chars), friendly and concrete.\n"
        "- Mention modality, body area, thin slices, and contrast timing if used.\n\n"
        "findings:\n"
        "- Return either (A) a single string composed of bullet lines that each start with '- ', or (B) an array of bullet strings where each item starts with '- '.\n"
        "- Write 3–8 (STRICT) bullets that cover all important findings (prioritize completeness over brevity).\n"
        "- Do NOT add a 'normal elsewhere' bullet — the UI adds this automatically.\n"
        "- Put the most important problem first. Each bullet may be 1–2 short sentences.\n"
        "- Use plain names (bladder, urine tube, kidney, neck of the womb, lung).\n"
        "- Show cause → effect clearly.\n"
        "- Include all significant abnormalities from the report, not just the top few.\n\n"
        "conclusion:\n"
        "- 1–2 sentences (80–150 chars) that tie the findings together in plain language.\n"
        "- Name the main problem and key spread/blockage in one tight summary.\n"
        "- MUST NOT be empty; always provide a summary.\n\n"
        "concern:\n"
        "- 2–3 short sentences (150–300 chars) with next steps and red-flags. Use action words.\n"
        "- Include urgent referrals, likely procedures (e.g., stent or nephrostomy), and 'go to hospital if...' warnings.\n"
        "- MUST NOT be empty; always provide next steps.\n\n"
        "CRITICAL CONTENT RULES\n"
        "- Extract ONLY from the actual report. Do not invent findings.\n"
        "- Keep units and grades/stages as written; add simple explanations in brackets.\n"
        "- Prefer common words: abdomen → tummy; urinary tract → urine system; lesion → abnormal spot; mass → lump;\n"
        "  dilated → widened/swollen; stenosis → narrowing. Avoid fear language but do not downplay serious issues.\n"
        "- ALL five fields (reason, technique, findings, conclusion, concern) MUST have content. Do not leave any field empty.\n\n"
        "OUTPUT FORMAT\n"
        "Return JSON only. No prose, no markdown, no headings, no prefix/suffix—just the object.\n"
        "STRICT JSON RULES: Valid JSON, no trailing commas, close all quotes/brackets/braces, and STOP after the final }.\n"
        "COMPLETE ALL FIELDS: Ensure conclusion and concern are NOT empty strings.\n"
        "TOTAL BUDGET: Keep the entire JSON under 1200 characters, but prioritize completeness over brevity."
    )

    if _is_kiswahili(language):
        developer += (
            "\n\nSTRICT KISWAHILI RULES\n"
            "- Andika kila neno kwa Kiswahili fasaha; usichanganye na Kiingereza.\n"
            "- Badili istilahi za kitabibu kuwa Kiswahili (mfano: mass  uvimbe; lesion  eneo lisilo la kawaida;\n"
            "  consolidation  muungano wa tishu za pafu; effusion  majimaji kwenye ganda la mapafu;\n"
            "  enhancement  kuonekana zaidi baada ya dawa ya rangi).\n"
            "- Ruhusu vifupisho vya kawaida tu (CT, MRI, IV, X-ray) na toa maelezo ya Kiswahili ndani ya mabano mara ya kwanza.\n"
            "- Usitumie maneno kama 'mass', 'lesion', 'contrast', 'enhancement', 'consolidation', 'effusion' kwa Kiingereza.\n"
        )

    user = (
        f"Study: {study or 'Unknown'}\n\n"
        f"Reason section:\n{secs.get('reason','').strip()}\n\n"
        f"Technique section:\n{secs.get('technique','').strip()}\n\n"
        f"Findings section:\n{secs.get('findings','').strip()}\n\n"
        f"Impression/Conclusion section:\n{secs.get('impression','').strip()}\n\n"
        f"REFERENCE STYLE: {REFERENCE_STYLE}"
    )

    # Responses API accepts a list of messages; we'll pass role-tagged messages.
    return [
        {"role": "system", "content": system},
        {"role": "developer", "content": developer},
        {"role": "user", "content": user},
    ]


def _call_gpt5(messages: List[dict]) -> str:
    """Call the OpenAI Responses API with GPT‑5 and return raw text output.

    Honors environment variables:
      - OPENAI_MODEL (default: gpt-5)
      - INSIDEIMAGING_ALLOW_LLM (must be truthy to call)
      - OPENAI_MAX_OUTPUT_TOKENS (default: 512)
      - OPENAI_TIMEOUT (seconds; default: 60)
    """
    allow = os.getenv("INSIDEIMAGING_ALLOW_LLM", "0").strip()
    if allow not in ("1", "true", "True", "yes", "YES"):  # guardrails
        logger.info("LLM disabled by INSIDEIMAGING_ALLOW_LLM=%r", allow)
        return ""

    # Lazy import so the app can run without the SDK in non-LLM mode
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        logger.exception("openai SDK not available; skipping LLM call")
        return ""

    model = os.getenv("OPENAI_MODEL", "gpt-5").strip() or "gpt-5"
    max_out = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "512") or 512)
    timeout_s = int(os.getenv("OPENAI_TIMEOUT", "60") or 60)

    # Some deployments pin verbosity low to encourage brevity
    text_cfg = {"verbosity": "low"}

    client = OpenAI()

    try:
        resp = client.responses.create(
            model=model,
            input=messages,
            text=text_cfg,
            max_output_tokens=max_out,
            reasoning={"effort": "minimal"},  # fast, deterministic rewriting
            timeout=timeout_s,
        )
    except Exception:
        logger.exception("OpenAI responses.create failed")
        return ""

    # Extract assistant text per the SDK pattern
    out_text = []
    try:
        for item in getattr(resp, "output", []) or []:
            if hasattr(item, "content"):
                for c in getattr(item, "content", []) or []:
                    if hasattr(c, "text") and c.text:
                        out_text.append(c.text)
    except Exception:
        logger.exception("Failed to parse OpenAI response output")
        return ""

    raw = "".join(out_text).strip()
    if raw:
        preview = raw if len(raw) <= 4000 else raw[:4000] + "…[truncated]"
        logger.info("GPT-5 raw output:%s\n%s", " (truncated)" if len(raw) > 4000 else "", preview)
    return raw


def _translate_parts_via_llm(parts: Dict[str, object], *, language: str) -> Optional[Dict[str, object]]:
    """Ask the LLM to translate already-parsed parts into the target language.

    Returns a dict with keys reason, technique, findings, conclusion, concern
    or None if the call is disabled/fails.
    """
    allow = os.getenv("INSIDEIMAGING_ALLOW_LLM", "0").strip()
    if allow not in ("1", "true", "True", "yes", "YES"):
        return None

    system = (
        "You translate patient-facing medical text into {language} ONLY. "
        "Use a warm, clear, supportive tone."
    ).replace("{language}", language or "Kiswahili")

    if _is_kiswahili(language):
        system += (
            " Use pure Kiswahili; do NOT mix languages. Avoid English words entirely. "
            "You may keep CT/MRI/IV/X-ray acronyms but explain them in Kiswahili in brackets the first time."
        )

    developer = (
        "Return ONLY a JSON object with keys: reason, technique, findings, conclusion, concern.\n"
        "RULES:\n"
        "- Translate content fully into the target language; no English words (for Kiswahili: hakikisha hakuna Kiingereza).\n"
        "- Keep numbers, units, grades/stages as-is (e.g., 5 mm, cm).\n"
        "- Keep acronyms (CT, MRI) but explain in the target language the first time in brackets.\n"
        "- findings must be either (A) an array of bullet strings, each starting with '- ', or (B) a single string of dash bullets.\n"
        "- Do not add or remove bullets; preserve the count as much as reasonable.\n"
        "- Do not include any extra keys, headings, or prose. JSON only."
    )

    user = (
        "Translate the following JSON fields into the target language, preserving structure and bullets.\n"
        + json.dumps({
            "reason": parts.get("reason", ""),
            "technique": parts.get("technique", ""),
            "findings": parts.get("findings", []),
            "conclusion": parts.get("conclusion", ""),
            "concern": parts.get("concern", ""),
        }, ensure_ascii=False)
    )

    raw = _call_gpt5([
        {"role": "system", "content": system},
        {"role": "developer", "content": developer},
        {"role": "user", "content": user},
    ])
    if not raw:
        return None

    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            # Ensure keys exist
            for k in ("reason", "technique", "findings", "conclusion", "concern"):
                obj.setdefault(k, "")
            return obj
    except Exception:
        logger.exception("JSON parse failed for LLM translation output")
    return None


def _split_sections(raw: str) -> Dict[str, str]:
    """Split raw model text into our five sections by fixed headings.

    Expected headings (case-insensitive):
      - Reason for the scan:
      - Procedure details:
      - Important Findings:
      - CONCLUSION:
      - NOTE OF CONCERN:
    """
    if not raw:
        return {"reason": "", "technique": "", "findings": "", "conclusion": "", "concern": ""}

    # Normalize headings and split
    normalized = raw.replace("\r", "")
    # Build regex to capture each heading and following block
    parts_rx = re.compile(
        r"(?is)\b(Reason for the scan|Procedure details|Important Findings|CONCLUSION|NOTE OF CONCERN)\s*:\s*\n?"
        r"(.*?)(?=\n\s*(?:Reason for the scan|Procedure details|Important Findings|CONCLUSION|NOTE OF CONCERN)\s*:|\Z)"
    )

    found: Dict[str, str] = {}
    for m in parts_rx.finditer(normalized):
        key = m.group(1).lower()
        body = (m.group(2) or "").strip()
        if key.startswith("reason"):
            found["reason"] = body
        elif key.startswith("procedure"):
            found["technique"] = body
        elif key.startswith("important"):
            found["findings"] = body
        elif key.startswith("conclusion"):
            found["conclusion"] = body
        elif key.startswith("note of concern"):
            found["concern"] = body

    # Ensure all keys are present
    for k in ("reason", "technique", "findings", "conclusion", "concern"):
        found.setdefault(k, "")
    return found


def _salvage_json_like(raw: str) -> Dict[str, object]:
    """Best-effort extraction when JSON is truncated or slightly malformed.

    Returns a dict with keys reason, technique, findings, conclusion, concern.
    findings may be a list[str] or a string of dash-lines.
    """
    out: Dict[str, object] = {"reason": "", "technique": "", "findings": "", "conclusion": "", "concern": ""}

    def grab_string(key: str) -> str:
        m = re.search(rf'"{key}"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', raw, flags=re.S)
        if m:
            return (m.group(1) or "").strip()
        # Partial capture (no closing quote): take to end and trim to last sentence end
        m2 = re.search(rf'"{key}"\s*:\s*"(.*)$', raw, flags=re.S)
        if m2:
            val = (m2.group(1) or "").strip()
            # Trim to last ., !, or ? to avoid ragged endings
            cut = max(val.rfind("."), val.rfind("!"), val.rfind("?"))
            if cut != -1:
                val = val[: cut + 1]
            # Remove any trailing quotes/braces/commas
            val = val.rstrip('\'"} ,')
            return val.strip()
        return ""

    def grab_array(key: str) -> List[str]:
        m = re.search(rf'"{key}"\s*:\s*\[(.*?)\]', raw, flags=re.S)
        items: List[str] = []
        if m:
            body = m.group(1) or ""
            for s in re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', body, flags=re.S):
                s = (s or "").strip()
                if s:
                    items.append(s)
        return items

    reason = grab_string("reason")
    technique = grab_string("technique")
    findings_list = grab_array("findings")
    findings_str = grab_string("findings") if not findings_list else ""
    conclusion = grab_string("conclusion")
    concern = grab_string("concern")

    if reason:
        out["reason"] = reason
    if technique:
        out["technique"] = technique
    if findings_list:
        out["findings"] = findings_list
    elif findings_str:
        out["findings"] = findings_str
    if conclusion:
        out["conclusion"] = conclusion
    if concern:
        out["concern"] = concern

    return out

# -----------------------
# Public interface
# -----------------------
def build_structured(report_text: str, glossary: Optional[Glossary] = None, *, language: str = "English") -> Dict[str, str]:
    """Create the structured, patient-friendly output consumed by result.html.

    Returns a dict with keys: reason, technique, findings, conclusion, concern, and
    a nested patient dict with non-identifying metadata when available.
    """
    text = report_text or ""
    cleaned = _strip_html(text)

    # Parse metadata and sections from the raw report
    try:
        meta = parse_metadata(cleaned)
    except Exception:
        logger.exception("parse_metadata failed")
        meta = {"hospital": "", "study": "", "name": "", "sex": "", "age": "", "date": ""}

    try:
        secs = sections_from_text(cleaned)
    except Exception:
        logger.exception("sections_from_text failed")
        secs = {"reason": "", "technique": "", "findings": cleaned, "impression": ""}

    # Compose and call GPT‑5
    messages = _compose_prompt(meta, secs, language)
    raw = _call_gpt5(messages)

    # If we got truncated JSON (common with complex Kiswahili), retry with higher token limit
    retry_attempted = False
    if raw and not raw.strip().endswith("}"):
        logger.warning("GPT-5 output appears truncated (doesn't end with }); attempting retry with higher token limit")
        # Temporarily boost max tokens for retry
        original_max = os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "512")
        os.environ["OPENAI_MAX_OUTPUT_TOKENS"] = "800"
        retry_raw = _call_gpt5(messages)
        os.environ["OPENAI_MAX_OUTPUT_TOKENS"] = original_max
        if retry_raw and len(retry_raw) > len(raw):
            raw = retry_raw
            retry_attempted = True
            logger.info("Retry successful; using longer output")

    if not raw:
        # Fallback: build simple, layperson text directly from sections
        logger.warning("LLM output empty; using heuristic fallback")
        fallback = {
            "reason": secs.get("reason", "").strip(),
            "technique": secs.get("technique", "").strip(),
            "findings": secs.get("findings", "").strip(),
            "conclusion": secs.get("impression", "").strip(),
            "concern": "",
        }
        # Convert first N sentences, simplified
        def sentences(s: str, n: int = 5) -> List[str]:
            pts = re.split(r"(?<=[.!?])\s+", s)
            return [p.strip() for p in pts if p.strip()][:n]

        # Build simplified English chunks first
        reason_parts = [_simplify_for_layperson(x) for x in sentences(fallback["reason"], 2)]
        tech_parts = [_simplify_for_layperson(x) for x in sentences(fallback["technique"], 2)]
        find_parts = [_simplify_for_layperson(s) for s in sentences(fallback["findings"], 6)]
        concl_parts = [_simplify_for_layperson(x) for x in sentences(fallback["conclusion"], 2)]

        # If Kiswahili is selected, translate these simplified parts
        if _is_kiswahili(language):
            reason_parts = [_to_kiswahili(p) for p in reason_parts]
            tech_parts = [_to_kiswahili(p) for p in tech_parts]
            find_parts = [_to_kiswahili(p) for p in find_parts]
            concl_parts = [_to_kiswahili(p) for p in concl_parts]

        reason_txt = html.escape(" ".join(reason_parts))
        tech_txt = html.escape(" ".join(tech_parts))
        find_ul = _dashes_to_ul("\n".join(f"- {s}" for s in find_parts))
        concl_txt = html.escape(" ".join(concl_parts))
        concern_txt = ""
    else:
        # Expect strict JSON; if not, fall back to section splitter
        try:
            parts_raw = json.loads(raw)
            if not isinstance(parts_raw, dict):
                raise ValueError("not a JSON object")
            parts: Dict[str, object] = {k: (parts_raw.get(k) or "") for k in ("reason", "technique", "findings", "conclusion", "concern")}
        except Exception:
            logger.exception("Failed to parse JSON from GPT-5 output; attempting salvage of partial JSON")
            salvaged = _salvage_json_like(raw)
            if any(bool(salvaged.get(k)) for k in ("reason", "technique", "findings", "conclusion", "concern")):
                parts = salvaged  # type: ignore[assignment]
            else:
                logger.info("Salvage unsuccessful; falling back to section splitter")
                parts = _split_sections(raw)

        # If Kiswahili required, try an LLM translation pass on the parsed parts first
        if _is_kiswahili(language):
            try:
                translated = _translate_parts_via_llm(parts, language="Kiswahili")
                if translated:
                    parts = translated
            except Exception:
                logger.exception("LLM translation pass failed; will apply local mapping")

        def _as_text(v: object) -> str:
            if isinstance(v, list):
                return " ".join(str(x).strip() for x in v if str(x).strip())
            return str(v or "").strip()

        def _as_bullets_text(v: object) -> str:
            if isinstance(v, list):
                bullets: list[str] = []
                for x in v:
                    s = str(x or "").strip()
                    if not s:
                        continue
                    if not s.startswith("- "):
                        s = "- " + s
                    bullets.append(s)
                return "\n".join(bullets)
            return str(v or "").strip()

        reason_txt = html.escape(_as_text(parts.get("reason")))
        tech_txt = html.escape(_as_text(parts.get("technique")))
        find_ul = _dashes_to_ul(_as_bullets_text(parts.get("findings")))
        concl_txt = html.escape(_as_text(parts.get("conclusion")))
        concern_txt = html.escape(_as_text(parts.get("concern")))

        # Log the lengths of each section for debugging
        logger.info(
            "Parsed section lengths: reason=%d, technique=%d, findings=%d, conclusion=%d, concern=%d",
            len(_strip_html(reason_txt)),
            len(_strip_html(tech_txt)),
            len(_strip_html(find_ul)),
            len(_strip_html(concl_txt)),
            len(_strip_html(concern_txt))
        )

        # If concern looks truncated or missing, attempt a focused completion
        if len(_strip_html(concern_txt)) < 60:
            try:
                system_content = (
                    "You write short, patient-facing next-step advice. "
                    "Use second person. Avoid identifiers. Write ONLY in {language}."
                ).replace("{language}", language or "English")
                
                if _is_kiswahili(language):
                    system_content += (
                        " Andika kwa Kiswahili safi tu; usichanganye na Kiingereza. "
                        "Tumia maneno rahisi ya kila siku."
                    )
                
                developer_content = (
                    "Return ONLY the Note of Concern text: 2–3 short sentences (<= 300 characters total). "
                    "Include urgent referrals, likely procedures, and clear red-flags (go to hospital if ...). "
                    "No markdown. No quotes. No JSON."
                )
                
                if _is_kiswahili(language):
                    developer_content += (
                        " LAZIMA kuwa Kiswahili tu; hakuna Kiingereza kabisa."
                    )
                
                small_messages = [
                    {
                        "role": "system",
                        "content": system_content,
                    },
                    {
                        "role": "developer",
                        "content": developer_content,
                    },
                    {
                        "role": "user",
                        "content": (
                            "Context from report (plain text):\n"
                            f"Reason: {html.unescape(reason_txt)}\n"
                            f"Technique: {html.unescape(tech_txt)}\n"
                            f"Findings bullets: {re.sub(r'<[^>]+>', ' ', find_ul)}\n"
                            f"Conclusion: {html.unescape(concl_txt)}\n"
                            f"Draft concern (may be incomplete): {html.unescape(concern_txt)}\n"
                            "Write the final Note of Concern now."
                        ),
                    },
                ]
                refined = _call_gpt5(small_messages).strip()
                if refined:
                    concern_txt = html.escape(refined)
                else:
                    logger.warning("Concern refinement returned empty; will use generic fallback")
            except Exception:
                logger.exception("Concern refinement call failed; keeping salvaged text")
        
        # If concern is still empty after refinement, provide a generic fallback
        if not _strip_html(concern_txt):
            if _is_kiswahili(language):
                concern_txt = html.escape(
                    "Muone daktari wako haraka kupanga hatua za matibabu. "
                    "Nenda hospitali ikiwa una maumivu makali, homa, au dalili zinazoongezeka."
                )
            else:
                concern_txt = html.escape(
                    "See your doctor urgently to plan next steps for treatment. "
                    "Go to hospital if you have severe pain, fever, or worsening symptoms."
                )

        # If any sections are empty, backfill from raw report sections heuristically
        def _sentences(s: str, n: int = 5) -> List[str]:
            pts = re.split(r"(?<=[.!?])\s+", s or "")
            return [p.strip() for p in pts if p.strip()][:n]

        if not _strip_html(reason_txt):
            simplified_reason = " ".join(_simplify_for_layperson(x) for x in _sentences(secs.get("reason", ""), 2))
            reason_txt = html.escape(_to_kiswahili(simplified_reason) if _is_kiswahili(language) else simplified_reason)
        if not _strip_html(tech_txt):
            simplified_tech = " ".join(_simplify_for_layperson(x) for x in _sentences(secs.get("technique", ""), 2))
            tech_txt = html.escape(_to_kiswahili(simplified_tech) if _is_kiswahili(language) else simplified_tech)
        if not _strip_html(find_ul):
            fb = _sentences(secs.get("findings", ""), 4)
            simplified_findings = [_simplify_for_layperson(s) for s in fb]
            if _is_kiswahili(language):
                simplified_findings = [_to_kiswahili(s) for s in simplified_findings]
            find_ul = _dashes_to_ul("\n".join(f"- {s}" for s in simplified_findings))
        if not _strip_html(concl_txt):
            simplified_concl = " ".join(_simplify_for_layperson(x) for x in _sentences(secs.get("impression", ""), 2))
            concl_txt = html.escape(_to_kiswahili(simplified_concl) if _is_kiswahili(language) else simplified_concl)

        # If Kiswahili requested, enforce Kiswahili on the structured strings.
        if _is_kiswahili(language):
            def _to_sw_html_text(s: str) -> str:
                # s is already html-escaped; unescape -> translate -> escape again
                return html.escape(_to_kiswahili(html.unescape(s)))

            def _to_sw_findings(html_or_text: str) -> str:
                body = html_or_text or ""
                if body.strip().lower().startswith("<ul"):
                    # Translate each <li>...</li> item
                    def repl(m: re.Match) -> str:
                        inner = m.group(1) or ""
                        translated = html.escape(_to_kiswahili(html.unescape(inner)))
                        return f"<li>{translated}</li>"
                    return re.sub(r"<li>(.*?)</li>", repl, body, flags=re.S|re.I)
                # Otherwise treat as dash-text and rebuild UL
                lines = []
                for ln in (body.splitlines()):
                    ln = ln.rstrip()
                    if ln.strip().startswith("- "):
                        content = ln.strip()[2:]
                        lines.append("- " + _to_kiswahili(content))
                return _dashes_to_ul("\n".join(lines) if lines else _to_kiswahili(body))

            reason_txt = _to_sw_html_text(reason_txt)
            tech_txt = _to_sw_html_text(tech_txt)
            find_ul = _to_sw_findings(find_ul)
            concl_txt = _to_sw_html_text(concl_txt)
            if concern_txt:
                concern_txt = _to_sw_html_text(concern_txt)

    # Patient block: omit name/identifiers; keep generic study fields
    patient = {
        "hospital": meta.get("hospital", ""),
        "study": meta.get("study", "Unknown"),
        "name": "",  # ensure PHI is stripped
        "sex": meta.get("sex", ""),
        "age": meta.get("age", ""),
        "date": meta.get("date", ""),
        "history": secs.get("reason", ""),
    }

    out = {
        "patient": patient,
        "reason": reason_txt,
        "technique": tech_txt,
        "findings": find_ul,
        "conclusion": concl_txt,
        "concern": concern_txt,
    }

    # Basic word count for stats (cheap and local)
    blob = " ".join(
        _strip_html(out.get(k, ""))
        for k in ("reason", "technique", "findings", "conclusion", "concern")
    )
    out["word_count"] = len(blob.split())
    out["sentence_count"] = len(re.findall(r"[.!?]+", blob))

    # Log summary lengths for debugging
    logger.info(
        "summary_keys={'reason': %d, 'technique': %d, 'findings': %d, 'conclusion': %d, 'concern': %d}",
        len(_strip_html(reason_txt)),
        len(_strip_html(tech_txt)),
        len(_strip_html(find_ul)),
        len(_strip_html(concl_txt)),
        len(_strip_html(concern_txt))
    )

    return out
