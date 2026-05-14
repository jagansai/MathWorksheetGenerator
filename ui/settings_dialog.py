"""Settings dialog — Groq API key and model selection."""
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from utils.logger import setup_logger

logger = setup_logger(__name__)

_TEXT_MODELS = [
    'llama-3.3-70b-versatile',
    'llama-3.1-70b-versatile',
    'llama-3.1-8b-instant',
    'mixtral-8x7b-32768',
    'gemma2-9b-it',
]

_VISION_MODELS = [
    'meta-llama/llama-4-scout-17b-16e-instruct',
    'llama-3.2-90b-vision-preview',
    'llama-3.2-11b-vision-preview',
]


class SettingsDialog(QDialog):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self._config = config_manager
        self.setWindowTitle('Settings')
        self.setMinimumWidth(500)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        # API key
        key_label = QLabel(
            '<b>Groq API Key</b><br>'
            '<small>Get a free key at '
            '<a href="https://console.groq.com">console.groq.com</a></small>'
        )
        key_label.setOpenExternalLinks(True)
        layout.addWidget(key_label)

        key_row = QHBoxLayout()
        self._key_edit = QLineEdit()
        self._key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_edit.setPlaceholderText('gsk_...')
        self._key_edit.setText(self._config.get('groq_api_key', ''))

        self._show_btn = QPushButton('Show')
        self._show_btn.setFixedWidth(60)
        self._show_btn.setCheckable(True)
        self._show_btn.toggled.connect(self._toggle_visibility)

        key_row.addWidget(self._key_edit)
        key_row.addWidget(self._show_btn)
        layout.addLayout(key_row)

        # Model selectors
        form = QFormLayout()
        form.setSpacing(10)

        self._text_combo = QComboBox()
        self._text_combo.addItems(_TEXT_MODELS)
        self._text_combo.setEditable(True)
        self._set_combo(self._text_combo, self._config.get('text_model', _TEXT_MODELS[0]))

        self._vision_combo = QComboBox()
        self._vision_combo.addItems(_VISION_MODELS)
        self._vision_combo.setEditable(True)
        self._set_combo(self._vision_combo, self._config.get('vision_model', _VISION_MODELS[0]))

        form.addRow('Text model (question generation):', self._text_combo)
        form.addRow('Vision model (image analysis):', self._vision_combo)
        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _set_combo(combo: QComboBox, value: str):
        idx = combo.findText(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.setCurrentText(value)

    def _toggle_visibility(self, checked: bool):
        self._key_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        self._show_btn.setText('Hide' if checked else 'Show')

    def _save_and_accept(self):
        self._config.set('groq_api_key', self._key_edit.text().strip())
        self._config.set('text_model', self._text_combo.currentText().strip())
        self._config.set('vision_model', self._vision_combo.currentText().strip())
        self._config.save()
        logger.info('Settings saved.')
        self.accept()
