from __future__ import annotations

import asyncio
import datetime
import hashlib
import io
import os
import re
import time
import traceback
from pathlib import Path
from typing import Optional

import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fpdf import FPDF
from openai import OpenAI
from PIL import Image
from pillow_heif import register_heif_opener
from pydantic import BaseModel

# ----- Boot-time setup -----

load_dotenv()
register_heif_opener()

app = FastAPI(title="Inside Imaging API")

ALLOWED_ORIGINS = [
    "https://schweinefilet.github.io",  # GitHub Pages host
    "http://localhost:5173",            # Vite dev
]
extra = os.getenv("FRONTEND_ORIGIN")
if extra:
    ALLOWED_ORIGINS.append(extra)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

# Lazy OpenAI client (avoid boot failure if key missing)
def get_openai_client() -> OpenAI:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=key)

# Lazy EasyOCR reader (CPU)
_reader = None
def get_reader():
    global _reader
    if _reader is None:
        import easyocr  # defer heavy import
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader

def now() -> float:
    return time.perf_counter()

# ----- PDF helper -----

class PDF(FPDF):
    def footer(self):
        self.set_y(-10)
        self.set_font("DejaVu", size=8)
        self.cell(0, 5, "Inside Imaging", align="C")

FONT_PATH = Path(__file__).parent / "fonts" / "DejaVuSans.ttf"

# ----- API models -----

class PDFRequest(BaseModel):
    ref_no: Optional[str] = None
    name: Optional[str] = None
    date: Optional[str] = None
    simplified_text: str

# ----- Routes -----

