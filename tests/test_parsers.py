"""
환경 센서 파서 모듈 테스트
"""

import pytest
import json
from app.parsers import (
    parse_mqtt_data,
    is_environment_data
)
from app.parsers.environment import (
    EnvironmentParser,
    ParsedEnvironmentData,
    DATA_FIELD_MAPPING
)


class TestEnvironmentParser:
    """환경 센서 파서 테스트"""

    def test_parse_valid_environment_data(self):
        """유효한 환경 데이터 파싱"""
        payload = json.dumps({
            'hCd': 'H001',
            'sCd': 'S0001',
            'dvNo': 'DEV001',
            'data1': 20.8,   # O2
            'data2': 0.02,   # NO2
            'data3': 1.5,    # CO
            'data4': 450,    # CO2
            'data5': 0.01,   # H2S
            'data6': 5.0,    # CH4
            'data7': 0.05,   # CH2O
            'data8': 0.03,   # O3
            'data9': 25,     # PM2.5
            'data10': 45,    # PM10
            'data11': 23.5,  # Temperature
            'data12': 55.0,  # Humidity
            'data13': 0.1,   # VOC
            'data14': 15     # PM1
        })

        result = parse_mqtt_data(payload, 'H001S0001/U')

        assert result is not None
        assert isinstance(result, ParsedEnvironmentData)
        assert result.h_cd == 'H001'
        assert result.s_cd == 'S0001'
        assert result.device_no == 'DEV001'
        assert result.o2 == 20.8
        assert result.co2 == 450
        assert result.temp == 23.5
        assert result.humi == 55.0

    def test_parse_partial_data(self):
        """일부 데이터만 있는 경우"""
        payload = json.dumps({
            'hCd': 'H001',
            'sCd': 'S0001',
            'dvNo': 'DEV001',
            'data1': 20.8,   # O2
            'data11': 23.5,  # Temperature
            'data12': 55.0,  # Humidity
        })

        parser = EnvironmentParser()
        result = parser.parse(payload)

        assert result is not None
        assert result.o2 == 20.8
        assert result.temp == 23.5
        assert result.no2 is None
        assert result.co is None

    def test_is_environment_data(self):
        """환경 데이터 형식 감지"""
        env_data = json.dumps({
            'hCd': 'H001',
            'sCd': 'S0001',
            'dvNo': 'DEV001',
            'data1': 20.8
        })

        old_format = json.dumps({
            'sensor_id': 'TEMP_001',
            'value': 25.5,
            'unit': 'celsius'
        })

        assert is_environment_data(env_data) == True
        assert is_environment_data(old_format) == False

    def test_data_field_mapping(self):
        """데이터 필드 매핑 확인"""
        assert DATA_FIELD_MAPPING['data1'] == 'o2'
        assert DATA_FIELD_MAPPING['data2'] == 'no2'
        assert DATA_FIELD_MAPPING['data3'] == 'co'
        assert DATA_FIELD_MAPPING['data4'] == 'co2'
        assert DATA_FIELD_MAPPING['data11'] == 'temp'
        assert DATA_FIELD_MAPPING['data12'] == 'humi'


class TestEnvironmentDataValidation:
    """환경 데이터 유효성 검사 테스트"""

    def test_missing_required_fields(self):
        """필수 필드 누락"""
        # hCd 누락
        payload = json.dumps({
            'sCd': 'S0001',
            'dvNo': 'DEV001',
            'data1': 20.8
        })

        parser = EnvironmentParser()
        result = parser.parse(payload)

        assert result is None

    def test_invalid_json(self):
        """잘못된 JSON"""
        result = parse_mqtt_data('not a json', 'H001S0001/U')
        assert result is None

    def test_value_conversion(self):
        """값 변환 테스트"""
        payload = json.dumps({
            'hCd': 'H001',
            'sCd': 'S0001',
            'dvNo': 'DEV001',
            'data1': '20.8',   # 문자열로 전달
            'data4': '450',    # 문자열로 전달
        })

        parser = EnvironmentParser()
        result = parser.parse(payload)

        assert result is not None
        assert result.o2 == 20.8
        assert result.co2 == 450


class TestSiteCodeExtraction:
    """현장 코드 추출 테스트"""

    def test_site_code_from_topic(self):
        """토픽에서 현장 코드 추출"""
        payload = json.dumps({
            'hCd': 'H001',
            'sCd': 'S0001',
            'dvNo': 'DEV001',
            'data1': 20.8
        })

        parser = EnvironmentParser()
        result = parser.parse(payload, topic='H001S0001/U')

        assert result is not None
        assert result.site_code == 'H001S0001'

    def test_site_code_from_payload(self):
        """페이로드에서 현장 코드 생성"""
        payload = json.dumps({
            'hCd': 'H002',
            'sCd': 'S0002',
            'dvNo': 'DEV002',
            'data1': 21.0
        })

        parser = EnvironmentParser()
        result = parser.parse(payload)

        assert result is not None
        assert result.site_code == 'H002S0002'


class TestAutoDetection:
    """자동 감지 테스트"""

    def test_auto_detect_environment_format(self):
        """환경 데이터 형식 자동 감지"""
        env_payload = json.dumps({
            'hCd': 'H001',
            'sCd': 'S0001',
            'dvNo': 'DEV001',
            'data1': 20.8,
            'data11': 23.5
        })

        result = parse_mqtt_data(env_payload, 'H001S0001/U')

        assert result is not None
        assert isinstance(result, ParsedEnvironmentData)
