# ebill-extractor

Extractor de parametros de boletas electricas chilenas en PDF. Lee una carpeta
completa o un archivo PDF y genera un resumen consolidado en CSV, JSON o Excel.

Fue probado con boletas Chilquinta de tarifa `BT-1A` y `BT-3 PPP`, incluyendo
boletas con lectura real, lectura estimada, saldo anterior, intereses por mora y
compensaciones SEC. El diseno tambien reconoce etiquetas habituales de otras
distribuidoras chilenas, pero cada distribuidora puede variar el layout.

## Requisitos

- Python 3.9 o superior.
- Dependencias: `pdfplumber` y `openpyxl` (se instalan automaticamente).

## Instalacion global

Desde esta carpeta:

```powershell
py -m pip install --upgrade pip
py -m pip install .
```

Si no tiene el lanzador `py`, use `python` en lugar de `py`.

Si el Python global no permite instalar paquetes, use una de estas alternativas:

```powershell
py -m pip install --user .
```

o, recomendado para una herramienta CLI:

```powershell
pipx install .
```

Verificar la instalacion:

```powershell
ebill-extractor --version
ebill-extractor --lista-campos
```

El instalador tambien crea el alias en espanol `extraer-boletas`, con las mismas
opciones:

```powershell
extraer-boletas .
```

## Uso rapido

Procesar todos los PDFs de la carpeta actual (`./`):

```powershell
ebill-extractor
```

Genera `boletas_extraidas.csv` en la carpeta actual.

Procesar otra carpeta:

```powershell
ebill-extractor "C:\Boletas\2023"
```

Procesar una carpeta y sus subcarpetas, generando Excel:

```powershell
ebill-extractor "C:\Boletas" --recursivo --formato xlsx --salida resumen.xlsx
```

Generar JSON con el texto completo del PDF incluido:

```powershell
ebill-extractor . --formato json --salida boletas.json --incluir-texto
```

Generar ademas el detalle largo de todos los cobros:

```powershell
ebill-extractor . --detalle-cargos --salida boletas.csv
```

Procesar un solo archivo:

```powershell
ebill-extractor "C:\Boletas\08-2023.pdf" -o agosto.csv
```

## Opciones principales

| Opcion | Descripcion |
|---|---|
| `ruta` | Carpeta o archivo PDF. Por defecto `./`. |
| `-o`, `--salida` | Archivo de salida. |
| `-f`, `--formato` | `csv` (por defecto), `json` o `xlsx`. |
| `-r`, `--recursivo` | Busca PDFs en subcarpetas. |
| `-p`, `--patron` | Patron de busqueda. Por defecto `*.pdf`. |
| `--separador` | Separador CSV. Por defecto `;` (compatible con Excel en espanol). |
| `--decimal` | `auto`, `coma` o `punto`. Por defecto `auto`. |
| `--incluir-texto` | Agrega la columna `texto_pdf` con el texto completo. |
| `--detalle-cargos` | Genera un archivo adicional con un registro por cada cobro. |
| `--deduplicar` | Omite boletas duplicadas (mismo cliente y folio, o mismo hash). |
| `--detener-en-error` | Se detiene en el primer PDF con error. |
| `-v`, `--verbose` | Muestra el progreso archivo por archivo. |
| `--silencioso` | No muestra progreso ni resumen. |
| `--lista-campos` | Lista todos los campos extraidos y sus descripciones. |

Los errores de lectura no detienen el proceso: quedan registrados en la columna
`error_extraccion` del archivo de salida.

## Campos extraidos

La lista completa y actualizada se obtiene con:

```powershell
ebill-extractor --lista-campos
```

Los campos se agrupan en:

- **Archivo:** nombre, ruta, hash SHA-256, paginas, fecha de extraccion, version.
- **Cliente:** nombre, RUT, giro, direccion, comuna, numero de cliente.
- **Suministro:** direccion, tarifa, zona tarifaria, subestacion, grupo de consumo.
- **Fechas:** emision, vencimiento, periodo de lectura desde/hasta, dias del periodo,
  proxima lectura estimada, limite de cambio de tarifa, termino de tarifa, fecha
  de corte, ultimo pago (fecha, hora, medio y monto).
