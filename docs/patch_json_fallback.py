import io, json, re
p = "src/translate.py"
s = io.open(p,"r",encoding="utf-8").read()

if "_extract_json_loose" not in s:
    s = s.replace(
        "def _summarize_with_openai",
        r"""
def _extract_json_loose(text: str):
    if not text: return None
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r'(\{.*\})', text, flags=re.S)
    if m:
        try: return json.loads(m.group(1))
        except Exception: pass
    return None

def _summarize_with_openai"""
    )

s = s.replace("_parse_json_loose(", "_extract_json_loose(")

io.open(p,"w",encoding="utf-8",newline="").write(s)
print("PATCHED_JSON_FALLBACK")
