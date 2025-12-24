import re
from src.parse import parse_metadata

# Test cases
test_cases = [
    # Case 1: Procedure Details with description on next line
    """PROCEDURE DETAILS
CT (special x-ray) of your tummy and pelvis with contrast. Thin slices were taken and shown in different views.""",
    
    # Case 2: X-ray case
    """PROCEDURE DETAILS
X-ray (plain film) of your foot with thin views to see the bones and joints clearly.""",
    
    # Case 3: Header with content on same line
    """EXAMINATION: CT Chest with contrast""",
    
    # Case 4: Just modality at start
    """CT scan (special x-ray) of your chest was done with thin slices."""
]

for i, text in enumerate(test_cases, 1):
    result = parse_metadata(text)
    print(f"Test {i}: {result['study']!r}")