- **Medidor y lecturas:** numero, tipo, propiedad, constante, tipo de lectura
  (real o estimada), lectura actual y anterior de energia activa, consumo,
  lectura y energia reactiva, factor de potencia estimado, potencia conectada,
  limite de invierno, bloque de corte y consumo de referencia.
- **Potencia:** demanda leida, demanda maxima facturada, potencia en hora de punta,
  potencia fuera de punta y potencia contratada cuando aparecen.
- **Energia:** energia consumida, consumo promedio diario y costo unitario.
- **Cobros:** administracion del servicio, electricidad consumida, uso del sistema
  de transmision, uso del sistema de distribucion, cargo Ley 21.472, demanda
  maxima, demanda en punta, energia reactiva, recargo por factor de potencia,
  arriendo de medidor, pago fuera de plazo, interes por mora, corte, reconexion,
  saldo anterior, descuentos y otros cargos.
- **Totales:** monto exento, neto, IVA, tasa de IVA implicita, total del periodo,
  saldo anterior, otros cargos y total a pagar.
- **Compensaciones SEC:** periodo evaluado, interrupciones, tiempos, energia,
  costo de falla y monto a compensar.
- **Detalle y mensajes:** `detalle_cobros_json` con todos los cobros detectados,
  incluso los que no tienen una columna fija, y `observaciones` con las notas
  numeradas impresas en la boleta.

## Criterios de interpretacion

- **Numeros chilenos:** `2.638,7` se interpreta como `2638.7`; `3.273` como
  `3273`. Los montos se expresan en pesos chilenos (CLP).
- **Fechas:** se normalizan a ISO 8601 (`AAAA-MM-DD`). Si una fecha no es
  parseable, se conserva el texto original.
- **Linea de totales:** en las boletas de ejemplo la linea final tiene siete
  valores: monto exento, neto, IVA, total del periodo, saldo anterior, otros
  cargos y total a pagar. El extractor usa ese orden y calcula la tasa de IVA
  implicita.
- **Potencia en hora de punta:** si la boleta trae una etiqueta explicita se usa
  esa. Si la tarifa contiene `PPP` y no hay etiqueta explicita, se replica la
  demanda maxima facturada, que es la potencia que cobra ese tipo de tarifa.
- **Lectura estimada:** cuando aparece `Estimado` o `Estmado` en la fila del
  medidor, se marca `tipo_lectura = Estimada` y se conserva la lectura anterior
  y el consumo informado.
- **Cobros no catalogados:** se agregan a `otros_cargos_clp` y al detalle JSON.
- **Compensaciones SEC:** se extraen los campos del bloque de compensacion por
  interrupciones de suministro.

## Salidas

- **CSV:** UTF-8 con BOM, separador `;` y decimal coma por defecto, para abrir
  directamente en Excel en espanol. Use `--separador , --decimal punto` para un
  CSV internacional.
- **JSON:** lista de objetos, un objeto por boleta. El campo
  `detalle_cobros_json` se convierte en una lista JSON anidada.
- **XLSX:** hoja `Boletas` con todos los campos, hoja `Diccionario` con la
  descripcion de cada campo y, si se usa `--detalle-cargos`, hoja `Cargos`.

## Limitaciones

- PDFs escaneados como imagen no tienen texto extraible. En ese caso la fila
  queda con `error_extraccion` y se requiere OCR externo (por ejemplo,
  `ocrmypdf` + Tesseract) antes de usar este extractor.
- Layouts muy distintos pueden requerir agregar patrones o alias en
  `src/ebill_extractor/extractor.py`.
- El extractor no valida legalmente la facturacion; solo interpreta y consolida
  los datos impresos en la boleta.

## Desarrollo

```powershell
py -m pip install -e .
py -m unittest discover -s tests -v
```
