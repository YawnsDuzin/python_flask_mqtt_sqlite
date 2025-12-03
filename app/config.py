"""
애플리케이션 설정 모듈
환경 변수를 기반으로 설정 값을 관리합니다.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 프로젝트 루트 디렉토리
BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """기본 설정 클래스"""

    # Flask 설정
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    DEBUG = os.getenv('FLASK_DEBUG', '0') == '1'

    # 데이터베이스 설정
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'instance/sensors.db')
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{BASE_DIR / DATABASE_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # MQTT 설정
    MQTT_BROKER_HOST = os.getenv('MQTT_BROKER_HOST', 'localhost')
    MQTT_BROKER_PORT = int(os.getenv('MQTT_BROKER_PORT', '1883'))
    MQTT_KEEPALIVE = int(os.getenv('MQTT_KEEPALIVE', '60'))
    MQTT_USERNAME = os.getenv('MQTT_USERNAME', '')
    MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', '')
    MQTT_CLIENT_ID = os.getenv('MQTT_CLIENT_ID', 'flask_mqtt_client')
    MQTT_QOS = int(os.getenv('MQTT_QOS', '1'))

    # MQTT 구독 토픽 (쉼표로 구분된 여러 토픽 지원)
    _topics = os.getenv('MQTT_SUBSCRIBE_TOPICS', 'sensors/#')
    MQTT_SUBSCRIBE_TOPICS = [t.strip() for t in _topics.split(',')]

    # 로깅 설정
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    # 알람 대상 센서 타입 (쉼표로 구분)
    _alarm_sensors = os.getenv('ALARM_SENSOR_TYPES', 'o2,no2,co,co2,h2s,ch4,ch2o,o3')
    ALARM_SENSOR_TYPES = [s.strip().lower() for s in _alarm_sensors.split(',')]

    # 환경 데이터 DB 저장 설정 (평균값 저장 간격)
    MQTT_DATA_SAVE_INTERVAL = int(os.getenv('MQTT_DATA_SAVE_INTERVAL', '10'))

    # MQTT 포워딩 설정 (두 번째 브로커)
    MQTT_FORWARD_ENABLED = os.getenv('MQTT_FORWARD_ENABLED', 'false').lower() == 'true'
    MQTT_FORWARD_HOST = os.getenv('MQTT_FORWARD_HOST', '')
    MQTT_FORWARD_PORT = int(os.getenv('MQTT_FORWARD_PORT', '1883'))
    MQTT_FORWARD_USERNAME = os.getenv('MQTT_FORWARD_USERNAME', '')
    MQTT_FORWARD_PASSWORD = os.getenv('MQTT_FORWARD_PASSWORD', '')
    MQTT_FORWARD_CLIENT_ID = os.getenv('MQTT_FORWARD_CLIENT_ID', 'flask_mqtt_forwarder')
    MQTT_FORWARD_TOPIC_PREFIX = os.getenv('MQTT_FORWARD_TOPIC_PREFIX', 'forwarded')
    MQTT_FORWARD_INTERVAL = int(os.getenv('MQTT_FORWARD_INTERVAL', '10'))


class DevelopmentConfig(Config):
    """개발 환경 설정"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """운영 환경 설정"""
    DEBUG = False
    LOG_LEVEL = 'WARNING'


class TestingConfig(Config):
    """테스트 환경 설정"""
    TESTING = True
    DATABASE_PATH = 'instance/test_sensors.db'
    LOG_LEVEL = 'DEBUG'


# 환경별 설정 매핑
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """현재 환경에 맞는 설정 반환"""
    env = os.getenv('FLASK_ENV', 'development')
    return config_by_name.get(env, DevelopmentConfig)
