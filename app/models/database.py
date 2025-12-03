"""
데이터베이스 모듈
SQLite 데이터베이스 연결 및 CRUD 작업을 관리합니다.
환경/가스 센서 복합 데이터 구조 지원
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class Site:
    """현장 정보 데이터 클래스"""
    site_code: str              # 현장코드 (H001S0001 형식)
    h_cd: str                   # 현장코드 앞부분 (H001)
    s_cd: str                   # 센서코드 (S0001)
    name: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Device:
    """장치 정보 데이터 클래스"""
    device_id: str              # 장치 고유 ID (H001S0001_1 형식)
    site_code: str              # 현장코드 (H001S0001)
    dv_no: str                  # 장치 번호 (1, 2, ...)
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    id: Optional[int] = None


@dataclass
class EnvironmentData:
    """환경/가스 센서 측정 데이터 클래스"""
    device_id: str              # 장치 ID (H001S0001_1)
    site_code: str              # 현장코드 (H001S0001)
    h_cd: str                   # 현장코드 (H001)
    s_cd: str                   # 센서코드 (S0001)
    dv_no: str                  # 장치번호
    # 가스 센서 데이터
    o2: Optional[float] = None      # 산소 (%)
    no2: Optional[float] = None     # 이산화질소 (ppm)
    co: Optional[float] = None      # 일산화탄소 (ppm)
    co2: Optional[float] = None     # 이산화탄소 (ppm)
    h2s: Optional[float] = None     # 황화수소 (ppm)
    ch4: Optional[float] = None     # 메탄 (% LEL)
    ch2o: Optional[float] = None    # 폼알데하이드 (ppm)
    o3: Optional[float] = None      # 오존 (ppm)
    voc: Optional[float] = None     # 휘발성유기화합물 (ppm)
    # 미세먼지 데이터
    pm1: Optional[float] = None     # PM1.0 (μg/m³)
    pm25: Optional[float] = None    # PM2.5 (μg/m³)
    pm10: Optional[float] = None    # PM10 (μg/m³)
    # 환경 데이터
    temp: Optional[float] = None    # 온도 (°C)
    humi: Optional[float] = None    # 습도 (%)
    # 메타 데이터
    check_time: Optional[str] = None    # 센서 측정 시간
    raw_payload: Optional[str] = None
    topic: Optional[str] = None
    qos: int = 0
    received_at: Optional[str] = None
    id: Optional[int] = None


@dataclass
class MqttLog:
    """MQTT 로그 데이터 클래스"""
    event_type: str
    topic: Optional[str] = None
    message: Optional[str] = None
    created_at: Optional[str] = None
    id: Optional[int] = None


@dataclass
class AlarmLog:
    """경고 알람 로그 데이터 클래스"""
    site_code: str              # 현장코드 (H001S0001)
    device_id: str              # 장치 ID (H001S0001_1)
    dv_no: str                  # 장치 번호
    sensor_type: str            # 센서 타입 (o2, co, co2 등)
    value: float                # 센서 값
    level: int                  # 경고 레벨 (0:정상, 1:주의, 2:경고, 3:위험)
    etc: Optional[str] = None   # 추가 정보
    alarm_time: Optional[str] = None  # 알람 발생 시간
    topic: Optional[str] = None
    raw_payload: Optional[str] = None
    is_acknowledged: bool = False     # 확인 여부
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    created_at: Optional[str] = None
    id: Optional[int] = None


# 경고 레벨 정의
ALARM_LEVELS = {
    0: {'name': '정상', 'name_en': 'Normal', 'color': '#2ecc71'},
    1: {'name': '주의', 'name_en': 'Caution', 'color': '#f39c12'},
    2: {'name': '경고', 'name_en': 'Warning', 'color': '#e67e22'},
    3: {'name': '위험', 'name_en': 'Danger', 'color': '#e74c3c'},
}

# 알람 대상 센서 타입 (config에서 로드, 기본값 제공)
def get_alarm_sensor_types():
    """config에서 알람 대상 센서 타입 목록 반환"""
    try:
        from app.config import get_config
        config = get_config()
        return config.ALARM_SENSOR_TYPES
    except Exception:
        # 기본값 (config 로드 실패 시)
        return ['o2', 'no2', 'co', 'co2', 'h2s', 'ch4', 'ch2o', 'o3']

# 하위 호환성을 위한 기본 상수 (동적 로드 권장)
ALARM_SENSOR_TYPES = ['o2', 'no2', 'co', 'co2', 'h2s', 'ch4', 'ch2o', 'o3']


# 센서 데이터 타입 정의 (단위 포함)
SENSOR_TYPES = {
    'o2': {'name': '산소', 'name_en': 'O2', 'unit': '%', 'min': 0, 'max': 25},
    'no2': {'name': '이산화질소', 'name_en': 'NO2', 'unit': 'ppm', 'min': 0, 'max': 20},
    'co': {'name': '일산화탄소', 'name_en': 'CO', 'unit': 'ppm', 'min': 0, 'max': 1000},
    'co2': {'name': '이산화탄소', 'name_en': 'CO2', 'unit': 'ppm', 'min': 0, 'max': 5000},
    'h2s': {'name': '황화수소', 'name_en': 'H2S', 'unit': 'ppm', 'min': 0, 'max': 100},
    'ch4': {'name': '메탄', 'name_en': 'CH4', 'unit': '% LEL', 'min': 0, 'max': 100},
    'ch2o': {'name': '폼알데하이드', 'name_en': 'CH2O', 'unit': 'ppm', 'min': 0, 'max': 10},
    'o3': {'name': '오존', 'name_en': 'O3', 'unit': 'ppm', 'min': 0, 'max': 1},
    'voc': {'name': 'VOC', 'name_en': 'VOC', 'unit': 'ppm', 'min': 0, 'max': 500},
    'pm1': {'name': 'PM1.0', 'name_en': 'PM1', 'unit': 'μg/m³', 'min': 0, 'max': 500},
    'pm25': {'name': 'PM2.5', 'name_en': 'PM2.5', 'unit': 'μg/m³', 'min': 0, 'max': 500},
    'pm10': {'name': 'PM10', 'name_en': 'PM10', 'unit': 'μg/m³', 'min': 0, 'max': 500},
    'temp': {'name': '온도', 'name_en': 'Temperature', 'unit': '°C', 'min': -40, 'max': 80},
    'humi': {'name': '습도', 'name_en': 'Humidity', 'unit': '%', 'min': 0, 'max': 100},
}


class Database:
    """SQLite 데이터베이스 관리 클래스"""

    # 테이블 생성 SQL
    SCHEMA = """
    -- sites 테이블: 현장 정보
    CREATE TABLE IF NOT EXISTS sites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        site_code VARCHAR(20) UNIQUE NOT NULL,  -- H001S0001
        h_cd VARCHAR(10) NOT NULL,               -- H001
        s_cd VARCHAR(10) NOT NULL,               -- S0001
        name VARCHAR(100),
        location VARCHAR(200),
        description TEXT,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- devices 테이블: 장치 정보
    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id VARCHAR(30) UNIQUE NOT NULL,   -- H001S0001_1
        site_code VARCHAR(20) NOT NULL,          -- H001S0001
        dv_no VARCHAR(10) NOT NULL,              -- 1
        name VARCHAR(100),
        description TEXT,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (site_code) REFERENCES sites(site_code)
    );

    -- environment_data 테이블: 환경/가스 센서 측정 데이터
    CREATE TABLE IF NOT EXISTS environment_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id VARCHAR(30) NOT NULL,          -- H001S0001_1
        site_code VARCHAR(20) NOT NULL,          -- H001S0001
        h_cd VARCHAR(10) NOT NULL,               -- H001
        s_cd VARCHAR(10) NOT NULL,               -- S0001
        dv_no VARCHAR(10) NOT NULL,              -- 1
        -- 가스 센서
        o2 REAL,                                 -- 산소 (%)
        no2 REAL,                                -- 이산화질소 (ppm)
        co REAL,                                 -- 일산화탄소 (ppm)
        co2 REAL,                                -- 이산화탄소 (ppm)
        h2s REAL,                                -- 황화수소 (ppm)
        ch4 REAL,                                -- 메탄 (% LEL)
        ch2o REAL,                               -- 폼알데하이드 (ppm)
        o3 REAL,                                 -- 오존 (ppm)
        voc REAL,                                -- VOC (ppm)
        -- 미세먼지
        pm1 REAL,                                -- PM1.0 (μg/m³)
        pm25 REAL,                               -- PM2.5 (μg/m³)
        pm10 REAL,                               -- PM10 (μg/m³)
        -- 환경
        temp REAL,                               -- 온도 (°C)
        humi REAL,                               -- 습도 (%)
        -- 메타데이터
        check_time DATETIME,                     -- 센서 측정 시간
        raw_payload TEXT,
        topic VARCHAR(200),
        qos INTEGER DEFAULT 0,
        received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (device_id) REFERENCES devices(device_id)
    );

    -- 인덱스
    CREATE INDEX IF NOT EXISTS idx_env_device_id ON environment_data(device_id);
    CREATE INDEX IF NOT EXISTS idx_env_site_code ON environment_data(site_code);
    CREATE INDEX IF NOT EXISTS idx_env_check_time ON environment_data(check_time);
    CREATE INDEX IF NOT EXISTS idx_env_received_at ON environment_data(received_at);
    CREATE INDEX IF NOT EXISTS idx_env_h_cd ON environment_data(h_cd);

    -- mqtt_logs 테이블: MQTT 이벤트 로그
    CREATE TABLE IF NOT EXISTS mqtt_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type VARCHAR(20) NOT NULL,
        topic VARCHAR(200),
        message TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- 알람 기준값 테이블 (선택적)
    CREATE TABLE IF NOT EXISTS alarm_thresholds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sensor_type VARCHAR(20) NOT NULL,        -- o2, co, etc.
        warning_low REAL,
        warning_high REAL,
        danger_low REAL,
        danger_high REAL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- alarm_logs 테이블: 경고 알람 로그
    CREATE TABLE IF NOT EXISTS alarm_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        site_code VARCHAR(20) NOT NULL,          -- H001S0001
        device_id VARCHAR(30) NOT NULL,          -- H001S0001_1
        dv_no VARCHAR(10) NOT NULL,              -- 장치 번호
        sensor_type VARCHAR(20) NOT NULL,        -- o2, co, co2 등
        value REAL NOT NULL,                     -- 센서 값
        level INTEGER NOT NULL,                  -- 경고 레벨 (0:정상, 1:주의, 2:경고, 3:위험)
        etc TEXT,                                -- 추가 정보
        alarm_time DATETIME,                     -- 알람 발생 시간
        topic VARCHAR(200),
        raw_payload TEXT,
        is_acknowledged BOOLEAN DEFAULT 0,       -- 확인 여부
        acknowledged_at DATETIME,
        acknowledged_by VARCHAR(100),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- alarm_logs 인덱스
    CREATE INDEX IF NOT EXISTS idx_alarm_site_code ON alarm_logs(site_code);
    CREATE INDEX IF NOT EXISTS idx_alarm_device_id ON alarm_logs(device_id);
    CREATE INDEX IF NOT EXISTS idx_alarm_sensor_type ON alarm_logs(sensor_type);
    CREATE INDEX IF NOT EXISTS idx_alarm_level ON alarm_logs(level);
    CREATE INDEX IF NOT EXISTS idx_alarm_created_at ON alarm_logs(created_at);
    CREATE INDEX IF NOT EXISTS idx_alarm_is_acknowledged ON alarm_logs(is_acknowledged);
    """

    def __init__(self, db_path: str):
        """
        데이터베이스 초기화

        Args:
            db_path: 데이터베이스 파일 경로
        """
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None

        # 디렉토리 생성
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    @property
    def connection(self) -> sqlite3.Connection:
        """데이터베이스 연결 반환 (지연 연결)"""
        if self._connection is None:
            self._connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                detect_types=sqlite3.PARSE_DECLTYPES
            )
            self._connection.row_factory = sqlite3.Row
            # 외래키 제약 활성화
            self._connection.execute("PRAGMA foreign_keys = ON")
        return self._connection

    @contextmanager
    def get_cursor(self):
        """커서 컨텍스트 매니저"""
        cursor = self.connection.cursor()
        try:
            yield cursor
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            logger.error(f"데이터베이스 오류: {e}")
            raise
        finally:
            cursor.close()

    def init_db(self):
        """데이터베이스 스키마 초기화"""
        with self.get_cursor() as cursor:
            cursor.executescript(self.SCHEMA)
        logger.info(f"데이터베이스 초기화 완료: {self.db_path}")

    def close(self):
        """데이터베이스 연결 종료"""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("데이터베이스 연결 종료")

    # ===== Site CRUD =====

    def create_site(self, site: Site) -> int:
        """현장 생성 또는 업데이트 (UPSERT)"""
        sql = """
        INSERT INTO sites (site_code, h_cd, s_cd, name, location, description, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(site_code) DO UPDATE SET
            updated_at = CURRENT_TIMESTAMP
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql, (
                site.site_code,
                site.h_cd,
                site.s_cd,
                site.name,
                site.location,
                site.description,
                site.is_active
            ))
            return cursor.lastrowid

    def get_site(self, site_code: str) -> Optional[Site]:
        """현장 조회"""
        sql = "SELECT * FROM sites WHERE site_code = ?"
        with self.get_cursor() as cursor:
            cursor.execute(sql, (site_code,))
            row = cursor.fetchone()
            if row:
                return Site(**dict(row))
        return None

    def get_all_sites(self, active_only: bool = False) -> List[Site]:
        """모든 현장 조회"""
        sql = "SELECT * FROM sites"
        if active_only:
            sql += " WHERE is_active = 1"
        sql += " ORDER BY site_code"

        with self.get_cursor() as cursor:
            cursor.execute(sql)
            return [Site(**dict(row)) for row in cursor.fetchall()]

    def update_site(self, site_code: str, **kwargs) -> bool:
        """현장 정보 수정"""
        allowed_fields = ['name', 'location', 'description', 'is_active']
        updates = []
        params = []

        for field in allowed_fields:
            if field in kwargs:
                updates.append(f"{field} = ?")
                params.append(kwargs[field])

        if not updates:
            return False

        updates.append("updated_at = CURRENT_TIMESTAMP")
        sql = f"UPDATE sites SET {', '.join(updates)} WHERE site_code = ?"
        params.append(site_code)

        with self.get_cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.rowcount > 0

    def delete_site(self, site_code: str) -> bool:
        """현장 삭제 (연결된 장치가 없는 경우만)"""
        sql = "DELETE FROM sites WHERE site_code = ?"
        with self.get_cursor() as cursor:
            cursor.execute(sql, (site_code,))
            return cursor.rowcount > 0

    def get_site_device_count(self, site_code: str) -> int:
        """현장에 연결된 장치 수 조회"""
        sql = "SELECT COUNT(*) FROM devices WHERE site_code = ?"
        with self.get_cursor() as cursor:
            cursor.execute(sql, (site_code,))
            return cursor.fetchone()[0]

    def create_site_manual(
        self,
        h_cd: str,
        s_cd: str,
        name: Optional[str] = None,
        location: Optional[str] = None,
        description: Optional[str] = None
    ) -> int:
        """수동 현장 생성 (중복 체크 포함)"""
        site_code = f"{h_cd}{s_cd}"

        # 중복 체크
        existing = self.get_site(site_code)
        if existing:
            raise ValueError(f"현장 코드 '{site_code}'가 이미 존재합니다.")

        site = Site(
            site_code=site_code,
            h_cd=h_cd,
            s_cd=s_cd,
            name=name,
            location=location,
            description=description,
            is_active=True
        )
        return self.create_site(site)

    # ===== Device CRUD =====

    def create_device(self, device: Device) -> int:
        """장치 생성 또는 업데이트 (UPSERT)"""
        sql = """
        INSERT INTO devices (device_id, site_code, dv_no, name, description, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(device_id) DO UPDATE SET
            updated_at = CURRENT_TIMESTAMP
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql, (
                device.device_id,
                device.site_code,
                device.dv_no,
                device.name,
                device.description,
                device.is_active
            ))
            return cursor.lastrowid

    def get_device(self, device_id: str) -> Optional[Device]:
        """장치 조회"""
        sql = "SELECT * FROM devices WHERE device_id = ?"
        with self.get_cursor() as cursor:
            cursor.execute(sql, (device_id,))
            row = cursor.fetchone()
            if row:
                return Device(**dict(row))
        return None

    def get_devices_by_site(self, site_code: str) -> List[Device]:
        """현장별 장치 목록 조회"""
        sql = "SELECT * FROM devices WHERE site_code = ? ORDER BY dv_no"
        with self.get_cursor() as cursor:
            cursor.execute(sql, (site_code,))
            return [Device(**dict(row)) for row in cursor.fetchall()]

    def get_all_devices(self, active_only: bool = False) -> List[Device]:
        """모든 장치 조회"""
        sql = "SELECT * FROM devices"
        if active_only:
            sql += " WHERE is_active = 1"
        sql += " ORDER BY device_id"

        with self.get_cursor() as cursor:
            cursor.execute(sql)
            return [Device(**dict(row)) for row in cursor.fetchall()]

    def update_device(self, device_id: str, **kwargs) -> bool:
        """장치 정보 수정"""
        allowed_fields = ['name', 'description', 'is_active']
        updates = []
        params = []

        for field in allowed_fields:
            if field in kwargs:
                updates.append(f"{field} = ?")
                params.append(kwargs[field])

        if not updates:
            return False

        updates.append("updated_at = CURRENT_TIMESTAMP")
        sql = f"UPDATE devices SET {', '.join(updates)} WHERE device_id = ?"
        params.append(device_id)

        with self.get_cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.rowcount > 0

    def delete_device(self, device_id: str) -> bool:
        """장치 삭제"""
        sql = "DELETE FROM devices WHERE device_id = ?"
        with self.get_cursor() as cursor:
            cursor.execute(sql, (device_id,))
            return cursor.rowcount > 0

    def get_device_data_count(self, device_id: str) -> int:
        """장치의 환경 데이터 수 조회"""
        sql = "SELECT COUNT(*) FROM environment_data WHERE device_id = ?"
        with self.get_cursor() as cursor:
            cursor.execute(sql, (device_id,))
            return cursor.fetchone()[0]

    def create_device_manual(
        self,
        site_code: str,
        dv_no: str,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> int:
        """수동 장치 생성 (중복 체크 포함)"""
        device_id = f"{site_code}_{dv_no}"

        # 중복 체크
        existing = self.get_device(device_id)
        if existing:
            raise ValueError(f"장치 ID '{device_id}'가 이미 존재합니다.")

        # 현장 존재 확인
        site = self.get_site(site_code)
        if not site:
            raise ValueError(f"현장 코드 '{site_code}'가 존재하지 않습니다.")

        device = Device(
            device_id=device_id,
            site_code=site_code,
            dv_no=dv_no,
            name=name,
            description=description,
            is_active=True
        )
        return self.create_device(device)

    # ===== EnvironmentData CRUD =====

    def save_environment_data(self, data: EnvironmentData) -> int:
        """환경 센서 데이터 저장"""
        sql = """
        INSERT INTO environment_data
        (device_id, site_code, h_cd, s_cd, dv_no,
         o2, no2, co, co2, h2s, ch4, ch2o, o3, voc,
         pm1, pm25, pm10, temp, humi,
         check_time, raw_payload, topic, qos)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql, (
                data.device_id,
                data.site_code,
                data.h_cd,
                data.s_cd,
                data.dv_no,
                data.o2,
                data.no2,
                data.co,
                data.co2,
                data.h2s,
                data.ch4,
                data.ch2o,
                data.o3,
                data.voc,
                data.pm1,
                data.pm25,
                data.pm10,
                data.temp,
                data.humi,
                data.check_time,
                data.raw_payload,
                data.topic,
                data.qos
            ))
            return cursor.lastrowid

    def get_environment_data(
        self,
        device_id: Optional[str] = None,
        site_code: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[EnvironmentData]:
        """환경 데이터 조회 (필터링 지원)"""
        sql = "SELECT * FROM environment_data WHERE 1=1"
        params = []

        if device_id:
            sql += " AND device_id = ?"
            params.append(device_id)

        if site_code:
            sql += " AND site_code = ?"
            params.append(site_code)

        if start_time:
            sql += " AND received_at >= ?"
            params.append(start_time)

        if end_time:
            sql += " AND received_at <= ?"
            params.append(end_time)

        sql += " ORDER BY received_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.get_cursor() as cursor:
            cursor.execute(sql, params)
            return [EnvironmentData(**dict(row)) for row in cursor.fetchall()]

    def get_latest_data(self, limit: int = 10) -> List[EnvironmentData]:
        """최신 환경 데이터 조회"""
        sql = """
        SELECT * FROM environment_data
        ORDER BY received_at DESC
        LIMIT ?
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql, (limit,))
            return [EnvironmentData(**dict(row)) for row in cursor.fetchall()]

    def get_latest_by_device(self) -> List[Dict[str, Any]]:
        """각 장치별 최신 데이터 조회"""
        sql = """
        SELECT ed.* FROM environment_data ed
        INNER JOIN (
            SELECT device_id, MAX(received_at) as max_time
            FROM environment_data
            GROUP BY device_id
        ) latest ON ed.device_id = latest.device_id
                AND ed.received_at = latest.max_time
        ORDER BY ed.device_id
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql)
            return [dict(row) for row in cursor.fetchall()]

    def get_latest_by_site(self) -> List[Dict[str, Any]]:
        """각 현장별 최신 데이터 조회"""
        sql = """
        SELECT ed.* FROM environment_data ed
        INNER JOIN (
            SELECT site_code, MAX(received_at) as max_time
            FROM environment_data
            GROUP BY site_code
        ) latest ON ed.site_code = latest.site_code
                AND ed.received_at = latest.max_time
        ORDER BY ed.site_code
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql)
            return [dict(row) for row in cursor.fetchall()]

    # ===== 통계 및 집계 =====

    def get_device_stats(
        self,
        device_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """장치별 데이터 통계 조회"""
        sql = """
        SELECT
            device_id,
            site_code,
            COUNT(*) as count,
            ROUND(AVG(o2), 2) as avg_o2,
            ROUND(AVG(co), 2) as avg_co,
            ROUND(AVG(co2), 2) as avg_co2,
            ROUND(AVG(temp), 2) as avg_temp,
            ROUND(AVG(humi), 2) as avg_humi,
            ROUND(AVG(pm25), 2) as avg_pm25,
            MIN(received_at) as first_received,
            MAX(received_at) as last_received
        FROM environment_data
        WHERE device_id = ?
        """
        params = [device_id]

        if start_time:
            sql += " AND received_at >= ?"
            params.append(start_time)

        if end_time:
            sql += " AND received_at <= ?"
            params.append(end_time)

        sql += " GROUP BY device_id, site_code"

        with self.get_cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()
            if row:
                return dict(row)
        return {}

    def get_all_stats(self) -> List[Dict[str, Any]]:
        """전체 장치 통계 조회"""
        sql = """
        SELECT
            device_id,
            site_code,
            COUNT(*) as count,
            ROUND(AVG(o2), 2) as avg_o2,
            ROUND(AVG(co), 2) as avg_co,
            ROUND(AVG(co2), 2) as avg_co2,
            ROUND(AVG(temp), 2) as avg_temp,
            ROUND(AVG(humi), 2) as avg_humi,
            ROUND(AVG(pm25), 2) as avg_pm25,
            MAX(received_at) as last_received
        FROM environment_data
        GROUP BY device_id, site_code
        ORDER BY device_id
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql)
            return [dict(row) for row in cursor.fetchall()]

    # ===== MqttLog CRUD =====

    def save_mqtt_log(self, log: MqttLog) -> int:
        """MQTT 로그 저장"""
        sql = """
        INSERT INTO mqtt_logs (event_type, topic, message)
        VALUES (?, ?, ?)
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql, (log.event_type, log.topic, log.message))
            return cursor.lastrowid

    def get_mqtt_logs(
        self,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[MqttLog]:
        """MQTT 로그 조회"""
        sql = "SELECT * FROM mqtt_logs"
        params = []

        if event_type:
            sql += " WHERE event_type = ?"
            params.append(event_type)

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self.get_cursor() as cursor:
            cursor.execute(sql, params)
            return [MqttLog(**dict(row)) for row in cursor.fetchall()]

    # ===== AlarmLog CRUD =====

    def save_alarm_log(self, alarm: AlarmLog) -> int:
        """알람 로그 저장"""
        sql = """
        INSERT INTO alarm_logs
        (site_code, device_id, dv_no, sensor_type, value, level,
         etc, alarm_time, topic, raw_payload)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql, (
                alarm.site_code,
                alarm.device_id,
                alarm.dv_no,
                alarm.sensor_type,
                alarm.value,
                alarm.level,
                alarm.etc,
                alarm.alarm_time,
                alarm.topic,
                alarm.raw_payload
            ))
            return cursor.lastrowid

    def get_alarm_logs(
        self,
        site_code: Optional[str] = None,
        device_id: Optional[str] = None,
        sensor_type: Optional[str] = None,
        level: Optional[int] = None,
        is_acknowledged: Optional[bool] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AlarmLog]:
        """알람 로그 조회 (필터링 지원)"""
        sql = "SELECT * FROM alarm_logs WHERE 1=1"
        params = []

        if site_code:
            sql += " AND site_code = ?"
            params.append(site_code)

        if device_id:
            sql += " AND device_id = ?"
            params.append(device_id)

        if sensor_type:
            sql += " AND sensor_type = ?"
            params.append(sensor_type)

        if level is not None:
            sql += " AND level = ?"
            params.append(level)

        if is_acknowledged is not None:
            sql += " AND is_acknowledged = ?"
            params.append(1 if is_acknowledged else 0)

        if start_time:
            sql += " AND created_at >= ?"
            params.append(start_time)

        if end_time:
            sql += " AND created_at <= ?"
            params.append(end_time)

        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.get_cursor() as cursor:
            cursor.execute(sql, params)
            return [AlarmLog(**dict(row)) for row in cursor.fetchall()]

    def get_unacknowledged_alarms(self, limit: int = 100) -> List[AlarmLog]:
        """미확인 알람 조회"""
        sql = """
        SELECT * FROM alarm_logs
        WHERE is_acknowledged = 0
        ORDER BY created_at DESC
        LIMIT ?
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql, (limit,))
            return [AlarmLog(**dict(row)) for row in cursor.fetchall()]

    def acknowledge_alarm(
        self,
        alarm_id: int,
        acknowledged_by: Optional[str] = None
    ) -> bool:
        """알람 확인 처리"""
        sql = """
        UPDATE alarm_logs
        SET is_acknowledged = 1,
            acknowledged_at = CURRENT_TIMESTAMP,
            acknowledged_by = ?
        WHERE id = ?
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql, (acknowledged_by, alarm_id))
            return cursor.rowcount > 0

    def acknowledge_all_alarms(
        self,
        site_code: Optional[str] = None,
        acknowledged_by: Optional[str] = None
    ) -> int:
        """모든 미확인 알람 확인 처리"""
        sql = """
        UPDATE alarm_logs
        SET is_acknowledged = 1,
            acknowledged_at = CURRENT_TIMESTAMP,
            acknowledged_by = ?
        WHERE is_acknowledged = 0
        """
        params = [acknowledged_by]

        if site_code:
            sql += " AND site_code = ?"
            params.append(site_code)

        with self.get_cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.rowcount

    def get_alarm_stats(self) -> Dict[str, Any]:
        """알람 통계 조회"""
        stats = {}

        with self.get_cursor() as cursor:
            # 전체 알람 수
            cursor.execute("SELECT COUNT(*) FROM alarm_logs")
            stats['total'] = cursor.fetchone()[0]

            # 미확인 알람 수
            cursor.execute("SELECT COUNT(*) FROM alarm_logs WHERE is_acknowledged = 0")
            stats['unacknowledged'] = cursor.fetchone()[0]

            # 레벨별 알람 수
            cursor.execute("""
                SELECT level, COUNT(*) as count
                FROM alarm_logs
                GROUP BY level
            """)
            stats['by_level'] = {row['level']: row['count'] for row in cursor.fetchall()}

            # 센서 타입별 알람 수
            cursor.execute("""
                SELECT sensor_type, COUNT(*) as count
                FROM alarm_logs
                GROUP BY sensor_type
                ORDER BY count DESC
            """)
            stats['by_sensor'] = {row['sensor_type']: row['count'] for row in cursor.fetchall()}

            # 최근 24시간 알람 수
            cursor.execute("""
                SELECT COUNT(*) FROM alarm_logs
                WHERE created_at >= datetime('now', '-24 hours')
            """)
            stats['last_24h'] = cursor.fetchone()[0]

        return stats

    def get_recent_alarms_by_device(self) -> List[Dict[str, Any]]:
        """장치별 최근 알람 조회"""
        sql = """
        SELECT al.* FROM alarm_logs al
        INNER JOIN (
            SELECT device_id, sensor_type, MAX(created_at) as max_time
            FROM alarm_logs
            GROUP BY device_id, sensor_type
        ) latest ON al.device_id = latest.device_id
                AND al.sensor_type = latest.sensor_type
                AND al.created_at = latest.max_time
        ORDER BY al.created_at DESC
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql)
            return [dict(row) for row in cursor.fetchall()]

    # ===== 유틸리티 =====

    def get_data_count(self) -> Dict[str, int]:
        """테이블별 데이터 수 조회"""
        tables = ['sites', 'devices', 'environment_data', 'mqtt_logs', 'alarm_logs']
        counts = {}

        with self.get_cursor() as cursor:
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cursor.fetchone()[0]

        return counts

    def cleanup_old_data(self, days: int = 30) -> int:
        """오래된 데이터 삭제"""
        sql = """
        DELETE FROM environment_data
        WHERE received_at < datetime('now', ?)
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql, (f'-{days} days',))
            deleted = cursor.rowcount
            logger.info(f"{deleted}개의 오래된 데이터 삭제됨")
            return deleted


# 전역 데이터베이스 인스턴스
_db_instance: Optional[Database] = None


def get_db() -> Database:
    """데이터베이스 인스턴스 반환"""
    global _db_instance
    if _db_instance is None:
        from app.config import get_config
        config = get_config()
        db_path = str(Path(config.DATABASE_PATH).resolve())
        _db_instance = Database(db_path)
    return _db_instance


def close_db():
    """데이터베이스 연결 종료"""
    global _db_instance
    if _db_instance:
        _db_instance.close()
        _db_instance = None


def init_db():
    """데이터베이스 초기화"""
    db = get_db()
    db.init_db()
