"""
온도 센서 파서
"""

import logging
from typing import Dict, Any, Optional
from .base import BaseParser, ParsedData

logger = logging.getLogger(__name__)


class TemperatureParser(BaseParser):
    """온도 센서 데이터 파서"""

    SENSOR_TYPE = "temperature"
    DEFAULT_UNIT = "celsius"

    # 지원하는 온도 단위
    VALID_UNITS = ['celsius', 'fahrenheit', 'kelvin', 'c', 'f', 'k']

    # 유효 온도 범위 (섭씨 기준)
    MIN_TEMP = -100
    MAX_TEMP = 200

    def _validate(self, data: Dict[str, Any]) -> bool:
        """온도 데이터 검증"""
        if not super()._validate(data):
            return False

        # 온도 범위 검증
        value = float(data['value'])
        unit = data.get('unit', self.DEFAULT_UNIT).lower()

        # 섭씨로 변환하여 검증
        temp_celsius = self._to_celsius(value, unit)

        if temp_celsius < self.MIN_TEMP or temp_celsius > self.MAX_TEMP:
            logger.warning(
                f"온도 범위 초과: {value} {unit} "
                f"(섭씨 {temp_celsius}도, 유효 범위: {self.MIN_TEMP}~{self.MAX_TEMP})"
            )
            return False

        return True

    def _transform(self, data: Dict[str, Any], topic: str = None) -> ParsedData:
        """온도 데이터 변환"""
        sensor_id = data.get('sensor_id')
        if not sensor_id and topic:
            sensor_id = self._extract_sensor_id_from_topic(topic)

        value = float(data['value'])
        unit = data.get('unit', self.DEFAULT_UNIT).lower()

        # 단위 정규화
        if unit in ['c', 'celsius']:
            unit = 'celsius'
        elif unit in ['f', 'fahrenheit']:
            unit = 'fahrenheit'
        elif unit in ['k', 'kelvin']:
            unit = 'kelvin'

        return ParsedData(
            sensor_id=sensor_id,
            sensor_type=self.SENSOR_TYPE,
            value=value,
            unit=unit,
            timestamp=self._parse_timestamp(data.get('timestamp')),
            extra_data={
                'celsius': self._to_celsius(value, unit),
                'fahrenheit': self._to_fahrenheit(value, unit),
            }
        )

    def _to_celsius(self, value: float, unit: str) -> float:
        """섭씨로 변환"""
        unit = unit.lower()
        if unit in ['fahrenheit', 'f']:
            return (value - 32) * 5 / 9
        elif unit in ['kelvin', 'k']:
            return value - 273.15
        return value

    def _to_fahrenheit(self, value: float, unit: str) -> float:
        """화씨로 변환"""
        unit = unit.lower()
        if unit in ['celsius', 'c']:
            return value * 9 / 5 + 32
        elif unit in ['kelvin', 'k']:
            return (value - 273.15) * 9 / 5 + 32
        return value
