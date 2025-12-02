"""
기본 파서 클래스
모든 센서 파서의 부모 클래스입니다.
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ParsedData:
    """파싱된 센서 데이터 구조"""
    sensor_id: str
    sensor_type: str
    value: float
    unit: str
    timestamp: Optional[str] = None
    raw_payload: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'sensor_id': self.sensor_id,
            'sensor_type': self.sensor_type,
            'value': self.value,
            'unit': self.unit,
            'timestamp': self.timestamp,
            'extra_data': self.extra_data
        }


class BaseParser(ABC):
    """
    센서 데이터 파서 기본 클래스

    모든 센서 타입별 파서는 이 클래스를 상속받아 구현합니다.
    """

    # 지원하는 센서 타입 (서브클래스에서 정의)
    SENSOR_TYPE: str = "generic"

    # 기본 단위 (서브클래스에서 정의)
    DEFAULT_UNIT: str = "unknown"

    def parse(self, payload: str, topic: str = None) -> Optional[ParsedData]:
        """
        페이로드 파싱 메인 메소드

        Args:
            payload: MQTT 메시지 페이로드 (JSON 문자열)
            topic: MQTT 토픽 (센서 ID 추출에 사용)

        Returns:
            ParsedData 또는 파싱 실패 시 None
        """
        try:
            # JSON 파싱
            data = json.loads(payload)

            # 필수 필드 검증
            if not self._validate(data):
                logger.warning(f"데이터 검증 실패: {payload[:100]}")
                return None

            # 데이터 변환
            parsed = self._transform(data, topic)
            parsed.raw_payload = payload

            logger.debug(f"파싱 성공: {parsed.sensor_id} = {parsed.value} {parsed.unit}")
            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 오류: {e}, payload: {payload[:100]}")
            return None
        except Exception as e:
            logger.error(f"파싱 중 오류 발생: {e}")
            return None

    def _validate(self, data: Dict[str, Any]) -> bool:
        """
        데이터 유효성 검증

        Args:
            data: 파싱된 JSON 데이터

        Returns:
            유효하면 True
        """
        # 기본 검증: sensor_id와 value 필수
        if 'sensor_id' not in data:
            logger.warning("sensor_id 필드 누락")
            return False

        if 'value' not in data:
            logger.warning("value 필드 누락")
            return False

        # value가 숫자인지 확인
        try:
            float(data['value'])
        except (TypeError, ValueError):
            logger.warning(f"value가 숫자가 아님: {data.get('value')}")
            return False

        return True

    @abstractmethod
    def _transform(self, data: Dict[str, Any], topic: str = None) -> ParsedData:
        """
        데이터 변환 (서브클래스에서 구현)

        Args:
            data: 검증된 JSON 데이터
            topic: MQTT 토픽

        Returns:
            ParsedData 인스턴스
        """
        pass

    def _extract_sensor_id_from_topic(self, topic: str) -> Optional[str]:
        """
        토픽에서 센서 ID 추출

        예: sensors/temperature/TEMP_001 -> TEMP_001

        Args:
            topic: MQTT 토픽

        Returns:
            센서 ID 또는 None
        """
        if topic:
            parts = topic.split('/')
            if len(parts) >= 3:
                return parts[-1]
        return None

    def _parse_timestamp(self, timestamp_str: str) -> Optional[str]:
        """
        타임스탬프 파싱 및 정규화

        Args:
            timestamp_str: 타임스탬프 문자열

        Returns:
            정규화된 ISO 형식 타임스탬프
        """
        if not timestamp_str:
            return datetime.utcnow().isoformat() + 'Z'

        # 다양한 형식 시도
        formats = [
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%Y/%m/%d %H:%M:%S',
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(timestamp_str, fmt)
                return dt.isoformat() + 'Z'
            except ValueError:
                continue

        # 파싱 실패 시 현재 시간 사용
        logger.warning(f"타임스탬프 파싱 실패: {timestamp_str}")
        return datetime.utcnow().isoformat() + 'Z'
