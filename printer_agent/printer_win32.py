"""Прямая бесшумная печать этикетки через Windows Print API."""

from __future__ import annotations

import logging
from pathlib import Path

import win32print
import win32ui
from PIL import Image, ImageWin

logger = logging.getLogger(__name__)

HORZRES = 8
VERTRES = 10


def _resolve_printer_name(printer_name: str) -> str:
    printers = [
        printer[2]
        for printer in win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )
    ]
    if printer_name not in printers:
        available = ", ".join(printers) if printers else "нет доступных принтеров"
        raise ValueError(
            f"Принтер '{printer_name}' не найден. Доступные принтеры: {available}"
        )
    return printer_name


def print_label(file_path: str, printer_name: str) -> None:
    """
    Отправляет изображение этикетки в спулер Windows без диалогов и окон.
    Изображение масштабируется на всю печатаемую область принтера.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Файл этикетки не найден: {file_path}")

    resolved_printer = _resolve_printer_name(printer_name)

    with Image.open(path) as image:
        if image.mode != "RGB":
            image = image.convert("RGB")

        dib_image = image.copy()

    hdc = win32ui.CreateDC()
    try:
        hdc.CreatePrinterDC(resolved_printer)

        printable_width = hdc.GetDeviceCaps(HORZRES)
        printable_height = hdc.GetDeviceCaps(VERTRES)

        hdc.StartDoc(path.name)
        hdc.StartPage()

        dib = ImageWin.Dib(dib_image)
        dib.draw(
            hdc.GetHandleOutput(),
            (0, 0, printable_width, printable_height),
        )

        hdc.EndPage()
        hdc.EndDoc()
    except Exception:
        logger.exception("Ошибка печати на принтере %s", resolved_printer)
        raise
    finally:
        hdc.DeleteDC()

    logger.info("Этикетка %s отправлена на принтер %s", path.name, resolved_printer)
