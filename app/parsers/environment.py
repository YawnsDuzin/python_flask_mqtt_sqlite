"""
환경/가스 센서 파서
복합 센서 데이터 (가스, 미세먼지, 온습도)를 파싱합니다.
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

from app.models.database import EnvironmentData, SENSOR_TYPES

logger = logging.getLogger(__name__)


# data1~data14 필드 매핑
DATA_FIELD_MAPPING = {
    'data1': 'o2',      # O2: 산소
    'data2': 'no2',     # NO2: 이산화질소
    'data3': 'co',      # CO: 일산화탄소
    'data4': 'co2',     # CO2: 이산화탄소
    'data5': 'h2s',     # H2S: 황화수소
    'data6': 'ch4',     # CH4: 메탄
    'data7': 'ch2o',    # CH2O: 폼알데하이드
    'data8': 'o3',      # O3: 오존
    'data9': 'pm25',    # PM2.5: 초미세먼지
    'data10': 'pm10',   # PM10: 미세먼지
    'data11': 'temp',   # Temp: 온도
    'data12': 'humi',   # Humi: 습도
    'data13': 'voc',    # VOC: 휘발성 유기 화합물
    'data14': 'pm1',    # PM1: 극초미세먼지
}


@dataclass
class ParsedEnvironmentData:
    """파싱된 환경 센서 데이터"""
    device_id: str
    site_code: str
    h_cd: str
    s_cd: str
    dv_no: str
    # 센서 데이터
    o2: Optional[float] = None
    no2: Optional[float] = None
    co: Optional[float] = None
    co2: Optional[float] = None
    h2s: Optional[float] = None
    ch4: Optional[float] = None
    ch2o: Optional[float] = None
    o3: Optional[float] = None
    voc: Optional[float] = None
    pm1: Optional[float] = None
    pm25: Optional[float] = None
    pm10: Optional[float] = None
    temp: Optional[float] = None
    humi: Optional[float] = None
    # 메타 데이터
    check_time: Optional[str] = None
    raw_payload: Optional[str] = None
    topic: Optional[str] = None

    def to_environment_data(self, qos: int = 0) -> EnvironmentData:
        """EnvironmentData 객체로 변환"""
        return EnvironmentData(
            device_id=self.device_id,
            site_code=self.site_code,
            h_cd=self.h_cd,
            s_cd=self.s_cd,
            dv_no=self.dv_no,
            o2=self.o2,
            no2=self.no2,
            co=self.co,
            co2=self.co2,
            h2s=self.h2s,
            ch4=self.ch4,
            ch2o=self.ch2o,
            o3=self.o3,
            voc=self.voc,
            pm1=self.pm1,
            pm25=self.pm25,
            pm10=self.pm10,
            temp=self.temp,
            humi=self.humi,
            check_time=self.check_time,
            raw_payload=self.raw_payload,
            topic=self.topic,
            qos=qos
        )

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'device_id': self.device_id,
            'site_code': self.site_code,
            'h_cd': self.h_cd,
            's_cd': self.s_cd,
            'dv_no': self.dv_no,
            'sensors': {
                'o2': {'value': self.o2, **SENSOR_TYPES.get('o2', {})},
                'no2': {'value': self.no2, **SENSOR_TYPES.get('no2', {})},
                'co': {'value': self.co, **SENSOR_TYPES.get('co', {})},
                'co2': {'value': self.co2, **SENSOR_TYPES.get('co2', {})},
                'h2s': {'value': self.h2s, **SENSOR_TYPES.get('h2s', {})},
                'ch4': {'value': self.ch4, **SENSOR_TYPES.get('ch4', {})},
                'ch2o': {'value': self.ch2o, **SENSOR_TYPES.get('ch2o', {})},
                'o3': {'value': self.o3, **SENSOR_TYPES.get('o3', {})},
                'voc': {'value': self.voc, **SENSOR_TYPES.get('voc', {})},
                'pm1': {'value': self.pm1, **SENSOR_TYPES.get('pm1', {})},
                'pm25': {'value': self.pm25, **SENSOR_TYPES.get('pm25', {})},
                'pm10': {'value': self.pm10, **SENSOR_TYPES.get('pm10', {})},
                'temp': {'value': self.temp, **SENSOR_TYPES.get('temp', {})},
                'humi': {'value': self.humi, **SENSOR_TYPES.get('humi', {})},
            },
            'check_time': self.check_time,
            'topic': self.topic
        }


class EnvironmentParser:
    """
    환경/가스 센서 데이터 파서

    MQTT 메시지 포맷:
    {
        "hCd": "H001",
        "sCd": "S0001",
        "dvNo": "1",
        "data1": "20.9",   // O2
        "data2": "0.1",    // NO2
        ...
        "checkTime": "2025-01-15 10:30:00"
    }
    """

    def parse(self, payload: str, topic: str = None) -> Optional[ParsedEnvironmentData]:
        """
        환경 센서 데이터 파싱

        Args:
            payload: MQTT 메시지 페이로드 (JSON 문자열)
            topic: MQTT 토픽

        Returns:
            ParsedEnvironmentData 또는 None
        """
        try:
            data = json.loads(payload)

            # 필수 필드 검증
            if not self._validate(data):
                return None

            # 데이터 변환
            parsed = self._transform(data, topic)
            parsed.raw_payload = payload

            logger.debug(
                f"환경 데이터 파싱 성공: {parsed.device_id} "
                f"(온도: {parsed.temp}, 습도: {parsed.humi})"
            )
            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 오류: {e}, payload: {payload[:100]}")
            return None
        except Exception as e:
            logger.error(f"환경 데이터 파싱 중 오류: {e}")
            return None

    def _validate(self, data: Dict[str, Any]) -> bool:
        """데이터 유효성 검증"""
        # 필수 필드 확인
        required_fields = ['hCd', 'sCd', 'dvNo']
        for field in required_fields:
            if field not in data:
                logger.warning(f"필수 필드 누락: {field}")
                return False

        # 최소 하나의 데이터 필드가 있어야 함
        has_data = any(
            data.get(f'data{i}') is not None
            for i in range(1, 15)
        )
        if not has_data:
            logger.warning("데이터 필드가 모두 비어있음")
            return False

        return True

    def _transform(self, data: Dict[str, Any], topic: str = None) -> ParsedEnvironmentData:
        """데이터 변환"""
        h_cd = data.get('hCd', '')
        s_cd = data.get('sCd', '')
        dv_no = str(data.get('dvNo', '1'))

        # site_code와 device_id 생성
        site_code = f"{h_cd}{s_cd}"
        device_id = f"{site_code}_{dv_no}"

        # 센서 데이터 추출
        sensor_values = {}
        for data_field, sensor_name in DATA_FIELD_MAPPING.items():
            raw_value = data.get(data_field)
            sensor_values[sensor_name] = self._parse_value(raw_value, sensor_name)

        # checkTime 파싱
        check_time = self._parse_check_time(data.get('checkTime'))

        return ParsedEnvironmentData(
            device_id=device_id,
            site_code=site_code,
            h_cd=h_cd,
            s_cd=s_cd,
            dv_no=dv_no,
            o2=sensor_values.get('o2'),
            no2=sensor_values.get('no2'),
            co=sensor_values.get('co'),
            co2=sensor_values.get('co2'),
            h2s=sensor_values.get('h2s'),
            ch4=sensor_values.get('ch4'),
            ch2o=sensor_values.get('ch2o'),
            o3=sensor_values.get('o3'),
            voc=sensor_values.get('voc'),
            pm1=sensor_values.get('pm1'),
            pm25=sensor_values.get('pm25'),
            pm10=sensor_values.get('pm10'),
            temp=sensor_values.get('temp'),
            humi=sensor_values.get('humi'),
            check_time=check_time,
            topic=topic
        )

    def _parse_value(self, raw_value: Any, sensor_type: str) -> Optional[float]:
        """센서 값 파싱 및 검증"""
        if raw_value is None or raw_value == '':
            return None

        try:
            value = float(raw_value)

            # 범위 검증
            sensor_info = SENSOR_TYPES.get(sensor_type, {})
            min_val = sensor_info.get('min')
            max_val = sensor_info.get('max')

            if min_val is not None and value < min_val:
                logger.warning(
                    f"{sensor_type} 값이 최소값 미만: {value} < {min_val}"
                )
                return None

            if max_val is not None and value > max_val:
                logger.warning(
                    f"{sensor_type} 값이 최대값 초과: {value} > {max_val}"
                )
                return None

            return round(value, 2)

        except (TypeError, ValueError) as e:
            logger.warning(f"{sensor_type} 값 변환 실패: {raw_value}")
            return None

    def _parse_check_time(self, check_time: str) -> Optional[str]:
        """checkTime 파싱"""
        if not check_time or check_time == '':
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 다양한 형식 지원
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y/%m/%d %H:%M:%S',
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(check_time, fmt)
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue

        # 파싱 실패 시 원본 반환
        return check_time


# 싱글톤 파서 인스턴스
_parser_instance: Optional[EnvironmentParser] = None


def get_environment_parser() -> EnvironmentParser:
    """환경 파서 인스턴스 반환"""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = EnvironmentParser()
    return _parser_instance


def parse_environment_data(payload: str, topic: str = None) -> Optional[ParsedEnvironmentData]:
    """환경 데이터 파싱 (단축 함수)"""
    parser = get_environment_parser()
    return parser.parse(payload, topic)
