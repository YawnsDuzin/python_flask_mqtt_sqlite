"""
습도 센서 파서
"""

import logging
from typing import Dict, Any
from .base import BaseParser, ParsedData

logger = logging.getLogger(__name__)


class HumidityParser(BaseParser):
    """습도 센서 데이터 파서"""

    SENSOR_TYPE = "humidity"
    DEFAULT_UNIT = "percent"

    # 유효 습도 범위
    MIN_HUMIDITY = 0
    MAX_HUMIDITY = 100

    def _validate(self, data: Dict[str, Any]) -> bool:
        """습도 데이터 검증"""
        if not super()._validate(data):
            return False

        # 습도 범위 검증
        value = float(data['value'])

        if value < self.MIN_HUMIDITY or value > self.MAX_HUMIDITY:
            logger.warning(
                f"습도 범위 초과: {value}% "
                f"(유효 범위: {self.MIN_HUMIDITY}~{self.MAX_HUMIDITY})"
            )
            return False

        return True

    def _transform(self, data: Dict[str, Any], topic: str = None) -> ParsedData:
        """습도 데이터 변환"""
        sensor_id = data.get('sensor_id')
        if not sensor_id and topic:
            sensor_id = self._extract_sensor_id_from_topic(topic)

        value = float(data['value'])
        unit = data.get('unit', self.DEFAULT_UNIT).lower()

        # 단위 정규화
        if unit in ['%', 'pct', 'percent', 'rh']:
            unit = 'percent'

        # 습도 상태 분류
        humidity_status = self._classify_humidity(value)

        return ParsedData(
            sensor_id=sensor_id,
            sensor_type=self.SENSOR_TYPE,
            value=value,
            unit=unit,
            timestamp=self._parse_timestamp(data.get('timestamp')),
            extra_data={
                'status': humidity_status,
                'is_comfortable': 30 <= value <= 60
            }
        )

    def _classify_humidity(self, value: float) -> str:
        """습도 상태 분류"""
        if value < 20:
            return 'very_dry'
        elif value < 30:
            return 'dry'
        elif value <= 60:
            return 'comfortable'
        elif value <= 70:
            return 'humid'
        else:
            return 'very_humid'
