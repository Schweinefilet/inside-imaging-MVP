from openai import OpenAI
import os, json, sys
model = os.getenv("OPENAI_MODEL","o3")
client = OpenAI()
print("probing model =", model)
try:
    r = client.responses.create(
        model=model,
        input=[{"role":"user","content":"ping"}],
        reasoning={"effort":"high"},
        max_output_tokens=32,  # o3 needs >=16
    )
    print("OK:", bool(getattr(r,"output_text","")))
    print("output_text:", getattr(r,"output_text", None))
except Exception as e:
    st = getattr(e, "status", None)
    body = getattr(e, "body", None)
    print("ERROR status:", st)
    print("ERROR body:", json.dumps(body, indent=2) if body else repr(e))
    sys.exit(2)
