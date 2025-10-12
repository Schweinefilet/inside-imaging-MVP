import io, re

p = "src/translate.py"
s = io.open(p, "r", encoding="utf-8").read()

# --- Fix Responses API call args
s = re.sub(
    r"client\.responses\.create\((.*?)\)",
    '''client.responses.create(
                model=model_responses,
                instructions=instructions,
                input=[{"role": "user", "content": report_text}],
                reasoning={"effort": "high"},
                max_output_tokens=max_out
            )''',
    s,
    flags=re.S
)

# --- Fix Chat Completions call args
s = re.sub(
    r"client2\.chat\.completions\.create\((.*?)\)",
    '''client2.chat.completions.create(
            model=model_chat,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": report_text}
            ],
            max_tokens=800
        )''',
    s,
    flags=re.S
)

io.open(p, "w", encoding="utf-8", newline="").write(s)
print("PATCHED")
