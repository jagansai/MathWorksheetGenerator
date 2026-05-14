"""Configuration management for Math Worksheet Generator."""
import json
import os
import sys

from dotenv import dotenv_values, set_key

from utils.logger import setup_logger

logger = setup_logger(__name__)

# groq_api_key is intentionally absent here — it lives in .env, not config.json
DEFAULT_CONFIG = {
    "text_model": "llama-3.3-70b-versatile",
    "vision_model": "meta-llama/llama-4-scout-17b-16e-instruct",
    "output_directory": "",
    "default_num_questions": 10,
    "default_difficulty": "Intermediate",
}


def _get_app_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ConfigManager:
    def __init__(self):
        self._app_dir = _get_app_dir()
        self._config_path = os.path.join(self._app_dir, 'config', 'config.json')
        self._env_path = os.path.join(self._app_dir, '.env')
        self._config = dict(DEFAULT_CONFIG)
        self._load()

    def _load(self):
        # Load non-secret settings from config.json
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                # Accept legacy configs that stored the key in JSON
                saved.pop('groq_api_key', None)
                self._config.update(saved)
                logger.debug('Config loaded from %s', self._config_path)
            except Exception as e:
                logger.error('Failed to load config: %s', e)

        # Load GROQ_API_KEY from .env (creates an empty file if missing)
        if not os.path.exists(self._env_path):
            open(self._env_path, 'w').close()  # create empty .env
            logger.debug('Created empty .env at %s', self._env_path)
        env_vals = dotenv_values(self._env_path)
        self._config['groq_api_key'] = env_vals.get('GROQ_API_KEY', '')
        logger.debug('GROQ_API_KEY loaded from .env (%s)',
                     'set' if self._config['groq_api_key'] else 'not set')

    def save(self):
        # Persist non-secret settings to config.json (never write the API key there)
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        try:
            json_data = {k: v for k, v in self._config.items() if k != 'groq_api_key'}
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=4)
            logger.debug('Config saved to %s', self._config_path)
        except Exception as e:
            logger.error('Failed to save config: %s', e)

        # Persist the API key to .env
        try:
            set_key(self._env_path, 'GROQ_API_KEY', self._config.get('groq_api_key', ''))
            logger.debug('GROQ_API_KEY written to .env')
        except Exception as e:
            logger.error('Failed to write .env: %s', e)

    def get(self, key: str, default=None):
        return self._config.get(key, default)

    def set(self, key: str, value):
        self._config[key] = value

    def get_output_directory(self) -> str:
        """Return configured output dir, falling back to ~/Documents/WorksheetApp."""
        d = self._config.get('output_directory', '').strip()
        if d and os.path.isdir(d):
            return d
        docs = os.path.join(os.path.expanduser('~'), 'Documents', 'WorksheetApp')
        os.makedirs(docs, exist_ok=True)
        return docs
