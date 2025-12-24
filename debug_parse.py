from src.parse import parse_metadata

# Test with actual CT text pattern from user's reports
ct_text = """PROCEDURE DETAILS
CT (special x-ray) of your tummy and pelvis with contrast. Thin slices were taken and shown in different views."""

mri_text = """PROCEDURE DETAILS
MRI scan of your brain."""

print("Testing CT detection:")
ct_result = parse_metadata(ct_text)
print(f"  Study: {ct_result['study']!r}")

print("\nTesting MRI detection:")
mri_result = parse_metadata(mri_text)
print(f"  Study: {mri_result['study']!r}")

# Test the raw regex
import re
print("\n--- Raw regex test ---")
t = ct_text.replace('\u2013', '-').replace('\u2014', '-').replace('\u00a0', ' ')
t = re.sub(r"[ \t]+", " ", t)
t = re.sub(r"\s+\n", "\n", t)
t = t.strip()

proc_match = re.search(
    r"(?im)^(?:PROCEDURE\s+DETAILS?|EXAMINATION|STUDY|EXAM)(?:[:\s]*)\n+([^\n]{10,150})",
    t
)
print(f"Strategy 1 match: {proc_match.group(1) if proc_match else 'NO MATCH'}")
