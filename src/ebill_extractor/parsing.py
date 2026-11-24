"""Utilidades de normalizacion, numeros y fechas para boletas chilenas."""

from __future__ import annotations

import re
from datetime import date
from typing import Any, List, Optional

# Tabla 1:1 para conservar exactamente el largo del texto. Esto permite usar
# expresiones regulares sobre texto sin tildes y luego recuperar el valor
# original (con tildes) usando los mismos indices.
_ACCENT_MAP = {
    "á": "a", "à": "a", "ä": "a", "â": "a", "ã": "a", "å": "a",
    "Á": "A", "À": "A", "Ä": "A", "Â": "A", "Ã": "A", "Å": "A",
    "é": "e", "è": "e", "ë": "e", "ê": "e",
    "É": "E", "È": "E", "Ë": "E", "Ê": "E",
    "í": "i", "ì": "i", "ï": "i", "î": "i",
    "Í": "I", "Ì": "I", "Ï": "I", "Î": "I",
    "ó": "o", "ò": "o", "ö": "o", "ô": "o", "õ": "o",
    "Ó": "O", "Ò": "O", "Ö": "O", "Ô": "O", "Õ": "O",
    "ú": "u", "ù": "u", "ü": "u", "û": "u",
    "Ú": "U", "Ù": "U", "Ü": "U", "Û": "U",
    "ñ": "n", "Ñ": "N",
    "ç": "c", "Ç": "C",
}
_ACCENT_TRANS = str.maketrans(_ACCENT_MAP)

_MONTHS = {
    "ene": 1, "enero": 1,
    "feb": 2, "febrero": 2,
    "mar": 3, "marzo": 3,
    "abr": 4, "abril": 4,
    "may": 5, "mayo": 5,
    "jun": 6, "junio": 6,
    "jul": 7, "julio": 7,
    "ago": 8, "agosto": 8,
    "sep": 9, "sept": 9, "set": 9, "septiembre": 9, "setiembre": 9,
    "oct": 10, "octubre": 10,
    "nov": 11, "noviembre": 11,
    "dic": 12, "diciembre": 12,
}


def fold_accents(text: str) -> str:
    """Reemplaza tildes y enes por ASCII sin cambiar el largo del texto."""
    return text.translate(_ACCENT_TRANS)


def clean_value(value: Optional[str]) -> Optional[str]:
    """Colapsa espacios y quita espacios en los extremos."""
    if value is None:
        return None
    value = re.sub(r"\s+", " ", str(value)).strip()
    return value or None


def parse_number(value: Any) -> Optional[float]:
    """Interpreta numeros en formato chileno (1.234,56) o internacional.

    Reglas principales:
    - Si hay coma y punto, el ultimo separador es el decimal.
    - Si solo hay puntos y el ultimo grupo tiene 3 digitos, son miles (Chile).
    - Si solo hay una coma con 1 o 2 digitos finales, es decimal.
    - Unidades como kWh, kW, kVA, kVArh, $ y % se eliminan.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    # Quitar etiquetas y unidades, conservando digitos y separadores.
    text = text.replace("$", " ")
    text = re.sub(r"(?i)\b(?:clp|kwh|kvarh|kvar|kw|kva|wh|seg|%)\b", " ", text)
    text = re.sub(r"[^0-9,.\-]", "", text)
    text = text.strip()
    if not text or text in {"-", ".", ","}:
        return None

    negative = text.startswith("-")
    text = text.lstrip("-")

    if "," in text and "." in text:
        # El separador decimal es el que aparece mas a la derecha.
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        # En formato chileno la coma es siempre el separador decimal. Varias
        # comas solo aparecen en formatos anglosajones (1,234,567).
        if text.count(",") == 1:
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "." in text:
        parts = text.split(".")
        if len(parts) > 2:
            # Varios puntos: separadores de miles.
            text = "".join(parts)
        else:
            integer, decimals = parts
            if len(decimals) == 3 and integer not in {"", "0"}:
                # Formato chileno: 1.234 = mil doscientos treinta y cuatro.
                text = integer + decimals
            elif len(decimals) == 3 and integer == "0":
                # 0.000 se interpreta como cero, sin perdida practica.
                text = "0." + decimals
            # En cualquier otro caso el punto es decimal.

    try:
        number = float(text)
    except ValueError:
        return None
    return -number if negative else number


def _month_number(name: str) -> Optional[int]:
    return _MONTHS.get(fold_accents(name).lower().strip("."))


def parse_date(value: Optional[str]) -> Optional[date]:
    """Interpreta fechas chilenas: 05 jun 2023, 04-SEP-2023, 04/09/2023."""
    if value is None:
        return None
    text = clean_value(value)
    if not text:
        return None
    text = fold_accents(text)

    # ISO: 2023-09-04
    match = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None

    # 05 jun 2023, 04-SEP-2023, 04/09/2023, 05.06.2023
    match = re.fullmatch(
        r"(\d{1,2})[\s\-/.,]+([A-Za-z]{3,10}|\d{1,2})[\s\-/.,]+(\d{2,4})",
        text,
    )
    if match:
        day_text, month_text, year_text = match.groups()
        month = _month_number(month_text) if not month_text.isdigit() else int(month_text)
        if month is None:
            return None
        year = int(year_text)
        if year < 100:
            year += 2000
        try:
            return date(year, month, int(day_text))
        except ValueError:
            return None

    return None


def date_to_iso(value: Optional[str]) -> Optional[str]:
    """Devuelve la fecha en ISO 8601 o el texto original si no es fecha."""
    if value is None:
        return None
    parsed = parse_date(value)
    return parsed.isoformat() if parsed else clean_value(value)


def normalize_client_number(value: Optional[str]) -> Optional[str]:
    """Normaliza '217292 - 5' a '217292-5'."""
    value = clean_value(value)
    if not value:
        return None
    return re.sub(r"\s*-\s*", "-", value)


def strip_trailing_date(value: Optional[str]) -> Optional[str]:
    """Quita una fecha al final de una linea (usado en el giro del cliente)."""
    value = clean_value(value)
    if not value:
        return None
    value = re.sub(
        r"\s+\d{1,2}\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,}\s+\d{4}\s*$",
        "",
        value,
    )
    return clean_value(value)


def natural_sort_key(value: str) -> List[Any]:
    """Orden natural para nombres como 08-2023, 09-2023, 10-2023."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def format_decimal(value: Optional[float], decimal: str = ".") -> str:
    """Formatea un numero sin notacion cientifica ni ceros innecesarios."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Si" if value else "No"
    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, float):
        if value.is_integer():
            text = str(int(value))
        else:
            text = f"{value:.10f}".rstrip("0").rstrip(".")
    else:
        text = str(value)
    if decimal == "," and "." in text:
        text = text.replace(".", ",")
    return text
