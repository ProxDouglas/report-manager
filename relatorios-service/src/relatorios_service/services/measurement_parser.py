import math
import re

from relatorios_service.pipeline_schemas import NumberFormat


class MeasurementParser:
    """Extrai pares completos sem converter unidades nem descartar texto desconhecido."""

    # Catálogo controlado: unidades desconhecidas não são inferidas pelo nome da coluna.
    units = (
        "unidades", "unidade", "units", "unit", "µg", "μg", "mg", "kg", "g", "t",
        "lbs", "lb", "oz", "mm", "cm", "km", "m", "ft", "in",
        "mL", "ml", "cL", "cl", "dL", "dl", "L", "l", "µL", "μL",
        "s", "min", "h", "K", "°C", "°F", "mol", "Pa", "kPa", "MPa",
        "N", "J", "kJ", "W", "kW", "Hz", "V", "A", "%",
    )
    atom = "(?:" + "|".join(re.escape(unit) for unit in sorted(units, key=len, reverse=True)) + ")(?:[²³]|\\^[23]|[23])?"
    unit_pattern = atom + "(?:[/*·]" + atom + ")*"
    separators = re.compile(r"[\s(),;]*")
    max_pairs = 10

    def __init__(self) -> None:
        numbers = {
            NumberFormat.STANDARD: r"[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?",
            NumberFormat.BRAZILIAN: r"[+-]?(?:[0-9]{1,3}(?:\.[0-9]{3})+|[0-9]+)(?:,[0-9]+)?(?:[eE][+-]?[0-9]+)?",
        }
        self.patterns = {
            number_format: re.compile("(" + number + r")\s*(" + self.unit_pattern + ")")
            for number_format, number in numbers.items()
        }

    def parse(self, value: str, number_format: NumberFormat = NumberFormat.STANDARD) -> list[tuple[float, str]] | None:
        pattern = self.patterns[number_format]
        pairs = []
        position = 0
        for match in pattern.finditer(value):
            if not self.separators.fullmatch(value[position:match.start()]):
                return None
            token = match[1]
            if number_format == NumberFormat.BRAZILIAN:
                token = token.replace(".", "").replace(",", ".")
            numeric = float(token)
            if not math.isfinite(numeric):
                return None
            pairs.append((numeric, match[2]))
            if len(pairs) > self.max_pairs:
                return None
            position = match.end()
        if not pairs or not self.separators.fullmatch(value[position:]):
            return None
        return pairs
