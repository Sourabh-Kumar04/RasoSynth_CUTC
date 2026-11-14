#!/usr/bin/env python3
"""
Mascot Artifact Cleanup & Edge Refinement Script.
Fixes:
1. Left edge of helmet: removes ragged, torn, speckled white/grey splatter along the face frame.
2. Raised waving hand: cleans grey mottling/smudges on the top edge into a clean, smooth, crisp boundary.
3. Helmet perimeter & low-alpha noise: eliminates dirty semi-transparent halo pixels.
Processes both PNG and WebP mascot assets in frontend/public/mascot/.
"""

import glob
import os
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter


def clean_mascot_frame(img_path: Path):
    im = Image.open(img_path).convert("RGBA")
    arr = np.array(im)
    r = arr[:, :, 0]
    g = arr[:, :, 1]
    b = arr[:, :, 2]
    a = arr[:, :, 3]

    # 1. Clean ultra-low alpha splatter/dust (< 16)
    a = np.where(a < 16, 0, a)

    # 2. Defect 1: Left edge of helmet / splatter above hand
    # For wave-1 / waving poses, clean the ragged bridge at Y: 224-234, X: 102-114
    for y in range(224, 235):
        for x in range(100, 114):
            # If this is the sticking-out smudge above the hand
            if a[y, x] < 140:
                a[y, x] = 0

    # 3. Clean dirty grey fringe along the left edge of the helmet face frame (Y: 140-230, X: 90-155)
    for y in range(140, 230):
        for x in range(90, 155):
            if a[y, x] > 0:
                px_r, px_g, px_b = int(r[y, x]), int(g[y, x]), int(b[y, x])
                # White/grey helmet area (not dark face screen or orange accents)
                if px_r > 150 and px_g > 150 and px_b > 150:
                    # Clean grey smudges to pure porcelain white
                    if px_r < 248 or px_g < 248 or px_b < 248:
                        r[y, x] = min(255, int(px_r * 1.12 + 12))
                        g[y, x] = min(255, int(px_g * 1.12 + 12))
                        b[y, x] = min(255, int(px_b * 1.12 + 12))

    # 4. Defect 2: Raised waving hand top edge grey mottling (Y: 225-265, X: 60-120)
    for y in range(225, 265):
        for x in range(60, 120):
            if a[y, x] > 0:
                px_r, px_g, px_b = int(r[y, x]), int(g[y, x]), int(b[y, x])
                # If on the hand (white), remove blurry grey mottling
                if px_r > 160 and px_g > 160 and px_b > 160:
                    if px_r < 245 or px_g < 245 or px_b < 245:
                        r[y, x] = min(255, int(px_r * 1.15 + 10))
                        g[y, x] = min(255, int(px_g * 1.15 + 10))
                        b[y, x] = min(255, int(px_b * 1.15 + 10))

    # 5. Clean top of helmet perimeter (Y: 45-120, X: 120-350)
    for y in range(45, 120):
        for x in range(120, 350):
            if a[y, x] > 0:
                px_r, px_g, px_b = int(r[y, x]), int(g[y, x]), int(b[y, x])
                if px_r > 180 and px_g > 180 and px_b > 180:
                    if px_r < 248 or px_g < 248 or px_b < 248:
                        r[y, x] = min(255, int(px_r * 1.08 + 8))
                        g[y, x] = min(255, int(px_g * 1.08 + 8))
                        b[y, x] = min(255, int(px_b * 1.08 + 8))

    arr[:, :, 0] = r
    arr[:, :, 1] = g
    arr[:, :, 2] = b
    arr[:, :, 3] = a

    cleaned = Image.fromarray(arr, "RGBA")
    
    # Save back to PNG
    png_path = img_path.with_suffix(".png")
    cleaned.save(png_path, "PNG", optimize=True)

    # Save back to WebP with lossless compression
    webp_path = img_path.with_suffix(".webp")
    cleaned.save(webp_path, "WEBP", lossless=True, quality=100)
    print(f"  ✓ Cleaned: {png_path.name} & {webp_path.name}")


def main():
    mascot_dir = Path("frontend/public/mascot")
    png_files = sorted(mascot_dir.glob("*.png"))
    print(f"Cleaning {len(png_files)} mascot frames...")
    for p in png_files:
        clean_mascot_frame(p)
    print("All mascot frames successfully cleaned.")


if __name__ == "__main__":
    main()
