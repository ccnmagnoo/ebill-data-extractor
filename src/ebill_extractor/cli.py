"""Interfaz de linea de comandos de ebill-extractor."""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__
from .exporters import (
    default_output_path,
    detail_rows_from_results,
    format_from_suffix,
    write_output,
)
from .extractor import extract_bill
from .fields import FIELDS, FIELD_KEYS
from .parsing import natural_sort_key


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ebill-extractor",
        description=(
            "Extrae parametros de boletas electricas chilenas en PDF "
            "(lecturas, cliente, medidor, energia, potencia, cobros, IVA, "
            "compensaciones SEC y totales)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  ebill-extractor\n"
            "  ebill-extractor C:\\boletas\n"
            "  ebill-extractor C:\\boletas -r -o resumen.xlsx\n"
            "  ebill-extractor . -f json -o boletas.json --incluir-texto\n"
            "  ebill-extractor . --detalle-cargos -o boletas.csv\n"
            "  ebill-extractor --lista-campos\n"
        ),
    )
    parser.add_argument(
        "ruta",
        nargs="?",
        default=".",
        help="Carpeta con PDFs o archivo PDF. Por defecto: ./",
    )
    parser.add_argument(
        "-o",
        "--salida",
        help="Archivo de salida. Por defecto: boletas_extraidas.<formato>",
    )
    parser.add_argument(
        "-f",
        "--formato",
        choices=["csv", "json", "xlsx"],
        help="Formato de salida. Si se omite, se infiere de la extension de --salida.",
    )
    parser.add_argument(
        "-r",
        "--recursivo",
        action="store_true",
        help="Buscar PDFs tambien en subcarpetas.",
    )
    parser.add_argument(
        "-p",
        "--patron",
        default="*.pdf",
        help="Patron de busqueda de archivos (por defecto: *.pdf).",
    )
    parser.add_argument(
        "--separador",
        default=";",
        help="Separador del CSV (por defecto: ';'). Use ',' para formato internacional.",
    )
    parser.add_argument(
        "--decimal",
        choices=["auto", "coma", "punto"],
        default="auto",
        help="Separador decimal del CSV. 'auto' usa coma con ';' y punto con ','.",
    )
    parser.add_argument(
        "--incluir-texto",
        action="store_true",
        help="Incluir el texto completo extraido del PDF en la columna texto_pdf.",
    )
    parser.add_argument(
        "--detalle-cargos",
        action="store_true",
        help="Generar ademas un archivo de detalle largo con todos los cobros.",
    )
    parser.add_argument(
        "--deduplicar",
        action="store_true",
        help="Omitir boletas duplicadas (mismo cliente y folio, o mismo hash).",
    )
    parser.add_argument(
        "--detener-en-error",
        action="store_true",
        help="Detener el proceso en el primer PDF con error.",
    )
    parser.add_argument(
        "--silencioso",
        action="store_true",
        help="No mostrar el progreso ni el resumen.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Mostrar el progreso archivo por archivo.",
    )
    parser.add_argument(
        "--lista-campos",
        action="store_true",
        help="Listar todos los campos extraidos y salir.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ebill-extractor {__version__}",
    )
    return parser


