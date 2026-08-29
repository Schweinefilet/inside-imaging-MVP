#!/usr/bin/env python3
"""
Update organ-highlight.js with new Radiopaedia image URLs from the CSV
"""
import json
import re

# Load the URL mapping (normalized version)
with open('url_mapping_normalized.json', 'r') as f:
    url_mapping = json.load(f)

# Read the current organ-highlight.js
with open('static/organ-highlight.js', 'r') as f:
    content = f.read()

# Track updates
updates = 0
skipped = 0

# For each condition in our mapping, find and replace its imageUrl
for condition, new_url in url_mapping.items():
    # Escape special regex characters in condition name
    cond_escaped = re.escape(condition)
    
    # Pattern to find the condition's imageUrl line (using single quotes in JS)
    # Matches: imageUrl: 'any_url_here',
    pattern = r"('" + cond_escaped + r"':\s*\{[^}]*imageUrl:\s*')[^']*(')"
    
    # Try to replace
    matches = re.findall(pattern, content)
    if matches:
        content = re.sub(pattern, r'\1' + new_url + r'\2', content, count=1)
        updates += 1
    else:
        skipped += 1
        print(f"⚠️  Could not find: {condition}")

# Write the updated file
with open('static/organ-highlight.js', 'w') as f:
    f.write(content)

print(f"\n✅ Updated {updates} image URLs")
print(f"⚠️  Skipped {skipped} conditions (not found in JS)")
print(f"📝 Updated static/organ-highlight.js")
