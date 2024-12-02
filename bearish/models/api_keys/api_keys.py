import json
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, Field


class SourceApiKeys(BaseModel):
    keys: Dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_file(cls, api_keys_path: Optional[Path] = None) -> "SourceApiKeys":
        if api_keys_path is None:
            return cls()
        if not api_keys_path.exists():
            raise FileNotFoundError(f"File not found: {api_keys_path}")
        try:
            return cls(keys=json.loads(api_keys_path.read_text()))
        except Exception as e:
            raise ValueError(f"Invalid JSON in file {api_keys_path}: {e}") from e
