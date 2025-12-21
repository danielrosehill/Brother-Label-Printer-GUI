#!/usr/bin/env python3
"""
Print labels with QR code and text on Brother QL-700.

For continuous (endless) tape:
- Image WIDTH must match tape width in pixels
- Image HEIGHT is variable (becomes label length)

Layout: [Box Icon] [QR Code] [Text Label]
"""

import argparse
import os
import sys
from contextlib import contextmanager
from PIL import Image, ImageDraw, ImageFont
import qrcode
from brother_ql.raster import BrotherQLRaster
from brother_ql.conversion import convert
from brother_ql.backends.helpers import send


@contextmanager
def suppress_stderr():
    """Temporarily suppress stderr output"""
    original_stderr = sys.stderr
    sys.stderr = open(os.devnull, 'w')
    try:
        yield
    finally:
        sys.stderr.close()
        sys.stderr = original_stderr

# Tape width specifications (at 300 DPI)
TAPE_WIDTHS = {
    29: 306,   # 29mm = 306 pixels
    38: 413,   # 38mm = 413 pixels
    50: 554,   # 50mm = 554 pixels
    62: 696,   # 62mm = 696 pixels
}

PRINTER_MODEL = "QL-700"
DEFAULT_PRINTER = "usb://0x04f9:0x2042"
DEFAULT_BACKEND = "pyusb"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FONT = os.path.join(SCRIPT_DIR, "fonts", "static", "Archivo-Bold.ttf")
BOX_ICON_PATH = os.path.join(SCRIPT_DIR, "assets", "box.png")


