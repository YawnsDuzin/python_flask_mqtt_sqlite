"""
데이터베이스 모듈
SQLite 데이터베이스 연결 및 CRUD 작업을 관리합니다.
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class Sensor:
    """센서 정보 데이터 클래스"""
    sensor_id: str
    sensor_type: str
    location: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    id: Optional[int] = None


@dataclass
class SensorData:
    """센서 데이터 데이터 클래스"""
    sensor_id: str
    sensor_type: str
    value: float
    unit: str
    raw_payload: Optional[str] = None
    topic: Optional[str] = None
    qos: int = 0
    timestamp: Optional[str] = None
    received_at: Optional[str] = None
    id: Optional[int] = None


@dataclass
class ProcessedData:
    """가공 데이터 데이터 클래스"""
    sensor_id: str
    process_type: str
    value: float
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    sample_count: Optional[int] = None
    created_at: Optional[str] = None
    id: Optional[int] = None


@dataclass
class MqttLog:
    """MQTT 로그 데이터 클래스"""
    event_type: str
    topic: Optional[str] = None
    message: Optional[str] = None
    created_at: Optional[str] = None
    id: Optional[int] = None


class Database:
    """SQLite 데이터베이스 관리 클래스"""

    # 테이블 생성 SQL
    SCHEMA = """
    -- sensors 테이블: 센서 정보
    CREATE TABLE IF NOT EXISTS sensors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sensor_id VARCHAR(50) UNIQUE NOT NULL,
        sensor_type VARCHAR(30) NOT NULL,
        location VARCHAR(100),
        description TEXT,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- sensor_data 테이블: 센서 측정 데이터
    CREATE TABLE IF NOT EXISTS sensor_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sensor_id VARCHAR(50) NOT NULL,
        sensor_type VARCHAR(30) NOT NULL,
        value REAL NOT NULL,
        unit VARCHAR(20) NOT NULL,
        raw_payload TEXT,
        topic VARCHAR(200),
        qos INTEGER DEFAULT 0,
        timestamp DATETIME,
        received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id)
    );

    -- 센서 데이터 인덱스
    CREATE INDEX IF NOT EXISTS idx_sensor_data_sensor_id ON sensor_data(sensor_id);
    CREATE INDEX IF NOT EXISTS idx_sensor_data_timestamp ON sensor_data(timestamp);
    CREATE INDEX IF NOT EXISTS idx_sensor_data_received_at ON sensor_data(received_at);
    CREATE INDEX IF NOT EXISTS idx_sensor_data_type ON sensor_data(sensor_type);

    -- processed_data 테이블: 가공/집계 데이터
    CREATE TABLE IF NOT EXISTS processed_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sensor_id VARCHAR(50) NOT NULL,
        process_type VARCHAR(30) NOT NULL,
        value REAL NOT NULL,
        period_start DATETIME,
        period_end DATETIME,
        sample_count INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id)
    );

    -- mqtt_logs 테이블: MQTT 이벤트 로그
    CREATE TABLE IF NOT EXISTS mqtt_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type VARCHAR(20) NOT NULL,
        topic VARCHAR(200),
        message TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
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

    # ===== Sensor CRUD =====

    def create_sensor(self, sensor: Sensor) -> int:
        """센서 생성 또는 업데이트 (UPSERT)"""
        sql = """
        INSERT INTO sensors (sensor_id, sensor_type, location, description, is_active)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(sensor_id) DO UPDATE SET
            sensor_type = excluded.sensor_type,
            updated_at = CURRENT_TIMESTAMP
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql, (
                sensor.sensor_id,
                sensor.sensor_type,
                sensor.location,
                sensor.description,
                sensor.is_active
            ))
            return cursor.lastrowid

    def get_sensor(self, sensor_id: str) -> Optional[Sensor]:
        """센서 조회"""
        sql = "SELECT * FROM sensors WHERE sensor_id = ?"
        with self.get_cursor() as cursor:
            cursor.execute(sql, (sensor_id,))
            row = cursor.fetchone()
            if row:
                return Sensor(**dict(row))
        return None

    def get_all_sensors(self, active_only: bool = False) -> List[Sensor]:
        """모든 센서 조회"""
        sql = "SELECT * FROM sensors"
        if active_only:
            sql += " WHERE is_active = 1"
        sql += " ORDER BY sensor_id"

        with self.get_cursor() as cursor:
            cursor.execute(sql)
            return [Sensor(**dict(row)) for row in cursor.fetchall()]

    def update_sensor_status(self, sensor_id: str, is_active: bool) -> bool:
        """센서 활성 상태 업데이트"""
        sql = """
        UPDATE sensors
        SET is_active = ?, updated_at = CURRENT_TIMESTAMP
        WHERE sensor_id = ?
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql, (is_active, sensor_id))
            return cursor.rowcount > 0

    # ===== SensorData CRUD =====

    def save_sensor_data(self, data: SensorData) -> int:
        """센서 데이터 저장"""
        sql = """
        INSERT INTO sensor_data
        (sensor_id, sensor_type, value, unit, raw_payload, topic, qos, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql, (
                data.sensor_id,
                data.sensor_type,
                data.value,
                data.unit,
                data.raw_payload,
                data.topic,
                data.qos,
                data.timestamp
            ))
            return cursor.lastrowid

    def get_sensor_data(
        self,
        sensor_id: Optional[str] = None,
        sensor_type: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[SensorData]:
        """센서 데이터 조회 (필터링 지원)"""
        sql = "SELECT * FROM sensor_data WHERE 1=1"
        params = []

        if sensor_id:
            sql += " AND sensor_id = ?"
            params.append(sensor_id)

        if sensor_type:
            sql += " AND sensor_type = ?"
            params.append(sensor_type)

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
            return [SensorData(**dict(row)) for row in cursor.fetchall()]

    def get_latest_data(self, limit: int = 10) -> List[SensorData]:
        """최신 센서 데이터 조회"""
        sql = """
        SELECT * FROM sensor_data
        ORDER BY received_at DESC
        LIMIT ?
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql, (limit,))
            return [SensorData(**dict(row)) for row in cursor.fetchall()]

    def get_latest_by_sensor(self) -> List[Dict[str, Any]]:
        """각 센서별 최신 데이터 조회"""
        sql = """
        SELECT sd.* FROM sensor_data sd
        INNER JOIN (
            SELECT sensor_id, MAX(received_at) as max_time
            FROM sensor_data
            GROUP BY sensor_id
        ) latest ON sd.sensor_id = latest.sensor_id
                AND sd.received_at = latest.max_time
        ORDER BY sd.sensor_id
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql)
            return [dict(row) for row in cursor.fetchall()]

    # ===== 통계 및 집계 =====

    def get_sensor_stats(
        self,
        sensor_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """센서 데이터 통계 조회"""
        sql = """
        SELECT
            sensor_id,
            sensor_type,
            COUNT(*) as count,
            AVG(value) as avg_value,
            MIN(value) as min_value,
            MAX(value) as max_value,
            MIN(received_at) as first_received,
            MAX(received_at) as last_received
        FROM sensor_data
        WHERE sensor_id = ?
        """
        params = [sensor_id]

        if start_time:
            sql += " AND received_at >= ?"
            params.append(start_time)

        if end_time:
            sql += " AND received_at <= ?"
            params.append(end_time)

        sql += " GROUP BY sensor_id, sensor_type"

        with self.get_cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()
            if row:
                return dict(row)
        return {}

    def get_all_stats(self) -> List[Dict[str, Any]]:
        """전체 센서 통계 조회"""
        sql = """
        SELECT
            sensor_id,
            sensor_type,
            COUNT(*) as count,
            ROUND(AVG(value), 2) as avg_value,
            ROUND(MIN(value), 2) as min_value,
            ROUND(MAX(value), 2) as max_value,
            MAX(received_at) as last_received
        FROM sensor_data
        GROUP BY sensor_id, sensor_type
        ORDER BY sensor_id
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql)
            return [dict(row) for row in cursor.fetchall()]

    # ===== ProcessedData CRUD =====

    def save_processed_data(self, data: ProcessedData) -> int:
        """가공 데이터 저장"""
        sql = """
        INSERT INTO processed_data
        (sensor_id, process_type, value, period_start, period_end, sample_count)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql, (
                data.sensor_id,
                data.process_type,
                data.value,
                data.period_start,
                data.period_end,
                data.sample_count
            ))
            return cursor.lastrowid

    def get_processed_data(
        self,
        sensor_id: Optional[str] = None,
        process_type: Optional[str] = None,
        limit: int = 100
    ) -> List[ProcessedData]:
        """가공 데이터 조회"""
        sql = "SELECT * FROM processed_data WHERE 1=1"
        params = []

        if sensor_id:
            sql += " AND sensor_id = ?"
            params.append(sensor_id)

        if process_type:
            sql += " AND process_type = ?"
            params.append(process_type)

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self.get_cursor() as cursor:
            cursor.execute(sql, params)
            return [ProcessedData(**dict(row)) for row in cursor.fetchall()]

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

    # ===== 유틸리티 =====

    def get_data_count(self) -> Dict[str, int]:
        """테이블별 데이터 수 조회"""
        tables = ['sensors', 'sensor_data', 'processed_data', 'mqtt_logs']
        counts = {}

        with self.get_cursor() as cursor:
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cursor.fetchone()[0]

        return counts

    def cleanup_old_data(self, days: int = 30) -> int:
        """오래된 데이터 삭제"""
        sql = """
        DELETE FROM sensor_data
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
