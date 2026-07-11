from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Optional per-person override: copy local_paths.example.py to local_paths.py (gitignored)
# and set RAW/PROCESSED there if your data doesn't live at ROOT/data/raw and
# ROOT/data/processed - e.g. it's on a different drive or shared folder. Most people won't
# need this and can leave local_paths.py absent.
try:
    from local_paths import PROCESSED as _PROCESSED_OVERRIDE
    from local_paths import RAW as _RAW_OVERRIDE
except ImportError:
    _RAW_OVERRIDE = _PROCESSED_OVERRIDE = None

RAW = Path(_RAW_OVERRIDE) if _RAW_OVERRIDE else ROOT / "data" / "raw"
PROCESSED = Path(_PROCESSED_OVERRIDE) if _PROCESSED_OVERRIDE else ROOT / "data" / "processed"
RESULTS = ROOT / "results"

PROCESSED.mkdir(parents=True, exist_ok=True)
RESULTS.mkdir(parents=True, exist_ok=True)


def savefig(fig, subfolder: str, name: str, dpi: int = 200) -> Path:
    out_dir = RESULTS / subfolder
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / name
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    return out_path
