"""Catalogo ordenado de campos extraidos de las boletas electricas."""

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Field:
    key: str
    description: str


FIELDS: List[Field] = [
    # Metadatos del archivo
    Field("archivo", "Nombre del archivo PDF."),
    Field("ruta_archivo", "Ruta absoluta del archivo PDF procesado."),
    Field("error_extraccion", "Error ocurrido al leer o interpretar el PDF."),
    Field("hash_pdf", "Huella SHA-256 del archivo PDF."),
    Field("paginas_pdf", "Cantidad de paginas del PDF."),
    Field("fecha_extraccion", "Fecha y hora en que se ejecuto la extraccion."),
    Field("version_extractor", "Version del extractor utilizada."),

    # Identificacion
    Field("distribuidora", "Empresa distribuidora de electricidad."),
    Field("folio_factura", "Numero o folio de la factura/boleta."),
    Field("numero_ruta", "Numero de ruta de reparto o lectura."),
    Field("timbre_electronico", "Cadena del timbre electronico SII."),
    Field("cliente_nombre", "Nombre o razon social del cliente."),
    Field("cliente_rut", "RUT del cliente."),
    Field("cliente_giro", "Giro o actividad economica del cliente."),
    Field("cliente_direccion", "Direccion postal del cliente."),
    Field("cliente_comuna", "Comuna del cliente."),
    Field("numero_cliente", "Numero de cliente (incluye digito verificador si existe)."),
    Field("direccion_suministro", "Direccion del inmueble o suministro electrico."),
    Field("tarifa", "Codigo de tarifa electrica (por ejemplo BT-1A o BT-3 PPP)."),
    Field("zona_tarifaria", "Zona tarifaria (aerea, subterranea, etc.)."),
    Field("subestacion", "Subestacion de distribucion asociada al suministro."),
    Field("grupo_consumo", "Grupo de consumo o distribuidora informada en la boleta."),

    # Fechas y periodo
    Field("fecha_emision", "Fecha de emision de la boleta (ISO 8601)."),
    Field("fecha_vencimiento", "Fecha de vencimiento de la boleta (ISO 8601)."),
    Field("periodo_desde", "Fecha de lectura inicial del periodo (ISO 8601)."),
    Field("periodo_hasta", "Fecha de lectura final del periodo (ISO 8601)."),
    Field("dias_periodo", "Dias transcurridos entre la lectura inicial y final."),
    Field("fecha_estimada_proxima_lectura", "Fecha estimada de la proxima lectura (ISO 8601)."),
    Field("fecha_limite_cambio_tarifa", "Fecha limite para cambio de tarifa, o condicion informada."),
    Field("fecha_termino_tarifa", "Fecha de termino de la tarifa, o condicion informada."),
    Field("fecha_corte", "Fecha de corte anunciada en la boleta (ISO 8601), si aparece."),
    Field("fecha_ultimo_pago", "Fecha del ultimo pago registrado (ISO 8601)."),
    Field("hora_ultimo_pago", "Hora del ultimo pago registrado."),
    Field("medio_ultimo_pago", "Medio o canal del ultimo pago registrado."),
    Field("monto_ultimo_pago_clp", "Monto del ultimo pago registrado (CLP)."),

    # Medidor y lecturas
    Field("numero_medidor", "Numero de serie del medidor."),
    Field("tipo_medidor", "Tipo de medidor (activo, reactivo, etc.)."),
    Field("tipo_lectura", "Tipo de lectura del periodo: Real o Estimada."),
    Field("propiedad_medidor", "Propiedad del medidor (empresa, cliente, etc.)."),
    Field("constante_medidor", "Constante o multiplicador del medidor."),
    Field("lectura_actual", "Lectura actual del medidor de energia activa."),
    Field("lectura_anterior", "Lectura anterior del medidor de energia activa."),
    Field("consumo_kwh", "Consumo de energia activa obtenido por diferencia de lecturas (kWh)."),
    Field("lectura_reactivo_actual", "Lectura actual del medidor de energia reactiva."),
    Field("lectura_reactivo_anterior", "Lectura anterior del medidor de energia reactiva."),
    Field("energia_reactiva_kvarh", "Energia reactiva consumida en el periodo (kVArh)."),
    Field("factor_potencia_estimado", "Factor de potencia estimado a partir de kWh y kVArh."),
    Field("potencia_conectada_kva", "Potencia conectada del suministro (kVA)."),
    Field("limite_invierno_kw", "Limite de invierno informado (kW), si aparece."),
    Field("bloque_corte", "Bloque de corte informado por la distribuidora."),
    Field("consumo_referencia_kwh", "Consumo de referencia para el proximo periodo (kWh)."),

    # Potencia y demanda
    Field("potencia_leida_kw", "Demanda leida en el periodo (kW)."),
    Field("potencia_maxima_demandada_kw", "Demanda maxima facturada o demandada (kW)."),
    Field(
        "potencia_hora_punta_kw",
        "Potencia en hora de punta (kW). Si la tarifa es PPP y la boleta no trae un campo "
        "explicito, se usa la demanda maxima facturada.",
    ),
    Field("potencia_fuera_punta_kw", "Potencia fuera de punta (kW), si aparece."),
    Field("potencia_contratada_kw", "Potencia o demanda contratada (kW), si aparece."),

    # Energia
    Field("energia_consumida_kwh", "Energia activa facturada en el periodo (kWh)."),
    Field("consumo_promedio_diario_kwh", "Consumo promedio diario del periodo (kWh/dia)."),
    Field("costo_unitario_energia_clp_kwh", "Costo unitario de la energia facturada (CLP/kWh)."),

    # Cobros itemizados
    Field("administracion_servicio_clp", "Cargo por administracion del servicio (CLP)."),
    Field("electricidad_consumida_clp", "Cargo por electricidad consumida (CLP)."),
    Field("uso_sistema_transmision_clp", "Cargo por uso del sistema de transmision (CLP)."),
    Field("uso_sistema_distribucion_clp", "Cargo por uso del sistema de distribucion (CLP)."),
    Field("cargo_ley_21472_clp", "Cargo por Fondo de Estabilizacion de Tarifas, Ley 21.472 (CLP)."),
    Field("demanda_maxima_clp", "Cargo por demanda maxima (CLP)."),
    Field("demanda_hora_punta_clp", "Cargo por demanda en hora de punta (CLP)."),
    Field("energia_reactiva_clp", "Cargo por energia reactiva (CLP)."),
    Field("recargo_factor_potencia_clp", "Recargo por bajo factor de potencia (CLP)."),
    Field("arriendo_medidor_clp", "Cargo por arriendo de medidor (CLP)."),
    Field("pago_fuera_plazo_clp", "Cargo o recargo por pago fuera de plazo (CLP)."),
    Field("interes_mora_clp", "Interes por mora (CLP)."),
    Field("servicio_corte_clp", "Cargo por corte de suministro (CLP)."),
    Field("servicio_reconexion_clp", "Cargo por reconexion de suministro (CLP)."),
    Field("saldo_anterior_clp", "Saldo anterior itemizado en la boleta (CLP)."),
    Field("descuento_generacion_local_clp", "Descuento por Reconocimiento de Generacion Local (CLP)."),
    Field("descuentos_clp", "Suma de descuentos itemizados (CLP)."),
    Field("otros_cargos_clp", "Suma de cobros no clasificados en las columnas anteriores (CLP)."),
    Field("detalle_cobros_json", "Detalle JSON de todos los cobros detectados (concepto y monto)."),

    # Totales
    Field("monto_exento_clp", "Monto exento o no afecto a IVA (CLP)."),
    Field("monto_neto_clp", "Monto neto afecto a IVA (CLP)."),
    Field("iva_clp", "Monto de IVA (CLP)."),
    Field("tasa_iva_pct", "Tasa de IVA implicita calculada sobre el monto neto (%)."),
    Field("total_periodo_clp", "Total del periodo facturado, incluido IVA (CLP)."),
    Field("saldo_anterior_facturado_clp", "Saldo anterior incluido en el total a pagar (CLP)."),
    Field("otros_cargos_factura_clp", "Otros cargos incluidos en el total a pagar (CLP)."),
    Field("total_a_pagar_clp", "Total final a pagar de la boleta (CLP)."),
    Field("moneda", "Moneda de los montos (CLP)."),

    # Compensaciones SEC
    Field("compensacion_periodo", "Periodo evaluado para la compensacion SEC por interrupciones."),
    Field("compensacion_interrupciones", "Numero total de interrupciones del periodo evaluado."),
    Field("compensacion_tiempo_total_seg", "Tiempo total interrumpido (segundos)."),
    Field("compensacion_tiempo_a_compensar_seg", "Tiempo a compensar (segundos)."),
    Field("compensacion_consumo_promedio_kwh_seg", "Consumo promedio usado en la compensacion (kWh/seg)."),
    Field("compensacion_energia_kwh", "Energia a compensar (kWh)."),
    Field("compensacion_costo_falla_clp_kwh", "Costo de falla usado en la compensacion (CLP/kWh)."),
    Field("compensacion_monto_clp", "Monto a compensar por interrupciones (CLP)."),

    # Mensajes y texto completo
    Field("observaciones", "Mensajes numerados impresos en la boleta (notas legales y avisos)."),
    Field("texto_pdf", "Texto completo extraido del PDF (solo con --incluir-texto)."),
]

FIELD_KEYS: List[str] = [field.key for field in FIELDS]
FIELD_DESCRIPTIONS: Dict[str, str] = {field.key: field.description for field in FIELDS}

# Campos que forman el detalle largo de cobros.
CHARGE_DETAIL_KEYS = ["archivo", "numero_cliente", "folio_factura", "concepto", "clave", "monto_clp"]
