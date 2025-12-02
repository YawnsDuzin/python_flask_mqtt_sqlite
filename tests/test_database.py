"""
데이터베이스 모듈 테스트
"""

import pytest
import tempfile
import os
from datetime import datetime

from app.models.database import (
    Database,
    Sensor,
    SensorData,
    ProcessedData,
    MqttLog
)


@pytest.fixture
def temp_db():
    """임시 데이터베이스 fixture"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    db = Database(path)
    db.init_db()

    yield db

    db.close()
    os.unlink(path)


class TestSensorCRUD:
    """센서 CRUD 테스트"""

    def test_create_sensor(self, temp_db):
        """센서 생성"""
        sensor = Sensor(
            sensor_id='TEMP_001',
            sensor_type='temperature',
            location='서버실'
        )
        sensor_id = temp_db.create_sensor(sensor)

        assert sensor_id > 0

    def test_get_sensor(self, temp_db):
        """센서 조회"""
        sensor = Sensor(
            sensor_id='TEMP_001',
            sensor_type='temperature',
            location='서버실'
        )
        temp_db.create_sensor(sensor)

        result = temp_db.get_sensor('TEMP_001')

        assert result is not None
        assert result.sensor_id == 'TEMP_001'
        assert result.sensor_type == 'temperature'
        assert result.location == '서버실'

    def test_get_nonexistent_sensor(self, temp_db):
        """존재하지 않는 센서 조회"""
        result = temp_db.get_sensor('NONEXISTENT')
        assert result is None

    def test_get_all_sensors(self, temp_db):
        """모든 센서 조회"""
        sensors = [
            Sensor(sensor_id='TEMP_001', sensor_type='temperature'),
            Sensor(sensor_id='HUM_001', sensor_type='humidity'),
            Sensor(sensor_id='VIB_001', sensor_type='vibration'),
        ]

        for sensor in sensors:
            temp_db.create_sensor(sensor)

        result = temp_db.get_all_sensors()

        assert len(result) == 3

    def test_update_sensor_status(self, temp_db):
        """센서 상태 업데이트"""
        sensor = Sensor(
            sensor_id='TEMP_001',
            sensor_type='temperature'
        )
        temp_db.create_sensor(sensor)

        # 비활성화
        success = temp_db.update_sensor_status('TEMP_001', False)
        assert success

        result = temp_db.get_sensor('TEMP_001')
        assert result.is_active == False


class TestSensorDataCRUD:
    """센서 데이터 CRUD 테스트"""

    def test_save_sensor_data(self, temp_db):
        """센서 데이터 저장"""
        # 센서 먼저 생성
        sensor = Sensor(sensor_id='TEMP_001', sensor_type='temperature')
        temp_db.create_sensor(sensor)

        data = SensorData(
            sensor_id='TEMP_001',
            sensor_type='temperature',
            value=25.5,
            unit='celsius',
            topic='sensors/temperature/TEMP_001'
        )

        data_id = temp_db.save_sensor_data(data)
        assert data_id > 0

    def test_get_sensor_data(self, temp_db):
        """센서 데이터 조회"""
        sensor = Sensor(sensor_id='TEMP_001', sensor_type='temperature')
        temp_db.create_sensor(sensor)

        # 여러 데이터 저장
        for i in range(5):
            data = SensorData(
                sensor_id='TEMP_001',
                sensor_type='temperature',
                value=20.0 + i,
                unit='celsius'
            )
            temp_db.save_sensor_data(data)

        result = temp_db.get_sensor_data(sensor_id='TEMP_001')

        assert len(result) == 5

    def test_get_latest_data(self, temp_db):
        """최신 데이터 조회"""
        sensor = Sensor(sensor_id='TEMP_001', sensor_type='temperature')
        temp_db.create_sensor(sensor)

        for i in range(20):
            data = SensorData(
                sensor_id='TEMP_001',
                sensor_type='temperature',
                value=20.0 + i,
                unit='celsius'
            )
            temp_db.save_sensor_data(data)

        result = temp_db.get_latest_data(limit=10)

        assert len(result) == 10


class TestStatistics:
    """통계 테스트"""

    def test_get_sensor_stats(self, temp_db):
        """센서 통계 조회"""
        sensor = Sensor(sensor_id='TEMP_001', sensor_type='temperature')
        temp_db.create_sensor(sensor)

        values = [20.0, 25.0, 30.0, 35.0, 40.0]
        for v in values:
            data = SensorData(
                sensor_id='TEMP_001',
                sensor_type='temperature',
                value=v,
                unit='celsius'
            )
            temp_db.save_sensor_data(data)

        stats = temp_db.get_sensor_stats('TEMP_001')

        assert stats['count'] == 5
        assert stats['avg_value'] == 30.0
        assert stats['min_value'] == 20.0
        assert stats['max_value'] == 40.0


class TestMqttLog:
    """MQTT 로그 테스트"""

    def test_save_mqtt_log(self, temp_db):
        """MQTT 로그 저장"""
        log = MqttLog(
            event_type='connect',
            message='연결 성공'
        )

        log_id = temp_db.save_mqtt_log(log)
        assert log_id > 0

    def test_get_mqtt_logs(self, temp_db):
        """MQTT 로그 조회"""
        logs = [
            MqttLog(event_type='connect', message='연결'),
            MqttLog(event_type='disconnect', message='연결 해제'),
            MqttLog(event_type='error', message='오류'),
        ]

        for log in logs:
            temp_db.save_mqtt_log(log)

        result = temp_db.get_mqtt_logs()
        assert len(result) == 3

        # 타입별 필터링
        connect_logs = temp_db.get_mqtt_logs(event_type='connect')
        assert len(connect_logs) == 1


class TestUtilities:
    """유틸리티 테스트"""

    def test_get_data_count(self, temp_db):
        """데이터 수 조회"""
        counts = temp_db.get_data_count()

        assert 'sensors' in counts
        assert 'sensor_data' in counts
        assert 'processed_data' in counts
        assert 'mqtt_logs' in counts
