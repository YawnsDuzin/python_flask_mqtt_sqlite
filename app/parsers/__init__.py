"""
데이터 파서 패키지
환경/가스 복합 센서 데이터 파싱을 담당합니다.
"""

import json
import logging
from typing import Optional

from .environment import (
    EnvironmentParser,
    ParsedEnvironmentData,
    parse_environment_data,
    get_environment_parser,
    DATA_FIELD_MAPPING
)

logger = logging.getLogger(__name__)


def is_environment_data(payload: str) -> bool:
    """
    환경 센서 데이터 포맷인지 확인

    환경 센서 데이터는 hCd, sCd, dvNo 필드를 포함합니다.
    """
    try:
        data = json.loads(payload)
        # 환경 센서 필수 필드 확인
        return all(key in data for key in ['hCd', 'sCd', 'dvNo'])
    except (json.JSONDecodeError, TypeError):
        return False


def parse_mqtt_data(
    payload: str,
    topic: str = None,
    qos: int = 0
) -> Optional[ParsedEnvironmentData]:
    """
    MQTT 데이터 파싱

    환경/가스 센서 데이터 포맷 ({hCd, sCd, dvNo, data1~14})을 파싱합니다.

    Args:
        payload: MQTT 메시지 페이로드
        topic: MQTT 토픽
        qos: QoS 레벨

    Returns:
        ParsedEnvironmentData 또는 None
    """
    if is_environment_data(payload):
        return parse_environment_data(payload, topic)

    logger.warning(f"지원하지 않는 데이터 포맷: {payload[:100]}")
    return None


__all__ = [
    # 환경 센서 관련
    'EnvironmentParser',
    'ParsedEnvironmentData',
    'parse_environment_data',
    'get_environment_parser',
    'is_environment_data',
    'parse_mqtt_data',
    'DATA_FIELD_MAPPING',
]
