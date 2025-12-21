#!/usr/bin/env python3
"""Test script to verify Template 2 and Template 6 text fitting fixes."""

import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from print_label import (
    create_label_image_template2,
    create_label_image_template6,
    DEFAULT_FONT
)

def test_templates():
    """Generate test labels for Template 2 and Template 6."""

    test_cases = [
        ("BOX 1", "uppercase_short"),
        ("Box 1", "mixed_case_short"),
        ("Storage Box 123", "longer_text"),
    ]

    output_dir = "/tmp/label_tests"
    os.makedirs(output_dir, exist_ok=True)

    for text, label in test_cases:
        print(f"\nTesting: '{text}'")

        # Test Template 2 (QR Above Text)
        try:
            img2 = create_label_image_template2(
                qr_data="https://example.com",
                text=text,
                tape_width_mm=29,
                font_path=DEFAULT_FONT,
                font_size=100,
                include_qr=True
            )

            output_path2 = os.path.join(output_dir, f"template2_{label}.png")
            img2.save(output_path2)
            print(f"  ✓ Template 2: {output_path2} ({img2.size[0]}x{img2.size[1]})")
        except Exception as e:
            print(f"  ✗ Template 2 ERROR: {e}")

        # Test Template 6 (Text Above QR)
        try:
            img6 = create_label_image_template6(
                qr_data="https://example.com",
                text=text,
                tape_width_mm=29,
                font_path=DEFAULT_FONT,
                font_size=100,
                include_qr=True
            )

            output_path6 = os.path.join(output_dir, f"template6_{label}.png")
            img6.save(output_path6)
            print(f"  ✓ Template 6: {output_path6} ({img6.size[0]}x{img6.size[1]})")
        except Exception as e:
            print(f"  ✗ Template 6 ERROR: {e}")

    print(f"\n✓ Test images saved to: {output_dir}")
    print("  You can view these images to verify the text is properly centered and not cut off.")

if __name__ == "__main__":
    test_templates()