def create_label_image(qr_data: str, text: str, tape_width_mm: int = 29,
                       font_path: str = DEFAULT_FONT, font_size: int = 100,
                       include_qr: bool = True) -> Image.Image:
    """
    Create a label image with optional QR code, large text, and small decorative box icon.

    Layout (with QR): [QR Code] [Large Text Label] (small box icon in bottom right)
    Layout (text-only): [Large Text Label] (small box icon in bottom right)

    Image dimensions:
    - Width: Variable (becomes label length)
    - Height: Fixed based on tape width (29mm, 38mm, 50mm, or 62mm)

    Args:
        qr_data: Data to encode in QR code (ignored if include_qr=False)
        text: Text to display on label
        tape_width_mm: Tape width in millimeters
        font_path: Path to TrueType font file
        font_size: Font size in points
        include_qr: Whether to include QR code (default: True)
    """

    # Get tape width in pixels
    if tape_width_mm not in TAPE_WIDTHS:
        raise ValueError(f"Unsupported tape width: {tape_width_mm}mm. "
                        f"Supported: {list(TAPE_WIDTHS.keys())}")

    label_height_px = TAPE_WIDTHS[tape_width_mm]
    padding = 15

    # Small decorative box icon (fixed size, not tape-dependent)
    box_icon_size = 80
    box_img = Image.open(BOX_ICON_PATH).convert("RGBA")
    box_img = box_img.resize((box_icon_size, box_icon_size), Image.Resampling.LANCZOS)

    # Make box icon semi-transparent watermark
    alpha = box_img.split()[3] if len(box_img.split()) == 4 else Image.new('L', box_img.size, 255)
    alpha = alpha.point(lambda p: int(p * 0.3))  # 30% opacity
    box_img.putalpha(alpha)

    # QR code generation (only if requested)
    qr_img = None
    qr_size = 0
    if include_qr:
        # QR code - scale to fill most of tape height with safe margins (85%)
        qr_size = int(label_height_px * 0.85)
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,  # Medium ECC - good balance for small labels
            box_size=10,
            border=4,  # Standard quiet zone (4 modules) for reliable scanning
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        # Use NEAREST resampling to keep QR modules sharp and crisp
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.NEAREST)

    # Calculate text dimensions with large font
    font = ImageFont.truetype(font_path, font_size)
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Calculate total image width with generous spacing
    text_padding = padding * 3  # More space around text for professional look

    if include_qr:
        # Layout: [padding] [QR] [padding*3] [text] [padding*3] [box icon] [padding]
        img_width = qr_size + text_width + box_icon_size + padding * 2 + text_padding * 2
    else:
        # Layout: [padding*2] [text] [padding*3] [box icon] [padding]
        # For text-only, add extra padding on left and center the text
        img_width = text_width + box_icon_size + padding * 3 + text_padding

    img_height = label_height_px

    # Create final image with white background
    img = Image.new("RGBA", (img_width, img_height), (255, 255, 255, 255))

    # Paste QR code (only if included)
    if include_qr and qr_img:
        qr_y = (img_height - qr_size) // 2
        img.paste(qr_img, (padding, qr_y))

    # Draw large text (vertically centered)
    draw = ImageDraw.Draw(img)

    if include_qr:
        # After QR code with generous spacing
        text_x = padding + qr_size + text_padding
    else:
        # Centered with extra left padding for text-only mode
        text_x = padding * 2

    # Use font metrics for precise vertical centering
    # Get the ascent and descent to properly center the baseline
    ascent, descent = font.getmetrics()
    text_y = (img_height - (ascent + descent)) // 2 + (descent // 2)

    draw.text((text_x, text_y), text, font=font, fill="black")

    # Paste small box icon in bottom right corner as subtle watermark
    box_x = img_width - box_icon_size - padding
    box_y = img_height - box_icon_size - padding
    img.paste(box_img, (box_x, box_y), box_img)

    # Add subtle border around the label
    border_width = 2
    border_color = (200, 200, 200)  # Light gray

    # Draw border rectangle
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        [(border_width//2, border_width//2),
         (img_width - border_width//2 - 1, img_height - border_width//2 - 1)],
        outline=border_color,
        width=border_width
    )

    # Convert back to RGB for printing
    img = img.convert("RGB")

    return img


def create_label_image_template2(qr_data: str, text: str, tape_width_mm: int = 29,
                                  font_path: str = DEFAULT_FONT, font_size: int = 100,
                                  include_qr: bool = True) -> Image.Image:
    """
    Create a label image with compact vertical layout (Template 2).

    Layout: QR code on top (centered), text below QR code (centered)

    Args:
        qr_data: Data to encode in QR code (ignored if include_qr=False)
        text: Text to display on label
        tape_width_mm: Tape width in millimeters
        font_path: Path to TrueType font file
        font_size: Font size in points
        include_qr: Whether to include QR code (default: True)
    """
    # Get tape width in pixels
    if tape_width_mm not in TAPE_WIDTHS:
        raise ValueError(f"Unsupported tape width: {tape_width_mm}mm. "
                        f"Supported: {list(TAPE_WIDTHS.keys())}")

    label_height_px = TAPE_WIDTHS[tape_width_mm]
    padding = 15

    # Small decorative box icon
    box_icon_size = 80
    box_img = Image.open(BOX_ICON_PATH).convert("RGBA")
    box_img = box_img.resize((box_icon_size, box_icon_size), Image.Resampling.LANCZOS)

    # Make box icon semi-transparent
    alpha = box_img.split()[3] if len(box_img.split()) == 4 else Image.new('L', box_img.size, 255)
    alpha = alpha.point(lambda p: int(p * 0.3))
    box_img.putalpha(alpha)

    # QR code generation
    qr_img = None
    qr_size = 0
    if include_qr:
        qr_size = int(label_height_px * 0.7)  # Slightly smaller for compact layout
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.NEAREST)

    # Calculate text dimensions
    font = ImageFont.truetype(font_path, font_size)
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Calculate image dimensions for vertical layout
    img_width = max(qr_size if include_qr else 0, text_width) + padding * 2

    if include_qr:
        # QR + gap + text + padding
        img_height = label_height_px
    else:
        # Just text centered
        img_height = label_height_px

    # Ensure width accommodates the box icon
    img_width = max(img_width, box_icon_size + padding * 2)

    # Create final image
    img = Image.new("RGBA", (img_width, img_height), (255, 255, 255, 255))

    # Calculate vertical centering for the combined QR + text block
    if include_qr and qr_img:
        text_gap = padding * 2
        total_content_height = qr_size + text_gap + text_height
        start_y = (img_height - total_content_height) // 2

        # Paste QR code (centered horizontally)
        qr_x = (img_width - qr_size) // 2
        img.paste(qr_img, (qr_x, start_y))

        # Draw text below QR code (centered horizontally)
        draw = ImageDraw.Draw(img)
        text_x = (img_width - text_width) // 2

        ascent, descent = font.getmetrics()
        text_y = start_y + qr_size + text_gap
        draw.text((text_x, text_y), text, font=font, fill="black")
    else:
        # Text-only, centered both ways
        draw = ImageDraw.Draw(img)
        text_x = (img_width - text_width) // 2
        ascent, descent = font.getmetrics()
        text_y = (img_height - (ascent + descent)) // 2 + (descent // 2)
        draw.text((text_x, text_y), text, font=font, fill="black")

    # Paste box icon in bottom right corner
    box_x = img_width - box_icon_size - padding
    box_y = img_height - box_icon_size - padding
    img.paste(box_img, (box_x, box_y), box_img)

    # Add border
    border_width = 2
    border_color = (200, 200, 200)
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        [(border_width//2, border_width//2),
         (img_width - border_width//2 - 1, img_height - border_width//2 - 1)],
        outline=border_color,
        width=border_width
    )

    img = img.convert("RGB")
    return img


def create_label_image_template3(qr_data: str, text: str, tape_width_mm: int = 29,
                                  font_path: str = DEFAULT_FONT, font_size: int = 100,
                                  include_qr: bool = True) -> Image.Image:
    """
    Create a label image with rotated text layout (Template 3).

    Layout: QR code on left, text rotated 90° counterclockwise on right

    Args:
        qr_data: Data to encode in QR code (ignored if include_qr=False)
        text: Text to display on label
        tape_width_mm: Tape width in millimeters
        font_path: Path to TrueType font file
        font_size: Font size in points
        include_qr: Whether to include QR code (default: True)
    """
    # Get tape width in pixels
    if tape_width_mm not in TAPE_WIDTHS:
        raise ValueError(f"Unsupported tape width: {tape_width_mm}mm. "
                        f"Supported: {list(TAPE_WIDTHS.keys())}")

    label_height_px = TAPE_WIDTHS[tape_width_mm]
    padding = 15

    # QR code generation
    qr_img = None
    qr_size = 0
    if include_qr:
        qr_size = int(label_height_px * 0.85)
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.NEAREST)

    # Calculate text dimensions (will be rotated)
    font = ImageFont.truetype(font_path, font_size)
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Create temporary image for text (will be rotated)
    text_img = Image.new("RGB", (text_width + 20, text_height + 20), (255, 255, 255))
    text_draw = ImageDraw.Draw(text_img)
    text_draw.text((10, 10), text, font=font, fill="black")

    # Rotate text 90° counterclockwise
    text_img_rotated = text_img.rotate(90, expand=True)

    # Calculate final image dimensions
    # Width = QR + padding + rotated text width + padding
    if include_qr:
        img_width = qr_size + padding * 2 + text_img_rotated.width
    else:
        img_width = text_img_rotated.width + padding * 2

    img_height = label_height_px

    # Create final image
    img = Image.new("RGB", (img_width, img_height), (255, 255, 255))

    # Paste QR code (if included)
    if include_qr and qr_img:
        qr_y = (img_height - qr_size) // 2
        img.paste(qr_img, (padding, qr_y))

    # Paste rotated text
    if include_qr:
        text_x = padding + qr_size + padding
    else:
        text_x = padding

    text_y = (img_height - text_img_rotated.height) // 2
    img.paste(text_img_rotated, (text_x, text_y))

    # Add subtle border
    border_width = 2
    border_color = (200, 200, 200)
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        [(border_width//2, border_width//2),
         (img_width - border_width//2 - 1, img_height - border_width//2 - 1)],
        outline=border_color,
        width=border_width
    )

    return img


def create_text_only_label(text: str, tape_width_mm: int = 29,
                           font_path: str = DEFAULT_FONT, font_size: int = 100) -> Image.Image:
    """
    Create a text-only label with text centered both horizontally and vertically.

    Image dimensions:
    - Width: Variable (becomes label length)
    - Height: Fixed based on tape width (29mm, 38mm, 50mm, or 62mm)

    Args:
        text: Text to display on label
        tape_width_mm: Tape width in millimeters
        font_path: Path to TrueType font file
        font_size: Font size in points
    """

    # Get tape width in pixels
    if tape_width_mm not in TAPE_WIDTHS:
        raise ValueError(f"Unsupported tape width: {tape_width_mm}mm. "
                        f"Supported: {list(TAPE_WIDTHS.keys())}")

    label_height_px = TAPE_WIDTHS[tape_width_mm]

    # Calculate text dimensions
    font = ImageFont.truetype(font_path, font_size)
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Add generous padding around text
    padding_horizontal = 60
    padding_vertical = 40

    # Calculate image dimensions
    img_width = text_width + (padding_horizontal * 2)
    img_height = label_height_px

    # Create image with white background
    img = Image.new("RGB", (img_width, img_height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Center text both horizontally and vertically
    text_x = (img_width - text_width) // 2

    # Use font metrics for precise vertical centering
    ascent, descent = font.getmetrics()
    text_y = (img_height - (ascent + descent)) // 2 + (descent // 2)

    draw.text((text_x, text_y), text, font=font, fill="black")

    # Add subtle border around the label
    border_width = 2
    border_color = (200, 200, 200)  # Light gray

    draw.rectangle(
        [(border_width//2, border_width//2),
         (img_width - border_width//2 - 1, img_height - border_width//2 - 1)],
        outline=border_color,
        width=border_width
    )

    return img


def print_label(image: Image.Image, tape_width_mm: int = 29,
                printer: str = DEFAULT_PRINTER, backend: str = DEFAULT_BACKEND,
                rotate: int = 90):
    """Send the label image to the printer."""

    # Save to temp file
    temp_path = "/tmp/brother_label.png"
    image.save(temp_path)

    # Create raster instructions
    qlr = BrotherQLRaster(PRINTER_MODEL)

    instructions = convert(
        qlr=qlr,
        images=[temp_path],
        label=str(tape_width_mm),  # Use tape width as label parameter
        rotate=rotate,
        threshold=70,
        dither=False,
        compress=False,
        red=False,
        cut=True,
    )

    # Send to printer (suppress stderr to hide "operating mode" warning)
    with suppress_stderr():
        send(
            instructions=instructions,
            printer_identifier=printer,
            backend_identifier=backend,
            blocking=True
        )


def main():
    parser = argparse.ArgumentParser(
        description="Print labels with box icon, QR code, and text on Brother QL-700",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "https://example.com/item/1" "Box 1"
  %(prog)s "https://inventory.local/box/5" "Box 5" --tape-width 38
  %(prog)s "https://example.com" "Label" --font-size 72 --preview
  %(prog)s "data" "Custom Label" --font /path/to/font.ttf --tape-width 50
        """
    )
    parser.add_argument("url", help="URL to encode in QR code")
    parser.add_argument("label", help="Text label to display")
    parser.add_argument("--tape-width", type=int, default=29,
                        choices=list(TAPE_WIDTHS.keys()),
                        help="Tape width in mm (default: 29)")
    parser.add_argument("--font", default=DEFAULT_FONT,
                        help=f"Path to TrueType font file (default: {DEFAULT_FONT})")
    parser.add_argument("--font-size", type=int, default=60,
                        help="Font size for text (default: 60)")
    parser.add_argument("--preview", action="store_true",
                        help="Save preview image instead of printing")
    parser.add_argument("--preview-path", default="/tmp/label_preview.png",
                        help="Path for preview image (default: /tmp/label_preview.png)")
    parser.add_argument("--printer", default=DEFAULT_PRINTER,
                        help=f"Printer URI (default: {DEFAULT_PRINTER})")
    parser.add_argument("--backend", default=DEFAULT_BACKEND,
                        choices=["pyusb", "linux_kernel", "network"],
                        help=f"Backend (default: {DEFAULT_BACKEND})")
    parser.add_argument("--rotate", type=int, default=90, choices=[0, 90, 180, 270],
                        help="Image rotation in degrees (default: 90)")

    args = parser.parse_args()

    # Verify font file exists
    if not os.path.isfile(args.font):
        print(f"Error: Font file not found: {args.font}")
        return 1

    # Create the label image
    img = create_label_image(
        qr_data=args.url,
        text=args.label,
        tape_width_mm=args.tape_width,
        font_path=args.font,
        font_size=args.font_size
    )

    if args.preview:
        img.save(args.preview_path)
        print(f"Preview saved: {args.preview_path}")
        print(f"Image size: {img.size[0]} x {img.size[1]} pixels")
        print(f"Tape width: {args.tape_width}mm ({TAPE_WIDTHS[args.tape_width]}px)")
    else:
        print(f"Printing label on {args.tape_width}mm tape:")
        print(f"  URL: {args.url}")
        print(f"  Label: {args.label}")
        print_label(img, args.tape_width, args.printer, args.backend, args.rotate)
        print("Done.")

    return 0


if __name__ == "__main__":
    exit(main())
