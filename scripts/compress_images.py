#!/usr/bin/env python3
"""
Compress and resize marquee images to web-friendly sizes
Target: max width/height of 720px, quality 85%, under 500KB

Run from the project root:
    python scripts/compress_images.py

Rewrites the JPEGs in static/images/marquee/ in place.
"""
import os
from pathlib import Path

from PIL import Image

MARQUEE_DIR = Path(__file__).resolve().parent.parent / "static" / "images" / "marquee"
MAX_SIZE = 720  # Max width or height in pixels
QUALITY = 85    # JPEG quality (1-100)

def compress_image(filepath):
    """Compress and resize a single image"""
    try:
        # Skip placeholder text files
        if os.path.getsize(filepath) < 1000:  # Less than 1KB = text file
            print(f"⏭️  Skipping {os.path.basename(filepath)} (text placeholder)")
            return
        
        with Image.open(filepath) as img:
            # Get original size
            original_size = os.path.getsize(filepath)
            original_dims = img.size
            
            # Convert RGBA to RGB if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            # Resize if larger than MAX_SIZE
            if max(img.size) > MAX_SIZE:
                img.thumbnail((MAX_SIZE, MAX_SIZE), Image.Resampling.LANCZOS)
            
            # Save with compression
            img.save(filepath, 'JPEG', quality=QUALITY, optimize=True)
            
            new_size = os.path.getsize(filepath)
            reduction = ((original_size - new_size) / original_size) * 100
            
            print(f"✅ {os.path.basename(filepath)}")
            print(f"   {original_dims} → {img.size}")
            print(f"   {original_size/1024/1024:.2f}MB → {new_size/1024:.0f}KB ({reduction:.1f}% reduction)")
            
    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")

def main():
    print("🖼️  Compressing marquee images...")
    print(f"Target: max {MAX_SIZE}px, quality {QUALITY}%\n")
    
    # Process all JPG files
    for filename in sorted(os.listdir(MARQUEE_DIR)):
        if filename.endswith('.jpg'):
            filepath = os.path.join(MARQUEE_DIR, filename)
            compress_image(filepath)
    
    print("\n✨ Done!")

if __name__ == "__main__":
    main()
