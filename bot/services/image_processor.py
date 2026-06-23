from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

logger = logging.getLogger(__name__)


class LabelGenerator:
    """Генератор этикеток для термопринтера 203 DPI (100×150 мм)."""

    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    FONT_PATH = PROJECT_ROOT / "data" / "assets" / "font.ttf"
    DEFAULT_LOGO_PATH = PROJECT_ROOT / "data" / "assets" / "logo.png"
    DEFAULT_QR_ANDROID_PATH = PROJECT_ROOT / "data" / "assets" / "qr_android.png"
    DEFAULT_QR_IOS_PATH = PROJECT_ROOT / "data" / "assets" / "qr_ios.png"

    LABEL_WIDTH = 800
    LABEL_HEIGHT = 1200
    DPI = 203

    MARGIN = 40
    GAP = 20
    SECTION_GAP = 24

    LOGO_MAX_WIDTH = LABEL_WIDTH - 2 * MARGIN
    LOGO_MAX_HEIGHT = 140

    QR_SIZE = 160
    QR_GAP = 40

    ORDER_FONT_SIZE = 40
    ORDER_MIN_FONT_SIZE = 24
    ORDER_LABEL_PREFIX = "Номера заказов: "

    PRINT_CONTRAST = 1.2

    def generate_label(
        self,
        screenshot_path: str,
        order_numbers_text: str,
        logo_path: str,
        qr_ios_path: str,
        qr_android_path: str,
        output_path: str,
    ) -> str:
        color_canvas = self._build_color_canvas(
            screenshot_path=screenshot_path,
            order_numbers_text=order_numbers_text,
            logo_path=logo_path,
            qr_android_path=qr_android_path,
            qr_ios_path=qr_ios_path,
        )

        print_path = Path(output_path)
        print_path.parent.mkdir(parents=True, exist_ok=True)

        preview_path = print_path.with_name(f"{print_path.stem}_preview{print_path.suffix}")
        color_canvas.save(preview_path)

        printable = self.convert_to_printable_bw(color_canvas)
        printable.save(print_path)

        return str(preview_path)

    def convert_to_printable_bw(self, image: Image.Image) -> Image.Image:
        rgb = image.convert("RGB")
        gray = rgb.convert("L")
        gray = ImageEnhance.Contrast(gray).enhance(self.PRINT_CONTRAST)
        return gray.convert("1", dither=Image.Dither.FLOYDSTEINBERG)

    def _build_color_canvas(
        self,
        screenshot_path: str,
        order_numbers_text: str,
        logo_path: str,
        qr_android_path: str,
        qr_ios_path: str,
    ) -> Image.Image:
        canvas = Image.new("RGB", (self.LABEL_WIDTH, self.LABEL_HEIGHT), "white")
        draw = ImageDraw.Draw(canvas)

        screenshot = self._load_rgb(screenshot_path)
        qr_android = self._load_color_asset(qr_android_path, self.DEFAULT_QR_ANDROID_PATH)
        qr_ios = self._load_color_asset(qr_ios_path, self.DEFAULT_QR_IOS_PATH)

        y_cursor = self.MARGIN

        logo = self._load_logo(logo_path)
        if logo is not None:
            logo = self._fit_image(logo, self.LOGO_MAX_WIDTH, self.LOGO_MAX_HEIGHT)
            y_cursor = self._paste_centered(canvas, logo, y_cursor) + self.GAP

        if qr_android is not None and qr_ios is not None:
            y_cursor = self._paste_qr_row(canvas, qr_android, qr_ios, y_cursor) + self.SECTION_GAP

        order_text = self._format_order_numbers(order_numbers_text)
        order_font, order_line_height, order_block_height, order_lines = (
            self._resolve_order_text_layout(draw, order_text)
        )

        order_y = self.LABEL_HEIGHT - self.MARGIN - order_block_height
        screenshot_height = max(120, order_y - y_cursor - self.GAP)
        screenshot_width = self.LABEL_WIDTH - 2 * self.MARGIN

        prepared_screenshot = self._prepare_color_screenshot(
            screenshot,
            screenshot_width,
            screenshot_height,
        )
        screenshot_x = self.MARGIN + (screenshot_width - prepared_screenshot.width) // 2
        canvas.paste(prepared_screenshot, (screenshot_x, y_cursor))

        self._draw_centered_order_block(
            draw,
            order_lines,
            order_y,
            order_font,
            order_line_height,
        )

        return canvas

    def _resolve_asset_path(self, path: str, default_path: Path) -> Path:
        candidate = Path(path)
        if candidate.is_file():
            return candidate
        if default_path.is_file():
            return default_path
        return candidate

    def _load_logo(self, logo_path: str) -> Image.Image | None:
        path = self._resolve_asset_path(logo_path, self.DEFAULT_LOGO_PATH)
        if not path.is_file():
            logger.warning("Файл логотипа не найден: %s", path)
            return None

        try:
            return self._load_rgb_with_alpha(path)
        except OSError:
            logger.exception("Не удалось загрузить логотип: %s", path)
            return None

    def _load_color_asset(self, path: str, default_path: Path) -> Image.Image | None:
        resolved = self._resolve_asset_path(path, default_path)
        if not resolved.is_file():
            logger.warning("Файл ассета не найден: %s", resolved)
            return None

        try:
            return self._load_rgb_with_alpha(resolved)
        except OSError:
            logger.exception("Не удалось загрузить ассет: %s", resolved)
            return None

    def _load_rgb_with_alpha(self, path: Path) -> Image.Image:
        with Image.open(path) as image:
            if image.mode in ("RGBA", "LA") or (
                image.mode == "P" and "transparency" in image.info
            ):
                return image.convert("RGBA")
            return image.convert("RGB")

    def _paste_qr_row(
        self,
        canvas: Image.Image,
        qr_android: Image.Image,
        qr_ios: Image.Image,
        y: int,
    ) -> int:
        qr_android = self._fit_image(qr_android, self.QR_SIZE, self.QR_SIZE)
        qr_ios = self._fit_image(qr_ios, self.QR_SIZE, self.QR_SIZE)

        row_width = qr_android.width + self.QR_GAP + qr_ios.width
        start_x = (self.LABEL_WIDTH - row_width) // 2

        android_x = start_x
        ios_x = start_x + qr_android.width + self.QR_GAP

        self._paste_on_canvas(canvas, qr_android, android_x, y)
        self._paste_on_canvas(canvas, qr_ios, ios_x, y)

        return y + max(qr_android.height, qr_ios.height)

    def _paste_on_canvas(
        self,
        canvas: Image.Image,
        image: Image.Image,
        x: int,
        y: int,
    ) -> None:
        if image.mode == "RGBA":
            canvas.paste(image, (x, y), image)
            return
        canvas.paste(image, (x, y))

    def _format_order_numbers(self, order_numbers_text: str) -> str:
        lines = [line.strip() for line in order_numbers_text.splitlines() if line.strip()]
        if not lines:
            numbers = order_numbers_text.strip() or "—"
        else:
            numbers = ", ".join(lines)
        return f"{self.ORDER_LABEL_PREFIX}{numbers}"

    def _load_rgb(self, path: str) -> Image.Image:
        with Image.open(path) as image:
            return image.convert("RGB")

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        if not self.FONT_PATH.is_file():
            raise FileNotFoundError(f"Файл шрифта не найден: {self.FONT_PATH}")
        return ImageFont.truetype(str(self.FONT_PATH), size)

    def _fit_image(self, image: Image.Image, max_width: int, max_height: int) -> Image.Image:
        width, height = image.size
        scale = min(max_width / width, max_height / height)
        if scale <= 0:
            return image.copy()

        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
        if new_size == image.size:
            return image.copy()
        return image.resize(new_size, Image.Resampling.LANCZOS)

    def _paste_centered(self, canvas: Image.Image, image: Image.Image, y: int) -> int:
        x = (self.LABEL_WIDTH - image.width) // 2
        self._paste_on_canvas(canvas, image, x, y)
        return y + image.height

    def _prepare_color_screenshot(
        self,
        image: Image.Image,
        box_width: int,
        box_height: int,
    ) -> Image.Image:
        fitted = image.copy()
        fitted.thumbnail((box_width, box_height), Image.Resampling.LANCZOS)
        return ImageOps.pad(
            fitted,
            (box_width, box_height),
            color=(255, 255, 255),
            centering=(0.5, 0.5),
        )

    def _wrap_order_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.FreeTypeFont,
        max_width: int,
    ) -> list[str]:
        words = text.split()
        if not words:
            return [self.ORDER_LABEL_PREFIX.strip()]

        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def _measure_wrapped_text(
        self,
        draw: ImageDraw.ImageDraw,
        lines: list[str],
        font: ImageFont.FreeTypeFont,
        line_height: int,
    ) -> tuple[int, int]:
        max_width = 0
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            max_width = max(max_width, bbox[2] - bbox[0])
        return max_width, line_height * len(lines)

    def _line_height(
        self,
        draw: ImageDraw.ImageDraw,
        font: ImageFont.FreeTypeFont,
        fallback_size: int,
    ) -> int:
        bbox = draw.textbbox((0, 0), "Ay", font=font)
        measured = bbox[3] - bbox[1]
        if measured <= 0:
            return fallback_size + 8
        return measured + 8

    def _resolve_order_text_layout(
        self,
        draw: ImageDraw.ImageDraw,
        order_text: str,
    ) -> tuple[ImageFont.FreeTypeFont, int, int, list[str]]:
        max_text_width = self.LABEL_WIDTH - 2 * self.MARGIN
        max_text_height = self.LABEL_HEIGHT // 5

        for size in range(self.ORDER_FONT_SIZE, self.ORDER_MIN_FONT_SIZE - 1, -2):
            font = self._get_font(size)
            line_height = self._line_height(draw, font, size)
            lines = self._wrap_order_text(draw, order_text, font, max_text_width)
            _, block_height = self._measure_wrapped_text(draw, lines, font, line_height)
            if block_height <= max_text_height:
                return font, line_height, block_height, lines

        font = self._get_font(self.ORDER_MIN_FONT_SIZE)
        line_height = self._line_height(draw, font, self.ORDER_MIN_FONT_SIZE)
        lines = self._wrap_order_text(draw, order_text, font, max_text_width)
        _, block_height = self._measure_wrapped_text(draw, lines, font, line_height)
        return font, line_height, block_height, lines

    def _draw_centered_order_block(
        self,
        draw: ImageDraw.ImageDraw,
        lines: list[str],
        y: int,
        font: ImageFont.FreeTypeFont,
        line_height: int,
    ) -> None:
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (self.LABEL_WIDTH - text_width) // 2
            draw.text(
                (x, y),
                line,
                fill="black",
                font=font,
                stroke_width=1,
                stroke_fill="black",
            )
            y += line_height
