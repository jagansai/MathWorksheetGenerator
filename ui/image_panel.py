"""Image upload panel with drag-and-drop, reordering, and preview support."""
import os
from io import BytesIO

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from utils.logger import setup_logger

logger = setup_logger(__name__)

_IMG_EXTS = {".jpg", ".jpeg", ".png"}
_PDF_EXTS = {".pdf"}
_ACCEPTED = _IMG_EXTS | _PDF_EXTS
_THUMB_W, _THUMB_H = 100, 90



_STYLE_IDLE = """
    QLabel {
        border: 2px dashed #aaaaaa;
        border-radius: 8px;
        background: #f8f8f8;
        color: #888888;
        font-size: 13px;
    }
"""
_STYLE_HOVER = """
    QLabel {
        border: 2px dashed #4a90d9;
        border-radius: 8px;
        background: #eef4ff;
        color: #4a90d9;
        font-size: 13px;
    }
"""
_STYLE_DISABLED = """
    QLabel {
        border: 2px dashed #cccccc;
        border-radius: 8px;
        background: #f2f2f2;
        color: #bbbbbb;
        font-size: 13px;
    }
"""


class _ThumbCard(QFrame):
    """Thumbnail card with remove, move-left/right, and preview buttons."""

    remove_requested     = pyqtSignal(str)
    move_left_requested  = pyqtSignal(str)
    move_right_requested = pyqtSignal(str)
    preview_requested    = pyqtSignal(str)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path
        self.setFixedWidth(120)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { border: 1px solid #cccccc; border-radius: 5px; background: #fafafa; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # top row: remove button
        remove_btn = QPushButton("x")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setToolTip("Remove")
        remove_btn.setStyleSheet(
            "QPushButton { background: #e57373; color: white; border-radius: 10px;"
            " font-weight: bold; border: none; font-size: 13px; }"
            "QPushButton:hover { background: #c62828; }"
        )
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self._path))

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.addStretch()
        btn_row.addWidget(remove_btn)
        layout.addLayout(btn_row)

        # preview area
        ext = os.path.splitext(path)[1].lower()
        if ext in _PDF_EXTS:
            preview_widget = QLabel("PDF")
            preview_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview_widget.setFixedHeight(_THUMB_H)
            preview_widget.setStyleSheet(
                "QLabel { border: none; background: #ffebee; color: #c62828;"
                " font-size: 24px; font-weight: bold; border-radius: 6px; }"
            )
        else:
            preview_widget = QLabel()
            preview_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap = QPixmap(path).scaled(
                _THUMB_W, _THUMB_H,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            preview_widget.setPixmap(pixmap)
            preview_widget.setFixedHeight(_THUMB_H)
            preview_widget.setStyleSheet("border: none;")

        preview_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        preview_widget.setToolTip("Click to preview")
        preview_widget.mousePressEvent = lambda _e: self.preview_requested.emit(self._path)
        layout.addWidget(preview_widget)

        # file name truncated
        name = QLabel(os.path.basename(path))
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setStyleSheet("border: none; color: #555; font-size: 9px;")
        name.setMaximumWidth(112)
        metrics = name.fontMetrics()
        name.setText(
            metrics.elidedText(os.path.basename(path), Qt.TextElideMode.ElideMiddle, 112)
        )
        layout.addWidget(name)

        # move left / right buttons
        _arrow_style = (
            "QPushButton { background: #e0e0e0; border-radius: 3px; border: none;"
            " font-size: 9px; padding: 0px; }"
            "QPushButton:hover { background: #bdbdbd; }"
            "QPushButton:disabled { color: #c0c0c0; background: #f0f0f0; }"
        )
        self._left_btn = QPushButton("<")
        self._left_btn.setFixedSize(28, 20)
        self._left_btn.setToolTip("Move left")
        self._left_btn.setStyleSheet(_arrow_style)
        self._left_btn.clicked.connect(lambda: self.move_left_requested.emit(self._path))

        self._right_btn = QPushButton(">")
        self._right_btn.setFixedSize(28, 20)
        self._right_btn.setToolTip("Move right")
        self._right_btn.setStyleSheet(_arrow_style)
        self._right_btn.clicked.connect(lambda: self.move_right_requested.emit(self._path))

        move_row = QHBoxLayout()
        move_row.setContentsMargins(0, 2, 0, 0)
        move_row.setSpacing(2)
        move_row.addWidget(self._left_btn)
        move_row.addStretch()
        move_row.addWidget(self._right_btn)
        layout.addLayout(move_row)

    def set_move_enabled(self, left: bool, right: bool):
        self._left_btn.setEnabled(left)
        self._right_btn.setEnabled(right)


class _PreviewDialog(QDialog):
    """Full-size preview dialog for an image or PDF."""

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        ext = os.path.splitext(path)[1].lower()
        self.setWindowTitle(f"Preview - {os.path.basename(path)}")
        self.setMinimumSize(640, 520)
        self.resize(820, 680)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        if ext in _IMG_EXTS:
            self._build_image_preview(path, layout)
        else:
            self._build_pdf_preview(path, layout)

        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(90)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

    def _build_image_preview(self, path: str, layout):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        lbl = QLabel()
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(path)
        scaled = pixmap.scaled(
            780, 580,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        lbl.setPixmap(scaled)
        scroll.setWidget(lbl)
        layout.addWidget(scroll)

    def _build_pdf_preview(self, path: str, layout):
        try:
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(path)
            n_pages = len(doc)

            self._pdf_pages = []
            self._current_page = 0

            for i in range(n_pages):
                page = doc[i]
                bitmap = page.render(scale=1.5)
                pil_img = bitmap.to_pil()
                buf = BytesIO()
                pil_img.save(buf, format="PNG")
                buf.seek(0)
                pix = QPixmap()
                pix.loadFromData(buf.getvalue())
                self._pdf_pages.append(pix)

            doc.close()

            self._scroll = QScrollArea()
            self._scroll.setWidgetResizable(True)
            self._img_lbl = QLabel()
            self._img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._scroll.setWidget(self._img_lbl)

            self._page_info = QLabel(f"Page 1 of {n_pages}")
            self._page_info.setAlignment(Qt.AlignmentFlag.AlignCenter)

            prev_btn = QPushButton("< Previous")
            prev_btn.clicked.connect(self._prev_page)
            next_btn = QPushButton("Next >")
            next_btn.clicked.connect(self._next_page)

            nav_row = QHBoxLayout()
            nav_row.addWidget(prev_btn)
            nav_row.addStretch()
            nav_row.addWidget(self._page_info)
            nav_row.addStretch()
            nav_row.addWidget(next_btn)

            self._show_page(0)
            layout.addWidget(self._scroll)
            layout.addLayout(nav_row)

        except Exception as exc:
            lbl = QLabel(
                f"PDF preview unavailable:\n{exc}\n\n"
                "(The file will still be analyzed normally.)"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            layout.addWidget(lbl)

    def _show_page(self, idx: int):
        self._current_page = idx
        pix = self._pdf_pages[idx]
        scaled = pix.scaled(
            780, 580,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._img_lbl.setPixmap(scaled)
        self._page_info.setText(f"Page {idx + 1} of {len(self._pdf_pages)}")

    def _prev_page(self):
        if self._current_page > 0:
            self._show_page(self._current_page - 1)

    def _next_page(self):
        if self._current_page < len(self._pdf_pages) - 1:
            self._show_page(self._current_page + 1)


class ImagePanel(QWidget):
    """Multi-image panel with drag-and-drop, reordering, and preview."""

    images_changed    = pyqtSignal(list)
    analyze_requested = pyqtSignal(list)
    subject_changed   = pyqtSignal(str)

    # Legacy signals kept for compatibility
    image_loaded  = pyqtSignal(str)
    image_cleared = pyqtSignal()

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self._config = config_manager
        self._image_paths: list[str] = []
        self._setup_ui()
        self.setAcceptDrops(True)

    def _setup_ui(self):
        self.setMinimumWidth(260)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ---- Subject selector ----
        subj_row = QHBoxLayout()
        subj_row.setSpacing(6)
        subj_row.addWidget(QLabel('Subject:'))
        self.subject_combo = QComboBox()
        self.subject_combo.addItem('\u2014 Select a subject \u2014')
        for s in (self._config.get('subjects') or ['Mathematics']):
            self.subject_combo.addItem(s)
        self.subject_combo.currentIndexChanged.connect(self._on_subject_changed)
        subj_row.addWidget(self.subject_combo)
        subj_row.addStretch()

        self._drop_label = QLabel('Select a subject above\nbefore uploading files')
        self._drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop_label.setWordWrap(True)
        self._drop_label.setMinimumHeight(160)
        self._drop_label.setStyleSheet(_STYLE_DISABLED)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFixedHeight(200)
        self._scroll.hide()

        self._thumb_container = QWidget()
        self._thumb_layout = QHBoxLayout(self._thumb_container)
        self._thumb_layout.setContentsMargins(4, 4, 4, 4)
        self._thumb_layout.setSpacing(8)
        self._thumb_layout.addStretch()
        self._scroll.setWidget(self._thumb_container)

        self._reorder_hint = QLabel("Use < > on each card to reorder  *  Click thumbnail to preview")
        self._reorder_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._reorder_hint.setStyleSheet("color: #777; font-size: 9px;")
        self._reorder_hint.hide()

        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet("color: #555; font-size: 10px;")
        self._status_label.hide()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self._browse_btn = QPushButton("Add Files...")
        self._browse_btn.setEnabled(False)
        self._browse_btn.clicked.connect(self._browse)

        self._analyze_btn = QPushButton("Analyze Files")
        self._analyze_btn.setStyleSheet(
            "QPushButton { background-color: #1565c0; color: white; font-weight: bold;"
            " border-radius: 4px; padding: 4px 8px; }"
            "QPushButton:hover { background-color: #1976d2; }"
            "QPushButton:pressed { background-color: #0d47a1; }"
            "QPushButton:disabled { background-color: #b0b0b0; color: #e0e0e0; }"
        )
        self._analyze_btn.clicked.connect(
            lambda: self.analyze_requested.emit(list(self._image_paths))
        )
        self._analyze_btn.hide()

        btn_row.addWidget(self._browse_btn)
        btn_row.addWidget(self._analyze_btn)

        self._clear_all_btn = QPushButton("Clear All")
        self._clear_all_btn.setStyleSheet("color: #cc0000;")
        self._clear_all_btn.clicked.connect(self._clear_all)
        self._clear_all_btn.hide()

        layout.addLayout(subj_row)
        layout.addWidget(self._drop_label)
        layout.addWidget(self._scroll)
        layout.addWidget(self._reorder_hint)
        layout.addWidget(self._status_label)
        layout.addLayout(btn_row)
        layout.addWidget(self._clear_all_btn)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def image_paths(self) -> list[str]:
        return list(self._image_paths)

    @property
    def image_path(self) -> "str | None":
        return self._image_paths[0] if self._image_paths else None

    def set_analyzing(self, analyzing: bool):
        if analyzing:
            self._status_label.setText("Analyzing...")
            self._status_label.show()
            self._analyze_btn.setEnabled(False)
            self._analyze_btn.setText("Analyzing...")
        else:
            self._update_status()
            self._analyze_btn.setEnabled(True)
            self._analyze_btn.setText("Analyze Files")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _browse(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Files", "",
            "Supported Files (*.jpg *.jpeg *.png *.pdf);;Images (*.jpg *.jpeg *.png);;PDFs (*.pdf)"
        )
        for path in paths:
            self._add_image(path)

    def get_subject(self) -> str:
        """Return the selected subject name, or '' when no subject is selected."""
        return (
            ''
            if self.subject_combo.currentIndex() == 0
            else self.subject_combo.currentText()
        )

    def _set_upload_enabled(self, enabled: bool):
        """Enable or disable upload controls based on whether a subject is selected."""
        self._browse_btn.setEnabled(enabled)
        if enabled and self._image_paths:
            self._analyze_btn.setEnabled(True)
        elif not enabled and self._analyze_btn.isVisible():
            self._analyze_btn.setEnabled(False)
        # Only update the drop-zone appearance when no files are currently loaded
        if not self._image_paths:
            if enabled:
                self._drop_label.setText('Drop images or PDFs here\n\nor click  Add Files')
                self._drop_label.setStyleSheet(_STYLE_IDLE)
            else:
                self._drop_label.setText('Select a subject above\nbefore uploading files')
                self._drop_label.setStyleSheet(_STYLE_DISABLED)

    def _on_subject_changed(self, index: int):
        self._set_upload_enabled(index > 0)
        self.subject_changed.emit(self.get_subject())

    def _add_image(self, path: str):
        if self.subject_combo.currentIndex() == 0:  # no subject selected
            return
        ext = os.path.splitext(path)[1].lower()
        if ext not in _ACCEPTED:
            return
        if path in self._image_paths:
            return

        # --- file-count guard ---
        max_files = self._config.get('max_files', 10)
        if len(self._image_paths) >= max_files:
            QMessageBox.warning(
                self,
                'Too Many Files',
                f'You can upload up to {max_files} files at a time.\n'
                'Remove some files first, then add more.',
            )
            return

        # --- per-file size guard ---
        size_mb = os.path.getsize(path) / (1024 * 1024)
        limit_mb = (
            self._config.get('max_pdf_size_mb', 25)
            if ext in _PDF_EXTS
            else self._config.get('max_image_size_mb', 8)
        )
        if size_mb > limit_mb:
            type_label = 'PDF' if ext in _PDF_EXTS else 'image'
            QMessageBox.warning(
                self,
                'File Too Large',
                f'"{os.path.basename(path)}" is {size_mb:.1f} MB — '
                f'the limit for {type_label}s is {limit_mb} MB.\n\n'
                'Please use a smaller or compressed file.',
            )
            return

        self._image_paths.append(path)
        self._rebuild_thumbnails()

        self._drop_label.hide()
        self._scroll.show()
        self._reorder_hint.show()
        self._status_label.show()
        self._analyze_btn.show()
        self._clear_all_btn.show()
        self._update_status()

        logger.debug("Image added: %s", path)
        self.image_loaded.emit(path)
        self.images_changed.emit(list(self._image_paths))

    def _remove_image(self, path: str):
        if path not in self._image_paths:
            return
        self._image_paths.remove(path)
        self._rebuild_thumbnails()

        if not self._image_paths:
            self._scroll.hide()
            self._reorder_hint.hide()
            self._status_label.hide()
            self._analyze_btn.hide()
            self._clear_all_btn.hide()
            self._drop_label.setStyleSheet(_STYLE_IDLE)
            self._drop_label.show()
            self.image_cleared.emit()
        else:
            self._update_status()

        self.images_changed.emit(list(self._image_paths))

    def _move_image(self, path: str, direction: int):
        if path not in self._image_paths:
            return
        idx = self._image_paths.index(path)
        new_idx = idx + direction
        if 0 <= new_idx < len(self._image_paths):
            self._image_paths[idx], self._image_paths[new_idx] = (
                self._image_paths[new_idx], self._image_paths[idx]
            )
            self._rebuild_thumbnails()
            self.images_changed.emit(list(self._image_paths))

    def _clear_all(self):
        self._image_paths.clear()
        self._rebuild_thumbnails()

        self._scroll.hide()
        self._reorder_hint.hide()
        self._status_label.hide()
        self._analyze_btn.hide()
        self._clear_all_btn.hide()
        self._drop_label.setStyleSheet(_STYLE_IDLE)
        self._drop_label.show()
        self.image_cleared.emit()
        self.images_changed.emit([])

    def _rebuild_thumbnails(self):
        for i in reversed(range(self._thumb_layout.count())):
            item = self._thumb_layout.itemAt(i)
            if item and isinstance(item.widget(), _ThumbCard):
                w = item.widget()
                self._thumb_layout.removeWidget(w)
                w.deleteLater()

        n = len(self._image_paths)
        for pos, path in enumerate(self._image_paths):
            card = _ThumbCard(path)
            card.set_move_enabled(left=(pos > 0), right=(pos < n - 1))
            card.remove_requested.connect(self._remove_image)
            card.move_left_requested.connect(lambda p: self._move_image(p, -1))
            card.move_right_requested.connect(lambda p: self._move_image(p, +1))
            card.preview_requested.connect(self._open_preview)
            self._thumb_layout.insertWidget(self._thumb_layout.count() - 1, card)

    def _open_preview(self, path: str):
        dlg = _PreviewDialog(path, parent=self)
        dlg.exec()

    def _update_status(self):
        imgs = sum(1 for p in self._image_paths if os.path.splitext(p)[1].lower() in _IMG_EXTS)
        pdfs = sum(1 for p in self._image_paths if os.path.splitext(p)[1].lower() in _PDF_EXTS)
        parts = []
        if imgs:
            parts.append(f"{imgs} image{'s' if imgs != 1 else ''}")
        if pdfs:
            parts.append(f"{pdfs} PDF{'s' if pdfs != 1 else ''}")
        self._status_label.setText(", ".join(parts) + " selected")

    # ------------------------------------------------------------------
    # Drag and drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent):  # type: ignore[override]
        if self.subject_combo.currentIndex() == 0:
            return
        if event.mimeData().hasUrls():
            accepted = any(
                os.path.splitext(u.toLocalFile())[1].lower() in _ACCEPTED
                for u in event.mimeData().urls()
            )
            if accepted:
                event.acceptProposedAction()
                self._drop_label.setStyleSheet(_STYLE_HOVER)

    def dragLeaveEvent(self, event):  # type: ignore[override]
        if self.subject_combo.currentIndex() > 0:
            self._drop_label.setStyleSheet(_STYLE_IDLE)
        else:
            self._drop_label.setStyleSheet(_STYLE_DISABLED)

    def dropEvent(self, event: QDropEvent):  # type: ignore[override]
        if self.subject_combo.currentIndex() == 0:
            return
        self._drop_label.setStyleSheet(_STYLE_IDLE)
        urls = event.mimeData().urls()
        if urls:
            event.acceptProposedAction()
            for url in urls:
                self._add_image(url.toLocalFile())
