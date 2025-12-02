"""
데이터 파서 패키지
센서 타입별 파서를 관리하는 팩토리 패턴을 제공합니다.
"""

import logging
from typing import Optional, Dict, Type
from .base import BaseParser, ParsedData
from .temperature import TemperatureParser
from .humidity import HumidityParser
from .vibration import VibrationParser

logger = logging.getLogger(__name__)


class GenericParser(BaseParser):
    """범용 센서 파서 (알 수 없는 타입용)"""

    SENSOR_TYPE = "generic"
    DEFAULT_UNIT = "unit"

    def _transform(self, data: Dict, topic: str = None) -> ParsedData:
        """범용 데이터 변환"""
        sensor_id = data.get('sensor_id')
        if not sensor_id and topic:
            sensor_id = self._extract_sensor_id_from_topic(topic)

        return ParsedData(
            sensor_id=sensor_id,
            sensor_type=data.get('type', self.SENSOR_TYPE),
            value=float(data['value']),
            unit=data.get('unit', self.DEFAULT_UNIT),
            timestamp=self._parse_timestamp(data.get('timestamp')),
            extra_data=None
        )


class ParserFactory:
    """센서 파서 팩토리 클래스"""

    # 등록된 파서들
    _parsers: Dict[str, Type[BaseParser]] = {
        'temperature': TemperatureParser,
        'humidity': HumidityParser,
        'vibration': VibrationParser,
        'generic': GenericParser,
    }

    # 파서 인스턴스 캐시
    _instances: Dict[str, BaseParser] = {}

    @classmethod
    def register_parser(cls, sensor_type: str, parser_class: Type[BaseParser]):
        """
        새로운 파서 등록

        Args:
            sensor_type: 센서 타입 이름
            parser_class: 파서 클래스
        """
        cls._parsers[sensor_type.lower()] = parser_class
        logger.info(f"파서 등록됨: {sensor_type}")

    @classmethod
    def get_parser(cls, sensor_type: str) -> BaseParser:
        """
        센서 타입에 맞는 파서 반환

        Args:
            sensor_type: 센서 타입 이름

        Returns:
            해당 타입의 파서 인스턴스
        """
        sensor_type = sensor_type.lower() if sensor_type else 'generic'

        # 캐시에서 반환
        if sensor_type in cls._instances:
            return cls._instances[sensor_type]

        # 새 인스턴스 생성
        parser_class = cls._parsers.get(sensor_type, GenericParser)
        instance = parser_class()
        cls._instances[sensor_type] = instance

        logger.debug(f"파서 생성: {sensor_type} -> {parser_class.__name__}")
        return instance

    @classmethod
    def parse(cls, payload: str, topic: str = None) -> Optional[ParsedData]:
        """
        자동으로 적절한 파서를 선택하여 파싱

        토픽 또는 페이로드에서 센서 타입을 추출하여 적절한 파서를 선택합니다.

        Args:
            payload: MQTT 메시지 페이로드
            topic: MQTT 토픽

        Returns:
            ParsedData 또는 None
        """
        import json

        # 센서 타입 추출
        sensor_type = None

        # 1. 토픽에서 추출 시도 (sensors/{type}/{id} 형식)
        if topic:
            parts = topic.split('/')
            if len(parts) >= 2:
                sensor_type = parts[1] if parts[0] == 'sensors' else parts[0]

        # 2. 페이로드에서 추출 시도
        if not sensor_type:
            try:
                data = json.loads(payload)
                sensor_type = data.get('type')
            except json.JSONDecodeError:
                pass

        # 파서 선택 및 파싱
        parser = cls.get_parser(sensor_type)
        return parser.parse(payload, topic)

    @classmethod
    def get_supported_types(cls) -> list:
        """지원하는 센서 타입 목록 반환"""
        return list(cls._parsers.keys())


# 편의를 위한 함수들
def parse_sensor_data(payload: str, topic: str = None) -> Optional[ParsedData]:
    """센서 데이터 파싱 (단축 함수)"""
    return ParserFactory.parse(payload, topic)


def get_parser(sensor_type: str) -> BaseParser:
    """파서 인스턴스 반환 (단축 함수)"""
    return ParserFactory.get_parser(sensor_type)


__all__ = [
    'BaseParser',
    'ParsedData',
    'TemperatureParser',
    'HumidityParser',
    'VibrationParser',
    'GenericParser',
    'ParserFactory',
    'parse_sensor_data',
    'get_parser',
]
