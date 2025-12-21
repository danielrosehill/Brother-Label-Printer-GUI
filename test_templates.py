#!/usr/bin/env python3
"""
Test script to verify all three template layouts work correctly
"""

from app.print_label import (
    create_label_image,
    create_label_image_template2,
    create_label_image_template3,
    create_text_only_label
)

# Test parameters
test_url = "https://example.com/box/1"
test_text = "BOX 1"
tape_width = 29

print("Testing Template 1 (Horizontal)...")
try:
    img1 = create_label_image(
        qr_data=test_url,
        text=test_text,
        tape_width_mm=tape_width
    )
    img1.save("/tmp/template1_test.png")
    print(f"✓ Template 1 generated: {img1.size[0]}x{img1.size[1]}px")
    print(f"  Saved to: /tmp/template1_test.png")
except Exception as e:
    print(f"✗ Template 1 failed: {e}")

print("\nTesting Template 2 (Compact/Vertical)...")
try:
    img2 = create_label_image_template2(
        qr_data=test_url,
        text=test_text,
        tape_width_mm=tape_width
    )
    img2.save("/tmp/template2_test.png")
    print(f"✓ Template 2 generated: {img2.size[0]}x{img2.size[1]}px")
    print(f"  Saved to: /tmp/template2_test.png")
except Exception as e:
    print(f"✗ Template 2 failed: {e}")

print("\nTesting Template 3 (Rotated Text)...")
try:
    img3 = create_label_image_template3(
        qr_data=test_url,
        text=test_text,
        tape_width_mm=tape_width
    )
    img3.save("/tmp/template3_test.png")
    print(f"✓ Template 3 generated: {img3.size[0]}x{img3.size[1]}px")
    print(f"  Saved to: /tmp/template3_test.png")
except Exception as e:
    print(f"✗ Template 3 failed: {e}")

print("\nTesting Template 4 (Text Only)...")
try:
    img4 = create_text_only_label(
        text=test_text,
        tape_width_mm=tape_width
    )
    img4.save("/tmp/template4_test.png")
    print(f"✓ Template 4 generated: {img4.size[0]}x{img4.size[1]}px")
    print(f"  Saved to: /tmp/template4_test.png")
except Exception as e:
    print(f"✗ Template 4 failed: {e}")

print("\n" + "="*50)
print("Test complete! Check the files in /tmp/")
print("="*50)
