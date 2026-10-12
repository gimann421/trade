"""Load Alpaca paper keys from config/.env without exposing them.

Keys are read with dotenv_values rather than load_dotenv, so they never land in
os.environ (and so never leak into subprocesses or environment dumps). If
config/.env is missing or sets neither key, the same variable names are read
from the process environment instead (e.g. secrets injected into a cloud
session or CI). The two keys always come from one source, never mixed. The
PaperKeys repr is redacted so an accidental print or traceback can't show them.
"""

import os

from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / "config" / ".env"


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class PaperKeys:
    api_key: str = field(repr=False)
    secret_key: str = field(repr=False)

    def __repr__(self) -> str:
        return "PaperKeys(<redacted>)"

    __str__ = __repr__


KEY_NAMES = ("ALPACA_PAPER_API_KEY", "ALPACA_PAPER_SECRET_KEY")


def _read(values) -> tuple[str, str]:
    return tuple((values.get(name) or "").strip() for name in KEY_NAMES)


def load_paper_keys(env_path: Path = ENV_PATH) -> PaperKeys:
    keys, source = ("", ""), env_path.name
    if env_path.exists():
        keys = _read(dotenv_values(env_path))
    if not any(keys):
        keys, source = _read(os.environ), "environment"
        if not any(keys):
            raise ConfigError(f"no paper keys: {env_path} is missing or empty and "
                              f"{' / '.join(KEY_NAMES)} are not set in the environment")
    missing = [name for name, v in zip(KEY_NAMES, keys) if not v]
    if missing:
        raise ConfigError(f"missing in {source}: {', '.join(missing)}")
    return PaperKeys(*keys)
