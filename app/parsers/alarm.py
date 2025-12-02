"""
알람 파서
센서 경고 알람 메시지를 파싱합니다.

토픽 형식: {현장코드}/W/{sensor}
예: H001S0001/W/O2, H001S0001/W/CO

JSON 형식:
{
    "dvNo": "1",
    "value": "23.5",
    "level": "2",
    "etc": "",
    "time": "2025-01-15 10:30:00"
}
"""

import json
import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

from app.models.database import AlarmLog, ALARM_SENSOR_TYPES, ALARM_LEVELS, SENSOR_TYPES

logger = logging.getLogger(__name__)


# 토픽에서 센서 타입 매핑 (대문자 -> 소문자)
TOPIC_SENSOR_MAPPING = {
    'O2': 'o2',
    'NO2': 'no2',
    'CO': 'co',
    'CO2': 'co2',
    'H2S': 'h2s',
    'CH4': 'ch4',
    'CH2O': 'ch2o',
    'O3': 'o3',
    'VOC': 'voc',
    'PM1': 'pm1',
    'PM25': 'pm25',
    'PM2.5': 'pm25',
    'PM10': 'pm10',
}


@dataclass
class ParsedAlarmData:
    """파싱된 알람 데이터"""
    site_code: str          # 현장코드 (H001S0001)
    device_id: str          # 장치 ID (H001S0001_1)
    dv_no: str              # 장치 번호
    sensor_type: str        # 센서 타입 (소문자: o2, co 등)
    value: float            # 센서 값
    level: int              # 경고 레벨 (0:정상, 1:주의, 2:경고, 3:위험)
    etc: Optional[str] = None
    alarm_time: Optional[str] = None
    topic: Optional[str] = None
    raw_payload: Optional[str] = None

    def to_alarm_log(self) -> AlarmLog:
        """AlarmLog 객체로 변환"""
        return AlarmLog(
            site_code=self.site_code,
            device_id=self.device_id,
            dv_no=self.dv_no,
            sensor_type=self.sensor_type,
            value=self.value,
            level=self.level,
            etc=self.etc,
            alarm_time=self.alarm_time,
            topic=self.topic,
            raw_payload=self.raw_payload
        )

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        sensor_info = SENSOR_TYPES.get(self.sensor_type, {})
        level_info = ALARM_LEVELS.get(self.level, {})

        return {
            'site_code': self.site_code,
            'device_id': self.device_id,
            'dv_no': self.dv_no,
            'sensor_type': self.sensor_type,
            'sensor_name': sensor_info.get('name', self.sensor_type),
            'sensor_name_en': sensor_info.get('name_en', self.sensor_type.upper()),
            'sensor_unit': sensor_info.get('unit', ''),
            'value': self.value,
            'level': self.level,
            'level_name': level_info.get('name', ''),
            'level_name_en': level_info.get('name_en', ''),
            'level_color': level_info.get('color', '#999'),
            'etc': self.etc,
            'alarm_time': self.alarm_time,
            'topic': self.topic
        }


