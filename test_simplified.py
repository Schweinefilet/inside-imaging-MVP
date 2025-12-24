from src.parse import parse_metadata

test_cases = [
    "Multiplanar multisequential MRI scans of the lumbar spine were obtained.",
    "CT (special x-ray) of your tummy and pelvis with contrast. Thin slices were taken.",
    "X-ray (plain film) of your foot with thin views to see the bones clearly.",
    "MRI scan of your brain.",
    "CT Chest with contrast"
]

print("Testing simplified study names:\n")
for test in test_cases:
    result = parse_metadata(f"PROCEDURE DETAILS\n{test}")
    print(f"Original: {test[:60]}...")
    print(f"Simplified: {result['study']!r}\n")
