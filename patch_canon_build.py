import io, re

p = "src/translate.py"
s = io.open(p, "r", encoding="utf-8").read()

# Replace ALL build_structured definitions with a single, correct one.
pat = r"\ndef\s+build_structured\([^)]*\):[\s\S]*?\n(?=\n(def |class )|$)"
canon = r"""
def build_structured(report_text: str,
                     glossary: "Glossary"|None = None,
                     language: str = "English") -> Dict[str, str]:
    """
    Summarize a report for lay readers. Uses LLM first; simple fallback otherwise.
    """
    res = _summarize_with_openai(report_text, language)
    if not res:
        # very simple fallback: just structure the raw text
        res = {
            "reason": "",
            "technique": "",
            "findings": (report_text or "").strip(),
            "conclusion": "",
            "concern": "",
        }
    # normalize keys to strings
    for k in ("reason","technique","findings","conclusion","concern"):
        v = res.get(k, "")
        res[k] = v if isinstance(v, str) else str(v or "")
    return res
"""

s_new = re.sub(pat, "\n"+canon+"\n", s, flags=re.S)

io.open(p, "w", encoding="utf-8", newline="").write(s_new)
print("PATCHED: canonical build_structured")
