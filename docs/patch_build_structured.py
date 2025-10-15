import io, re

p = "src/translate.py"
s = io.open(p,"r",encoding="utf-8").read()

# Replace the whole build_structured() with a 3-arg version.
pat = r"\ndef\s+build_structured\([^)]*\):[\s\S]*?\n(?=\n(def |class )|$)"
new = r"""
def build_structured(report_text: str,
                     glossary: "Glossary"|None = None,
                     language: str = "English") -> Dict[str, str]:
    """
    Summarize a report for lay readers. Tries LLM first; falls back to simple formatting.
    """
    res = _summarize_with_openai(report_text, language)
    if not res:
        # very simple fallback; leave real rewriting to LLM
        res = {
            "reason": "",
            "technique": "",
            "findings": (report_text or "").strip(),
            "conclusion": "",
            "concern": "",
        }
    for k in ("reason","technique","findings","conclusion","concern"):
        res.setdefault(k, "")
        if not isinstance(res[k], str):
            res[k] = str(res[k] or "")
    return res
"""

s = re.sub(pat, "\n"+new+"\n", s, flags=re.S)

io.open(p,"w",encoding="utf-8",newline="").write(s)
print("PATCHED build_structured")
