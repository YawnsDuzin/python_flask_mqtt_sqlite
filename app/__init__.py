"""
Flask 애플리케이션 팩토리
애플리케이션 인스턴스 생성 및 초기화를 담당합니다.
"""

import logging
import os
from flask import Flask
from flask_socketio import SocketIO

# SocketIO 인스턴스 (전역)
socketio = SocketIO()


def create_app(config_name: str = None):
    """
    Flask 애플리케이션 팩토리

    Args:
        config_name: 설정 이름 (development, production, testing)

    Returns:
        Flask 애플리케이션 인스턴스
    """
    app = Flask(__name__)

    # 설정 로드
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    from app.config import config_by_name
    app.config.from_object(config_by_name[config_name])

    # 로깅 설정
    setup_logging(app)

    # 확장 초기화
    socketio.init_app(app, cors_allowed_origins="*")

    # 데이터베이스 초기화
    with app.app_context():
        from app.models import init_db
        init_db()

    # 블루프린트 등록
    from app.routes import main_bp, api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    # SocketIO 이벤트 핸들러 등록
    register_socketio_handlers(socketio)

    # MQTT 클라이언트 초기화 (프로덕션 모드에서만)
    if not app.config.get('TESTING', False):
        try:
            from app.mqtt.client import init_mqtt_client
            init_mqtt_client(app, socketio)
            app.logger.info("MQTT 클라이언트 초기화 완료")
        except Exception as e:
            app.logger.warning(f"MQTT 클라이언트 초기화 실패: {e}")

    app.logger.info(f"애플리케이션 생성 완료 ({config_name} 모드)")

    return app


def setup_logging(app: Flask):
    """로깅 설정"""
    log_level = app.config.get('LOG_LEVEL', 'INFO')

    # 루트 로거 설정
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Flask 앱 로거 설정
    app.logger.setLevel(getattr(logging, log_level))

    # paho-mqtt 로거 레벨 조정 (너무 많은 로그 방지)
    logging.getLogger('paho').setLevel(logging.WARNING)


def register_socketio_handlers(sio: SocketIO):
    """SocketIO 이벤트 핸들러 등록"""

    @sio.on('connect')
    def handle_connect():
        """클라이언트 연결"""
        from flask import request
        app_logger = logging.getLogger(__name__)
        app_logger.info(f"WebSocket 클라이언트 연결: {request.sid}")
        sio.emit('connection_response', {'status': 'connected'})

    @sio.on('disconnect')
    def handle_disconnect():
        """클라이언트 연결 해제"""
        from flask import request
        app_logger = logging.getLogger(__name__)
        app_logger.info(f"WebSocket 클라이언트 연결 해제: {request.sid}")

    @sio.on('subscribe_sensor')
    def handle_subscribe_sensor(data):
        """특정 센서 구독"""
        from flask_socketio import join_room
        sensor_id = data.get('sensor_id')
        if sensor_id:
            join_room(f"sensor_{sensor_id}")

    @sio.on('request_latest')
    def handle_request_latest(data):
        """최신 데이터 요청"""
        from app.models import get_db
        try:
            db = get_db()
            latest = db.get_latest_by_sensor()
            sio.emit('latest_data', {'data': latest})
        except Exception as e:
            sio.emit('error', {'message': str(e)})
