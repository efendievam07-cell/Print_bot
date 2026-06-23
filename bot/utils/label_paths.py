import uuid
from datetime import datetime
from pathlib import Path

LABELS_DIR = Path("data/labels")


def build_label_output_path(job_id: uuid.UUID, created_at: datetime) -> Path:
    date_dir = LABELS_DIR / f"{created_at:%Y}" / f"{created_at:%m}" / f"{created_at:%d}"
    date_dir.mkdir(parents=True, exist_ok=True)
    return date_dir / f"{job_id}.png"
