#!/usr/bin/env python3
"""
Quick test for the new shelf label template
"""
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from print_label import create_shelf_label

# Test the shelf label function
if __name__ == "__main__":
    # Create a test shelf label matching the SHELF.png design
    img = create_shelf_label(
        label_text="SHELF",
        number="2",
        tape_width_mm=29
    )

    # Save preview
    output_path = "test_shelf_label_preview.png"
    img.save(output_path)
    print(f"✓ Shelf label created: {output_path}")
    print(f"  Dimensions: {img.size[0]}x{img.size[1]} pixels")

    # Test with different numbers
    for i in range(1, 6):
        img = create_shelf_label(
            label_text="SHELF",
            number=str(i),
            tape_width_mm=29
        )
        output_path = f"test_shelf_{i}.png"
        img.save(output_path)
        print(f"✓ Created: {output_path}")

    print("\nAll test labels created successfully!")
    print("You can now use Template 7 (Shelf Label) in the GUI for bulk creation.")
