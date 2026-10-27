"""Current-format compatibility; the frozen 0.9 validator stays independent."""
from pathlib import Path

CURRENT_VERSION = (Path(__file__).resolve().parents[1] / 'VERSION').read_text(encoding='utf-8').strip()
SUPPORTED_CURRENT_VERSIONS = {CURRENT_VERSION, '0.10.0-candidate.1'}
