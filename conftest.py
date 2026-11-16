"""Shared pytest fixtures. Having this file at the repo root also puts `src` on the import path."""
import shutil
from pathlib import Path

import pytest

from src.config import load_config

ROOT = Path(__file__).resolve().parent


@pytest.fixture
def cfg(tmp_path):
    """A copy of the real config whose database and outputs live in a temp folder."""
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    (tmp_path / "data").mkdir()
    shutil.copy(ROOT / "data" / "inventory_seed.csv", tmp_path / "data" / "inventory_seed.csv")
    return load_config(tmp_path / "config.yaml")
