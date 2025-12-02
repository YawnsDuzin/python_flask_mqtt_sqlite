"""
환경 센서 데이터베이스 모듈 테스트
"""

import pytest
import tempfile
import os
from datetime import datetime

from app.models.database import (
    Database,
    Site,
    Device,
    EnvironmentData,
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


class TestSiteCRUD:
    """현장(Site) CRUD 테스트"""

    def test_create_site(self, temp_db):
        """현장 생성"""
        site = Site(
            h_cd='H001',
            s_cd='S0001',
            name='테스트 현장'
        )
        site_id = temp_db.create_site(site)

        assert site_id > 0

    def test_get_site(self, temp_db):
        """현장 조회"""
        site = Site(
            h_cd='H001',
            s_cd='S0001',
            name='테스트 현장',
            description='테스트용 현장입니다'
        )
        temp_db.create_site(site)

        result = temp_db.get_site('H001S0001')

        assert result is not None
        assert result.h_cd == 'H001'
        assert result.s_cd == 'S0001'
        assert result.name == '테스트 현장'

    def test_get_nonexistent_site(self, temp_db):
        """존재하지 않는 현장 조회"""
        result = temp_db.get_site('NONEXISTENT')
        assert result is None

    def test_get_all_sites(self, temp_db):
        """모든 현장 조회"""
        sites = [
            Site(h_cd='H001', s_cd='S0001', name='현장 1'),
            Site(h_cd='H001', s_cd='S0002', name='현장 2'),
            Site(h_cd='H002', s_cd='S0001', name='현장 3'),
        ]

        for site in sites:
            temp_db.create_site(site)

        result = temp_db.get_all_sites()

        assert len(result) == 3


class TestDeviceCRUD:
    """장치(Device) CRUD 테스트"""

    def test_create_device(self, temp_db):
        """장치 생성"""
        # 현장 먼저 생성
        site = Site(h_cd='H001', s_cd='S0001', name='테스트 현장')
        temp_db.create_site(site)

        device = Device(
            device_no='DEV001',
            site_code='H001S0001',
            name='테스트 장치'
        )
        device_id = temp_db.create_device(device)

        assert device_id > 0

    def test_get_device(self, temp_db):
        """장치 조회"""
        site = Site(h_cd='H001', s_cd='S0001')
        temp_db.create_site(site)

        device = Device(
            device_no='DEV001',
            site_code='H001S0001',
            name='테스트 장치',
            description='테스트용 장치입니다'
        )
        temp_db.create_device(device)

        result = temp_db.get_device('DEV001')

        assert result is not None
        assert result.device_no == 'DEV001'
        assert result.site_code == 'H001S0001'

    def test_get_devices_by_site(self, temp_db):
        """현장별 장치 조회"""
        site = Site(h_cd='H001', s_cd='S0001')
        temp_db.create_site(site)

        devices = [
            Device(device_no='DEV001', site_code='H001S0001'),
            Device(device_no='DEV002', site_code='H001S0001'),
        ]

        for device in devices:
            temp_db.create_device(device)

        result = temp_db.get_devices_by_site('H001S0001')

        assert len(result) == 2


class TestEnvironmentDataCRUD:
    """환경 데이터 CRUD 테스트"""

    def test_save_environment_data(self, temp_db):
        """환경 데이터 저장"""
        # 현장 및 장치 먼저 생성
        site = Site(h_cd='H001', s_cd='S0001')
        temp_db.create_site(site)

        device = Device(device_no='DEV001', site_code='H001S0001')
        temp_db.create_device(device)

        data = EnvironmentData(
            device_no='DEV001',
            site_code='H001S0001',
            o2=20.8,
            co=1.5,
            co2=450,
            temp=23.5,
            humi=55.0,
            topic='H001S0001/U'
        )

        data_id = temp_db.save_environment_data(data)
        assert data_id > 0

    def test_get_environment_data(self, temp_db):
        """환경 데이터 조회"""
        site = Site(h_cd='H001', s_cd='S0001')
        temp_db.create_site(site)

        device = Device(device_no='DEV001', site_code='H001S0001')
        temp_db.create_device(device)

        # 여러 데이터 저장
        for i in range(5):
            data = EnvironmentData(
                device_no='DEV001',
                site_code='H001S0001',
                o2=20.0 + i * 0.1,
                temp=20.0 + i
            )
            temp_db.save_environment_data(data)

        result = temp_db.get_environment_data(device_no='DEV001')

        assert len(result) == 5

    def test_get_latest_data(self, temp_db):
        """최신 데이터 조회"""
        site = Site(h_cd='H001', s_cd='S0001')
        temp_db.create_site(site)

        device = Device(device_no='DEV001', site_code='H001S0001')
        temp_db.create_device(device)

        for i in range(20):
            data = EnvironmentData(
                device_no='DEV001',
                site_code='H001S0001',
                o2=20.0 + i * 0.1
            )
            temp_db.save_environment_data(data)

        result = temp_db.get_latest_data(limit=10)

        assert len(result) == 10


class TestStatistics:
    """통계 테스트"""

    def test_get_device_stats(self, temp_db):
        """장치 통계 조회"""
        site = Site(h_cd='H001', s_cd='S0001')
        temp_db.create_site(site)

        device = Device(device_no='DEV001', site_code='H001S0001')
        temp_db.create_device(device)

        # 다양한 데이터 저장
        values = [20.0, 20.5, 21.0, 21.5, 22.0]
        for v in values:
            data = EnvironmentData(
                device_no='DEV001',
                site_code='H001S0001',
                o2=v,
                temp=25.0
            )
            temp_db.save_environment_data(data)

        stats = temp_db.get_device_stats('DEV001')

        assert stats['count'] == 5
        assert 'o2' in stats
        assert stats['o2']['avg'] == pytest.approx(21.0, 0.01)
        assert stats['o2']['min'] == 20.0
        assert stats['o2']['max'] == 22.0


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


class TestAlarmThresholds:
    """알람 임계값 테스트"""

    def test_set_alarm_threshold(self, temp_db):
        """알람 임계값 설정"""
        success = temp_db.set_alarm_threshold(
            sensor_type='o2',
            min_value=19.5,
            max_value=23.5
        )
        assert success

    def test_get_alarm_thresholds(self, temp_db):
        """알람 임계값 조회"""
        temp_db.set_alarm_threshold('o2', 19.5, 23.5)
        temp_db.set_alarm_threshold('co', None, 25)

        thresholds = temp_db.get_alarm_thresholds()

        assert len(thresholds) == 2


class TestUtilities:
    """유틸리티 테스트"""

    def test_get_data_count(self, temp_db):
        """데이터 수 조회"""
        counts = temp_db.get_data_count()

        assert 'sites' in counts
        assert 'devices' in counts
        assert 'environment_data' in counts
        assert 'mqtt_logs' in counts
