"""
파서 모듈 테스트
"""

import pytest
import json
from app.parsers import (
    ParserFactory,
    parse_sensor_data,
    TemperatureParser,
    HumidityParser,
    VibrationParser,
    GenericParser
)


class TestTemperatureParser:
    """온도 파서 테스트"""

    def test_parse_valid_temperature(self):
        """유효한 온도 데이터 파싱"""
        payload = json.dumps({
            'sensor_id': 'TEMP_001',
            'type': 'temperature',
            'value': 25.5,
            'unit': 'celsius',
            'timestamp': '2025-01-15T10:30:00Z'
        })

        result = parse_sensor_data(payload, 'sensors/temperature/TEMP_001')

        assert result is not None
        assert result.sensor_id == 'TEMP_001'
        assert result.sensor_type == 'temperature'
        assert result.value == 25.5
        assert result.unit == 'celsius'

    def test_parse_fahrenheit(self):
        """화씨 온도 변환 테스트"""
        payload = json.dumps({
            'sensor_id': 'TEMP_002',
            'value': 77.0,
            'unit': 'fahrenheit'
        })

        parser = TemperatureParser()
        result = parser.parse(payload)

        assert result is not None
        assert result.unit == 'fahrenheit'
        # 섭씨 변환 확인
        assert 'celsius' in result.extra_data
        assert abs(result.extra_data['celsius'] - 25.0) < 0.1

    def test_invalid_temperature_range(self):
        """유효하지 않은 온도 범위"""
        payload = json.dumps({
            'sensor_id': 'TEMP_001',
            'value': 500.0,  # 범위 초과
            'unit': 'celsius'
        })

        parser = TemperatureParser()
        result = parser.parse(payload)

        assert result is None


class TestHumidityParser:
    """습도 파서 테스트"""

    def test_parse_valid_humidity(self):
        """유효한 습도 데이터 파싱"""
        payload = json.dumps({
            'sensor_id': 'HUM_001',
            'type': 'humidity',
            'value': 45.0,
            'unit': 'percent'
        })

        result = parse_sensor_data(payload, 'sensors/humidity/HUM_001')

        assert result is not None
        assert result.sensor_id == 'HUM_001'
        assert result.value == 45.0
        assert result.extra_data['status'] == 'comfortable'

    def test_humidity_status_classification(self):
        """습도 상태 분류 테스트"""
        parser = HumidityParser()

        # 매우 건조
        result = parser.parse(json.dumps({
            'sensor_id': 'HUM_001',
            'value': 15.0,
            'unit': 'percent'
        }))
        assert result.extra_data['status'] == 'very_dry'

        # 매우 습함
        result = parser.parse(json.dumps({
            'sensor_id': 'HUM_001',
            'value': 85.0,
            'unit': 'percent'
        }))
        assert result.extra_data['status'] == 'very_humid'


class TestVibrationParser:
    """진동 파서 테스트"""

    def test_parse_valid_vibration(self):
        """유효한 진동 데이터 파싱"""
        payload = json.dumps({
            'sensor_id': 'VIB_001',
            'type': 'vibration',
            'value': 2.5,
            'unit': 'mm/s'
        })

        result = parse_sensor_data(payload, 'sensors/vibration/VIB_001')

        assert result is not None
        assert result.sensor_id == 'VIB_001'
        assert result.value == 2.5
        assert result.extra_data['status'] == 'good'


class TestParserFactory:
    """파서 팩토리 테스트"""

    def test_get_temperature_parser(self):
        """온도 파서 반환"""
        parser = ParserFactory.get_parser('temperature')
        assert isinstance(parser, TemperatureParser)

    def test_get_humidity_parser(self):
        """습도 파서 반환"""
        parser = ParserFactory.get_parser('humidity')
        assert isinstance(parser, HumidityParser)

    def test_get_generic_parser_for_unknown_type(self):
        """알 수 없는 타입에 대해 범용 파서 반환"""
        parser = ParserFactory.get_parser('unknown_type')
        assert isinstance(parser, GenericParser)

    def test_auto_parse_from_topic(self):
        """토픽에서 자동으로 파서 선택"""
        payload = json.dumps({
            'sensor_id': 'TEMP_001',
            'value': 25.0,
            'unit': 'celsius'
        })

        result = ParserFactory.parse(payload, 'sensors/temperature/TEMP_001')

        assert result is not None
        assert result.sensor_type == 'temperature'


class TestInvalidData:
    """유효하지 않은 데이터 테스트"""

    def test_invalid_json(self):
        """잘못된 JSON"""
        result = parse_sensor_data('not a json', 'sensors/temperature/TEMP_001')
        assert result is None

    def test_missing_sensor_id(self):
        """센서 ID 누락"""
        payload = json.dumps({
            'value': 25.0,
            'unit': 'celsius'
        })

        parser = TemperatureParser()
        result = parser.parse(payload)
        assert result is None

    def test_missing_value(self):
        """값 누락"""
        payload = json.dumps({
            'sensor_id': 'TEMP_001',
            'unit': 'celsius'
        })

        parser = TemperatureParser()
        result = parser.parse(payload)
        assert result is None

    def test_non_numeric_value(self):
        """숫자가 아닌 값"""
        payload = json.dumps({
            'sensor_id': 'TEMP_001',
            'value': 'not_a_number',
            'unit': 'celsius'
        })

        parser = TemperatureParser()
        result = parser.parse(payload)
        assert result is None
