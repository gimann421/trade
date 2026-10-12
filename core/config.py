"""Load Alpaca paper keys from config/.env without exposing them.

Keys are read with dotenv_values rather than load_dotenv, so they never land in
os.environ (and so never leak into subprocesses or environment dumps). The
PaperKeys repr is redacted so an accidental print or traceback can't show them.
"""

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


def load_paper_keys(env_path: Path = ENV_PATH) -> PaperKeys:
    if not env_path.exists():
        raise ConfigError(f"{env_path} not found; copy config/.env.example and add your paper keys")
    values = dotenv_values(env_path)
    api_key = (values.get("ALPACA_PAPER_API_KEY") or "").strip()
    secret_key = (values.get("ALPACA_PAPER_SECRET_KEY") or "").strip()
    missing = [name for name, v in (("ALPACA_PAPER_API_KEY", api_key),
                                    ("ALPACA_PAPER_SECRET_KEY", secret_key)) if not v]
    if missing:
        raise ConfigError(f"missing in {env_path.name}: {', '.join(missing)}")
    return PaperKeys(api_key, secret_key)