class AlarmParser:
    """
    알람 메시지 파서

    MQTT 토픽 형식: {현장코드}/W/{sensor}
    예: H001S0001/W/O2

    MQTT 메시지 포맷:
    {
        "dvNo": "1",
        "value": "23.5",
        "level": "2",
        "etc": "",
        "time": "2025-01-15 10:30:00"
    }
    """

    # 알람 토픽 패턴: {site_code}/W/{sensor_type}
    TOPIC_PATTERN = re.compile(r'^([A-Za-z0-9]+)/W/([A-Za-z0-9.]+)$')

    def parse(self, payload: str, topic: str) -> Optional[ParsedAlarmData]:
        """
        알람 메시지 파싱

        Args:
            payload: MQTT 메시지 페이로드 (JSON 문자열)
            topic: MQTT 토픽 (예: H001S0001/W/O2)

        Returns:
            ParsedAlarmData 또는 None
        """
        try:
            # 토픽에서 현장코드와 센서 타입 추출
            topic_info = self._parse_topic(topic)
            if not topic_info:
                return None

            site_code, sensor_type = topic_info

            # 페이로드 파싱
            data = json.loads(payload)

            # 필수 필드 검증
            if not self._validate(data):
                return None

            # 데이터 변환
            parsed = self._transform(data, site_code, sensor_type, topic)
            parsed.raw_payload = payload

            logger.debug(
                f"알람 데이터 파싱 성공: {parsed.device_id} "
                f"({parsed.sensor_type}: {parsed.value}, 레벨: {parsed.level})"
            )
            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"알람 JSON 파싱 오류: {e}, payload: {payload[:100]}")
            return None
        except Exception as e:
            logger.error(f"알람 데이터 파싱 중 오류: {e}")
            return None

    def _parse_topic(self, topic: str) -> Optional[tuple]:
        """
        토픽 파싱

        Args:
            topic: MQTT 토픽 (예: H001S0001/W/O2)

        Returns:
            (site_code, sensor_type) 튜플 또는 None
        """
        if not topic:
            logger.warning("알람 토픽이 비어있음")
            return None

        match = self.TOPIC_PATTERN.match(topic)
        if not match:
            logger.warning(f"알람 토픽 형식 불일치: {topic}")
            return None

        site_code = match.group(1)
        sensor_raw = match.group(2).upper()

        # 센서 타입 매핑
        sensor_type = TOPIC_SENSOR_MAPPING.get(sensor_raw)
        if not sensor_type:
            logger.warning(f"알 수 없는 센서 타입: {sensor_raw}")
            return None

        # 알람 대상 센서인지 확인
        if sensor_type not in ALARM_SENSOR_TYPES:
            logger.warning(f"알람 대상이 아닌 센서: {sensor_type}")
            return None

        return (site_code, sensor_type)

    def _validate(self, data: Dict[str, Any]) -> bool:
        """데이터 유효성 검증"""
        # 필수 필드 확인
        required_fields = ['dvNo', 'value', 'level']
        for field in required_fields:
            if field not in data:
                logger.warning(f"알람 필수 필드 누락: {field}")
                return False

        # level 값 검증
        try:
            level = int(data['level'])
            if level not in ALARM_LEVELS:
                logger.warning(f"유효하지 않은 알람 레벨: {level}")
                return False
        except (ValueError, TypeError):
            logger.warning(f"알람 레벨 변환 실패: {data['level']}")
            return False

        return True

    def _transform(
        self,
        data: Dict[str, Any],
        site_code: str,
        sensor_type: str,
        topic: str
    ) -> ParsedAlarmData:
        """데이터 변환"""
        dv_no = str(data.get('dvNo', '1'))
        device_id = f"{site_code}_{dv_no}"

        # 값 파싱
        value = self._parse_value(data.get('value'), sensor_type)
        level = int(data.get('level', 0))
        etc = data.get('etc', '')
        alarm_time = self._parse_time(data.get('time'))

        return ParsedAlarmData(
            site_code=site_code,
            device_id=device_id,
            dv_no=dv_no,
            sensor_type=sensor_type,
            value=value,
            level=level,
            etc=etc if etc else None,
            alarm_time=alarm_time,
            topic=topic
        )

    def _parse_value(self, raw_value: Any, sensor_type: str) -> float:
        """센서 값 파싱"""
        if raw_value is None or raw_value == '':
            return 0.0

        try:
            return round(float(raw_value), 2)
        except (TypeError, ValueError):
            logger.warning(f"{sensor_type} 값 변환 실패: {raw_value}")
            return 0.0

    def _parse_time(self, time_str: str) -> Optional[str]:
        """시간 파싱"""
        if not time_str or time_str == '':
            return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        # 다양한 형식 지원
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y/%m/%d %H:%M:%S',
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(time_str, fmt)
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue

        # 파싱 실패 시 원본 반환
        return time_str


# 싱글톤 파서 인스턴스
_alarm_parser_instance: Optional[AlarmParser] = None


def get_alarm_parser() -> AlarmParser:
    """알람 파서 인스턴스 반환"""
    global _alarm_parser_instance
    if _alarm_parser_instance is None:
        _alarm_parser_instance = AlarmParser()
    return _alarm_parser_instance


def parse_alarm_data(payload: str, topic: str) -> Optional[ParsedAlarmData]:
    """알람 데이터 파싱 (단축 함수)"""
    parser = get_alarm_parser()
    return parser.parse(payload, topic)


def is_alarm_topic(topic: str) -> bool:
    """알람 토픽인지 확인"""
    if not topic:
        return False
    return bool(AlarmParser.TOPIC_PATTERN.match(topic))
