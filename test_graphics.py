"""Локальный скрипт для визуальной проверки раскладки этикетки."""

from pathlib import Path

from PIL import Image, ImageDraw

from bot.services.image_processor import LabelGenerator

ASSETS_DIR = Path("data/test_assets")
PRINT_OUTPUT_PATH = Path("test_label_print.png")


def create_placeholder(path: Path, size: tuple[int, int], color: tuple[int, int, int], label: str) -> None:
    image = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(image)
    bbox = draw.textbbox((0, 0), label)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size[0] - text_width) // 2
    y = (size[1] - text_height) // 2
    draw.text((x, y), label, fill="white")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def main() -> None:
    logo_path = Path("data/assets/logo.png")
    screenshot_path = ASSETS_DIR / "screenshot.png"
    qr_ios_path = ASSETS_DIR / "qr_ios.png"
    qr_android_path = ASSETS_DIR / "qr_android.png"

    create_placeholder(screenshot_path, (700, 500), (40, 160, 90), "SCREENSHOT")

    generator = LabelGenerator()
    preview_path = generator.generate_label(
        screenshot_path=str(screenshot_path),
        order_numbers_text="ORD-100245\nORD-100246",
        logo_path=str(logo_path),
        qr_ios_path=str(qr_ios_path),
        qr_android_path=str(qr_android_path),
        output_path=str(PRINT_OUTPUT_PATH),
    )

    print(f"Цветной макет: {preview_path}")
    print(f"ЧБ для печати: {PRINT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