@app.post("/upload/")
async def upload_file(files: list[UploadFile] = File(...)):
    t0 = now()
    read_time = 0.0
    ocr_time = 0.0
    all_lines: list[str] = []
    sensitive = {
        "ref_no": None,
        "name": None,
        "date": None,
        "age": None,
        "sex": None,
    }

    reader = get_reader()

    for file in files:
        if not file.content_type.startswith("image/"):
            return JSONResponse({"error": f"Unsupported file type: {file.filename}"}, status_code=400)

        # Load image
        t_a = now()
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        np_image = np.array(image)
        t_b = now()
        read_time += (t_b - t_a)

        # OCR
        t_c = now()
        detections = reader.readtext(np_image, paragraph=False, detail=0)
        t_d = now()
        ocr_time += (t_d - t_c)

        lines = "\n".join(detections).splitlines()
        for i, line in enumerate(lines):
            low = line.lower().strip()

            # Ref No
            if sensitive["ref_no"] is None and "ref" in low and "no" in low:
                sensitive["ref_no"] = line.strip()
                continue

            # Name (same line or next line)
            if sensitive["name"] is None and "name" in low and not low.startswith("dr"):
                if re.fullmatch(r"name\s*[:\-]?\s*", low):
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        sensitive["name"] = f"Name: {next_line}"
                    continue
                else:
                    sensitive["name"] = line.strip()
                    continue

            # Date
            if sensitive["date"] is None and "date" in low:
                sensitive["date"] = line.strip()
                continue

            # Age
            if sensitive["age"] is None:
                age_match = re.search(r"\bage\s*[:\-]?\s*(\d{1,3})\b", line, re.IGNORECASE)
                if age_match and age_match.group(1).isdigit():
                    sensitive["age"] = age_match.group(1)
                    all_lines.append(line.strip())
                    continue

            # Sex
            if sensitive["sex"] is None and "sex" in low:
                valid_sex = None
                if re.match(r"^sex\s*[:\-]?\s*$", low) and i + 1 < len(lines):
                    next_word = lines[i + 1].strip().split()[0]
                    if next_word.lower() in ["f", "m", "female", "male"]:
                        valid_sex = next_word.upper()
                        all_lines.append(f"Sex: {next_word}")
                else:
                    m = re.search(r"sex\s*[:\-]?\s*([A-Za-z]+)", line, re.IGNORECASE)
                    if m:
                        sex_val = m.group(1).lower()
                        if sex_val in ["f", "m", "female", "male"]:
                            valid_sex = sex_val.upper()
                            all_lines.append(line.strip())
                if valid_sex:
                    sensitive["sex"] = valid_sex
                continue

            if "dr" in low or "signature" in low:
                continue

            all_lines.append(line.strip())

    # Validations
    if sensitive["age"] is None:
        t_end = now()
        print(f"[TIMING] read={read_time:.2f}s ocr={ocr_time:.2f}s total={t_end - t0:.2f}s (age missing)")
        return JSONResponse({"error": "Missing or invalid age, retake photo"}, status_code=400)

    if sensitive["sex"] is None:
        t_end = now()
        print(f"[TIMING] read={read_time:.2f}s ocr={ocr_time:.2f}s total={t_end - t0:.2f}s (sex missing)")
        return JSONResponse({"error": "Missing or invalid sex, retake photo"}, status_code=400)

    final_text = "\n".join(all_lines)
    t_llm0 = now()

    # LLM call
    prompt = """
You are “II Radiographer,” a bilingual medical communicator who rewrites radiology reports for an average Kenyan reader with little medical background.
For every report (PDF text or plain text) produce two simplified summaries—one in clear, everyday English and one in equally simple Kiswahili—using the exact template and rules below. Follow them word-for-word unless the user explicitly overrides a rule.

1 TEMPLATE  (use this order and CAPITALISATION)

[EXAM TYPE] – PLAIN-LANGUAGE REPORT (KENYA)
Age: <## yrs>  Sex: <M/F> 

WHY WAS THIS SCAN DONE?
<One or two short sentences—why the doctor ordered the exam, in lay words.>

HOW WAS THE SCAN DONE?
<One sentence on scanner type + contrast use; keep jargon out.>

IMPORTANT FINDINGS
    • <Bullet 1>
    • <Bullet 2>
    • <Bullet 3>

CONCLUSION

QUESTIONS TO DISCUSS WITH YOUR DOCTOR
    • <Bullet A>
    • <Bullet B>
    • <Danger-sign sentence>

RIPOTI YA [EXAM] – KISWAHILI RAHISI
Mgonjwa:  Umri: <##>  Jinsia: <M/W>  Tarehe: 

KWANINI KIPIMO KILIFANYWA?
<Sentensi 1–2.>

KIPIMO KILIFANYWAJE?
<Sentensi fupi.>

MATOKEO MUHIMU
    • <Kipengele 1>
    • <Kipengele 2>
    • <Kipengele 3>

HITIMISHO
<Sentensi 1.>

MASWALI YA KUJADILI NA DAKTARI WAKO
    • <Kipengele A>
    • <Kipengele B>
    • <Dalili hatari>

2 STYLE RULES
No tables; plain text only. Keep bullets ≤ 30 words. Avoid em dashes. Begin English section with "English:" and Kiswahili with "Kiswahili:". End with "Confidence = <0–1>".

4 OUTPUT ONLY THE TWO FINAL REPORTS + CONFIDENCE—NOTHING ELSE.
""".strip()

    try:
        client = get_openai_client()
        #
        # Use the GPT‑5 reasoning model with high effort to force more
        # deliberate thought from the language model.  According to
        # Microsoft’s documentation on the Azure OpenAI reasoning models
        # the `reasoning_effort` parameter can be set to
        # ``minimal``, ``low``, ``medium`` or ``high`` and higher values
        # cause the model to spend more time planning its answer【142767710599151†L57-L67】.
        # The site’s translate module already enforces a minimum wall‑clock
        # think time of 30 seconds for calls to the Responses API.  We
        # replicate that behaviour here by timing the call and, if
        # necessary, sleeping so that the overall thinking time is at
        # least 30 seconds.  This helps ensure that the GPT‑5 model
        # produces a thoughtful, high‑quality summary instead of a rushed
        # response.

        start_llm = now()
        response = client.responses.create(
            model="gpt-5-mini",
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": final_text},
            ],
            # Request the model spend more time reasoning about the input.
            reasoning={"effort": "high"},
            text={"verbosity": "medium"},
        )
        # Enforce a minimum think time of 30 seconds.  If the API call
        # returns sooner, pause before continuing so that the user
        # benefits from GPT‑5’s deeper reasoning.  See translate.py for
        # similar logic.
        elapsed_llm = now() - start_llm
        MIN_THINK = 30.0
        if elapsed_llm < MIN_THINK:
            time.sleep(MIN_THINK - elapsed_llm)
        simplified = response.output_text.strip()
        usage = getattr(response, "usage", None)
        if usage:
            print(
                f"[USAGE] input={getattr(usage, 'input_tokens', None)} "
                f"output={getattr(usage, 'output_tokens', None)} "
                f"total={getattr(usage, 'total_tokens', None)}"
            )
        print(f"[SIZE] in_chars={len(final_text)} out_chars={len(simplified)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI failure: {e}")

    t_llm1 = now()
    t_end = now()
    print(
        f"[TIMING] read={read_time:.2f}s "
        f"ocr={ocr_time:.2f}s "
        f"llm={t_llm1 - t_llm0:.2f}s "
        f"total={t_end - t0:.2f}s"
    )

    return JSONResponse({
        "filtered_text": final_text,
        "info": sensitive,
        "simplified_text": simplified
    })

@app.post("/make-pdf")
async def make_pdf(payload: PDFRequest):
    pdf = PDF()
    pdf.add_page()
    pdf.add_font("DejaVu", "", str(FONT_PATH), uni=True)
    pdf.set_font("DejaVu", size=14)

    if payload.name:
        pdf.cell(0, 8, f"{payload.name}", ln=True)
    if payload.ref_no:
        pdf.cell(0, 8, f"{payload.ref_no}", ln=True)
    if payload.date:
        pdf.cell(0, 8, f"{payload.date}", ln=True)
    pdf.ln(4)

    pdf.set_font("DejaVu", size=12)
    for line in payload.simplified_text.split("\n"):
        pdf.multi_cell(0, 6, line)

    pdf_bytes = pdf.output(dest="S").encode("latin-1")
    buf = io.BytesIO(pdf_bytes)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="Inside-Imaging-Report.pdf"'}
    )
