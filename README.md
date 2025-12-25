# Brother QL Label Printer for Inventory Management

A desktop label printing application for Brother QL-700 label printers, designed specifically for **inventory management** workflows. Print professional labels for boxes, shelves, containers, and assets with QR codes for tracking.

Built with PyQt6 for a native desktop experience on Linux.

**Tested on:** Ubuntu 25.10 with Brother QL-700
**Note:** Not validated with other Brother QL models - use at your own risk with other printers.

---

## Why This Tool?

Managing inventory - whether for home storage, small business, or warehouse operations - requires consistent, scannable labels. This tool provides:

- **Quick label generation** with common prefixes (Box, Shelf, Container, Asset)
- **QR codes** that link to your inventory database or tracking URLs
- **Batch printing** for labeling multiple items efficiently
- **Consistent formatting** across all your inventory labels
- **Persistent settings** so you can pick up where you left off

---

## Features

### Printing Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **QR + Text** | Labels with scannable QR code and large text | Track items with URL/database links |
| **Text Only** | Simple centered text labels | Shelf labels, category markers |
| **Batch Mode** | Print up to 10 different labels at once | Initial inventory setup |
| **Batch Range** | Auto-generate numbered sequences | "Box 1" through "Box 50" |

### Label Templates (8 styles)

1. **Horizontal QR + Text** - QR left, text right (default)
2. **QR Above Text** - Vertical layout, QR on top
3. **Rotated Layout** - Text rotated for vertical reading
4. **Text Only Centered** - No QR, text fills label
5. **Text Rotated 90° CCW** - Vertical text orientation
6. **Text Above QR** - Inverse of template 2
7. **Shelf Label** - Optimized for shelf edge labels
8. **Storage QR Label** - Storage type + numbered identifier

### Additional Features

- **Printer Selection** - Choose from multiple connected Brother QL printers
- **Label Prefixes** - Box, Container, Shelf, Asset, or custom text
- **Multiple Tape Widths** - 29mm, 38mm, 50mm, 62mm support
- **Live Preview** - See your label before printing
- **Auto-increment** - Box 1 → Box 2 → Box 3 with one click
- **Keyboard Shortcuts** - Enter (preview), Ctrl+P (print), Ctrl+R (reset)
- **Customizable Fonts** - 40-250pt, any TrueType font
- **Persistent Settings** - Printer, tape width, font, and prefix selections saved

---

## Screenshots

### Main Interface (QR + Text Mode)
![Main Interface](screenshots/main-interface.png)
*Create labels with QR codes and text. Select a prefix, enter URL and label details.*

### Label Preview
![Label Preview](screenshots/label-preview.png)
*Preview before printing - "BOX 1" label with QR code and box icon watermark.*

### Batch Mode
![Batch Mode](screenshots/batch-mode.png)
*Print up to 10 different labels in one session with individual copy counts.*

### Template Gallery
![About Tab](screenshots/about-tab.png)
*Browse all 8 label templates and tape specifications.*

---

## Hardware Requirements

| Component | Requirement |
|-----------|-------------|
| **Printer** | Brother QL-700 (validated) |
| **Tape** | Continuous (endless) tape - DK-22210 (29mm) or similar |
| **Connection** | USB (USB ID: 04f9:2042) |
| **OS** | Ubuntu/Debian Linux (tested on Ubuntu 25.10) |

### Supported Tape Widths

| Width | Pixels (300 DPI) | Brother Model |
|-------|------------------|---------------|
| 29mm  | 306px | DK-22210 |
| 38mm  | 413px | DK-22225 |
| 50mm  | 554px | DK-22223 |
| 62mm  | 696px | DK-11209 |

---

## Installation

### Option 1: System-Wide Installation (Recommended)

```bash
# Clone the repository
git clone https://github.com/danielrosehill/brother-ql-label-printer.git
cd brother-ql-label-printer

# Build and install as Debian package
./build-and-install.sh
```

This creates a system-wide installation with:
- Application in your desktop menu
- `brother-label-printer-gui` command
- Automatic dependency handling

### Option 2: Development Mode

