"""Exportacion de resultados a CSV, JSON y Excel."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .fields import CHARGE_DETAIL_KEYS, FIELDS, FIELD_DESCRIPTIONS, FIELD_KEYS
from .parsing import format_decimal


def _csv_value(value: Any, decimal: str) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Si" if value else "No"
    if isinstance(value, float):
        return format_decimal(value, decimal=decimal)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


_ILLEGAL_XLSX = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")


def _xlsx_value(value: Any) -> Any:
    """Evita caracteres de control y celdas demasiado largas en Excel."""
    if isinstance(value, str):
        value = _ILLEGAL_XLSX.sub("", value)
        if len(value) > 32000:
            value = value[:32000]
    return value


def write_csv(
    rows: List[Dict[str, Any]],
    path: Path,
    *,
    fields: Optional[List[str]] = None,
    separator: str = ";",
    decimal: str = ",",
) -> None:
    fields = fields or FIELD_KEYS
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, delimiter=separator, extrasaction="ignore"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key), decimal) for key in fields})


def _json_ready(row: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(row)
    detail = result.get("detalle_cobros_json")
    if isinstance(detail, str) and detail:
        try:
            result["detalle_cobros_json"] = json.loads(detail)
        except json.JSONDecodeError:
            pass
    return result


def write_json(
    rows: List[Dict[str, Any]],
    path: Path,
    *,
    fields: Optional[List[str]] = None,
) -> None:
    fields = fields or FIELD_KEYS
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [
        {key: _json_ready(row).get(key) for key in fields}
        for row in rows
    ]
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, default=str)


def _style_header(ws) -> None:
    fill = PatternFill("solid", fgColor="1F4E79")
    font = Font(color="FFFFFF", bold=True)
    for cell in ws[1]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def _adjust_widths(ws, fields: List[str], rows: List[Dict[str, Any]]) -> None:
    for index, field in enumerate(fields, start=1):
        header_len = len(field)
        max_len = header_len
        for row in rows[:200]:
            value = row.get(field)
            if value is None:
                continue
            text = str(value)
            if "\n" in text:
                text = text.split("\n", 1)[0]
            max_len = max(max_len, min(len(text), 80))
        width = min(max(max_len + 2, 10), 80)
        ws.column_dimensions[get_column_letter(index)].width = width


def write_xlsx(
    rows: List[Dict[str, Any]],
    path: Path,
    *,
    fields: Optional[List[str]] = None,
    detail_rows: Optional[List[Dict[str, Any]]] = None,
) -> None:
    fields = fields or FIELD_KEYS
    path.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    ws = workbook.active
    ws.title = "Boletas"
    ws.append(fields)
    for row in rows:
        ws.append([_xlsx_value(row.get(field)) for field in fields])
    _style_header(ws)
    _adjust_widths(ws, fields, rows)

    # Hoja de diccionario de campos.
    ws_dict = workbook.create_sheet("Diccionario")
    ws_dict.append(["campo", "descripcion"])
    for field in FIELDS:
        ws_dict.append([field.key, field.description])
    _style_header(ws_dict)
    ws_dict.column_dimensions["A"].width = 42
    ws_dict.column_dimensions["B"].width = 110

    if detail_rows:
        ws_detail = workbook.create_sheet("Cargos")
        ws_detail.append(CHARGE_DETAIL_KEYS)
        for detail in detail_rows:
            ws_detail.append(
                [_xlsx_value(detail.get(key)) for key in CHARGE_DETAIL_KEYS]
            )
        _style_header(ws_detail)
        _adjust_widths(ws_detail, CHARGE_DETAIL_KEYS, detail_rows)

    workbook.save(str(path))


def write_detail_csv(
    detail_rows: List[Dict[str, Any]],
    path: Path,
    *,
    separator: str = ";",
    decimal: str = ",",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=CHARGE_DETAIL_KEYS,
            delimiter=separator,
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in detail_rows:
            writer.writerow(
                {key: _csv_value(row.get(key), decimal) for key in CHARGE_DETAIL_KEYS}
            )


def write_detail_json(detail_rows: List[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(detail_rows, handle, ensure_ascii=False, indent=2, default=str)


def write_output(
    rows: List[Dict[str, Any]],
    path: Path,
    fmt: str,
    *,
    separator: str = ";",
    decimal: str = ",",
    detail_rows: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Path]:
    """Escribe el resultado principal y, si corresponde, el detalle de cobros.

    Devuelve la ruta del archivo de detalle generado, si existe.
    """
    fmt = fmt.lower()
    if fmt == "csv":
        write_csv(rows, path, separator=separator, decimal=decimal)
        if detail_rows:
            detail_path = path.with_name(path.stem + "_cargos.csv")
            write_detail_csv(detail_rows, detail_path, separator=separator, decimal=decimal)
            return detail_path
    elif fmt == "json":
        write_json(rows, path)
        if detail_rows:
            detail_path = path.with_name(path.stem + "_cargos.json")
            write_detail_json(detail_rows, detail_path)
            return detail_path
    elif fmt in {"xlsx", "excel"}:
        write_xlsx(rows, path, detail_rows=detail_rows)
    else:
        raise ValueError(f"Formato no soportado: {fmt}")
    return None


def format_from_suffix(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    if suffix in {"xlsx", "xlsm"}:
        return "xlsx"
    if suffix == "json":
        return "json"
    return "csv"


def default_output_path(fmt: str) -> Path:
    extension = "xlsx" if fmt in {"xlsx", "excel"} else fmt
    return Path(f"boletas_extraidas.{extension}")


def detail_rows_from_results(results: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convierte el detalle JSON de cada boleta en filas largas."""
    rows: List[Dict[str, Any]] = []
    for result in results:
        raw = result.get("detalle_cobros_json")
        if not raw:
            continue
        try:
            items = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        for item in items:
            rows.append(
                {
                    "archivo": result.get("archivo"),
                    "numero_cliente": result.get("numero_cliente"),
                    "folio_factura": result.get("folio_factura"),
                    "concepto": item.get("concepto"),
                    "clave": item.get("clave"),
                    "monto_clp": item.get("monto_clp"),
                }
            )
    return rows


__all__ = [
    "FIELD_DESCRIPTIONS",
    "default_output_path",
    "detail_rows_from_results",
    "format_from_suffix",
    "write_csv",
    "write_detail_csv",
    "write_json",
    "write_output",
    "write_xlsx",
]
