"""Lectura de texto desde archivos PDF."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pdfplumber


class PdfReadError(Exception):
    """Error al abrir o leer un PDF."""


class NoTextError(PdfReadError):
    """El PDF no contiene texto extraible (probablemente es escaneado)."""


@dataclass
class PdfContent:
    text: str
    pages: int


def read_pdf(path: Path, *, layout: bool = False) -> PdfContent:
    """Extrae el texto de todas las paginas de un PDF.

    Con layout=True se conservan mejor las columnas, a costa de agregar espacios.
    """
    try:
        with pdfplumber.open(str(path)) as pdf:
            page_texts = []
            for page in pdf.pages:
                text = page.extract_text(layout=layout) or ""
                if not text.strip() and not layout:
                    # Algunos PDFs con columnas se leen mejor conservando el layout.
                    text = page.extract_text(layout=True) or ""
                page_texts.append(text)
            pages = len(pdf.pages)
    except Exception as exc:  # pdfplumber puede lanzar distintos tipos de error
        raise PdfReadError(f"No se pudo leer el PDF: {exc}") from exc

    text = "\n\f\n".join(page_texts)
    if not text.strip():
        raise NoTextError(
            "El PDF no contiene texto extraible. Probablemente es una imagen "
            "escaneada y requiere OCR (por ejemplo, ocrmypdf + tesseract)."
        )
    return PdfContent(text=text, pages=pages)