```bash
# Clone and run directly
git clone https://github.com/danielrosehill/brother-ql-label-printer.git
cd brother-ql-label-printer
./run.sh
```

### USB Permissions

Add your user to the `lp` group:

```bash
sudo usermod -a -G lp $USER
# Log out and back in for changes to take effect
```

Or create udev rules at `/etc/udev/rules.d/99-brother-ql.rules`:

```
SUBSYSTEM=="usb", ATTR{idVendor}=="04f9", ATTR{idProduct}=="2042", MODE="0666"
```

Then reload:
```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

---

## Usage

### Launch

```bash
# If installed system-wide
brother-label-printer-gui

# Or from repository
./run.sh
```

Or find "Brother Label Printer" in your application menu.

### Quick Start: Print Your First Label

1. **Select prefix**: Choose "Box" from the dropdown
2. **Enter URL**: Your inventory tracking URL (or any URL)
3. **Enter number**: "1" (will create "Box 1" label)
4. **Preview**: Press Enter or click "Generate Preview"
5. **Print**: Press Ctrl+P or click "Print Label"

### Workflow Tips

- **Auto-increment**: After printing "Box 1", click +1 to jump to "Box 2"
- **Batch setup**: Use Batch Mode to create multiple different labels at once
- **Range printing**: Use Batch Range for sequences like "Shelf 1" through "Shelf 20"
- **Text-only labels**: Switch to Text Only tab for simple category labels

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Enter | Generate preview |
| Ctrl+P | Print label |
| Ctrl+R | Clear/reset form |
| Ctrl+Up | Increment label number |
| Ctrl+, | Open settings |

### Settings

Access via **Settings → Printer Settings** or **Ctrl+,**:

- **Printer**: Select from connected Brother QL printers
- **Paper Size**: 29mm, 38mm, 50mm, or 62mm tape
- **Font Size**: 40-250 points
- **Font**: Browse to select any TrueType font

---

## Label Layout

```
┌────────────────────────────────────────────────┐
│  ┌──────────┐                                  │
│  │ ████████ │                                  │
│  │ ██    ██ │     LARGE LABEL TEXT        📦   │  ← Tape height (29-62mm)
│  │ ████████ │                                  │
│  └──────────┘                                  │
└────────────────────────────────────────────────┘
      ↑                  ↑                    ↑
   QR Code    Archivo Bold Text (100pt)   Box icon
   (85% height)                           watermark

   ←──────────── Variable length ────────────────→
```

---

## Project Structure

```
brother-ql-label-printer/
├── app/
│   ├── label_printer_gui.py    # Main GUI application
│   ├── print_label.py          # Label generation & printing
│   ├── assets/box.png          # Watermark icon
│   └── fonts/                  # Archivo Bold font
├── debian/                     # Debian packaging
├── screenshots/                # Documentation images
├── template-previews/          # Template examples
├── build-and-install.sh        # Build script
├── run.sh                      # Development launcher
└── requirements.txt            # Python dependencies
```

---

## Troubleshooting

### Printer Not Found

```bash
# Check USB connection
lsusb | grep Brother
# Should show: ID 04f9:2042 Brother Industries, Ltd
```

If not detected:
1. Check USB cable connection
2. Ensure printer is powered on
3. Try a different USB port

### Permission Denied

Ensure USB permissions are configured (see Installation section).

### Multiple Printers

If you have multiple Brother QL printers:
1. Open Settings (Ctrl+,)
2. Click "Refresh" to scan for printers
3. Select the desired printer from the dropdown

---

## Dependencies

- **Python 3.10+**
- **PyQt6** - GUI framework
- **brother_ql** - Printer communication
- **Pillow** - Image generation
- **qrcode** - QR code generation

All dependencies are automatically installed during setup.

---

## License

This project is open source. See individual files for licensing details.

## Contributing

Contributions welcome! Please test with actual hardware before submitting changes.

---

## Acknowledgments

- Uses the [Archivo](https://fonts.google.com/specimen/Archivo) font family
- Built on the [brother_ql](https://github.com/pklaus/brother_ql) library
