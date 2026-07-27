#%%
"""Small helpers for transitioning generated CSV artifacts to gzip storage."""

from pathlib import Path


def prefer_compressed_csv_path(preferred_path: Path) -> Path:
    """Return gzip CSV when present, otherwise its legacy plain-CSV counterpart."""
    path = Path(preferred_path)
    if path.name.lower().endswith(".csv.gz"):
        if path.exists():
            return path
        plain_path = path.with_suffix("")
        if plain_path.exists():
            return plain_path
    elif path.name.lower().endswith(".csv"):
        compressed_path = path.with_name(f"{path.name}.gz")
        if compressed_path.exists():
            return compressed_path
    return path


#%%
