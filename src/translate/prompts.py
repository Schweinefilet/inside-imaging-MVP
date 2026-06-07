"""Prompt composition for the OpenAI Responses API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.translate.kiswahili import _is_kiswahili


# Reference style used by the prompt
REFERENCE_STYLE = (
    "You convert radiology reports into a kind, patient-facing summary. "
    "Use second person (you/your). Be confident and plain. Avoid hedging. "
    "Short to medium sentences (8–22 words) with everyday words. Define medical terms in brackets. "
    "Keep numbers; add simple size comparisons when helpful. Use direct verbs: shows, spreads into, blocks, likely spread."
)


def _compose_prompt(
    meta: Dict[str, str],
    secs: Dict[str, str],
    language: str,
    few_shot_examples: Optional[List[Dict[str, Any]]] = None,
) -> List[dict]:
    """Build a Responses API input payload requesting strict JSON with required keys."""
    study = (meta.get("study") or "").strip()
    hospital = (meta.get("hospital") or "").strip()
    if hospital:
        hospital = "a hospital"  # keep institution name generic

    system = (
        "You convert radiology reports into a kind, patient-facing summary. "
        "Write ALL output ONLY in {language}. Do not include any personal identifiers."
    ).replace("{language}", language or "English")

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

    if few_shot_examples:
        block = (
            "\n\nRADIOLOGIST-CORRECTED EXAMPLES\n"
            "A radiologist reviewed previous AI outputs and made these corrections. "
            "Use them to calibrate tone, terminology, and accuracy — do not copy them verbatim.\n"
        )
        for i, ex in enumerate(few_shot_examples, 1):
            block += f"\nExample {i}:"
            if ex.get("ai_output"):
                block += f"\n  AI output:              {ex['ai_output'][:400]}"
            block += f"\n  Radiologist correction: {ex['corrected_text'][:400]}\n"
        developer += block

    if _is_kiswahili(language):
        developer += (
            "\n\nSTRICT KISWAHILI RULES\n"
            "- Andika kila neno kwa Kiswahili fasaha; usichanganye na Kiingereza.\n"
            "- Badili istilahi za kitabibu kuwa Kiswahili (mfano: mass  uvimbe; lesion  eneo lisilo la kawaida;\n"
            "  consolidation  muungano wa tishu za pafu; effusion  majimaji kwenye ganda la mapafu;\n"
            "  enhancement  kuonekana zaidi baada ya dawa ya rangi).\n"
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

    return [
        {"role": "system", "content": system},
        {"role": "developer", "content": developer},
        {"role": "user", "content": user},
    ]
