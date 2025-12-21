#!/usr/bin/env python3
"""
GUI for Brother QL-700 Label Printer
Prints labels with box icon, QR code, and text
"""

import sys
import os
import json
from pathlib import Path
from contextlib import contextmanager
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QSpinBox, QGroupBox,
    QFileDialog, QMessageBox, QScrollArea, QToolButton, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QPixmap, QFont, QAction, QKeySequence, QIcon
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

# Import constants from print_label.py
from print_label import (
    TAPE_WIDTHS, PRINTER_MODEL, DEFAULT_PRINTER, DEFAULT_BACKEND,
    DEFAULT_FONT, BOX_ICON_PATH, create_label_image, create_text_only_label,
    create_label_image_template2, create_label_image_template3
)


class LabelPrinterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("BrotherQL", "LabelPrinter")
        self.preview_image = None
        self.text_only_preview_image = None
        self.recent_items = []
        self.batch_labels = []
        self.last_copies = 1  # Track last used copies for batch mode
        self.current_copies = 1  # Track current copies selection
        self.init_ui()
        self.load_settings()
        self.setup_shortcuts()

    def init_ui(self):
        self.setWindowTitle("Brother Label Printer")
        self.setMinimumWidth(900)
        self.setMinimumHeight(700)

        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Create QR + Text tab
        qr_text_tab = QWidget()
        self.init_single_tab(qr_text_tab)
        self.tab_widget.addTab(qr_text_tab, "QR + Text")

        # Create batch mode tab
        batch_tab = QWidget()
        self.init_batch_tab(batch_tab)
        self.tab_widget.addTab(batch_tab, "Batch Mode")

        # Create text only tab
        text_only_tab = QWidget()
        self.init_text_only_tab(text_only_tab)
        self.tab_widget.addTab(text_only_tab, "Text Only")

        # Create template preview tab
        template_preview_tab = QWidget()
        self.init_template_preview_tab(template_preview_tab)
        self.tab_widget.addTab(template_preview_tab, "Templates")

        # Create about tab
        about_tab = QWidget()
        self.init_about_tab(about_tab)
        self.tab_widget.addTab(about_tab, "About")

        # Status bar
        self.statusBar().showMessage("Ready")

    def init_single_tab(self, parent):
        """Initialize the single label printing tab"""
        layout = QVBoxLayout(parent)

        # Input section
        input_group = QGroupBox("Label Content")
        input_layout = QVBoxLayout()

        # URL input
        url_layout = QHBoxLayout()
        url_label = QLabel("URL:")
        url_label.setMinimumWidth(50)
        url_layout.addWidget(url_label)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/box/123")
        self.url_input.setToolTip("URL or text to encode in the QR code")
        self.url_input.textChanged.connect(self.on_input_changed)
        url_layout.addWidget(self.url_input)
        input_layout.addLayout(url_layout)

        # QR code checkbox
        qr_checkbox_layout = QHBoxLayout()
        qr_checkbox_layout.addSpacing(50)  # Align with input fields
        self.include_qr_checkbox = QCheckBox("Include QR Code")
        self.include_qr_checkbox.setChecked(True)  # Default to including QR code
        self.include_qr_checkbox.setToolTip("Uncheck to create text-only labels without QR codes")
        self.include_qr_checkbox.stateChanged.connect(self.on_qr_checkbox_changed)
        qr_checkbox_layout.addWidget(self.include_qr_checkbox)
        qr_checkbox_layout.addStretch()
        input_layout.addLayout(qr_checkbox_layout)

        # Prefix selection
        prefix_layout = QHBoxLayout()
        prefix_label = QLabel("Prefix:")
        prefix_label.setMinimumWidth(50)
        prefix_layout.addWidget(prefix_label)
        self.prefix_combo = QComboBox()
        self.prefix_combo.addItem("None", "")
        self.prefix_combo.addItem("Box", "Box")
        self.prefix_combo.addItem("Container", "Container")
        self.prefix_combo.addItem("Shelf", "Shelf")
        self.prefix_combo.addItem("Asset", "Asset")
        self.prefix_combo.setToolTip("Select a prefix to add before the label number")
        self.prefix_combo.currentIndexChanged.connect(self.on_prefix_changed)
        prefix_layout.addWidget(self.prefix_combo)
        prefix_layout.addStretch()
        input_layout.addLayout(prefix_layout)

        # Label text input
        label_layout = QHBoxLayout()
        self.label_label = QLabel("Label:")
        self.label_label.setMinimumWidth(50)
        label_layout.addWidget(self.label_label)
        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText("Box 1")
        self.label_input.setToolTip("Text to display on the label")
        self.label_input.textChanged.connect(self.on_input_changed)
        label_layout.addWidget(self.label_input)

        # Auto-increment button
        self.increment_button = QToolButton()
        self.increment_button.setText("+1")
        self.increment_button.setToolTip("Increment label number")
        self.increment_button.clicked.connect(self.increment_label)
        label_layout.addWidget(self.increment_button)

        input_layout.addLayout(label_layout)

        # Clear button
        clear_button_layout = QHBoxLayout()
        clear_button_layout.addStretch()
        self.clear_button = QPushButton("Clear Form")
        self.clear_button.setToolTip("Reset all fields to default values")
        self.clear_button.clicked.connect(self.clear_form)
        clear_button_layout.addWidget(self.clear_button)
        input_layout.addLayout(clear_button_layout)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # Settings section
        settings_group = QGroupBox("Printer Settings")
        settings_layout = QVBoxLayout()

        # Template selection
        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("Template:"))
        self.template_combo = QComboBox()
        self.template_combo.setToolTip("Label template layout")
        self.template_combo.addItem("Template 1 (Horizontal)", 1)
        self.template_combo.addItem("Template 2 (Compact/Vertical)", 2)
        self.template_combo.addItem("Template 3 (Rotated Text)", 3)
        self.template_combo.addItem("Template 4 (Text Only)", 4)
        self.template_combo.currentIndexChanged.connect(self.on_input_changed)
        template_layout.addWidget(self.template_combo)
        template_layout.addStretch()
        settings_layout.addLayout(template_layout)

        # Tape width, font size, and copies on one compact row
        main_settings_layout = QHBoxLayout()

        # Tape width
        main_settings_layout.addWidget(QLabel("Tape:"))
        self.tape_width_combo = QComboBox()
        self.tape_width_combo.setToolTip("Width of the continuous label tape")
        for width in sorted(TAPE_WIDTHS.keys()):
            self.tape_width_combo.addItem(f"{width}mm", width)
        main_settings_layout.addWidget(self.tape_width_combo)

        main_settings_layout.addSpacing(20)

        # Font size
        main_settings_layout.addWidget(QLabel("Font:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(40, 250)
        self.font_size_spin.setValue(100)
        self.font_size_spin.setSuffix("pt")
        self.font_size_spin.setToolTip("Size of the label text (40-250pt)")
        main_settings_layout.addWidget(self.font_size_spin)

        main_settings_layout.addSpacing(20)

        # Copies with quick buttons
        main_settings_layout.addWidget(QLabel("Copies:"))

        # Quick copy buttons
        self.copy_buttons = []
        for count in [1, 4, 5, 6, 8]:
            btn = QPushButton(str(count))
            btn.setFixedWidth(40)
            btn.setCheckable(True)
            btn.setToolTip(f"Print {count} cop{'y' if count == 1 else 'ies'}")
            btn.clicked.connect(lambda checked, c=count: self.set_copies(c))
            self.copy_buttons.append(btn)
            main_settings_layout.addWidget(btn)

        # Dropdown for custom amounts
        self.copies_combo = QComboBox()
        self.copies_combo.setToolTip("Custom number of copies")
        self.copies_combo.addItem("Other", 0)
        for i in range(1, 21):
            self.copies_combo.addItem(str(i), i)
        self.copies_combo.setCurrentIndex(0)
        self.copies_combo.currentIndexChanged.connect(self.on_copies_combo_changed)
        main_settings_layout.addWidget(self.copies_combo)

        main_settings_layout.addStretch()
        settings_layout.addLayout(main_settings_layout)

        # Font selection
        font_select_layout = QHBoxLayout()
        font_select_layout.addWidget(QLabel("Font:"))
        self.font_path_label = QLabel(DEFAULT_FONT)
        self.font_path_label.setStyleSheet("QLabel { color: gray; font-size: 10pt; }")
        self.font_path_label.setToolTip(DEFAULT_FONT)
        font_select_layout.addWidget(self.font_path_label, 1)
        self.font_button = QPushButton("Browse...")
        self.font_button.setToolTip("Select a custom TrueType font file")
        self.font_button.clicked.connect(self.select_font)
        font_select_layout.addWidget(self.font_button)
        settings_layout.addLayout(font_select_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Action buttons
        button_layout = QHBoxLayout()

        self.preview_button = QPushButton("Generate Preview")
        self.preview_button.clicked.connect(self.generate_preview)
        self.preview_button.setFont(QFont("Sans", 11, QFont.Weight.Bold))
        self.preview_button.setToolTip("Generate preview image (Enter)")
        button_layout.addWidget(self.preview_button)

        self.print_button = QPushButton("Print Label")
        self.print_button.clicked.connect(self.print_label)
        self.print_button.setFont(QFont("Sans", 11, QFont.Weight.Bold))
        self.print_button.setToolTip("Send label to printer (Ctrl+P)")
        button_layout.addWidget(self.print_button)

        layout.addLayout(button_layout)

        # Preview section
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout()

        # Scrollable preview area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(200)

        self.preview_label = QLabel("Generate a preview to see your label")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 20px; }")

        scroll_area.setWidget(self.preview_label)
        preview_layout.addWidget(scroll_area)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group, 1)

    def init_batch_tab(self, parent):
        """Initialize the batch printing tab"""
        layout = QVBoxLayout(parent)

        # Shared settings
        settings_group = QGroupBox("Shared Printer Settings")
        settings_layout = QVBoxLayout()

        # First row: Template selection
        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("Template:"))
        self.batch_template_combo = QComboBox()
        self.batch_template_combo.setToolTip("Label template layout (applies to all labels)")
        self.batch_template_combo.addItem("Template 1 (Horizontal)", 1)
        self.batch_template_combo.addItem("Template 2 (Compact/Vertical)", 2)
        self.batch_template_combo.addItem("Template 3 (Rotated Text)", 3)
        self.batch_template_combo.addItem("Template 4 (Text Only)", 4)
        template_layout.addWidget(self.batch_template_combo)
        template_layout.addStretch()
        settings_layout.addLayout(template_layout)

        # Second row: Tape width and font size
        tape_font_layout = QHBoxLayout()

        # Tape width
        tape_font_layout.addWidget(QLabel("Tape Width:"))
        self.batch_tape_width = QComboBox()
        self.batch_tape_width.setToolTip("Width of the continuous label tape (applies to all labels)")
        for width in sorted(TAPE_WIDTHS.keys()):
            self.batch_tape_width.addItem(f"{width}mm", width)
        tape_font_layout.addWidget(self.batch_tape_width)

        # Font size
        tape_font_layout.addWidget(QLabel("Font Size:"))
        self.batch_font_size = QSpinBox()
        self.batch_font_size.setRange(40, 250)
        self.batch_font_size.setValue(100)
        self.batch_font_size.setSuffix("pt")
        self.batch_font_size.setToolTip("Font size for all labels (40-250pt)")
        tape_font_layout.addWidget(self.batch_font_size)

        tape_font_layout.addStretch()
        settings_layout.addLayout(tape_font_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Batch labels table
        batch_group = QGroupBox("Batch Labels (up to 10)")
        batch_layout = QVBoxLayout()

        # Table for labels
        self.batch_table = QTableWidget(0, 3)
        self.batch_table.setHorizontalHeaderLabels(["URL / QR Data", "Label Text", "Copies"])
        self.batch_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.batch_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.batch_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.batch_table.setColumnWidth(2, 100)
        self.batch_table.setToolTip("Define up to 10 labels to print in one batch")
        batch_layout.addWidget(self.batch_table)

        # Batch control buttons
        batch_button_layout = QHBoxLayout()

        self.add_batch_button = QPushButton("Add Label")
        self.add_batch_button.setToolTip("Add a new label to the batch (max 10)")
        self.add_batch_button.clicked.connect(self.add_batch_label)
        batch_button_layout.addWidget(self.add_batch_button)

        self.remove_batch_button = QPushButton("Remove Selected")
        self.remove_batch_button.setToolTip("Remove the selected label from the batch")
        self.remove_batch_button.clicked.connect(self.remove_batch_label)
        batch_button_layout.addWidget(self.remove_batch_button)

        self.clear_batch_button = QPushButton("Clear All")
        self.clear_batch_button.setToolTip("Clear all labels from the batch")
        self.clear_batch_button.clicked.connect(self.clear_batch)
        batch_button_layout.addWidget(self.clear_batch_button)

        batch_button_layout.addStretch()
        batch_layout.addLayout(batch_button_layout)

        batch_group.setLayout(batch_layout)
        layout.addWidget(batch_group)

        # Batch action buttons
        action_layout = QHBoxLayout()

        self.batch_preview_button = QPushButton("Preview All Labels")
        self.batch_preview_button.setFont(QFont("Sans", 11, QFont.Weight.Bold))
        self.batch_preview_button.setToolTip("Generate preview for all labels in batch")
        self.batch_preview_button.clicked.connect(self.preview_batch)
        action_layout.addWidget(self.batch_preview_button)

        self.batch_print_button = QPushButton("Print Batch")
        self.batch_print_button.setFont(QFont("Sans", 11, QFont.Weight.Bold))
        self.batch_print_button.setToolTip("Print all labels in batch")
        self.batch_print_button.clicked.connect(self.print_batch)
        action_layout.addWidget(self.batch_print_button)

        layout.addLayout(action_layout)

        # Batch preview area
        preview_group = QGroupBox("Batch Preview")
        preview_layout = QVBoxLayout()

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(200)

        self.batch_preview_label = QLabel("Add labels and click 'Preview All Labels' to see your batch")
        self.batch_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.batch_preview_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 20px; }")

        scroll_area.setWidget(self.batch_preview_label)
        preview_layout.addWidget(scroll_area)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group, 1)

    def init_text_only_tab(self, parent):
        """Initialize the text-only label printing tab"""
        layout = QVBoxLayout(parent)

        # Input section
        input_group = QGroupBox("Label Content")
        input_layout = QVBoxLayout()

        # Prefix selection
        prefix_layout = QHBoxLayout()
        prefix_label = QLabel("Prefix:")
        prefix_label.setMinimumWidth(50)
        prefix_layout.addWidget(prefix_label)
        self.text_only_prefix_combo = QComboBox()
        self.text_only_prefix_combo.addItem("None", "")
        self.text_only_prefix_combo.addItem("Box", "Box")
        self.text_only_prefix_combo.addItem("Container", "Container")
        self.text_only_prefix_combo.addItem("Shelf", "Shelf")
        self.text_only_prefix_combo.addItem("Asset", "Asset")
        self.text_only_prefix_combo.setToolTip("Select a prefix to add before the label number")
        self.text_only_prefix_combo.currentIndexChanged.connect(self.on_text_only_prefix_changed)
        prefix_layout.addWidget(self.text_only_prefix_combo)
        prefix_layout.addStretch()
        input_layout.addLayout(prefix_layout)

        # Label text input
        label_layout = QHBoxLayout()
        self.text_only_label_label = QLabel("Text:")
        self.text_only_label_label.setMinimumWidth(50)
        label_layout.addWidget(self.text_only_label_label)
        self.text_only_input = QLineEdit()
        self.text_only_input.setPlaceholderText("Enter label text")
        self.text_only_input.setToolTip("Text to display on the label (centered)")
        self.text_only_input.textChanged.connect(self.on_text_only_input_changed)
        label_layout.addWidget(self.text_only_input)

        # Auto-increment button
        self.text_only_increment_button = QToolButton()
        self.text_only_increment_button.setText("+1")
        self.text_only_increment_button.setToolTip("Increment label number")
        self.text_only_increment_button.clicked.connect(self.increment_text_only_label)
        label_layout.addWidget(self.text_only_increment_button)

        input_layout.addLayout(label_layout)

        # Clear button
        clear_button_layout = QHBoxLayout()
        clear_button_layout.addStretch()
        self.text_only_clear_button = QPushButton("Clear Form")
        self.text_only_clear_button.setToolTip("Reset all fields to default values")
        self.text_only_clear_button.clicked.connect(self.clear_text_only_form)
        clear_button_layout.addWidget(self.text_only_clear_button)
        input_layout.addLayout(clear_button_layout)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # Settings section
        settings_group = QGroupBox("Printer Settings")
        settings_layout = QVBoxLayout()

        # Tape width, font size, and copies on one compact row
        main_settings_layout = QHBoxLayout()

        # Tape width
        main_settings_layout.addWidget(QLabel("Tape:"))
        self.text_only_tape_width = QComboBox()
        self.text_only_tape_width.setToolTip("Width of the continuous label tape")
        for width in sorted(TAPE_WIDTHS.keys()):
            self.text_only_tape_width.addItem(f"{width}mm", width)
        # Set default to 29mm
        index = self.text_only_tape_width.findData(29)
        if index >= 0:
            self.text_only_tape_width.setCurrentIndex(index)
        main_settings_layout.addWidget(self.text_only_tape_width)

        main_settings_layout.addSpacing(20)

        # Font size
        main_settings_layout.addWidget(QLabel("Font:"))
        self.text_only_font_size = QSpinBox()
        self.text_only_font_size.setRange(40, 250)
        self.text_only_font_size.setValue(100)
        self.text_only_font_size.setSuffix("pt")
        self.text_only_font_size.setToolTip("Size of the label text (40-250pt)")
        main_settings_layout.addWidget(self.text_only_font_size)

        main_settings_layout.addSpacing(20)

        # Copies with quick buttons
        main_settings_layout.addWidget(QLabel("Copies:"))

        # Quick copy buttons
        self.text_only_copy_buttons = []
        for count in [1, 4, 5, 6, 8]:
            btn = QPushButton(str(count))
            btn.setFixedWidth(40)
            btn.setCheckable(True)
            btn.setToolTip(f"Print {count} cop{'y' if count == 1 else 'ies'}")
            btn.clicked.connect(lambda checked, c=count: self.set_text_only_copies(c))
            self.text_only_copy_buttons.append(btn)
            main_settings_layout.addWidget(btn)

        # Dropdown for custom amounts
        self.text_only_copies_combo = QComboBox()
        self.text_only_copies_combo.setToolTip("Custom number of copies")
        self.text_only_copies_combo.addItem("Other", 0)
        for i in range(1, 21):
            self.text_only_copies_combo.addItem(str(i), i)
        self.text_only_copies_combo.setCurrentIndex(0)
        self.text_only_copies_combo.currentIndexChanged.connect(self.on_text_only_copies_combo_changed)
        main_settings_layout.addWidget(self.text_only_copies_combo)

        main_settings_layout.addStretch()
        settings_layout.addLayout(main_settings_layout)

        # Font selection
        font_select_layout = QHBoxLayout()
        font_select_layout.addWidget(QLabel("Font:"))
        self.text_only_font_path_label = QLabel(DEFAULT_FONT)
        self.text_only_font_path_label.setStyleSheet("QLabel { color: gray; font-size: 10pt; }")
        self.text_only_font_path_label.setToolTip(DEFAULT_FONT)
        font_select_layout.addWidget(self.text_only_font_path_label, 1)
        self.text_only_font_button = QPushButton("Browse...")
        self.text_only_font_button.setToolTip("Select a custom TrueType font file")
        self.text_only_font_button.clicked.connect(self.select_text_only_font)
        font_select_layout.addWidget(self.text_only_font_button)
        settings_layout.addLayout(font_select_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Action buttons
        button_layout = QHBoxLayout()

        self.text_only_preview_button = QPushButton("Generate Preview")
        self.text_only_preview_button.clicked.connect(self.generate_text_only_preview)
        self.text_only_preview_button.setFont(QFont("Sans", 11, QFont.Weight.Bold))
        self.text_only_preview_button.setToolTip("Generate preview image")
        button_layout.addWidget(self.text_only_preview_button)

        self.text_only_print_button = QPushButton("Print Label")
        self.text_only_print_button.clicked.connect(self.print_text_only_label)
        self.text_only_print_button.setFont(QFont("Sans", 11, QFont.Weight.Bold))
        self.text_only_print_button.setToolTip("Send label to printer")
        button_layout.addWidget(self.text_only_print_button)

        layout.addLayout(button_layout)

        # Preview section
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout()

        # Scrollable preview area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(200)

        self.text_only_preview_label = QLabel("Generate a preview to see your label")
        self.text_only_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_only_preview_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 20px; }")

        scroll_area.setWidget(self.text_only_preview_label)
        preview_layout.addWidget(scroll_area)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group, 1)

        # Default to 1 copy (first button)
        if self.text_only_copy_buttons:
            self.text_only_copy_buttons[0].setChecked(True)

    def load_settings(self):
        """Load persistent settings"""
        # Tape width
        tape_width = self.settings.value("tape_width", 29, type=int)
        index = self.tape_width_combo.findData(tape_width)
        if index >= 0:
            self.tape_width_combo.setCurrentIndex(index)

        # Font size
        font_size = self.settings.value("font_size", 100, type=int)
        self.font_size_spin.setValue(font_size)

        # Font path
        font_path = self.settings.value("font_path", DEFAULT_FONT)
        self.font_path_label.setText(font_path)

        # Prefix (QR+Text tab)
        prefix = self.settings.value("prefix", "")
        index = self.prefix_combo.findData(prefix)
        if index >= 0:
            self.prefix_combo.setCurrentIndex(index)

        # Prefix (Text-only tab)
        text_only_prefix = self.settings.value("text_only_prefix", "")
        index = self.text_only_prefix_combo.findData(text_only_prefix)
        if index >= 0:
            self.text_only_prefix_combo.setCurrentIndex(index)

        # Default to 1 copy (first button)
        if self.copy_buttons:
            self.copy_buttons[0].setChecked(True)

    def save_settings(self):
        """Save persistent settings"""
        self.settings.setValue("tape_width", self.tape_width_combo.currentData())
        self.settings.setValue("font_size", self.font_size_spin.value())
        self.settings.setValue("font_path", self.font_path_label.text())
        self.settings.setValue("prefix", self.prefix_combo.currentData())
        self.settings.setValue("text_only_prefix", self.text_only_prefix_combo.currentData())

    def select_font(self):
        """Open file dialog to select font"""
        font_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Font File",
            "/usr/share/fonts/truetype/",
            "TrueType Fonts (*.ttf);;All Files (*)"
        )
        if font_path:
            self.font_path_label.setText(font_path)
            self.save_settings()

    def generate_preview(self):
        """Generate preview image"""
        url = self.url_input.text().strip()
        label = self.label_input.text().strip()
        include_qr = self.include_qr_checkbox.isChecked()

        # Validate required fields
        if not label:
            QMessageBox.warning(
                self,
                "Missing Input",
                "Please enter label text."
            )
            return

        if include_qr and not url:
            QMessageBox.warning(
                self,
                "Missing Input",
                "Please enter URL for QR code, or uncheck 'Include QR Code' for text-only labels."
            )
            return

        try:
            self.statusBar().showMessage("Generating preview...")

            # Save settings
            self.save_settings()

            # Get final label text with prefix
            final_label = self.get_final_label_text()

            # Get selected template
            template = self.template_combo.currentData()

            # Generate image based on template selection
            if template == 1:
                self.preview_image = create_label_image(
                    qr_data=url if include_qr else "",
                    text=final_label,
                    tape_width_mm=self.tape_width_combo.currentData(),
                    font_path=self.font_path_label.text(),
                    font_size=self.font_size_spin.value(),
                    include_qr=include_qr
                )
            elif template == 2:
                self.preview_image = create_label_image_template2(
                    qr_data=url if include_qr else "",
                    text=final_label,
                    tape_width_mm=self.tape_width_combo.currentData(),
                    font_path=self.font_path_label.text(),
                    font_size=self.font_size_spin.value(),
                    include_qr=include_qr
                )
            elif template == 3:
                self.preview_image = create_label_image_template3(
                    qr_data=url if include_qr else "",
                    text=final_label,
                    tape_width_mm=self.tape_width_combo.currentData(),
                    font_path=self.font_path_label.text(),
                    font_size=self.font_size_spin.value(),
                    include_qr=include_qr
                )
            elif template == 4:
                self.preview_image = create_text_only_label(
                    text=final_label,
                    tape_width_mm=self.tape_width_combo.currentData(),
                    font_path=self.font_path_label.text(),
                    font_size=self.font_size_spin.value()
                )

            # Save to temp file and display
            temp_path = "/tmp/brother_ql_preview.png"
            self.preview_image.save(temp_path)

            # Load and display preview
            pixmap = QPixmap(temp_path)
            self.preview_label.setPixmap(pixmap)
            self.preview_label.setScaledContents(False)

            # Enable print button
            self.print_button.setEnabled(True)

            tape_width = self.tape_width_combo.currentData()
            label_type = "with QR code" if include_qr else "text-only"
            self.statusBar().showMessage(
                f"Preview generated ({label_type}): {self.preview_image.size[0]}x{self.preview_image.size[1]}px "
                f"({tape_width}mm tape)"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Preview Error",
                f"Failed to generate preview:\n{str(e)}"
            )
            self.statusBar().showMessage("Preview failed")

    def print_label(self):
        """Print the label"""
        # If no preview, generate it first
        if not self.preview_image:
            url = self.url_input.text().strip()
            label = self.label_input.text().strip()
            include_qr = self.include_qr_checkbox.isChecked()

            # Validate required fields
            if not label:
                QMessageBox.warning(
                    self,
                    "Missing Input",
                    "Please enter label text."
                )
                return

            if include_qr and not url:
                QMessageBox.warning(
                    self,
                    "Missing Input",
                    "Please enter URL for QR code, or uncheck 'Include QR Code' for text-only labels."
                )
                return

            try:
                # Get final label text with prefix
                final_label = self.get_final_label_text()

                # Get selected template
                template = self.template_combo.currentData()

                # Generate image without preview based on template selection
                if template == 1:
                    self.preview_image = create_label_image(
                        qr_data=url if include_qr else "",
                        text=final_label,
                        tape_width_mm=self.tape_width_combo.currentData(),
                        font_path=self.font_path_label.text(),
                        font_size=self.font_size_spin.value(),
                        include_qr=include_qr
                    )
                elif template == 2:
                    self.preview_image = create_label_image_template2(
                        qr_data=url if include_qr else "",
                        text=final_label,
                        tape_width_mm=self.tape_width_combo.currentData(),
                        font_path=self.font_path_label.text(),
                        font_size=self.font_size_spin.value(),
                        include_qr=include_qr
                    )
                elif template == 3:
                    self.preview_image = create_label_image_template3(
                        qr_data=url if include_qr else "",
                        text=final_label,
                        tape_width_mm=self.tape_width_combo.currentData(),
                        font_path=self.font_path_label.text(),
                        font_size=self.font_size_spin.value(),
                        include_qr=include_qr
                    )
                elif template == 4:
                    self.preview_image = create_text_only_label(
                        text=final_label,
                        tape_width_mm=self.tape_width_combo.currentData(),
                        font_path=self.font_path_label.text(),
                        font_size=self.font_size_spin.value()
                    )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to generate label:\n{str(e)}"
                )
                return

        copies = self.get_copies()
        include_qr = self.include_qr_checkbox.isChecked()
        label_type = "label with QR code" if include_qr else "text-only label"

        reply = QMessageBox.question(
            self,
            "Confirm Print",
            f"Print {copies} {label_type}{'s' if copies > 1 else ''} on {self.tape_width_combo.currentData()}mm tape?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Save to temp file
                temp_path = "/tmp/brother_ql_print.png"
                self.preview_image.save(temp_path)

                # Print multiple copies
                for copy_num in range(copies):
                    self.statusBar().showMessage(f"Printing copy {copy_num + 1} of {copies}...")

                    # Create raster instructions
                    qlr = BrotherQLRaster(PRINTER_MODEL)

                    instructions = convert(
                        qlr=qlr,
                        images=[temp_path],
                        label=str(self.tape_width_combo.currentData()),
                        rotate=90,
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
                            printer_identifier=DEFAULT_PRINTER,
                            backend_identifier=DEFAULT_BACKEND,
                            blocking=True
                        )

                self.statusBar().showMessage(f"Print complete! {copies} label{'s' if copies > 1 else ''} printed.")
                QMessageBox.information(
                    self,
                    "Success",
                    f"{copies} label{'s' if copies > 1 else ''} printed successfully!"
                )

            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Print Error",
                    f"Failed to print label:\n{str(e)}"
                )
                self.statusBar().showMessage("Print failed")

    def on_input_changed(self):
        """Handle any input field changes - clear cached preview and validate"""
        # Clear cached preview so next print regenerates from current inputs
        self.preview_image = None
        # Also clear the preview display to show it's outdated
        if self.preview_label.pixmap() and not self.preview_label.pixmap().isNull():
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("Preview cleared - generate new preview or print directly")
            self.statusBar().showMessage("Inputs changed - preview cleared")
        self.validate_inputs()

    def on_qr_checkbox_changed(self, state):
        """Handle QR code checkbox state changes"""
        include_qr = self.include_qr_checkbox.isChecked()

        # Update URL field requirement based on QR inclusion
        if include_qr:
            self.url_input.setEnabled(True)
            self.url_input.setPlaceholderText("https://example.com/box/123")
        else:
            self.url_input.setEnabled(False)
            self.url_input.setPlaceholderText("(QR code disabled - not required)")
            self.url_input.setStyleSheet("")  # Clear any validation styling

        # Clear cached preview since QR setting changed
        self.on_input_changed()

    def on_prefix_changed(self):
        """Handle prefix selection changes"""
        prefix = self.prefix_combo.currentData()

        # Update label field placeholder and label based on prefix selection
        if prefix:
            self.label_label.setText("Number:")
            self.label_input.setPlaceholderText("18")
            self.label_input.setToolTip(f"Enter number (will be displayed as '{prefix} #')")
        else:
            self.label_label.setText("Label:")
            self.label_input.setPlaceholderText("Box 1")
            self.label_input.setToolTip("Text to display on the label")

        # Clear cached preview since prefix changed
        self.on_input_changed()

    def on_text_only_prefix_changed(self):
        """Handle text-only prefix selection changes"""
        prefix = self.text_only_prefix_combo.currentData()

        # Update label field placeholder and label based on prefix selection
        if prefix:
            self.text_only_label_label.setText("Number:")
            self.text_only_input.setPlaceholderText("18")
            self.text_only_input.setToolTip(f"Enter number (will be displayed as '{prefix} #')")
        else:
            self.text_only_label_label.setText("Text:")
            self.text_only_input.setPlaceholderText("Enter label text")
            self.text_only_input.setToolTip("Text to display on the label (centered)")

        # Clear cached preview
        self.on_text_only_input_changed()

    def get_final_label_text(self):
        """Get the final label text combining prefix and input"""
        prefix = self.prefix_combo.currentData()
        text = self.label_input.text().strip()

        if prefix and text:
            return f"{prefix} {text}"
        return text

    def get_final_text_only_label_text(self):
        """Get the final text-only label text combining prefix and input"""
        prefix = self.text_only_prefix_combo.currentData()
        text = self.text_only_input.text().strip()

        if prefix and text:
            return f"{prefix} {text}"
        return text

    def validate_inputs(self):
        """Validate input fields and provide visual feedback"""
        url = self.url_input.text().strip()
        label = self.label_input.text().strip()
        include_qr = self.include_qr_checkbox.isChecked()

        # Label text is always required
        if not label:
            self.label_input.setStyleSheet("border: 1px solid #ffcccc;")
        else:
            self.label_input.setStyleSheet("")

        # URL is only required if QR code is enabled
        if include_qr:
            if not url:
                self.url_input.setStyleSheet("border: 1px solid #ffcccc;")
            else:
                self.url_input.setStyleSheet("")

    def increment_label(self):
        """Increment the number in the label text"""
        text = self.label_input.text()
        import re

        # If prefix is selected, just increment the number
        prefix = self.prefix_combo.currentData()
        if prefix:
            # Text should be just a number when prefix is selected
            if text.isdigit():
                self.label_input.setText(str(int(text) + 1))
            else:
                # Find trailing number in case user typed something else
                match = re.search(r'(\d+)$', text)
                if match:
                    num = int(match.group(1))
                    new_text = text[:match.start()] + str(num + 1)
                    self.label_input.setText(new_text)
                else:
                    # If no number, start with 1
                    self.label_input.setText("1")
        else:
            # Original behavior for full text labels
            # Find trailing number
            match = re.search(r'(\d+)$', text)
            if match:
                num = int(match.group(1))
                new_text = text[:match.start()] + str(num + 1)
                self.label_input.setText(new_text)
            else:
                # If no number, append " 2"
                self.label_input.setText(text + " 2")

    def set_copies(self, count):
        """Set the number of copies from a quick button"""
        # Uncheck all buttons
        for btn in self.copy_buttons:
            btn.setChecked(False)

        # Check the clicked button
        for btn in self.copy_buttons:
            if btn.text() == str(count):
                btn.setChecked(True)
                break

        # Reset dropdown to "Other"
        self.copies_combo.setCurrentIndex(0)
        self.current_copies = count

    def on_copies_combo_changed(self):
        """Handle dropdown selection for custom copy count"""
        if self.copies_combo.currentIndex() > 0:
            # User selected a number from dropdown
            # Uncheck all quick buttons
            for btn in self.copy_buttons:
                btn.setChecked(False)
            self.current_copies = self.copies_combo.currentData()

    def get_copies(self):
        """Get the currently selected number of copies"""
        # Check if any button is selected
        for btn in self.copy_buttons:
            if btn.isChecked():
                return int(btn.text())

        # Otherwise use dropdown (if not "Other")
        if self.copies_combo.currentIndex() > 0:
            return self.copies_combo.currentData()

        # Default to 1
        return 1

    def clear_form(self):
        """Clear all input fields"""
        self.url_input.clear()
        self.label_input.clear()
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("Generate a preview to see your label")
        self.preview_image = None
        self.print_button.setEnabled(False)

        # Reset copies to 1
        for btn in self.copy_buttons:
            btn.setChecked(False)
        self.copy_buttons[0].setChecked(True)
        self.copies_combo.setCurrentIndex(0)
        self.current_copies = 1

        self.statusBar().showMessage("Form cleared")

    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Enter to generate preview
        preview_action = QAction(self)
        preview_action.setShortcut(QKeySequence(Qt.Key.Key_Return))
        preview_action.triggered.connect(self.generate_preview)
        self.addAction(preview_action)

        # Ctrl+P to print
        print_action = QAction(self)
        print_action.setShortcut(QKeySequence("Ctrl+P"))
        print_action.triggered.connect(self.print_label)
        self.addAction(print_action)

        # Ctrl+R to clear/reset
        clear_action = QAction(self)
        clear_action.setShortcut(QKeySequence("Ctrl+R"))
        clear_action.triggered.connect(self.clear_form)
        self.addAction(clear_action)

    def add_batch_label(self):
        """Add a new label to the batch table"""
        if self.batch_table.rowCount() >= 10:
            QMessageBox.warning(
                self,
                "Batch Full",
                "Maximum of 10 labels per batch reached."
            )
            return

        row = self.batch_table.rowCount()
        self.batch_table.insertRow(row)

        # URL cell
        url_item = QTableWidgetItem("")
        self.batch_table.setItem(row, 0, url_item)

        # Label text cell
        label_item = QTableWidgetItem("")
        self.batch_table.setItem(row, 1, label_item)

        # Copies dropdown
        copies_combo = QComboBox()
        for i in range(1, 11):
            copies_combo.addItem(str(i), i)
        # Set to last used value
        copies_combo.setCurrentIndex(self.last_copies - 1)
        self.batch_table.setCellWidget(row, 2, copies_combo)

        # Connect copies change to track last used
        copies_combo.currentIndexChanged.connect(
            lambda: self.update_last_copies(copies_combo.currentData())
        )

        self.statusBar().showMessage(f"Added label {row + 1} to batch")

    def update_last_copies(self, value):
        """Update the last used copies value"""
        self.last_copies = value

    def remove_batch_label(self):
        """Remove selected label from batch"""
        current_row = self.batch_table.currentRow()
        if current_row >= 0:
            self.batch_table.removeRow(current_row)
            self.statusBar().showMessage(f"Removed label from batch")
        else:
            QMessageBox.warning(
                self,
                "No Selection",
                "Please select a label to remove."
            )

    def clear_batch(self):
        """Clear all labels from batch"""
        if self.batch_table.rowCount() == 0:
            return

        reply = QMessageBox.question(
            self,
            "Clear Batch",
            "Remove all labels from the batch?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.batch_table.setRowCount(0)
            self.batch_preview_label.setPixmap(QPixmap())
            self.batch_preview_label.setText("Add labels and click 'Preview All Labels' to see your batch")
            self.statusBar().showMessage("Batch cleared")

    def preview_batch(self):
        """Generate preview for all labels in batch"""
        if self.batch_table.rowCount() == 0:
            QMessageBox.warning(
                self,
                "Empty Batch",
                "Please add labels to the batch first."
            )
            return

        try:
            self.statusBar().showMessage("Generating batch preview...")

            # Collect all labels from table
            labels = []
            for row in range(self.batch_table.rowCount()):
                url = self.batch_table.item(row, 0).text().strip()
                label_text = self.batch_table.item(row, 1).text().strip()
                copies_widget = self.batch_table.cellWidget(row, 2)
                copies = copies_widget.currentData() if copies_widget else 1

                if not url or not label_text:
                    QMessageBox.warning(
                        self,
                        "Missing Data",
                        f"Row {row + 1} is missing URL or label text."
                    )
                    return

                labels.append((url, label_text, copies))

            # Generate preview images
            preview_images = []
            tape_width = self.batch_tape_width.currentData()
            font_size = self.batch_font_size.value()
            template = self.batch_template_combo.currentData()

            for url, label_text, copies in labels:
                # Generate image based on template selection
                if template == 1:
                    img = create_label_image(
                        qr_data=url,
                        text=label_text,
                        tape_width_mm=tape_width,
                        font_path=DEFAULT_FONT,
                        font_size=font_size
                    )
                elif template == 2:
                    img = create_label_image_template2(
                        qr_data=url,
                        text=label_text,
                        tape_width_mm=tape_width,
                        font_path=DEFAULT_FONT,
                        font_size=font_size
                    )
                elif template == 3:
                    img = create_label_image_template3(
                        qr_data=url,
                        text=label_text,
                        tape_width_mm=tape_width,
                        font_path=DEFAULT_FONT,
                        font_size=font_size
                    )
                elif template == 4:
                    img = create_text_only_label(
                        text=label_text,
                        tape_width_mm=tape_width,
                        font_path=DEFAULT_FONT,
                        font_size=font_size
                    )
                preview_images.append(img)

            # Combine images vertically for preview
            if preview_images:
                total_height = sum(img.height for img in preview_images) + (len(preview_images) - 1) * 10
                max_width = max(img.width for img in preview_images)

                combined = Image.new("RGB", (max_width, total_height), (255, 255, 255))
                y_offset = 0
                for img in preview_images:
                    combined.paste(img, (0, y_offset))
                    y_offset += img.height + 10

                # Save and display
                temp_path = "/tmp/brother_ql_batch_preview.png"
                combined.save(temp_path)

                pixmap = QPixmap(temp_path)
                self.batch_preview_label.setPixmap(pixmap)
                self.batch_preview_label.setScaledContents(False)

                self.statusBar().showMessage(f"Batch preview generated: {len(preview_images)} labels")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Preview Error",
                f"Failed to generate batch preview:\n{str(e)}"
            )
            self.statusBar().showMessage("Batch preview failed")

    def print_batch(self):
        """Print all labels in batch"""
        if self.batch_table.rowCount() == 0:
            QMessageBox.warning(
                self,
                "Empty Batch",
                "Please add labels to the batch first."
            )
            return

        try:
            # Collect all labels from table
            labels = []
            total_copies = 0
            for row in range(self.batch_table.rowCount()):
                url = self.batch_table.item(row, 0).text().strip()
                label_text = self.batch_table.item(row, 1).text().strip()
                copies_widget = self.batch_table.cellWidget(row, 2)
                copies = copies_widget.currentData() if copies_widget else 1

                if not url or not label_text:
                    QMessageBox.warning(
                        self,
                        "Missing Data",
                        f"Row {row + 1} is missing URL or label text."
                    )
                    return

                labels.append((url, label_text, copies))
                total_copies += copies

            # Confirm print
            reply = QMessageBox.question(
                self,
                "Confirm Batch Print",
                f"Print {len(labels)} label designs ({total_copies} total labels)?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            # Print each label
            tape_width = self.batch_tape_width.currentData()
            font_size = self.batch_font_size.value()
            template = self.batch_template_combo.currentData()
            printed_count = 0

            for idx, (url, label_text, copies) in enumerate(labels, 1):
                self.statusBar().showMessage(f"Printing label {idx}/{len(labels)}...")

                # Generate image based on template selection
                if template == 1:
                    img = create_label_image(
                        qr_data=url,
                        text=label_text,
                        tape_width_mm=tape_width,
                        font_path=DEFAULT_FONT,
                        font_size=font_size
                    )
                elif template == 2:
                    img = create_label_image_template2(
                        qr_data=url,
                        text=label_text,
                        tape_width_mm=tape_width,
                        font_path=DEFAULT_FONT,
                        font_size=font_size
                    )
                elif template == 3:
                    img = create_label_image_template3(
                        qr_data=url,
                        text=label_text,
                        tape_width_mm=tape_width,
                        font_path=DEFAULT_FONT,
                        font_size=font_size
                    )
                elif template == 4:
                    img = create_text_only_label(
                        text=label_text,
                        tape_width_mm=tape_width,
                        font_path=DEFAULT_FONT,
                        font_size=font_size
                    )

                # Save to temp file
                temp_path = "/tmp/brother_ql_batch_print.png"
                img.save(temp_path)

                # Print copies
                for copy_num in range(copies):
                    # Create raster instructions
                    qlr = BrotherQLRaster(PRINTER_MODEL)

                    instructions = convert(
                        qlr=qlr,
                        images=[temp_path],
                        label=str(tape_width),
                        rotate=90,
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
                            printer_identifier=DEFAULT_PRINTER,
                            backend_identifier=DEFAULT_BACKEND,
                            blocking=True
                        )
                    printed_count += 1

            self.statusBar().showMessage(f"Batch print complete! {printed_count} labels printed.")
            QMessageBox.information(
                self,
                "Success",
                f"Batch printed successfully!\n{len(labels)} designs, {printed_count} total labels."
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Print Error",
                f"Failed to print batch:\n{str(e)}"
            )
            self.statusBar().showMessage("Batch print failed")

    # Text-only tab methods
    def on_text_only_input_changed(self):
        """Handle text-only input field changes"""
        # Clear cached preview
        self.text_only_preview_image = None
        if hasattr(self, 'text_only_preview_label') and self.text_only_preview_label.pixmap() and not self.text_only_preview_label.pixmap().isNull():
            self.text_only_preview_label.setPixmap(QPixmap())
            self.text_only_preview_label.setText("Preview cleared - generate new preview or print directly")

    def increment_text_only_label(self):
        """Increment the number in the text-only label"""
        text = self.text_only_input.text()
        import re

        # If prefix is selected, just increment the number
        prefix = self.text_only_prefix_combo.currentData()
        if prefix:
            # Text should be just a number when prefix is selected
            if text.isdigit():
                self.text_only_input.setText(str(int(text) + 1))
            else:
                # Find trailing number in case user typed something else
                match = re.search(r'(\d+)$', text)
                if match:
                    num = int(match.group(1))
                    new_text = text[:match.start()] + str(num + 1)
                    self.text_only_input.setText(new_text)
                else:
                    # If no number, start with 1
                    self.text_only_input.setText("1")
        else:
            # Original behavior for full text labels
            # Find trailing number
            match = re.search(r'(\d+)$', text)
            if match:
                num = int(match.group(1))
                new_text = text[:match.start()] + str(num + 1)
                self.text_only_input.setText(new_text)
            else:
                # If no number, append " 2"
                self.text_only_input.setText(text + " 2")

    def clear_text_only_form(self):
        """Clear the text-only form"""
        self.text_only_input.clear()
        self.text_only_preview_label.setPixmap(QPixmap())
        self.text_only_preview_label.setText("Generate a preview to see your label")
        self.text_only_preview_image = None

        # Reset copies to 1
        for btn in self.text_only_copy_buttons:
            btn.setChecked(False)
        self.text_only_copy_buttons[0].setChecked(True)
        self.text_only_copies_combo.setCurrentIndex(0)

        self.statusBar().showMessage("Text-only form cleared")

    def set_text_only_copies(self, count):
        """Set the number of copies for text-only labels"""
        # Uncheck all buttons
        for btn in self.text_only_copy_buttons:
            btn.setChecked(False)

        # Check the clicked button
        for btn in self.text_only_copy_buttons:
            if btn.text() == str(count):
                btn.setChecked(True)
                break

        # Reset dropdown to "Other"
        self.text_only_copies_combo.setCurrentIndex(0)

    def on_text_only_copies_combo_changed(self):
        """Handle text-only copies combo changes"""
        if self.text_only_copies_combo.currentIndex() > 0:
            # Uncheck all quick buttons
            for btn in self.text_only_copy_buttons:
                btn.setChecked(False)

    def get_text_only_copies(self):
        """Get the currently selected number of copies for text-only"""
        # Check if any button is selected
        for btn in self.text_only_copy_buttons:
            if btn.isChecked():
                return int(btn.text())

        # Otherwise use dropdown (if not "Other")
        if self.text_only_copies_combo.currentIndex() > 0:
            return self.text_only_copies_combo.currentData()

        # Default to 1
        return 1

    def select_text_only_font(self):
        """Select font for text-only labels"""
        font_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Font File",
            "/usr/share/fonts/truetype/",
            "TrueType Fonts (*.ttf);;All Files (*)"
        )
        if font_path:
            self.text_only_font_path_label.setText(font_path)

    def generate_text_only_preview(self):
        """Generate preview for text-only label"""
        text = self.text_only_input.text().strip()

        if not text:
            QMessageBox.warning(
                self,
                "Missing Input",
                "Please enter text for the label."
            )
            return

        try:
            self.statusBar().showMessage("Generating text-only preview...")

            # Get final label text with prefix
            final_text = self.get_final_text_only_label_text()

            # Generate image
            self.text_only_preview_image = create_text_only_label(
                text=final_text,
                tape_width_mm=self.text_only_tape_width.currentData(),
                font_path=self.text_only_font_path_label.text(),
                font_size=self.text_only_font_size.value()
            )

            # Save to temp file and display
            temp_path = "/tmp/brother_ql_text_only_preview.png"
            self.text_only_preview_image.save(temp_path)

            # Load and display preview
            pixmap = QPixmap(temp_path)
            self.text_only_preview_label.setPixmap(pixmap)
            self.text_only_preview_label.setScaledContents(False)

            tape_width = self.text_only_tape_width.currentData()
            self.statusBar().showMessage(
                f"Text-only preview generated: {self.text_only_preview_image.size[0]}x{self.text_only_preview_image.size[1]}px "
                f"({tape_width}mm tape)"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Preview Error",
                f"Failed to generate preview:\n{str(e)}"
            )
            self.statusBar().showMessage("Preview failed")

    def print_text_only_label(self):
        """Print the text-only label"""
        text = self.text_only_input.text().strip()

        if not text:
            QMessageBox.warning(
                self,
                "Missing Input",
                "Please enter text for the label."
            )
            return

        # Generate image if not already previewed
        if not hasattr(self, 'text_only_preview_image') or not self.text_only_preview_image:
            try:
                # Get final label text with prefix
                final_text = self.get_final_text_only_label_text()

                self.text_only_preview_image = create_text_only_label(
                    text=final_text,
                    tape_width_mm=self.text_only_tape_width.currentData(),
                    font_path=self.text_only_font_path_label.text(),
                    font_size=self.text_only_font_size.value()
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to generate label:\n{str(e)}"
                )
                return

        copies = self.get_text_only_copies()

        reply = QMessageBox.question(
            self,
            "Confirm Print",
            f"Print {copies} text-only label{'s' if copies > 1 else ''} on {self.text_only_tape_width.currentData()}mm tape?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Save to temp file
                temp_path = "/tmp/brother_ql_text_only_print.png"
                self.text_only_preview_image.save(temp_path)

                # Print multiple copies
                for copy_num in range(copies):
                    self.statusBar().showMessage(f"Printing copy {copy_num + 1} of {copies}...")

                    # Create raster instructions
                    qlr = BrotherQLRaster(PRINTER_MODEL)

                    instructions = convert(
                        qlr=qlr,
                        images=[temp_path],
                        label=str(self.text_only_tape_width.currentData()),
                        rotate=90,
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
                            printer_identifier=DEFAULT_PRINTER,
                            backend_identifier=DEFAULT_BACKEND,
                            blocking=True
                        )

                self.statusBar().showMessage(f"Print complete! {copies} label{'s' if copies > 1 else ''} printed.")
                QMessageBox.information(
                    self,
                    "Success",
                    f"{copies} text-only label{'s' if copies > 1 else ''} printed successfully!"
                )

            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Print Error",
                    f"Failed to print label:\n{str(e)}"
                )
                self.statusBar().showMessage("Print failed")

    def init_about_tab(self, parent):
        """Initialize the About tab with product information and tape references"""
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(20, 20, 20, 20)

        # Main scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        # Content widget
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(15)

        # Title
        title = QLabel("Brother QL-700 Label Printer")
        title.setFont(QFont("Sans", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(title)

        # Version
        version = QLabel("Version 1.1.0")
        version.setFont(QFont("Sans", 10))
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet("color: gray;")
        content_layout.addWidget(version)

        content_layout.addSpacing(10)

        # Application Description
        desc_group = QGroupBox("About This Application")
        desc_layout = QVBoxLayout()
        desc_text = QLabel(
            "A user-friendly GUI application for printing labels with QR codes on Brother QL-700 "
            "label printers. Features single label printing, batch mode, and text-only labels with "
            "support for multiple tape widths."
        )
        desc_text.setWordWrap(True)
        desc_text.setStyleSheet("padding: 10px;")
        desc_layout.addWidget(desc_text)
        desc_group.setLayout(desc_layout)
        content_layout.addWidget(desc_group)

        # Tape Product References
        tape_group = QGroupBox("Continuous Tape Product References")
        tape_layout = QVBoxLayout()
        tape_layout.setSpacing(10)

        # Info text
        tape_info = QLabel(
            "Use genuine Brother continuous length (endless) paper tape for best results. "
            "The following DK tape references are recommended for the QL-700:"
        )
        tape_info.setWordWrap(True)
        tape_info.setStyleSheet("padding: 10px; margin-bottom: 5px;")
        tape_layout.addWidget(tape_info)

        # Tape specifications table
        tape_specs = [
            ("29mm", "DK-22210", "Continuous Length Paper (White)"),
            ("38mm", "DK-22225", "Continuous Length Paper (White)"),
            ("50mm", "DK-22223", "Continuous Length Paper (White)"),
            ("62mm", "DK-22205", "Continuous Length Paper (White)")
        ]

        for width, product_code, description in tape_specs:
            tape_item = QWidget()
            tape_item_layout = QHBoxLayout(tape_item)
            tape_item_layout.setContentsMargins(10, 5, 10, 5)

            # Width label
            width_label = QLabel(width)
            width_label.setFont(QFont("Sans", 11, QFont.Weight.Bold))
            width_label.setMinimumWidth(60)
            tape_item_layout.addWidget(width_label)

            # Product code
            code_label = QLabel(product_code)
            code_label.setFont(QFont("Monospace", 10, QFont.Weight.Bold))
            code_label.setStyleSheet("background-color: #f0f0f0; padding: 5px; border-radius: 3px;")
            code_label.setMinimumWidth(100)
            tape_item_layout.addWidget(code_label)

            # Description
            desc_label = QLabel(description)
            desc_label.setStyleSheet("color: #555;")
            tape_item_layout.addWidget(desc_label, 1)

            tape_layout.addWidget(tape_item)

        # Note about compatibility
        note_label = QLabel(
            "Note: This application is validated only for the Brother QL-700 printer. "
            "Use with other Brother QL models at your own risk."
        )
        note_label.setWordWrap(True)
        note_label.setStyleSheet("padding: 10px; margin-top: 10px; color: #666; font-style: italic;")
        tape_layout.addWidget(note_label)

        tape_group.setLayout(tape_layout)
        content_layout.addWidget(tape_group)

        # Features
        features_group = QGroupBox("Key Features")
        features_layout = QVBoxLayout()
        features_list = [
            "QR Code + Text labels for inventory tracking",
            "Text-only labels without QR codes",
            "Batch mode for printing up to 10 different labels",
            "Live preview before printing",
            "Support for multiple tape widths (29mm, 38mm, 50mm, 62mm)",
            "Keyboard shortcuts for faster workflow",
            "Customizable fonts and font sizes (40-250pt)",
            "Auto-increment label numbers"
        ]

        for feature in features_list:
            feature_label = QLabel(f"• {feature}")
            feature_label.setWordWrap(True)
            feature_label.setStyleSheet("padding: 3px 10px;")
            features_layout.addWidget(feature_label)

        features_group.setLayout(features_layout)
        content_layout.addWidget(features_group)

        # Requirements
        req_group = QGroupBox("System Requirements")
        req_layout = QVBoxLayout()
        req_text = QLabel(
            "<b>Printer:</b> Brother QL-700 (validated)<br>"
            "<b>Connection:</b> USB (ID: 04f9:2042)<br>"
            "<b>Tape:</b> Continuous (endless) tape - DK-22210 or compatible<br>"
            "<b>Operating System:</b> Linux (tested on Ubuntu 25.10)"
        )
        req_text.setWordWrap(True)
        req_text.setStyleSheet("padding: 10px;")
        req_layout.addWidget(req_text)
        req_group.setLayout(req_layout)
        content_layout.addWidget(req_group)

        # Credits and Links
        credits_group = QGroupBox("Credits & Information")
        credits_layout = QVBoxLayout()
        credits_text = QLabel(
            "<b>Developer:</b> Daniel Rosehill<br>"
            "<b>GitHub:</b> <a href='https://github.com/danielrosehill/QL700-Label-Printer-GUI'>"
            "github.com/danielrosehill/QL700-Label-Printer-GUI</a><br>"
            "<b>License:</b> Open Source<br><br>"
            "Built with PyQt6, Pillow, qrcode, and brother_ql"
        )
        credits_text.setOpenExternalLinks(True)
        credits_text.setWordWrap(True)
        credits_text.setStyleSheet("padding: 10px;")
        credits_layout.addWidget(credits_text)
        credits_group.setLayout(credits_layout)
        content_layout.addWidget(credits_group)

        # Add stretch to push content to top
        content_layout.addStretch()

        # Set content widget to scroll area
        scroll.setWidget(content)
        layout.addWidget(scroll)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Brother QL Label Printer")

    window = LabelPrinterGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
