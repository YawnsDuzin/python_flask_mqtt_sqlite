"""
데이터 파서 패키지
환경/가스 복합 센서 데이터 및 알람 파싱을 담당합니다.
"""

import json
import logging
from typing import Optional, Union

from .environment import (
    EnvironmentParser,
    ParsedEnvironmentData,
    parse_environment_data,
    get_environment_parser,
    DATA_FIELD_MAPPING
)

from .alarm import (
    AlarmParser,
    ParsedAlarmData,
    parse_alarm_data,
    get_alarm_parser,
    is_alarm_topic,
    TOPIC_SENSOR_MAPPING
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
) -> Optional[Union[ParsedEnvironmentData, ParsedAlarmData]]:
    """
    MQTT 데이터 파싱

    토픽 형식에 따라 환경 데이터 또는 알람 데이터를 파싱합니다.
    - 환경 데이터: {site_code}/U 토픽, {hCd, sCd, dvNo, data1~14} 포맷
    - 알람 데이터: {site_code}/W/{sensor} 토픽, {dvNo, value, level, etc, time} 포맷

    Args:
        payload: MQTT 메시지 페이로드
        topic: MQTT 토픽
        qos: QoS 레벨

    Returns:
        ParsedEnvironmentData, ParsedAlarmData 또는 None
    """
    # 알람 토픽인 경우
    if topic and is_alarm_topic(topic):
        return parse_alarm_data(payload, topic)

    # 환경 데이터인 경우
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
    # 알람 관련
    'AlarmParser',
    'ParsedAlarmData',
    'parse_alarm_data',
    'get_alarm_parser',
    'is_alarm_topic',
    'TOPIC_SENSOR_MAPPING',
]
