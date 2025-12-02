"""
진동 센서 파서
"""

import logging
from typing import Dict, Any
from .base import BaseParser, ParsedData

logger = logging.getLogger(__name__)


class VibrationParser(BaseParser):
    """진동 센서 데이터 파서"""

    SENSOR_TYPE = "vibration"
    DEFAULT_UNIT = "mm/s"

    # 유효 진동 범위 (mm/s)
    MIN_VIBRATION = 0
    MAX_VIBRATION = 1000

    # 진동 임계값 (ISO 10816 기준 참고)
    THRESHOLDS = {
        'good': 2.8,       # 좋음
        'satisfactory': 7.1,  # 만족
        'unsatisfactory': 18.0,  # 불만족
        # 그 이상: 허용 불가
    }

    def _validate(self, data: Dict[str, Any]) -> bool:
        """진동 데이터 검증"""
        if not super()._validate(data):
            return False

        # 진동 값 범위 검증
        value = float(data['value'])

        if value < self.MIN_VIBRATION:
            logger.warning(f"진동 값이 음수: {value}")
            return False

        if value > self.MAX_VIBRATION:
            logger.warning(
                f"진동 값 범위 초과: {value} "
                f"(최대: {self.MAX_VIBRATION})"
            )
            return False

        return True

    def _transform(self, data: Dict[str, Any], topic: str = None) -> ParsedData:
        """진동 데이터 변환"""
        sensor_id = data.get('sensor_id')
        if not sensor_id and topic:
            sensor_id = self._extract_sensor_id_from_topic(topic)

        value = float(data['value'])
        unit = data.get('unit', self.DEFAULT_UNIT).lower()

        # 단위 정규화
        if unit in ['mm/s', 'mms', 'velocity']:
            unit = 'mm/s'
        elif unit in ['g', 'acceleration']:
            unit = 'g'
        elif unit in ['um', 'displacement', 'micrometer']:
            unit = 'um'

        # 진동 상태 분류
        vibration_status = self._classify_vibration(value, unit)

        return ParsedData(
            sensor_id=sensor_id,
            sensor_type=self.SENSOR_TYPE,
            value=value,
            unit=unit,
            timestamp=self._parse_timestamp(data.get('timestamp')),
            extra_data={
                'status': vibration_status,
                'is_critical': vibration_status == 'unacceptable',
                'axis': data.get('axis'),  # x, y, z 축 정보
                'frequency': data.get('frequency')  # 주파수 정보
            }
        )

    def _classify_vibration(self, value: float, unit: str) -> str:
        """진동 상태 분류 (ISO 10816 기준)"""
        # mm/s 단위 기준으로 분류
        if unit == 'g':
            # g를 mm/s로 대략적 변환 (주파수에 따라 다름)
            value = value * 9.81 * 1000 / (2 * 3.14159 * 100)

        if value <= self.THRESHOLDS['good']:
            return 'good'
        elif value <= self.THRESHOLDS['satisfactory']:
            return 'satisfactory'
        elif value <= self.THRESHOLDS['unsatisfactory']:
            return 'unsatisfactory'
        else:
            return 'unacceptable'
