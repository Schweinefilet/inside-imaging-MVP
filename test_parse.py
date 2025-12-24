import re

text = """PROCEDURE DETAILS
CT (special x-ray) of your tummy and pelvis with contrast. Thin slices were taken and shown in different views."""

# Test pattern 1b
m = re.search(r"(?im)^(?:EXAMINATION|STUDY|PROCEDURE|EXAM)(?:\s+DETAILS)?[:\s]*\n+([^\n]{3,60})", text)
if m:
    candidate = m.group(1).strip()
    print(f"Match found: {candidate!r}")
    print(f"Is all caps? {re.match(r'^[A-Z\s]+$', candidate)}")
    print(f"Should accept? {not re.match(r'^[A-Z\s]+$', candidate) and len(candidate) > 2}")
else:
    print("No match")
