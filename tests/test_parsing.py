import unittest

from ebill_extractor.parsing import (
    fold_accents,
    format_decimal,
    normalize_client_number,
    parse_date,
    parse_number,
)


class ParsingTests(unittest.TestCase):
    def test_fold_accents_preserves_length(self):
        original = "ACTIVIDADES DE LA ADMINISTRACIÓN PÚBLICA"
        folded = fold_accents(original)
        self.assertEqual(len(original), len(folded))
        self.assertEqual(folded, "ACTIVIDADES DE LA ADMINISTRACION PUBLICA")

    def test_parse_number_chilean(self):
        cases = {
            "2.638,7": 2638.7,
            "3.273": 3273.0,
            "1.465.217": 1465217.0,
            "12,9": 12.9,
            "0,00000": 0.0,
            "100,000": 100.0,
            "1,234,567": 1234567.0,
            "100 KVA": 100.0,
            "$ 1.393": 1393.0,
            "1.234.567": 1234567.0,
            "32kW": 32.0,
            "200kWh": 200.0,
            "0": 0.0,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(parse_number(raw), expected)

    def test_parse_date(self):
        self.assertEqual(parse_date("05 jun 2023").isoformat(), "2023-06-05")
        self.assertEqual(parse_date("04-SEP-2023").isoformat(), "2023-09-04")
        self.assertEqual(parse_date("04/09/2023").isoformat(), "2023-09-04")
        self.assertEqual(parse_date("2023-09-04").isoformat(), "2023-09-04")
        self.assertIsNone(parse_date("Indefinida"))

    def test_normalize_client_number(self):
        self.assertEqual(normalize_client_number("217292 - 5"), "217292-5")
        self.assertEqual(normalize_client_number("162645 - K"), "162645-K")

    def test_format_decimal(self):
        self.assertEqual(format_decimal(2638.7, ","), "2638,7")
        self.assertEqual(format_decimal(129792.0, ","), "129792")
        self.assertEqual(format_decimal(0.9991, "."), "0.9991")


if __name__ == "__main__":
    unittest.main()
