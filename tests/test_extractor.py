import unittest

from ebill_extractor.extractor import extract_from_text

SAMPLE_TEXT = """
 1.234.567
SEÑOR(A)Cliente Demo N° CLIENTE:123456 - 7
Calle Falsa 123 FECHA EMISIÓN: 05 jun 2023
Santiago FECHA VENCIMIENTO: 25 jun 2023
Cliente Demo 12.345.678-9
GIRO DEMO 05 jun 2023
Calle Falsa 123, Santiago
Tarifa BT-3 PPP LECTURAS Desde 05 may 2023 al 05 jun 2023
Zona Tarifaria Aéreo
Subestación CENTRAL Nr. Medidor Cte Tipo Prop. Actual Anterior Consumo
Potencia Conectada 50 KVA 12345678 1 Activo Empresa 1000 800 200
Límite de Invierno
Dirección Calle Falsa 123 Santiago
Bloque de Corte 10
Cons. Referencia Prx. Per 210 kWh
Grupo Consumo DEMO
Fecha estimada próx. lectura: 05-JUL-2023
Fecha Límite para cambio tarifa 05-JUN-2024 COBROS
Fecha Término de tarifa Indefinida
Demanda Leida 10,5 kW Administración del servicio 1.000
Electricidad consumida 200kWh 20.000
Uso del Sistema de Transmisión 1.000
Cargo Ley 21.472 200kWh 500
Demanda Máxima 12,0kW 5.000
Arriendo Medidor 300
Pago Fuera de Plazo 100
Interés por Mora 200
Último pago: $ 15.000
01-06-2023 10:00 BANCO ESTADO
Detalle de Compensaciones
Compensación SEC por interrupciones de
suministro del periodo: Jun/2022-May/2023
Total de interrupciones: 1
Tiempo total interrumpido(seg): 3600
Tiempo a compensar(seg): 1800
Consumo promedio(Kwh/Seg): 0,00001
Energía a compensar(Kwh): 0,02000
Costo de falla($/Kwh): 100,000
Monto a compensar($): 2
1.000 25.000 4.750 30.750 0 0 30.750
N° FACTURA: 1234567
12345670003075000P0202000178907183 N° CLIENTE: 123456 - 7
N° RUTA: 01_234_5678
"""


class ExtractorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.row = extract_from_text(SAMPLE_TEXT, source="demo.pdf", pages=1)

    def test_identificacion(self):
        self.assertEqual(self.row["cliente_nombre"], "Cliente Demo")
        self.assertEqual(self.row["cliente_rut"], "12.345.678-9")
        self.assertEqual(self.row["numero_cliente"], "123456-7")
        self.assertEqual(self.row["cliente_direccion"], "Calle Falsa 123, Santiago")
        self.assertEqual(self.row["cliente_comuna"], "Santiago")
        self.assertEqual(self.row["folio_factura"], "1234567")
        self.assertEqual(self.row["numero_ruta"], "01_234_5678")

    def test_tarifa_y_fechas(self):
        self.assertEqual(self.row["tarifa"], "BT-3 PPP")
        self.assertEqual(self.row["periodo_desde"], "2023-05-05")
        self.assertEqual(self.row["periodo_hasta"], "2023-06-05")
        self.assertEqual(self.row["dias_periodo"], 31)
        self.assertEqual(self.row["fecha_emision"], "2023-06-05")
        self.assertEqual(self.row["fecha_vencimiento"], "2023-06-25")
        self.assertEqual(self.row["fecha_limite_cambio_tarifa"], "2024-06-05")
        self.assertEqual(self.row["fecha_termino_tarifa"], "Indefinida")

    def test_medidor_y_energia(self):
        self.assertEqual(self.row["numero_medidor"], "12345678")
        self.assertEqual(self.row["tipo_lectura"], "Real")
        self.assertEqual(self.row["lectura_actual"], 1000.0)
        self.assertEqual(self.row["lectura_anterior"], 800.0)
        self.assertEqual(self.row["consumo_kwh"], 200.0)
        self.assertEqual(self.row["energia_consumida_kwh"], 200.0)
        self.assertEqual(self.row["potencia_leida_kw"], 10.5)
        self.assertEqual(self.row["potencia_maxima_demandada_kw"], 12.0)
        self.assertEqual(self.row["potencia_hora_punta_kw"], 12.0)

    def test_cobros_y_totales(self):
        self.assertEqual(self.row["administracion_servicio_clp"], 1000.0)
        self.assertEqual(self.row["electricidad_consumida_clp"], 20000.0)
        self.assertEqual(self.row["uso_sistema_transmision_clp"], 1000.0)
        self.assertEqual(self.row["cargo_ley_21472_clp"], 500.0)
        self.assertEqual(self.row["demanda_maxima_clp"], 5000.0)
        self.assertEqual(self.row["arriendo_medidor_clp"], 300.0)
        self.assertEqual(self.row["pago_fuera_plazo_clp"], 100.0)
        self.assertEqual(self.row["interes_mora_clp"], 200.0)
        self.assertIsNone(self.row["otros_cargos_clp"])
        self.assertEqual(self.row["monto_exento_clp"], 1000.0)
        self.assertEqual(self.row["monto_neto_clp"], 25000.0)
        self.assertEqual(self.row["iva_clp"], 4750.0)
        self.assertEqual(self.row["total_periodo_clp"], 30750.0)
        self.assertEqual(self.row["total_a_pagar_clp"], 30750.0)
        self.assertEqual(self.row["tasa_iva_pct"], 19.0)

    def test_compensaciones(self):
        self.assertEqual(self.row["compensacion_periodo"], "Jun/2022-May/2023")
        self.assertEqual(self.row["compensacion_interrupciones"], 1)
        self.assertEqual(self.row["compensacion_tiempo_total_seg"], 3600.0)
        self.assertEqual(self.row["compensacion_tiempo_a_compensar_seg"], 1800.0)
        self.assertEqual(self.row["compensacion_monto_clp"], 2.0)


if __name__ == "__main__":
    unittest.main()
