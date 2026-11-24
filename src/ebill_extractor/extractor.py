"""Extraccion de parametros desde el texto de boletas electricas chilenas."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import __version__
from .fields import FIELD_KEYS
from .parsing import (
    clean_value,
    date_to_iso,
    fold_accents,
    normalize_client_number,
    parse_date,
    parse_number,
    strip_trailing_date,
)
from .pdf_reader import PdfReadError, read_pdf

_FLAGS = re.IGNORECASE | re.MULTILINE


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, _FLAGS)


# ---------------------------------------------------------------------------
# Patrones generales
# ---------------------------------------------------------------------------

_RE_SENOR = _rx(r"SENOR\s*\(\s*A\s*\)")
_RE_RUT = re.compile(r"\b(?:\d{1,2}\.\d{3}\.\d{3}|\d{7,8})-[\dKk]\b")
_RE_CLIENTE_NOMBRE = _rx(r"SENOR\s*\(\s*A\s*\)\s*(?P<v>.*?)\s*N[°º]\s*CLIENTE\s*:")
_RE_CLIENTE_NUMERO = _rx(r"N[°º]\s*CLIENTE\s*:\s*(?P<v>\d+\s*-\s*[\dKk])")
_RE_FACTURA = _rx(r"N[°º]\s*FACTURA\s*:\s*(?P<v>\d+)")
_RE_RUTA = _rx(r"N[°º]\s*RUTA\s*:\s*(?P<v>[\w\-]+)")
_RE_TIMBRE = re.compile(r"\b[0-9A-Z]{30,}\b", re.IGNORECASE)
_RE_FOLIO_SUELTO = _rx(r"^\s*(?P<v>\d{1,3}(?:\.\d{3})+)\s*$")

_RE_FECHA_EMISION = _rx(
    r"FECHA\s+EMISION\s*:\s*(?P<v>\d{1,2}[\s\-/]+[A-Za-z]{3,10}[\s\-/]+\d{4})"
)
_RE_FECHA_VENCIMIENTO = _rx(
    r"FECHA\s+VENCIMIENTO\s*:\s*(?P<v>\d{1,2}[\s\-/]+[A-Za-z]{3,10}[\s\-/]+\d{4})"
)
_RE_PERIODO = _rx(
    r"LECTURAS\s*:?\s*DESDE\s+(?P<desde>\d{1,2}\s+[A-Za-z]{3,10}\s+\d{4})"
    r"\s+(?:AL|HASTA)\s+(?P<hasta>\d{1,2}\s+[A-Za-z]{3,10}\s+\d{4})"
)
_RE_TARIFA = _rx(
    r"TARIFA\s*:?\s*(?P<v>[A-Z0-9][A-Z0-9 .\-/]*?)\s+(?:LECTURAS|PERIODO)"
)
_RE_ZONA = _rx(r"ZONA\s+TARIFARIA\s*:?\s*(?P<v>[^\n]+)")
_RE_SUBESTACION = _rx(r"SUBESTACION\s*:?\s*(?P<v>.*?)\s+NR\.?\s+MEDIDOR")
_RE_GRUPO = _rx(r"GRUPO\s+CONSUMO\s*:?\s*(?P<v>\S+)")
_RE_DIRECCION = _rx(r"^\s*DIRECCION\s*:?\s*(?P<v>[^\n]+)$")

_RE_PROX_LECTURA = _rx(
    r"FECHA\s+ESTIMADA\s+PROX\.?\s*LECTURA\s*:\s*"
    r"(?P<v>\d{1,2}[\s\-/]+[A-Za-z]{3,10}[\s\-/]+\d{4})"
)
_RE_LIMITE_TARIFA = _rx(r"FECHA\s+LIMITE\s+PARA\s+CAMBIO\s+TARIFA\s+(?P<v>[^\n]+)")
_RE_TERMINO_TARIFA = _rx(r"FECHA\s+TERMINO\s+DE\s+TARIFA\s+(?P<v>[^\n]+)")
_RE_FECHA_CORTE = _rx(
    r"FECHA\s+DE\s+CORTE(?:\s+A\s+PARTIR\s+DE)?\s*:?\s*"
    r"(?P<v>\d{1,2}[\s\-/]+[A-Za-z]{3,10}[\s\-/]+\d{4})"
)
_RE_NOTA_NUMERADA = re.compile(r"^\s*\d+\.-")

_RE_ULTIMO_PAGO = _rx(
    r"ULTIMO\s+PAGO\s*:\s*\$\s*(?P<monto>[\d.,]+)"
    r"[\s\S]{0,180}?(?P<fecha>\d{2}-\d{2}-\d{4})\s+"
    r"(?P<hora>\d{2}:\d{2})\s+(?P<medio>[^\n]+)"
)
_RE_FECHA_HORA = _rx(
    r"(?P<fecha>\d{2}-\d{2}-\d{4})\s+(?P<hora>\d{2}:\d{2})\s+(?P<medio>[^\n]+)"
)
_RE_MONTO_ULTIMO_PAGO = _rx(r"ULTIMO\s+PAGO\s*:\s*\$\s*(?P<v>[\d.,]+)")

_RE_POTENCIA_CONECTADA = _rx(
    r"POTENCIA\s+CONECTADA\s*:?\s*(?P<v>[\d.,]+)\s*KVA"
)
_RE_LIMITE_INVIERNO = _rx(r"LIMITE\s+DE\s+INVIERNO\s*:?\s*(?P<v>[\d.,]+)\s*KW")
_RE_BLOQUE_CORTE = _rx(r"BLOQUE\s+DE\s+CORTE\s*:?\s*(?P<v>\d+)")
_RE_CONS_REFERENCIA = _rx(
    r"CONS\.?\s+REFERENCIA\s+PRX\.?\s+PER(?:IODO)?\s*:?\s*(?P<v>[\d.,]+)\s*KWH"
)

_RE_MEDIDOR_ACTIVO = _rx(
    r"(?P<medidor>\d{4,})\s+(?P<cte>\d+)\s+ACTIVO\s+(?P<prop>\w+)\s+"
    r"(?P<actual>[\d.,]+)\s+(?P<anterior>[\d.,]+)\s+(?P<consumo>[\d.,]+)"
)
_RE_MEDIDOR_REACTIVO = _rx(
    r"(?P<medidor>\d{4,})\s+(?P<cte>\d+)\s+REACTIVO\s+(?P<prop>\w+)\s+"
    r"(?P<actual>[\d.,]+)\s+(?P<anterior>[\d.,]+)\s+(?P<consumo>[\d.,]+)"
)
# Lectura estimada: la columna "actual" no se imprime; aparecen la lectura
# anterior y el consumo.
_RE_MEDIDOR_ACTIVO_ESTIMADO = _rx(
    r"(?P<medidor>\d{4,})\s+(?P<cte>\d+)\s+ACTIVO\s+(?P<prop>\w+)\s+"
    r"EST(?:I)?MADO\s+(?P<anterior>[\d.,]+)\s+(?P<consumo>[\d.,]+)"
)

_RE_DEMANDA_LEIDA = _rx(r"DEMANDA\s+LEIDA\s*:?\s*(?P<v>[\d.,]+)\s*KW")
_RE_DEMANDA_MAXIMA = _rx(r"DEMANDA\s+MAXIMA\s*:?\s*(?P<v>[\d.,]+)\s*KW")
_RE_ENERGIA_CONSUMIDA = _rx(
    r"ELECTRICIDAD\s+CONSUMIDA\s*:?\s*(?P<v>[\d.,]+)\s*KWH"
)
_RE_ENERGIA_REACTIVA_FACTURADA = _rx(
    r"ENERGIA\s+REACTIVA\s*:?\s*(?P<v>[\d.,]+)\s*KVARH?"
)

_RE_POTENCIA_PUNTA = [
    _rx(
        r"(?:DEMANDA|POTENCIA)\s+(?:EN\s+)?(?:HORA[S]?\s+DE\s+)?PUNTA\s*:?\s*"
        r"(?P<v>[\d.,]+)\s*KW"
    ),
    _rx(r"(?:DEMANDA|POTENCIA)\s+PUNTA\s*:?\s*(?P<v>[\d.,]+)\s*KW"),
]
_RE_POTENCIA_FUERA_PUNTA = [
    _rx(
        r"(?:DEMANDA|POTENCIA)\s+FUERA\s+DE\s+PUNTA\s*:?\s*"
        r"(?P<v>[\d.,]+)\s*KW"
    ),
    _rx(
        r"(?:DEMANDA|POTENCIA)\s+(?:EN\s+)?(?:HORA[S]?\s+DE\s+)?FUERA\s+DE\s+PUNTA"
        r"\s*:?\s*(?P<v>[\d.,]+)\s*KW"
    ),
]
_RE_POTENCIA_CONTRATADA = [
    _rx(r"POTENCIA\s+CONTRATADA\s*:?\s*(?P<v>[\d.,]+)\s*KW"),
    _rx(r"DEMANDA\s+CONTRATADA\s*:?\s*(?P<v>[\d.,]+)\s*KW"),
]

_RE_FOOTER = _rx(
    r"^\s*([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+"
    r"([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s*$"
)
_RE_FECHA_MONTO = _rx(
    r"(?P<fecha>\d{1,2}\s+[A-Za-z]{3,10}\s+\d{4})\s+\$\s*(?P<monto>[\d.,]+)"
)

_RE_COMP_PERIODO = _rx(
    r"COMPENSACION\s+SEC\s+POR\s+INTERRUPCIONES\s+DE\s+SUMINISTRO\s+"
    r"DEL\s+PERIODO\s*:\s*(?P<v>[^\n]+)"
)
_RE_COMP_INTERRUPCIONES = _rx(r"TOTAL\s+DE\s+INTERRUPCIONES\s*:\s*(?P<v>\d+)")
_RE_COMP_TIEMPO_TOTAL = _rx(
    r"TIEMPO\s+TOTAL\s+INTERRUMPIDO\s*\(\s*SEG\s*\)\s*:\s*(?P<v>[\d.,]+)"
)
_RE_COMP_TIEMPO_COMPENSAR = _rx(
    r"TIEMPO\s+A\s+COMPENSAR\s*\(\s*SEG\s*\)\s*:\s*(?P<v>[\d.,]+)"
)
_RE_COMP_CONSUMO_PROMEDIO = _rx(
    r"CONSUMO\s+PROMEDIO\s*\(\s*KWH\s*/\s*SEG\s*\)\s*:\s*(?P<v>[\d.,]+)"
)
_RE_COMP_ENERGIA = _rx(
    r"ENERGIA\s+A\s+COMPENSAR\s*\(\s*KWH\s*\)\s*:\s*(?P<v>[\d.,]+)"
)
_RE_COMP_COSTO_FALLA = _rx(
    r"COSTO\s+DE\s+FALLA\s*\(\s*\$?\s*/\s*KWH\s*\)\s*:\s*(?P<v>[\d.,]+)"
)
_RE_COMP_MONTO = _rx(
    r"MONTO\s+A\s+COMPENSAR\s*\(\s*\$?\s*\)\s*:\s*(?P<v>[\d.,]+)"
)

# ---------------------------------------------------------------------------
# Cobros itemizados
# ---------------------------------------------------------------------------

# (clave, concepto, patron con el monto en el grupo 1)
_CHARGE_DEFS: List[Tuple[str, str, re.Pattern[str]]] = [
    (
        "administracion_servicio",
        "Administracion del servicio",
        _rx(r"ADMINISTRACION\s+DEL\s+SERVICIO\s+\$?\s*([\d.,]+)"),
    ),
    (
        "electricidad_consumida",
        "Electricidad consumida",
        _rx(r"ELECTRICIDAD\s+CONSUMIDA\s+[\d.,]+\s*KWH\s+\$?\s*([\d.,]+)"),
    ),
    (
        "uso_sistema_transmision",
        "Uso del Sistema de Transmision",
        _rx(r"USO\s+DEL\s+SISTEMA\s+DE\s+TRANSMISION\s+\$?\s*([\d.,]+)"),
    ),
    (
        "uso_sistema_distribucion",
        "Uso del Sistema de Distribucion",
        _rx(r"USO\s+DEL\s+SISTEMA\s+DE\s+DISTRIBUCION\s+\$?\s*([\d.,]+)"),
    ),
    (
        "cargo_ley_21472",
        "Cargo Ley 21.472",
        _rx(r"(?:CARGO\s+)?LEY\s+21[.,\s]?472\s+[\d.,]+\s*KWH\s+\$?\s*([\d.,]+)"),
    ),
    (
        "demanda_maxima",
        "Demanda Maxima",
        _rx(r"DEMANDA\s+MAXIMA\s+[\d.,]+\s*KW\s+\$?\s*([\d.,]+)"),
    ),
    (
        "demanda_hora_punta",
        "Demanda en hora de punta",
        _rx(
            r"(?:DEMANDA|POTENCIA)\s+(?:EN\s+)?(?:HORA[S]?\s+DE\s+)?PUNTA\s+"
            r"[\d.,]+\s*KW\s+\$?\s*([\d.,]+)"
        ),
    ),
    (
        "energia_reactiva",
        "Energia reactiva",
        _rx(
            r"(?:CARGO\s+(?:POR\s+)?)?ENERGIA\s+REACTIVA\s+[\d.,]+\s*KVARH?\s+"
            r"\$?\s*([\d.,]+)"
        ),
    ),
    (
        "recargo_factor_potencia",
        "Recargo por bajo factor de potencia",
        _rx(
            r"RECARGO\s+(?:POR\s+)?(?:BAJO\s+)?FACTOR\s+DE\s+POTENCIA\s+"
            r"\$?\s*([\d.,]+)"
        ),
    ),
    (
        "arriendo_medidor",
        "Arriendo medidor",
        _rx(r"ARRIENDO\s+(?:DE\s+)?MEDIDOR\s+\$?\s*([\d.,]+)"),
    ),
    (
        "pago_fuera_plazo",
        "Pago fuera de plazo",
        _rx(r"PAGO\s+FUERA\s+(?:DE\s+)?PLAZO\s+\$?\s*([\d.,]+)"),
    ),
    (
        "interes_mora",
        "Interes por mora",
        _rx(r"INTERES\s+POR\s+MORA\s+\$?\s*([\d.,]+)"),
    ),
    (
        "servicio_corte",
        "Servicio de corte de suministro",
        _rx(
            r"(?:SERVICIO\s+DE\s+)?CORTE\s+(?:DE\s+)?SUMINISTRO\s+\$?\s*([\d.,]+)"
        ),
    ),
    (
        "servicio_reconexion",
        "Servicio de reconexion",
        _rx(r"(?:SERVICIO\s+DE\s+)?RECONEXION\s+\$?\s*([\d.,]+)"),
    ),
    (
        "saldo_anterior",
        "Saldo anterior",
        _rx(r"SALDO\s+ANTERIOR(?:\s*\(\d+\))?\s+\$?\s*([\d.,]+)"),
    ),
    (
        "descuento_generacion_local",
        "Descuento por Reconocimiento de Generacion Local",
        _rx(
            r"(?:RECONOCIMIENTO\s+DE\s+GENERACION\s+LOCAL|"
            r"DESCUENTO\s+GENERACION\s+LOCAL)\s+\$?\s*([\d.,]+)"
        ),
    ),
    (
        "descuento",
        "Descuento",
        _rx(r"DESCUENTO\s+\$?\s*([\d.,]+)"),
    ),
]

_CHARGE_COLUMN = {
    "administracion_servicio": "administracion_servicio_clp",
    "electricidad_consumida": "electricidad_consumida_clp",
    "uso_sistema_transmision": "uso_sistema_transmision_clp",
    "uso_sistema_distribucion": "uso_sistema_distribucion_clp",
    "cargo_ley_21472": "cargo_ley_21472_clp",
    "demanda_maxima": "demanda_maxima_clp",
    "demanda_hora_punta": "demanda_hora_punta_clp",
    "energia_reactiva": "energia_reactiva_clp",
    "recargo_factor_potencia": "recargo_factor_potencia_clp",
    "arriendo_medidor": "arriendo_medidor_clp",
    "pago_fuera_plazo": "pago_fuera_plazo_clp",
    "interes_mora": "interes_mora_clp",
    "servicio_corte": "servicio_corte_clp",
    "servicio_reconexion": "servicio_reconexion_clp",
    "saldo_anterior": "saldo_anterior_clp",
    "descuento_generacion_local": "descuento_generacion_local_clp",
}

_KNOWN_CHARGE_LABELS = {
    fold_accents(concept).upper(): key for key, concept, _ in _CHARGE_DEFS
}
# Variantes de rotulo que deben reconocerse como el mismo cobro para no
# contarlo dos veces en la columna de otros cargos.
_KNOWN_CHARGE_LABELS.update(
    {
        "PAGO FUERA PLAZO": "pago_fuera_plazo",
        "ARRIENDO DE MEDIDOR": "arriendo_medidor",
        "USO SISTEMA DE TRANSMISION": "uso_sistema_transmision",
        "USO SISTEMA DE DISTRIBUCION": "uso_sistema_distribucion",
        "CARGO LEY 21.472": "cargo_ley_21472",
    }
)

_GENERIC_CHARGE = re.compile(
    r"^(?P<label>[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ .()\-/]{2,}?)"
    r"\s+\$?\s*(?P<amount>\d{1,3}(?:\.\d{3})+|\d+)\s*$"
)

_GENERIC_BLOCK_PREFIXES = (
    "CONS. REFERENCIA",
    "CONSUMO REFERENCIA",
    "BLOQUE DE CORTE",
    "POTENCIA CONECTADA",
    "LIMITE DE INVIERNO",
    "TOTAL DE INTERRUPCIONES",
    "TIEMPO TOTAL INTERRUMPIDO",
    "TIEMPO A COMPENSAR",
    "CONSUMO PROMEDIO",
    "ENERGIA A COMPENSAR",
    "COSTO DE FALLA",
    "MONTO A COMPENSAR",
    "SUBESTACION",
    "ZONA TARIFARIA",
    "GRUPO CONSUMO",
    "TARIFA",
    "DIRECCION",
    "N ",
)


# ---------------------------------------------------------------------------
# Helpers de busqueda que conservan tildes
# ---------------------------------------------------------------------------


def _value(pattern: re.Pattern[str], folded: str, original: str, group: Any = 1) -> Optional[str]:
    match = pattern.search(folded)
    if not match:
        return None
    start, end = match.span(group)
    if start < 0:
        return None
    return clean_value(original[start:end])


def _number(pattern: re.Pattern[str], folded: str, group: Any = 1) -> Optional[float]:
    match = pattern.search(folded)
    if not match:
        return None
    return parse_number(match.group(group))


def _number_from_patterns(
    patterns: List[re.Pattern[str]], folded: str, group: Any = 1
) -> Optional[float]:
    for pattern in patterns:
        value = _number(pattern, folded, group)
        if value is not None:
            return value
    return None


def _date_value(pattern: re.Pattern[str], folded: str, original: str, group: Any = 1) -> Optional[str]:
    value = _value(pattern, folded, original, group)
    return date_to_iso(value) if value else None


def _strip_cobros(value: Optional[str]) -> Optional[str]:
    value = clean_value(value)
    if not value:
        return None
    return clean_value(re.sub(r"\s+COBROS\s*$", "", value, flags=re.IGNORECASE))


def _clean_header_line(value: Optional[str]) -> Optional[str]:
    """Quita columnas de fecha que pdfplumber puede mezclar con la direccion."""
    value = clean_value(value)
    if not value:
        return None
    value = re.split(
        r"\s+FECHA\s+(?:EMISI[OÓ]N|VENCIMIENTO)\s*:", value, maxsplit=1, flags=re.IGNORECASE
    )[0]
    return clean_value(value)


def _tariff_condition(value: Optional[str]) -> Optional[str]:
    """Limpia fechas o condiciones de tarifa mezcladas con columnas de cobros."""
    value = _strip_cobros(value)
    if not value:
        return None
    date_match = re.match(
        r"\s*(\d{1,2}[\s\-/]+[A-Za-z]{3,10}[\s\-/]+\d{4})", value, re.IGNORECASE
    )
    if date_match:
        return date_to_iso(date_match.group(1))
    condition_match = re.match(
        r"\s*(Indefinida|A\s+opci[oó]n\s+del\s+cliente)", value, re.IGNORECASE
    )
    if condition_match:
        return clean_value(condition_match.group(1))
    return clean_value(value)


# ---------------------------------------------------------------------------
# Parseo
# ---------------------------------------------------------------------------


def _extract_charges(original: str, folded: str) -> Dict[str, Any]:
    """Extrae cobros conocidos y genericos. Devuelve montos e items de detalle."""
    amounts: Dict[str, float] = {}
    items: List[Dict[str, Any]] = []
    # Los dos puntos son opcionales en muchas distribuidoras; eliminarlos solo
    # para el matching de cobros no afecta la recuperacion de valores.
    charge_text = folded.replace(":", " ")

    for key, concept, pattern in _CHARGE_DEFS:
        match = pattern.search(charge_text)
        if not match:
            continue
        amount = parse_number(match.group(1))
        if amount is None:
            continue
        amounts[key] = amounts.get(key, 0.0) + amount
        items.append({"concepto": concept, "clave": key, "monto_clp": amount})

    # Cobros no catalogados: lineas con etiqueta alfabetica y un monto al final,
    # dentro del bloque de cobros de la boleta.
    folded_lines = folded.splitlines()
    original_lines = original.splitlines()
    start = 0
    for index, line in enumerate(folded_lines):
        if re.search(r"\bCOBROS\b", line, re.IGNORECASE):
            start = index + 1
            break

    otros = 0.0
    for line in original_lines[start:]:
        folded_line = fold_accents(line)
        if re.search(r"\bULTIMO\s+PAGO\b", folded_line, re.IGNORECASE):
            break
        match = _GENERIC_CHARGE.match(line.strip())
        if not match:
            continue
        label = clean_value(match.group("label"))
        if not label:
            continue
        label_upper = fold_accents(label).upper()
        if label_upper in _KNOWN_CHARGE_LABELS:
            continue
        # pdfplumber puede mezclar una etiqueta de la columna izquierda con el
        # cobro de la columna derecha. Si el texto contiene un cobro conocido,
        # ese cobro ya fue extraido por su patron especifico.
        if any(known in label_upper for known in _KNOWN_CHARGE_LABELS):
            continue
        if any(label_upper.startswith(prefix) for prefix in _GENERIC_BLOCK_PREFIXES):
            continue
        amount = parse_number(match.group("amount"))
        if amount is None:
            continue
        otros += amount
        items.append({"concepto": label, "clave": "otro", "monto_clp": amount})

    discounts = 0.0
    has_discount = False
    for key in ("descuento", "descuento_generacion_local"):
        if key in amounts:
            discounts += amounts[key]
            has_discount = True

    detail = json.dumps(items, ensure_ascii=False, separators=(",", ":")) if items else None

    return {
        "amounts": amounts,
        "items": items,
        "otros": otros if otros else None,
        "descuentos": discounts if has_discount else None,
        "detail_json": detail,
    }


def extract_from_text(
    text: str,
    *,
    source: str = "texto.pdf",
    pages: Optional[int] = None,
    pdf_hash: Optional[str] = None,
    include_text: bool = False,
) -> Dict[str, Any]:
    """Extrae todos los campos de una boleta a partir de su texto."""
    row: Dict[str, Any] = {key: None for key in FIELD_KEYS}
    row["archivo"] = Path(source).name
    row["ruta_archivo"] = str(Path(source).resolve())
    row["fecha_extraccion"] = datetime.now().isoformat(timespec="seconds")
    row["version_extractor"] = __version__
    row["moneda"] = "CLP"
    row["paginas_pdf"] = pages
    row["hash_pdf"] = pdf_hash
    row["texto_pdf"] = text if include_text else None

    original = text
    folded = fold_accents(text)

    # --- Identificacion del cliente -------------------------------------
    row["cliente_nombre"] = _value(_RE_CLIENTE_NOMBRE, folded, original)
    if not row["cliente_nombre"]:
        fallback_name = _value(
            _rx(r"^\s*SENOR\s*\(\s*A\s*\)\s*(?P<v>[^\n]+)$"), folded, original
        )
        if fallback_name:
            row["cliente_nombre"] = clean_value(
                re.split(r"\s+N[°º]\s*CLIENTE", fallback_name, maxsplit=1, flags=re.IGNORECASE)[0]
            )
    row["numero_cliente"] = normalize_client_number(
        _value(_RE_CLIENTE_NUMERO, folded, original)
    )
    row["folio_factura"] = _value(_RE_FACTURA, folded, original)
    if not row["folio_factura"]:
        row["folio_factura"] = _value(_RE_FOLIO_SUELTO, folded, original)
    row["numero_ruta"] = _value(_RE_RUTA, folded, original)
    row["timbre_electronico"] = _value(_RE_TIMBRE, folded, original, group=0)

    original_lines = original.splitlines()
    folded_lines = folded.splitlines()
    senor_index = next(
        (i for i, line in enumerate(folded_lines) if _RE_SENOR.search(line)), None
    )
    if senor_index is not None:
        rut_index = next(
            (
                i
                for i in range(senor_index + 1, min(len(original_lines), senor_index + 7))
                if _RE_RUT.search(folded_lines[i])
            ),
            None,
        )
        if rut_index is not None:
            rut_match = _RE_RUT.search(folded_lines[rut_index])
            if rut_match:
                start, end = rut_match.span()
                row["cliente_rut"] = clean_value(original_lines[rut_index][start:end])
            if rut_index - 1 >= 0:
                row["cliente_comuna"] = _clean_header_line(original_lines[rut_index - 1])
            if rut_index - 2 >= 0:
                street = _clean_header_line(original_lines[rut_index - 2])
                city = row["cliente_comuna"]
                if street and city:
                    row["cliente_direccion"] = f"{street}, {city}"
                elif street:
                    row["cliente_direccion"] = street
            if rut_index + 1 < len(original_lines):
                row["cliente_giro"] = strip_trailing_date(original_lines[rut_index + 1])

    if not row["cliente_rut"]:
        rut_match = _RE_RUT.search(folded)
        if rut_match:
            start, end = rut_match.span()
            row["cliente_rut"] = clean_value(original[start:end])

    # --- Suministro, tarifa y fechas -------------------------------------
    row["tarifa"] = _value(_RE_TARIFA, folded, original)
    row["zona_tarifaria"] = _value(_RE_ZONA, folded, original)
    row["subestacion"] = _value(_RE_SUBESTACION, folded, original)
    row["grupo_consumo"] = _value(_RE_GRUPO, folded, original)
    row["distribuidora"] = row["grupo_consumo"]
    row["direccion_suministro"] = _value(_RE_DIRECCION, folded, original)
    if not row["direccion_suministro"]:
        row["direccion_suministro"] = row["cliente_direccion"]

    row["fecha_emision"] = _date_value(_RE_FECHA_EMISION, folded, original)
    row["fecha_vencimiento"] = _date_value(_RE_FECHA_VENCIMIENTO, folded, original)
    row["fecha_estimada_proxima_lectura"] = _date_value(
        _RE_PROX_LECTURA, folded, original
    )
    row["fecha_limite_cambio_tarifa"] = _tariff_condition(
        _value(_RE_LIMITE_TARIFA, folded, original)
    )
    row["fecha_termino_tarifa"] = _tariff_condition(
        _value(_RE_TERMINO_TARIFA, folded, original)
    )
    row["fecha_corte"] = _date_value(_RE_FECHA_CORTE, folded, original)

    periodo_match = _RE_PERIODO.search(folded)
    if periodo_match:
        start, end = periodo_match.span("desde")
        desde_raw = original[start:end]
        start, end = periodo_match.span("hasta")
        hasta_raw = original[start:end]
        desde = parse_date(desde_raw)
        hasta = parse_date(hasta_raw)
        row["periodo_desde"] = desde.isoformat() if desde else clean_value(desde_raw)
        row["periodo_hasta"] = hasta.isoformat() if hasta else clean_value(hasta_raw)
        if desde and hasta:
            row["dias_periodo"] = (hasta - desde).days

    pago_match = _RE_ULTIMO_PAGO.search(folded)
    if pago_match:
        row["fecha_ultimo_pago"] = date_to_iso(pago_match.group("fecha"))
        row["hora_ultimo_pago"] = pago_match.group("hora")
        start, end = pago_match.span("medio")
        row["medio_ultimo_pago"] = clean_value(original[start:end])
    else:
        pago_match = _RE_FECHA_HORA.search(folded)
        if pago_match:
            row["fecha_ultimo_pago"] = date_to_iso(pago_match.group("fecha"))
            row["hora_ultimo_pago"] = pago_match.group("hora")
            start, end = pago_match.span("medio")
            row["medio_ultimo_pago"] = clean_value(original[start:end])
    row["monto_ultimo_pago_clp"] = _number(_RE_MONTO_ULTIMO_PAGO, folded)

    # --- Medidor, lecturas y potencia ------------------------------------
    row["potencia_conectada_kva"] = _number(_RE_POTENCIA_CONECTADA, folded)
    row["limite_invierno_kw"] = _number(_RE_LIMITE_INVIERNO, folded)
    row["bloque_corte"] = _value(_RE_BLOQUE_CORTE, folded, original)
    row["consumo_referencia_kwh"] = _number(_RE_CONS_REFERENCIA, folded)

    activo = _RE_MEDIDOR_ACTIVO.search(folded)
    if activo:
        row["numero_medidor"] = activo.group("medidor")
        row["tipo_medidor"] = "Activo"
        row["tipo_lectura"] = "Real"
        row["constante_medidor"] = activo.group("cte")
        start, end = activo.span("prop")
        row["propiedad_medidor"] = clean_value(original[start:end])
        row["lectura_actual"] = parse_number(activo.group("actual"))
        row["lectura_anterior"] = parse_number(activo.group("anterior"))
        row["consumo_kwh"] = parse_number(activo.group("consumo"))
    else:
        estimado = _RE_MEDIDOR_ACTIVO_ESTIMADO.search(folded)
        if estimado:
            row["numero_medidor"] = estimado.group("medidor")
            row["tipo_medidor"] = "Activo"
            row["tipo_lectura"] = "Estimada"
            row["constante_medidor"] = estimado.group("cte")
            start, end = estimado.span("prop")
            row["propiedad_medidor"] = clean_value(original[start:end])
            row["lectura_anterior"] = parse_number(estimado.group("anterior"))
            row["consumo_kwh"] = parse_number(estimado.group("consumo"))

    reactivo = _RE_MEDIDOR_REACTIVO.search(folded)
    if reactivo:
        row["lectura_reactivo_actual"] = parse_number(reactivo.group("actual"))
        row["lectura_reactivo_anterior"] = parse_number(reactivo.group("anterior"))
        row["energia_reactiva_kvarh"] = parse_number(reactivo.group("consumo"))
    if row["energia_reactiva_kvarh"] is None:
        row["energia_reactiva_kvarh"] = _number(
            _RE_ENERGIA_REACTIVA_FACTURADA, folded
        )

    row["potencia_leida_kw"] = _number(_RE_DEMANDA_LEIDA, folded)
    row["potencia_maxima_demandada_kw"] = _number(_RE_DEMANDA_MAXIMA, folded)
    row["potencia_hora_punta_kw"] = _number_from_patterns(_RE_POTENCIA_PUNTA, folded)
    row["potencia_fuera_punta_kw"] = _number_from_patterns(
        _RE_POTENCIA_FUERA_PUNTA, folded
    )
    row["potencia_contratada_kw"] = _number_from_patterns(
        _RE_POTENCIA_CONTRATADA, folded
    )

    row["energia_consumida_kwh"] = _number(_RE_ENERGIA_CONSUMIDA, folded)
    if row["energia_consumida_kwh"] is None:
        row["energia_consumida_kwh"] = row["consumo_kwh"]

    # Para tarifas PPP la demanda facturada corresponde a la demanda en punta.
    if (
        row["potencia_hora_punta_kw"] is None
        and row["potencia_maxima_demandada_kw"] is not None
        and row["tarifa"]
        and "PPP" in row["tarifa"].upper()
    ):
        row["potencia_hora_punta_kw"] = row["potencia_maxima_demandada_kw"]

    # El factor de potencia se estima con la energia activa del medidor, que es
    # la que corresponde a la energia reactiva registrada por ese mismo equipo.
    activa_medidor = row["consumo_kwh"]
    if activa_medidor is None:
        activa_medidor = row["energia_consumida_kwh"]
    if activa_medidor and row["energia_reactiva_kvarh"] is not None:
        reactiva = row["energia_reactiva_kvarh"]
        if activa_medidor > 0:
            row["factor_potencia_estimado"] = round(
                activa_medidor / ((activa_medidor**2 + reactiva**2) ** 0.5), 4
            )

    if row["energia_consumida_kwh"] and row["dias_periodo"]:
        row["consumo_promedio_diario_kwh"] = round(
            row["energia_consumida_kwh"] / row["dias_periodo"], 3
        )

    # --- Cobros -----------------------------------------------------------
    charges = _extract_charges(original, folded)
    for key, amount in charges["amounts"].items():
        column = _CHARGE_COLUMN.get(key)
        if column:
            row[column] = amount
    if row["electricidad_consumida_clp"] and row["energia_consumida_kwh"]:
        row["costo_unitario_energia_clp_kwh"] = round(
            row["electricidad_consumida_clp"] / row["energia_consumida_kwh"], 2
        )
    row["descuentos_clp"] = charges["descuentos"]
    row["otros_cargos_clp"] = charges["otros"]
    row["detalle_cobros_json"] = charges["detail_json"]

    # --- Totales ----------------------------------------------------------
    footer_matches = _RE_FOOTER.findall(folded)
    if footer_matches:
        values = [parse_number(part) for part in footer_matches[-1]]
        if all(value is not None for value in values):
            (
                row["monto_exento_clp"],
                row["monto_neto_clp"],
                row["iva_clp"],
                row["total_periodo_clp"],
                row["saldo_anterior_facturado_clp"],
                row["otros_cargos_factura_clp"],
                row["total_a_pagar_clp"],
            ) = values

    if row["total_a_pagar_clp"] is None:
        fecha_monto = _RE_FECHA_MONTO.findall(folded)
        if fecha_monto:
            fecha_raw, monto_raw = fecha_monto[-1]
            row["total_a_pagar_clp"] = parse_number(monto_raw)
            if not row["fecha_vencimiento"]:
                row["fecha_vencimiento"] = date_to_iso(fecha_raw)

    if row["saldo_anterior_clp"] is None and row["saldo_anterior_facturado_clp"]:
        row["saldo_anterior_clp"] = row["saldo_anterior_facturado_clp"]

    if row["monto_neto_clp"] and row["iva_clp"] is not None:
        row["tasa_iva_pct"] = round(
            row["iva_clp"] / row["monto_neto_clp"] * 100, 2
        )

    # --- Compensaciones SEC ----------------------------------------------
    row["compensacion_periodo"] = _value(_RE_COMP_PERIODO, folded, original)
    interrupciones = _number(_RE_COMP_INTERRUPCIONES, folded)
    row["compensacion_interrupciones"] = int(interrupciones) if interrupciones is not None else None
    row["compensacion_tiempo_total_seg"] = _number(_RE_COMP_TIEMPO_TOTAL, folded)
    row["compensacion_tiempo_a_compensar_seg"] = _number(
        _RE_COMP_TIEMPO_COMPENSAR, folded
    )
    row["compensacion_consumo_promedio_kwh_seg"] = _number(
        _RE_COMP_CONSUMO_PROMEDIO, folded
    )
    row["compensacion_energia_kwh"] = _number(_RE_COMP_ENERGIA, folded)
    row["compensacion_costo_falla_clp_kwh"] = _number(_RE_COMP_COSTO_FALLA, folded)
    row["compensacion_monto_clp"] = _number(_RE_COMP_MONTO, folded)

    # --- Mensajes numerados de la boleta ---------------------------------
    note_lines: List[str] = []
    started = False
    for line in original_lines:
        stripped = line.strip()
        if _RE_NOTA_NUMERADA.match(stripped):
            started = True
        if not started:
            continue
        if re.match(
            r"^\d{1,2}\s+[A-Za-z]{3,10}\s+\d{4}\s+\$", stripped, re.IGNORECASE
        ):
            break
        if stripped:
            note_lines.append(stripped)
    row["observaciones"] = clean_value(" ".join(note_lines)) if note_lines else None

    return row


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


_KEY_FIELDS_FOR_FALLBACK = (
    "numero_cliente",
    "folio_factura",
    "cliente_nombre",
    "tarifa",
    "periodo_desde",
    "periodo_hasta",
    "numero_medidor",
    "energia_consumida_kwh",
    "total_a_pagar_clp",
)


def _row_score(row: Dict[str, Any]) -> int:
    return sum(1 for key in _KEY_FIELDS_FOR_FALLBACK if row.get(key) is not None)


def extract_bill(path: Path, *, include_text: bool = False) -> Dict[str, Any]:
    """Lee un PDF y devuelve un diccionario con todos los campos de la boleta."""
    content = read_pdf(path)
    pdf_hash = _sha256(path)
    row = extract_from_text(
        content.text,
        source=str(path),
        pages=content.pages,
        pdf_hash=pdf_hash,
        include_text=include_text,
    )

    # Si faltan datos clave, probar la extraccion conservando el layout de las
    # columnas y quedarse con el resultado que reconozca mas campos.
    if any(row.get(key) is None for key in ("numero_cliente", "periodo_desde", "total_a_pagar_clp")):
        try:
            alternative = read_pdf(path, layout=True)
            alternative_row = extract_from_text(
                alternative.text,
                source=str(path),
                pages=alternative.pages,
                pdf_hash=pdf_hash,
                include_text=include_text,
            )
            if _row_score(alternative_row) > _row_score(row):
                row = alternative_row
        except PdfReadError:
            pass

    return row
