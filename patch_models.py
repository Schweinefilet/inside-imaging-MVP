import io, re

path = "src/translate.py"
with io.open(path, "r", encoding="utf-8") as f:
    s = f.read()

# Insert model names right after the max_out line
m = re.search(r'max_out\s*=\s*int\(\s*os\.getenv\(\s*"OPENAI_MAX_OUTPUT_TOKENS"\s*,\s*"[0-9]+"\s*\)\s*\)', s)
if not m:
    print("NEEDLE_NOT_FOUND"); raise SystemExit(2)

insert = '\n    model_responses = os.getenv("OPENAI_MODEL", "gpt-5")\n    model_chat = os.getenv("OPENAI_MODEL", "gpt-5")'
s = s[:m.end()] + insert + s[m.end():]

with io.open(path, "w", encoding="utf-8", newline="") as f:
    f.write(s)
print("PATCHED")
