from functools import lru_cache
from pathlib import Path

PROMPTS_DIRECTORY = Path(__file__).resolve().parent


@lru_cache
def load_prompt(name: str) -> str:
    return (PROMPTS_DIRECTORY / f"{name}.txt").read_text(encoding="utf-8")
