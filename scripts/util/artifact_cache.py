"""Read/write Pydantic JSON artifacts for pipeline stages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def read_json_model(path: Path, model: type[T], *, use_cache: bool) -> T | None:
    if not use_cache or not path.is_file():
        return None
    return model.model_validate(json.loads(path.read_text(encoding="utf-8")))


def write_json_model(path: Path, value: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value.model_dump(by_alias=True), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
