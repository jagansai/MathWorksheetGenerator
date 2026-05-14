"""Modal progress dialog shown during worksheet generation."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QLabel, QProgressBar, QVBoxLayout


class ProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Generating Worksheet')
        self.setModal(True)
        self.setFixedSize(380, 110)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        self._label = QLabel('Starting...')
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)

        self._bar = QProgressBar()
        self._bar.setRange(0, 0)  # indeterminate spinner

        layout.addWidget(self._label)
        layout.addWidget(self._bar)

    def set_step(self, message: str):
        self._label.setText(message)