def _find_pdfs(path: Path, pattern: str, recursive: bool) -> List[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() == ".pdf" else []
    if not path.is_dir():
        return []
    if pattern.lower() == "*.pdf":
        # En Windows el glob ya es insensible a mayusculas; en otros sistemas
        # conviene aceptar tambien archivos .PDF.
        iterator = path.rglob("*") if recursive else path.iterdir()
        candidates = [
            item for item in iterator if item.is_file() and item.suffix.lower() == ".pdf"
        ]
    else:
        iterator = path.rglob(pattern) if recursive else path.glob(pattern)
        candidates = [
            item for item in iterator if item.is_file() and item.suffix.lower() == ".pdf"
        ]
    pdfs = [item.resolve() for item in candidates]
    return sorted(pdfs, key=lambda item: natural_sort_key(item.name))


def _sha256(path: Path) -> Optional[str]:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _error_row(path: Path, exc: Exception) -> Dict[str, Any]:
    row: Dict[str, Any] = {key: None for key in FIELD_KEYS}
    row["archivo"] = path.name
    row["ruta_archivo"] = str(path.resolve())
    row["error_extraccion"] = str(exc)
    row["hash_pdf"] = _sha256(path)
    row["fecha_extraccion"] = datetime.now().isoformat(timespec="seconds")
    row["version_extractor"] = __version__
    row["moneda"] = "CLP"
    return row


def _print_fields() -> None:
    print("Campos extraidos (para usar en CSV/JSON/Excel):")
    print()
    for field in FIELDS:
        print(f"  {field.key:<44} {field.description}")


def main(argv: Optional[List[str]] = None) -> int:
    # Evita que un caracter no representable en la consola de Windows corte el CLI.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.lista_campos:
        _print_fields()
        return 0

    input_path = Path(args.ruta).expanduser()
    if not input_path.exists():
        parser.error(f"La ruta no existe: {input_path}")

    pdfs = _find_pdfs(input_path, args.patron, args.recursivo)
    if not pdfs:
        print(
            f"No se encontraron archivos PDF en: {input_path.resolve()} "
            f"(patron: {args.patron})",
            file=sys.stderr,
        )
        return 2

    if len(args.separador) != 1:
        parser.error("--separador debe ser exactamente un caracter")

    if args.formato:
        fmt = "xlsx" if args.formato == "excel" else args.formato
    elif args.salida:
        fmt = format_from_suffix(Path(args.salida))
    else:
        fmt = "csv"

    if args.salida:
        output_path = Path(args.salida).expanduser()
        if output_path.is_dir():
            output_path = output_path / default_output_path(fmt).name
    else:
        output_path = default_output_path(fmt)

    if args.decimal == "auto":
        decimal = "," if args.separador == ";" else "."
    elif args.decimal == "coma":
        decimal = ","
    else:
        decimal = "."

    if not args.silencioso:
        print(f"Buscando boletas en: {input_path.resolve()}")
        print(f"PDFs encontrados: {len(pdfs)}")

    rows: List[Dict[str, Any]] = []
    errors = 0
    skipped_duplicates = 0
    seen_bills: Dict[Any, Path] = {}

    for index, pdf in enumerate(pdfs, start=1):
        try:
            row = extract_bill(pdf, include_text=args.incluir_texto)
            if args.deduplicar:
                if row.get("numero_cliente") and row.get("folio_factura"):
                    dedup_key: Any = (
                        row["numero_cliente"],
                        row["folio_factura"],
                    )
                else:
                    dedup_key = row.get("hash_pdf")
                if dedup_key is not None:
                    previous = seen_bills.get(dedup_key)
                    if previous is not None:
                        skipped_duplicates += 1
                        if args.verbose and not args.silencioso:
                            print(f"  [duplicado] {pdf.name} = {previous.name}")
                        continue
                    seen_bills[dedup_key] = pdf
            rows.append(row)
            if args.verbose and not args.silencioso:
                print(f"  [{index}/{len(pdfs)}] OK  {pdf.name}")
        except Exception as exc:
            errors += 1
            rows.append(_error_row(pdf, exc))
            print(f"  [ERROR] {pdf.name}: {exc}", file=sys.stderr)
            if args.detener_en_error:
                break

    detail_rows = detail_rows_from_results(rows) if args.detalle_cargos else None
    try:
        detail_path = write_output(
            rows,
            output_path,
            fmt,
            separator=args.separador,
            decimal=decimal,
            detail_rows=detail_rows,
        )
    except Exception as exc:
        print(f"No se pudo escribir el archivo de salida: {exc}", file=sys.stderr)
        return 1

    success = len(rows) - errors
    if not args.silencioso:
        print()
        print(f"Boletas procesadas: {success}")
        if errors:
            print(f"PDFs con error: {errors}")
        if skipped_duplicates:
            print(f"Duplicados omitidos: {skipped_duplicates}")
        print(f"Archivo generado: {output_path.resolve()}")
        if detail_path:
            print(f"Detalle de cobros: {detail_path.resolve()}")

    return 0 if success > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
