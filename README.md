# Brother QL-700 Label Printer

A basic label printing utility for the Brother QL-700 label printer, optimized for inventory applications. Built with CLI foundation and PyQt6 GUI interface.

**Validated on:** Ubuntu 25.10 with Brother QL-700
**Note:** Not validated with other Brother QL models - use at your own risk with other printers.

## Features

Three printing modes for flexible inventory labeling:

- **QR Code + Text Mode**: Labels with QR codes and text for inventory tracking
- **Text-Only Mode**: Simple centered text labels without QR codes
- **Batch Mode**: Print up to 10 different labels in one session with individual copy counts

Additional features:
- **Label prefixes**: Select from common prefixes (Box, Container, Shelf, Asset) or use none
- Support for multiple tape widths: **29mm, 38mm, 50mm, 62mm**
- **Live preview** before printing
- **Keyboard shortcuts** for faster workflow (Enter to preview, Ctrl+P to print, Ctrl+R to reset)
- **Auto-increment** label numbers (Box 1 → Box 2 → Box 3)
- Customizable fonts and font sizes (40-250pt)
- Persistent settings across sessions
- **Easy Debian packaging** for system-wide installation

## Hardware Requirements

- **Printer**: Brother QL-700 (validated - other models not tested)
- **Tape**: Continuous (endless) tape - DK-22210 (29mm) or similar
- **Connection**: USB (USB ID: 04f9:2042)
- **Tested OS**: Ubuntu 25.10

## Installation

### Option 1: System-Wide Installation (Recommended)

Build and install as a Debian package:

```bash
# Clone the repository
git clone https://github.com/danielrosehill/QL700-Label-Printer-GUI.git
cd QL700-Label-Printer-GUI

# Build and install
./build-and-install.sh
```

This will:
- Build a Debian package
- Install it system-wide
- Add the application to your application menu
- Create a `brother-label-printer-gui` command

### Option 2: Development Mode

Run directly from the repository:

```bash
./run.sh
```

Dependencies are automatically installed when you run the app.

### Updating to a New Version

```bash
# Update version and rebuild
./update-version.sh 1.1.0

# Or just rebuild with current version
./build-and-install.sh
```

The application uses the **Archivo Bold** font (included) for high-quality label printing.

### USB Permissions

Add your user to the `lp` group or create udev rules:

```bash
sudo usermod -a -G lp $USER
```

Or create `/etc/udev/rules.d/99-brother-ql.rules`:
```
SUBSYSTEM=="usb", ATTR{idVendor}=="04f9", ATTR{idProduct}=="2042", MODE="0666"
```

Then reload udev rules:
```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## Usage

### Launch the Application

If installed system-wide:
```bash
brother-label-printer-gui
```

Or from the repository:
```bash
./run.sh
```

Or use your application menu and search for "Brother Label Printer".

### Single Label Mode

1. Select a prefix (optional): Box, Container, Shelf, Asset, or None
2. Enter the URL or text for the QR code
3. Enter the label number (if prefix selected) or full label text
4. Adjust tape width, font size, and copies as needed
5. Click "Generate Preview" (or press Enter)
6. Click "Print Label" (or press Ctrl+P)

**Pro tips:**
- **Prefix feature**: Select "Box" and enter "18" to automatically create "Box 18" labels
- Use the **+1 button** to auto-increment label numbers
- Press **Ctrl+R** to quickly clear the form
- Your prefix selection is saved automatically for next time

### Text-Only Mode

Same as Single Label Mode but without QR codes - perfect for simple inventory labels.

1. Select a prefix (optional): Box, Container, Shelf, Asset, or None
2. Enter the label number (if prefix selected) or full label text
3. Adjust tape width, font size, and copies as needed
4. Click "Generate Preview" to see your label
5. Click "Print Label" to print

### Batch Mode

1. Switch to the "Batch Mode" tab
2. Set shared settings (tape width, font size)
3. Click "Add Label" to add labels to the batch
4. Fill in URL, label text, and copies for each label
5. Click "Preview All Labels" to see all labels
6. Click "Print Batch" to print everything

**Batch features:**
- Up to 10 different labels per batch
- Individual copy count for each label (1-10)
- Copy count defaults to the last value used
- Preview shows all labels stacked vertically

## Label Layout

```
┌────────────────────────────────────────────────┐
│  ┌──────────┐                                  │
│  │ ████████ │                                  │
│  │ ██    ██ │     LARGE LABEL TEXT        📦   │  ← Tape height (29-62mm)
│  │ ████████ │                              │   │
│  └──────────┘                                  │
└────────────────────────────────────────────────┘
      ↑                  ↑                    ↑
   QR Code    100pt Archivo Bold Text    Subtle box
                                         watermark

   ←──────────── Variable length ────────────────→
```

**Design features:**
- QR code on left (70% of tape height)
- Large, bold text in Archivo font (100pt default)
- Small decorative box icon watermark in bottom right
- Subtle light gray border for professional finish

### Keyboard Shortcuts

| Shortcut  | Action                |
|-----------|----------------------|
| Enter     | Generate preview     |
| Ctrl+P    | Print label          |
| Ctrl+R    | Clear/reset form     |

## Tape Width Specifications

| Tape Width | Pixel Height | Model      |
|------------|--------------|------------|
| 29mm       | 306px        | DK-22210   |
| 38mm       | 413px        | DK-22225   |
| 50mm       | 554px        | DK-22223   |
| 62mm       | 696px        | DK-11209   |

## Troubleshooting

### Printer Not Found

Check USB connection:
```bash
lsusb | grep Brother
```

Should show: `Bus XXX Device XXX: ID 04f9:2042 Brother Industries, Ltd`

### Permissions Error

Ensure you're in the `lp` group or have udev rules configured (see Installation).

### GUI Won't Start

Make sure PyQt6 is installed. The launcher script handles this automatically, but if you encounter issues, manually install:
```bash
uv pip install -r requirements.txt
```

## Project Structure

```
brother-ql-label-printer/
├── app/
│   ├── label_printer_gui.py      # GUI application (PyQt6)
│   ├── print_label.py            # Core label generation logic
│   ├── assets/
│   │   └── box.png              # Box icon
│   └── fonts/
│       └── static/
│           └── Archivo-Bold.ttf  # Label font
├── debian/                      # Debian packaging files
│   ├── control                  # Package metadata
│   ├── rules                    # Build rules
│   ├── changelog                # Version history
│   └── compat                   # Debhelper compatibility
├── brother-label-printer-gui    # Wrapper script
├── brother-label-printer.desktop # Desktop entry file
├── build-and-install.sh         # Build and install script
├── update-version.sh            # Version bump script
├── run.sh                       # Development launcher
├── requirements.txt             # Python dependencies
├── CLAUDE.md                    # Technical documentation
└── README.md                    # This file
```

## License

This project is open source. See individual files for licensing details.

## Contributing

Contributions are welcome! Please test thoroughly with actual hardware before submitting changes.
