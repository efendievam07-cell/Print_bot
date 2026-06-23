from pathlib import Path

from PIL import Image, ImageDraw

ASSET_SPECS: dict[str, tuple[tuple[int, int], tuple[int, int, int], str]] = {
    "qr_ios.png": ((200, 200), (200, 50, 50), "iOS"),
    "qr_android.png": ((200, 200), (220, 120, 30), "Android"),
}


def ensure_default_assets(assets_dir: Path = Path("data/assets")) -> None:
    assets_dir.mkdir(parents=True, exist_ok=True)

    for filename, (size, color, label) in ASSET_SPECS.items():
        asset_path = assets_dir / filename
        if asset_path.exists():
            continue

        image = Image.new("RGB", size, color)
        draw = ImageDraw.Draw(image)
        bbox = draw.textbbox((0, 0), label)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (size[0] - text_width) // 2
        y = (size[1] - text_height) // 2
        draw.text((x, y), label, fill="white")
        image.save(asset_path)
