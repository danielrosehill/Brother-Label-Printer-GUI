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

# Reference tape width for scaling calculations (29mm is the smallest/base)
REFERENCE_TAPE_WIDTH = 29
REFERENCE_TAPE_PIXELS = TAPE_WIDTHS[REFERENCE_TAPE_WIDTH]


def get_scale_factor(tape_width_mm: int) -> float:
    """
    Calculate scale factor for proportional sizing based on tape width.

    Uses 29mm tape (306px) as the reference. Larger tapes get proportionally
    larger fonts, padding, icons, etc.

    Args:
        tape_width_mm: Tape width in millimeters

    Returns:
        Scale factor (1.0 for 29mm, ~1.35 for 38mm, ~1.81 for 50mm, ~2.27 for 62mm)
    """
    if tape_width_mm not in TAPE_WIDTHS:
        return 1.0
    return TAPE_WIDTHS[tape_width_mm] / REFERENCE_TAPE_PIXELS

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
    Text is automatically scaled to fit within the label height.

    Image dimensions:
    - Width: Variable (becomes label length)
    - Height: Fixed based on tape width (29mm, 38mm, 50mm, or 62mm)

    Args:
        qr_data: Data to encode in QR code (ignored if include_qr=False)
        text: Text to display on label
        tape_width_mm: Tape width in millimeters
        font_path: Path to TrueType font file
        font_size: Font size in points (used as maximum, will be scaled down if needed)
        include_qr: Whether to include QR code (default: True)
    """

    # Get tape width in pixels
    if tape_width_mm not in TAPE_WIDTHS:
        raise ValueError(f"Unsupported tape width: {tape_width_mm}mm. "
                        f"Supported: {list(TAPE_WIDTHS.keys())}")

    label_height_px = TAPE_WIDTHS[tape_width_mm]

    # Calculate scale factor for proportional sizing
    scale = get_scale_factor(tape_width_mm)

    # Scale padding and other fixed sizes proportionally
    padding = int(15 * scale)

    # Decorative box icon scales with tape size
    box_icon_size = int(80 * scale)
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

    # Calculate maximum text height to fit within label
    target_height = label_height_px - (padding * 2)

    # Binary search for optimal font size to fit text height within constraint
    # Scale font sizes proportionally to tape width
    min_font_size = int(20 * scale)
    max_font_size = int(font_size * scale)  # Scale provided font_size by tape width
    optimal_font_size = max_font_size

    while max_font_size - min_font_size > 1:
        test_font_size = (min_font_size + max_font_size) // 2
        font = ImageFont.truetype(font_path, test_font_size)

        # Measure text height using font metrics
        ascent, descent = font.getmetrics()
        text_height_measured = ascent + descent

        if text_height_measured <= target_height:
            min_font_size = test_font_size
            optimal_font_size = test_font_size
        else:
            max_font_size = test_font_size

    # Calculate text dimensions with optimal font size
    font = ImageFont.truetype(font_path, optimal_font_size)
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

    # Add subtle border around the label (scaled)
    border_width = max(2, int(2 * scale))
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
    Optimized for maximum QR code size on thin labels - no decorative elements.
    Text is automatically scaled to fit within available space after QR code.

    Args:
        qr_data: Data to encode in QR code (ignored if include_qr=False)
        text: Text to display on label
        tape_width_mm: Tape width in millimeters
        font_path: Path to TrueType font file
        font_size: Font size in points (used as maximum, will be scaled down if needed)
        include_qr: Whether to include QR code (default: True)
    """
    # Get tape width in pixels
    if tape_width_mm not in TAPE_WIDTHS:
        raise ValueError(f"Unsupported tape width: {tape_width_mm}mm. "
                        f"Supported: {list(TAPE_WIDTHS.keys())}")

    label_height_px = TAPE_WIDTHS[tape_width_mm]

    # Calculate scale factor for proportional sizing
    scale = get_scale_factor(tape_width_mm)

    # Scale padding and gaps proportionally
    padding = int(15 * scale)
    text_gap = int(30 * scale)

    # QR code generation - maximize size for scannability
    qr_img = None
    qr_size = 0
    if include_qr:
        qr_size = int(label_height_px * 0.85)  # Larger QR code for better scanning
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

    # Calculate available space for text (must fit: QR + gap + text within label height)
    if include_qr:
        available_for_text = label_height_px - qr_size - text_gap - (padding * 2)
    else:
        available_for_text = label_height_px - (padding * 2)

    # Binary search for optimal font size to fit text within available space
    # Scale font sizes proportionally to tape width
    min_font_size = int(20 * scale)
    max_font_size = int(font_size * scale)
    optimal_font_size = max_font_size

    while max_font_size - min_font_size > 1:
        test_font_size = (min_font_size + max_font_size) // 2
        font = ImageFont.truetype(font_path, test_font_size)

        # Measure text height using font metrics
        ascent, descent = font.getmetrics()
        text_height_measured = ascent + descent

        if text_height_measured <= available_for_text:
            min_font_size = test_font_size
            optimal_font_size = test_font_size
        else:
            max_font_size = test_font_size

    # Calculate text dimensions with optimal font size
    font = ImageFont.truetype(font_path, optimal_font_size)
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]

    # Use font metrics for accurate vertical spacing
    ascent, descent = font.getmetrics()
    text_height_metrics = ascent + descent

    # Calculate image dimensions for vertical layout
    img_width = max(qr_size if include_qr else 0, text_width) + padding * 2
    img_height = label_height_px

    # Create final image
    img = Image.new("RGB", (img_width, img_height), (255, 255, 255))

    # Calculate vertical centering for the combined QR + text block
    if include_qr and qr_img:
        total_content_height = qr_size + text_gap + text_height_metrics
        start_y = (img_height - total_content_height) // 2

        # Paste QR code (centered horizontally)
        qr_x = (img_width - qr_size) // 2
        img.paste(qr_img, (qr_x, start_y))

        # Draw text below QR code (centered horizontally)
        draw = ImageDraw.Draw(img)
        text_x = (img_width - text_width) // 2

        text_y = start_y + qr_size + text_gap
        draw.text((text_x, text_y), text, font=font, fill="black")
    else:
        # Text-only, centered both ways
        draw = ImageDraw.Draw(img)
        text_x = (img_width - text_width) // 2
        text_y = (img_height - text_height_metrics) // 2
        draw.text((text_x, text_y), text, font=font, fill="black")

    # Add border (scaled)
    border_width = max(2, int(2 * scale))
    border_color = (200, 200, 200)
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        [(border_width//2, border_width//2),
         (img_width - border_width//2 - 1, img_height - border_width//2 - 1)],
        outline=border_color,
        width=border_width
    )

    return img


def create_label_image_template3(qr_data: str, text: str, tape_width_mm: int = 29,
                                  font_path: str = DEFAULT_FONT, font_size: int = 100,
                                  include_qr: bool = True) -> Image.Image:
    """
    Create a label image with rotated text layout (Template 3).

    Layout: QR code on left, text rotated 90° counterclockwise on right
    Text is automatically scaled to fit within the label height.

    Args:
        qr_data: Data to encode in QR code (ignored if include_qr=False)
        text: Text to display on label
        tape_width_mm: Tape width in millimeters
        font_path: Path to TrueType font file
        font_size: Font size in points (used as maximum, will be scaled down if needed)
        include_qr: Whether to include QR code (default: True)
    """
    # Get tape width in pixels
    if tape_width_mm not in TAPE_WIDTHS:
        raise ValueError(f"Unsupported tape width: {tape_width_mm}mm. "
                        f"Supported: {list(TAPE_WIDTHS.keys())}")

    label_height_px = TAPE_WIDTHS[tape_width_mm]

    # Calculate scale factor for proportional sizing
    scale = get_scale_factor(tape_width_mm)

    # Scale padding and other fixed sizes proportionally
    padding = int(15 * scale)
    text_right_padding = int(40 * scale)  # Extra padding on right to prevent cutoff

    # QR code generation - increased to 90% for better scannability
    qr_img = None
    qr_size = 0
    if include_qr:
        qr_size = int(label_height_px * 0.90)
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

    # Calculate maximum text height when rotated
    # After 90° counterclockwise rotation: text WIDTH becomes the vertical HEIGHT
    # So we need to constrain the text width to fit within label height
    target_height = label_height_px - (padding * 2)

    # Binary search for optimal font size to fit text width within height constraint
    # Scale font sizes proportionally to tape width
    min_font_size = int(20 * scale)
    max_font_size = int(font_size * scale)
    optimal_font_size = max_font_size

    while max_font_size - min_font_size > 1:
        test_font_size = (min_font_size + max_font_size) // 2
        font = ImageFont.truetype(font_path, test_font_size)

        dummy = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(dummy)

        # Measure the actual text width (which becomes height after rotation)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width_measured = bbox[2] - bbox[0]

        # After 90° counterclockwise rotation, text width becomes the vertical dimension
        # Check if the rotated text will fit within the label height
        if text_width_measured <= target_height:
            min_font_size = test_font_size
            optimal_font_size = test_font_size
        else:
            max_font_size = test_font_size

    # Create text with optimal font size
    font = ImageFont.truetype(font_path, optimal_font_size)
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Create temporary image for text (will be rotated)
    # Add padding to prevent cutoff during rotation (scaled)
    text_img_padding = int(40 * scale)
    text_img = Image.new("RGB", (text_width + text_img_padding, text_height + text_img_padding), (255, 255, 255))
    text_draw = ImageDraw.Draw(text_img)
    text_draw.text((text_img_padding // 2, text_img_padding // 2), text, font=font, fill="black")

    # Rotate text 90° counterclockwise
    text_img_rotated = text_img.rotate(90, expand=True)

    # Calculate final image dimensions with extra right padding
    if include_qr:
        img_width = qr_size + padding * 2 + text_img_rotated.width + text_right_padding
    else:
        img_width = text_img_rotated.width + padding * 2 + text_right_padding

    img_height = label_height_px

    # Create final image
    img = Image.new("RGB", (img_width, img_height), (255, 255, 255))

    # Paste QR code (if included)
    if include_qr and qr_img:
        qr_y = (img_height - qr_size) // 2
        img.paste(qr_img, (padding, qr_y))

    # Paste rotated text (centered vertically)
    if include_qr:
        text_x = padding + qr_size + padding
    else:
        text_x = padding

    text_y = (img_height - text_img_rotated.height) // 2
    img.paste(text_img_rotated, (text_x, text_y))

    # Add subtle border (scaled)
    border_width = max(2, int(2 * scale))
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
    Text is automatically scaled to fit within the label height.

    Image dimensions:
    - Width: Variable (becomes label length)
    - Height: Fixed based on tape width (29mm, 38mm, 50mm, or 62mm)

    Args:
        text: Text to display on label
        tape_width_mm: Tape width in millimeters
        font_path: Path to TrueType font file
        font_size: Font size in points (used as maximum, will be scaled down if needed)
    """

    # Get tape width in pixels
    if tape_width_mm not in TAPE_WIDTHS:
        raise ValueError(f"Unsupported tape width: {tape_width_mm}mm. "
                        f"Supported: {list(TAPE_WIDTHS.keys())}")

    label_height_px = TAPE_WIDTHS[tape_width_mm]

    # Calculate scale factor for proportional sizing
    scale = get_scale_factor(tape_width_mm)

    # Add generous padding around text (scaled)
    padding_horizontal = int(60 * scale)
    padding_vertical = int(40 * scale)

    # Calculate maximum text height to fit within label
    target_height = label_height_px - (padding_vertical * 2)

    # Binary search for optimal font size to fit text height within constraint
    # Scale font sizes proportionally to tape width
    min_font_size = int(20 * scale)
    max_font_size = int(font_size * scale)
    optimal_font_size = max_font_size

    while max_font_size - min_font_size > 1:
        test_font_size = (min_font_size + max_font_size) // 2
        font = ImageFont.truetype(font_path, test_font_size)

        # Measure text height using font metrics
        ascent, descent = font.getmetrics()
        text_height_measured = ascent + descent

        if text_height_measured <= target_height:
            min_font_size = test_font_size
            optimal_font_size = test_font_size
        else:
            max_font_size = test_font_size

    # Calculate text dimensions with optimal font size
    font = ImageFont.truetype(font_path, optimal_font_size)
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

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

    # Add subtle border around the label (scaled)
    border_width = max(2, int(2 * scale))
    border_color = (200, 200, 200)  # Light gray

    draw.rectangle(
        [(border_width//2, border_width//2),
         (img_width - border_width//2 - 1, img_height - border_width//2 - 1)],
        outline=border_color,
        width=border_width
    )

    return img


def create_vertical_text_label(text: str, tape_width_mm: int = 29,
                               font_path: str = DEFAULT_FONT) -> Image.Image:
    """
    Create a text-only label with vertical text (rotated 90° counterclockwise).
    Text is constrained to one line and scaled to fit vertically.

    Image dimensions:
    - Width: Variable (becomes label length)
    - Height: Fixed based on tape width (29mm, 38mm, 50mm, or 62mm)

    Args:
        text: Text to display on label (one line)
        tape_width_mm: Tape width in millimeters
        font_path: Path to TrueType font file
    """
    # Get tape width in pixels
    if tape_width_mm not in TAPE_WIDTHS:
        raise ValueError(f"Unsupported tape width: {tape_width_mm}mm. "
                        f"Supported: {list(TAPE_WIDTHS.keys())}")

    label_height_px = TAPE_WIDTHS[tape_width_mm]

    # Calculate scale factor for proportional sizing
    scale = get_scale_factor(tape_width_mm)

    # Margins and padding configuration - proportional to tape size
    # Use percentage-based margins to adapt to different tape widths (29mm-62mm)
    # outer_margin_pct: percentage of label height reserved for margins on each side
    outer_margin_pct = 0.05  # 5% margin on each side (10% total)
    outer_margin = max(int(15 * scale), int(label_height_px * outer_margin_pct))

    # Internal padding added to text image before rotation (prevents clipping)
    text_img_padding_pct = 0.03  # ~3% padding
    text_img_padding = max(int(10 * scale), int(label_height_px * text_img_padding_pct))
    border_width = max(2, int(2 * scale))

    # Start with a large font size and scale down to fit
    # The text needs to fit vertically when rotated
    # After rotation, text_width becomes height, so we need:
    # text_width + (text_img_padding * 2) <= label_height_px - (outer_margin * 2)
    # This ensures the rotated text image fits within the label with margins
    target_height = label_height_px - (outer_margin * 2) - (text_img_padding * 2)

    # Binary search for optimal font size (scaled)
    min_font_size = int(20 * scale)
    max_font_size = int(500 * scale)
    optimal_font_size = max_font_size

    while max_font_size - min_font_size > 1:
        test_font_size = (min_font_size + max_font_size) // 2
        font = ImageFont.truetype(font_path, test_font_size)

        # Measure text dimensions
        dummy = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(dummy)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]

        # When rotated 90°, text width becomes the height
        if text_width <= target_height:
            min_font_size = test_font_size
            optimal_font_size = test_font_size
        else:
            max_font_size = test_font_size

    # Create text with optimal font size
    font = ImageFont.truetype(font_path, optimal_font_size)
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Create temporary image for text with internal padding
    text_img = Image.new("RGB", (text_width + text_img_padding * 2,
                                  text_height + text_img_padding * 2), (255, 255, 255))
    text_draw = ImageDraw.Draw(text_img)
    text_draw.text((text_img_padding, text_img_padding), text, font=font, fill="black")

    # Rotate text 90° counterclockwise
    text_img_rotated = text_img.rotate(90, expand=True)

    # Calculate final image dimensions
    # Add outer margin on left/right (which affects label length)
    img_width = text_img_rotated.width + (outer_margin * 2)
    img_height = label_height_px

    # Create final image
    img = Image.new("RGB", (img_width, img_height), (255, 255, 255))

    # Paste rotated text (centered)
    # The rotated image should now fit within label_height with outer_margin clearance
    text_x = (img_width - text_img_rotated.width) // 2
    text_y = (img_height - text_img_rotated.height) // 2
    img.paste(text_img_rotated, (text_x, text_y))

    # Add subtle border
    border_color = (200, 200, 200)
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        [(border_width//2, border_width//2),
         (img_width - border_width//2 - 1, img_height - border_width//2 - 1)],
        outline=border_color,
        width=border_width
    )

    return img


def create_label_image_template6(qr_data: str, text: str, tape_width_mm: int = 29,
                                  font_path: str = DEFAULT_FONT, font_size: int = 100,
                                  include_qr: bool = True) -> Image.Image:
    """
    Create a label image with text above QR code layout (Template 6).

    Layout: Text on top (centered), QR code below text (centered)
    Inverse of Template 2 - optimized for readability with text first.
    Text is automatically scaled to fit within available space after QR code.

    Args:
        qr_data: Data to encode in QR code (ignored if include_qr=False)
        text: Text to display on label
        tape_width_mm: Tape width in millimeters
        font_path: Path to TrueType font file
        font_size: Font size in points (used as maximum, will be scaled down if needed)
        include_qr: Whether to include QR code (default: True)
    """
    # Get tape width in pixels
    if tape_width_mm not in TAPE_WIDTHS:
        raise ValueError(f"Unsupported tape width: {tape_width_mm}mm. "
                        f"Supported: {list(TAPE_WIDTHS.keys())}")

    label_height_px = TAPE_WIDTHS[tape_width_mm]

    # Calculate scale factor for proportional sizing
    scale = get_scale_factor(tape_width_mm)

    # Scale padding and gaps proportionally
    padding = int(15 * scale)
    text_gap = int(30 * scale)

    # QR code generation - maximize size for scannability
    qr_img = None
    qr_size = 0
    if include_qr:
        qr_size = int(label_height_px * 0.85)  # Large QR code for better scanning
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

    # Calculate available space for text (must fit: text + gap + QR within label height)
    if include_qr:
        available_for_text = label_height_px - qr_size - text_gap - (padding * 2)
    else:
        available_for_text = label_height_px - (padding * 2)

    # Binary search for optimal font size to fit text within available space
    # Scale font sizes proportionally to tape width
    min_font_size = int(20 * scale)
    max_font_size = int(font_size * scale)
    optimal_font_size = max_font_size

    while max_font_size - min_font_size > 1:
        test_font_size = (min_font_size + max_font_size) // 2
        font = ImageFont.truetype(font_path, test_font_size)

        # Measure text height using font metrics
        ascent, descent = font.getmetrics()
        text_height_measured = ascent + descent

        if text_height_measured <= available_for_text:
            min_font_size = test_font_size
            optimal_font_size = test_font_size
        else:
            max_font_size = test_font_size

    # Calculate text dimensions with optimal font size
    font = ImageFont.truetype(font_path, optimal_font_size)
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]

    # Use font metrics for accurate vertical spacing
    ascent, descent = font.getmetrics()
    text_height_metrics = ascent + descent

    # Calculate image dimensions for vertical layout
    img_width = max(qr_size if include_qr else 0, text_width) + padding * 2
    img_height = label_height_px

    # Create final image
    img = Image.new("RGB", (img_width, img_height), (255, 255, 255))

    # Calculate vertical centering for the combined text + QR block
    if include_qr and qr_img:
        total_content_height = text_height_metrics + text_gap + qr_size
        start_y = (img_height - total_content_height) // 2

        # Draw text on top (centered horizontally)
        draw = ImageDraw.Draw(img)
        text_x = (img_width - text_width) // 2

        text_y = start_y
        draw.text((text_x, text_y), text, font=font, fill="black")

        # Paste QR code below text (centered horizontally)
        qr_x = (img_width - qr_size) // 2
        qr_y = start_y + text_height_metrics + text_gap
        img.paste(qr_img, (qr_x, qr_y))
    else:
        # Text-only, centered both ways
        draw = ImageDraw.Draw(img)
        text_x = (img_width - text_width) // 2
        text_y = (img_height - text_height_metrics) // 2
        draw.text((text_x, text_y), text, font=font, fill="black")

    # Add border (scaled)
    border_width = max(2, int(2 * scale))
    border_color = (200, 200, 200)
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        [(border_width//2, border_width//2),
         (img_width - border_width//2 - 1, img_height - border_width//2 - 1)],
        outline=border_color,
        width=border_width
    )

    return img


def create_horizontal_centered_label(text: str, tape_width_mm: int = 29,
                                     font_path: str = DEFAULT_FONT) -> Image.Image:
    """
    Create a text-only label with horizontal centered text.
    Text takes up approximately half the vertical space and is centered both ways.

    Image dimensions:
    - Width: Variable (becomes label length)
    - Height: Fixed based on tape width (29mm, 38mm, 50mm, or 62mm)

    Args:
        text: Text to display on label
        tape_width_mm: Tape width in millimeters
        font_path: Path to TrueType font file
    """
    # Get tape width in pixels
    if tape_width_mm not in TAPE_WIDTHS:
        raise ValueError(f"Unsupported tape width: {tape_width_mm}mm. "
                        f"Supported: {list(TAPE_WIDTHS.keys())}")

    label_height_px = TAPE_WIDTHS[tape_width_mm]

    # Calculate scale factor for proportional sizing
    scale = get_scale_factor(tape_width_mm)

    # Scale padding proportionally
    padding = int(40 * scale)

    # Font size should make text take up ~50% of vertical space
    target_text_height = label_height_px * 0.5

    # Binary search for optimal font size (scaled)
    min_font_size = int(20 * scale)
    max_font_size = int(500 * scale)
    optimal_font_size = max_font_size

    while max_font_size - min_font_size > 1:
        test_font_size = (min_font_size + max_font_size) // 2
        font = ImageFont.truetype(font_path, test_font_size)

        # Measure text dimensions
        ascent, descent = font.getmetrics()
        text_height = ascent + descent

        if text_height <= target_text_height:
            min_font_size = test_font_size
            optimal_font_size = test_font_size
        else:
            max_font_size = test_font_size

    # Create final image with optimal font
    font = ImageFont.truetype(font_path, optimal_font_size)
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Calculate image dimensions
    img_width = text_width + (padding * 2)
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

    # Add subtle border around the label (scaled)
    border_width = max(2, int(2 * scale))
    border_color = (200, 200, 200)  # Light gray

    draw.rectangle(
        [(border_width//2, border_width//2),
         (img_width - border_width//2 - 1, img_height - border_width//2 - 1)],
        outline=border_color,
        width=border_width
    )

    return img


def create_shelf_label(label_text: str, number: str, tape_width_mm: int = 29,
                       font_path: str = DEFAULT_FONT) -> Image.Image:
    """
    Create a shelf label with vertical text on left and large number on right (Template 7).

    Layout: [Vertical "SHELF" text] [Large number]
    Example: "SHELF" (vertical) + "2" (horizontal large)

    Image dimensions:
    - Width: Variable (becomes label length)
    - Height: Fixed based on tape width (29mm, 38mm, 50mm, or 62mm)

    Args:
        label_text: Text to display vertically on the left (e.g., "SHELF")
        number: Number to display horizontally on the right (e.g., "2")
        tape_width_mm: Tape width in millimeters
        font_path: Path to TrueType font file
    """
    # Get tape width in pixels
    if tape_width_mm not in TAPE_WIDTHS:
        raise ValueError(f"Unsupported tape width: {tape_width_mm}mm. "
                        f"Supported: {list(TAPE_WIDTHS.keys())}")

    label_height_px = TAPE_WIDTHS[tape_width_mm]

    # Calculate scale factor for proportional sizing
    scale = get_scale_factor(tape_width_mm)

    # Scale padding and gaps proportionally
    padding = int(20 * scale)
    gap = int(30 * scale)  # Gap between vertical text and number

    # Calculate optimal font size for vertical text to fit in tape height
    target_height = label_height_px - (padding * 2)

    # Binary search for vertical text font size (scaled)
    min_font_size = int(30 * scale)
    max_font_size = int(200 * scale)
    vertical_font_size = max_font_size

    while max_font_size - min_font_size > 1:
        test_font_size = (min_font_size + max_font_size) // 2
        font = ImageFont.truetype(font_path, test_font_size)

        dummy = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(dummy)
        bbox = draw.textbbox((0, 0), label_text, font=font)
        text_width = bbox[2] - bbox[0]

        # When rotated 90° clockwise, text width becomes vertical dimension
        if text_width <= target_height:
            min_font_size = test_font_size
            vertical_font_size = test_font_size
        else:
            max_font_size = test_font_size

    # Create vertical text (rotated 90° clockwise)
    vertical_font = ImageFont.truetype(font_path, vertical_font_size)
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), label_text, font=vertical_font)
    vert_text_width = bbox[2] - bbox[0]
    vert_text_height = bbox[3] - bbox[1]

    # Create temporary image for vertical text with extra padding (scaled)
    text_img_padding = int(40 * scale)
    vert_text_img = Image.new("RGB", (vert_text_width + text_img_padding, vert_text_height + text_img_padding), (255, 255, 255))
    vert_draw = ImageDraw.Draw(vert_text_img)
    vert_draw.text((text_img_padding // 2, text_img_padding // 2), label_text, font=vertical_font, fill="black")

    # Rotate text 90° clockwise (use -90 for clockwise rotation)
    vert_text_rotated = vert_text_img.rotate(-90, expand=True)

    # Calculate optimal font size for number to fill most of remaining space
    # Number should be large and prominent
    number_target_height = label_height_px * 0.7

    min_font_size = int(80 * scale)
    max_font_size = int(500 * scale)
    number_font_size = max_font_size

    while max_font_size - min_font_size > 1:
        test_font_size = (min_font_size + max_font_size) // 2
        font = ImageFont.truetype(font_path, test_font_size)

        ascent, descent = font.getmetrics()
        text_height = ascent + descent

        if text_height <= number_target_height:
            min_font_size = test_font_size
            number_font_size = test_font_size
        else:
            max_font_size = test_font_size

    # Create number text
    number_font = ImageFont.truetype(font_path, number_font_size)
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), number, font=number_font)
    number_width = bbox[2] - bbox[0]
    number_height = bbox[3] - bbox[1]

    # Calculate final image dimensions
    img_width = vert_text_rotated.width + gap + number_width + (padding * 2)
    img_height = label_height_px

    # Create final image
    img = Image.new("RGB", (img_width, img_height), (255, 255, 255))

    # Paste vertical text on left (centered vertically)
    vert_x = padding
    vert_y = (img_height - vert_text_rotated.height) // 2
    img.paste(vert_text_rotated, (vert_x, vert_y))

    # Draw number on right (centered vertically)
    draw = ImageDraw.Draw(img)
    number_x = padding + vert_text_rotated.width + gap

    ascent, descent = number_font.getmetrics()
    number_y = (img_height - (ascent + descent)) // 2 + (descent // 2)

    draw.text((number_x, number_y), number, font=number_font, fill="black")

    # Add subtle border (scaled)
    border_width = max(2, int(2 * scale))
    border_color = (200, 200, 200)
    draw.rectangle(
        [(border_width//2, border_width//2),
         (img_width - border_width//2 - 1, img_height - border_width//2 - 1)],
        outline=border_color,
        width=border_width
    )

    return img


def create_storage_qr_label(qr_data: str, storage_type: str, number: str,
                            tape_width_mm: int = 62,
                            font_path: str = DEFAULT_FONT,
                            include_qr: bool = True) -> Image.Image:
    """
    Create a storage label with QR code, storage type below QR, and large number (Template 8).

    Layout: [QR Code on left with storage type text below] [Large number on right]
    Example: QR + "BOX" below it + large "2" on the right
    Optimized for larger label sizes (50mm, 62mm).

    Image dimensions:
    - Width: Variable (becomes label length)
    - Height: Fixed based on tape width (29mm, 38mm, 50mm, or 62mm)

    Args:
        qr_data: Data to encode in QR code (ignored if include_qr=False)
        storage_type: Text to display below QR code (e.g., "BOX", "SHELF", "BIN")
        number: Number to display on the right (e.g., "1", "2", "10")
        tape_width_mm: Tape width in millimeters (default: 62 for larger labels)
        font_path: Path to TrueType font file
        include_qr: Whether to include QR code (default: True)
    """
    # Get tape width in pixels
    if tape_width_mm not in TAPE_WIDTHS:
        raise ValueError(f"Unsupported tape width: {tape_width_mm}mm. "
                        f"Supported: {list(TAPE_WIDTHS.keys())}")

    label_height_px = TAPE_WIDTHS[tape_width_mm]

    # Calculate scale factor for proportional sizing
    scale = get_scale_factor(tape_width_mm)

    # Scale padding and gaps proportionally
    padding = int(20 * scale)
    gap = int(40 * scale)  # Gap between left section and number

    # QR code generation - sized to leave room for text below
    qr_img = None
    qr_size = 0
    if include_qr:
        # QR takes up ~65% of height to leave room for text below
        qr_size = int(label_height_px * 0.65)
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

    # Calculate storage type text size
    # Text should fit below QR code and be reasonably sized
    available_for_text = label_height_px - qr_size - padding * 2 if include_qr else label_height_px * 0.3
    target_text_height = min(available_for_text * 0.8, label_height_px * 0.2)

    # Binary search for storage type font size (scaled)
    min_font_size = int(20 * scale)
    max_font_size = int(150 * scale)
    storage_font_size = max_font_size

    while max_font_size - min_font_size > 1:
        test_font_size = (min_font_size + max_font_size) // 2
        font = ImageFont.truetype(font_path, test_font_size)

        ascent, descent = font.getmetrics()
        text_height = ascent + descent

        if text_height <= target_text_height:
            min_font_size = test_font_size
            storage_font_size = test_font_size
        else:
            max_font_size = test_font_size

    # Create storage type text
    storage_font = ImageFont.truetype(font_path, storage_font_size)
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), storage_type, font=storage_font)
    storage_text_width = bbox[2] - bbox[0]
    storage_ascent, storage_descent = storage_font.getmetrics()
    storage_text_height = storage_ascent + storage_descent

    # Calculate left section width (max of QR and storage text)
    left_section_width = max(qr_size if include_qr else 0, storage_text_width)

    # Calculate optimal font size for number - should be large and prominent
    # Number takes up ~75% of vertical space
    number_target_height = label_height_px * 0.75

    min_font_size = int(100 * scale)
    max_font_size = int(600 * scale)
    number_font_size = max_font_size

    while max_font_size - min_font_size > 1:
        test_font_size = (min_font_size + max_font_size) // 2
        font = ImageFont.truetype(font_path, test_font_size)

        ascent, descent = font.getmetrics()
        text_height = ascent + descent

        if text_height <= number_target_height:
            min_font_size = test_font_size
            number_font_size = test_font_size
        else:
            max_font_size = test_font_size

    # Create number text
    number_font = ImageFont.truetype(font_path, number_font_size)
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), number, font=number_font)
    number_width = bbox[2] - bbox[0]

    # Calculate final image dimensions
    img_width = padding + left_section_width + gap + number_width + padding
    img_height = label_height_px

    # Create final image
    img = Image.new("RGB", (img_width, img_height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Calculate vertical layout for left section (QR + text stacked)
    if include_qr and qr_img:
        total_left_height = qr_size + storage_text_height
        left_start_y = (img_height - total_left_height) // 2

        # Paste QR code (centered horizontally within left section)
        qr_x = padding + (left_section_width - qr_size) // 2
        img.paste(qr_img, (qr_x, left_start_y))

        # Draw storage type text below QR (centered within left section)
        storage_x = padding + (left_section_width - storage_text_width) // 2
        storage_y = left_start_y + qr_size
        draw.text((storage_x, storage_y), storage_type, font=storage_font, fill="black")
    else:
        # No QR - just center the storage type text in left section
        storage_x = padding + (left_section_width - storage_text_width) // 2
        storage_y = (img_height - storage_text_height) // 2
        draw.text((storage_x, storage_y), storage_type, font=storage_font, fill="black")

    # Draw large number on right (centered vertically)
    number_x = padding + left_section_width + gap

    number_ascent, number_descent = number_font.getmetrics()
    number_y = (img_height - (number_ascent + number_descent)) // 2 + (number_descent // 2)

    draw.text((number_x, number_y), number, font=number_font, fill="black")

    # Add subtle border (scaled)
    border_width = max(2, int(2 * scale))
    border_color = (200, 200, 200)
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
