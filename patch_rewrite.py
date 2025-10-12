import sys, re, io

path = "src/translate.py"
with io.open(path, "r", encoding="utf-8") as f:
    s = f.read()

start = s.find("def _summarize_with_openai(")
if start < 0:
    print("ERROR: function not found"); sys.exit(1)

# find the end of the function: next blank-line-then-def/class or EOF
m_def = re.search(r"\n\n(def |class )", s[start+1:])
end = (start+1 + m_def.start()) if m_def else len(s)

func = r"""
def _summarize_with_openai(report_text: str, language: str) -> Dict[str, str] | None:
    \"\"\"Summarize using OpenAI; enforce min think time and highlight phrases.\"\"\"
    import time
    instructions = (
        "You are a medical report summarizer for the public. "
        f"Write all output in {language}. "
        "Return ONLY a JSON object with keys: reason, technique, findings, conclusion, concern. "
        "Use clear, simple language and short sentences. No treatment advice. "
        "Highlight important phrases by wrapping them in **double asterisks** in findings and conclusion."
    )

    min_think = _min_think_seconds()
    max_out   = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "2048"))

    # ---- Try Responses API (v1) ----
    client = _responses_api_client()
    if client is not None:
        try:
            t_start = time.perf_counter()
            logger.info("[LLM] Responses.create model=%s", model_responses)
            resp = client.responses.create(
                model=model_responses,
                instructions=instructions,
                input=[{"role": "user", "content": report_text}],
                reasoning={"effort": "high"},
                max_output_tokens=max_out,
                temperature=0.2,
            )
            elapsed = time.perf_counter() - t_start
            if elapsed < min_think:
                time.sleep(min_think - elapsed)
            print(f"[LLM] think time {elapsed:.2f}s; enforced >= {min_think:.2f}s")
            logger.info("[LLM] Responses finished in %.2fs; enforced >= %.2fs", elapsed, min_think)

            # Try to extract text robustly across SDK variants
            text = getattr(resp, "output_text", None)
            if not text:
                try:
                    text = resp.output[0].content[0].text
                except Exception:
                    text = str(resp)
            data = _parse_json_loose(text) or {}
            for k in ("reason","technique","findings","conclusion","concern"):
                data.setdefault(k, "")
            return {
                "reason": data["reason"].strip(),
                "technique": data["technique"].strip(),
                "findings": data["findings"].strip(),
                "conclusion": data["conclusion"].strip(),
                "concern": data["concern"].strip(),
            }
        except Exception:
            logger.exception("[LLM] Responses API failed")

    # ---- Fallback: Chat Completions (v1) ----
    try:
        from openai import OpenAI
        t_start = time.perf_counter()
        logger.info("[LLM] Chat Completions.create model=%s", model_chat)
        client2 = OpenAI(timeout=_env_float("OPENAI_TIMEOUT", 60.0))
        resp = client2.chat.completions.create(
            model=model_chat,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": report_text},
            ],
            temperature=0.2,
            max_tokens=800,
        )
        elapsed = time.perf_counter() - t_start
        if elapsed < min_think:
            time.sleep(min_think - elapsed)
        print(f"[LLM] think time {elapsed:.2f}s; enforced >= {min_think:.2f}s")
        logger.info("[LLM] ChatCompletion finished in %.2fs; enforced >= %.2fs", elapsed, min_think)

        content = resp.choices[0].message.content
        data = _parse_json_loose(content) or {}
        for k in ("reason","technique","findings","conclusion","concern"):
            data.setdefault(k, "")
        return {
            "reason": data["reason"].strip(),
            "technique": data["technique"].strip(),
            "findings": data["findings"].strip(),
            "conclusion": data["conclusion"].strip(),
            "concern": data["concern"].strip(),
        }
    except Exception:
        logger.exception("[LLM] ChatCompletion failed")

    return None
"""

new = s[:start] + func + s[end:]
with io.open(path, "w", encoding="utf-8", newline="") as f:
    f.write(new)
print("PATCHED")
