"""
MQTT 클라이언트 모듈
MQTT 브로커와의 연결, 구독, 발행을 관리합니다.
환경/가스 센서 복합 데이터 지원
"""

import json
import logging
import threading
import time
from typing import Optional, Callable, List, Dict, Any
from datetime import datetime

import paho.mqtt.client as mqtt

from app.parsers import (
    parse_mqtt_data,
    is_environment_data,
    ParsedEnvironmentData,
    ParsedData
)
from app.models import get_db, Site, Device, EnvironmentData, MqttLog, SENSOR_TYPES

logger = logging.getLogger(__name__)


class MQTTClient:
    """
    MQTT 클라이언트 클래스

    브로커 연결, 메시지 구독/발행, 자동 재연결을 관리합니다.
    환경/가스 복합 센서 데이터를 지원합니다.
    """

    def __init__(
        self,
        broker_host: str = 'localhost',
        broker_port: int = 1883,
        client_id: str = 'flask_mqtt_client',
        username: str = None,
        password: str = None,
        keepalive: int = 60,
        qos: int = 1
    ):
        """
        MQTT 클라이언트 초기화

        Args:
            broker_host: 브로커 호스트 주소
            broker_port: 브로커 포트 (기본 1883)
            client_id: 클라이언트 식별자
            username: 인증 사용자명 (선택)
            password: 인증 비밀번호 (선택)
            keepalive: Keep Alive 간격 (초)
            qos: 기본 QoS 레벨
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id
        self.username = username
        self.password = password
        self.keepalive = keepalive
        self.default_qos = qos

        # MQTT 클라이언트 생성
        self.client = mqtt.Client(
            client_id=client_id,
            clean_session=True,
            protocol=mqtt.MQTTv311
        )

        # 콜백 설정
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_subscribe = self._on_subscribe
        self.client.on_publish = self._on_publish

        # 인증 설정
        if username and password:
            self.client.username_pw_set(username, password)

        # 상태 변수
        self.is_connected = False
        self.subscribed_topics: List[str] = []
        self._reconnect_delay = 1  # 재연결 지연 시간 (초)
        self._max_reconnect_delay = 60
        self._stop_flag = False

        # 메시지 콜백 핸들러 (외부에서 등록 가능)
        self._message_handlers: List[Callable[[str, str, int], None]] = []

        # SocketIO 인스턴스 (웹 실시간 업데이트용)
        self.socketio = None

        logger.info(f"MQTT 클라이언트 초기화: {broker_host}:{broker_port}")

    def set_socketio(self, socketio):
        """SocketIO 인스턴스 설정"""
        self.socketio = socketio

    def connect(self) -> bool:
        """
        브로커에 연결

        Returns:
            연결 성공 여부
        """
        try:
            logger.info(f"MQTT 브로커 연결 시도: {self.broker_host}:{self.broker_port}")
            self.client.connect(
                self.broker_host,
                self.broker_port,
                self.keepalive
            )
            return True
        except Exception as e:
            logger.error(f"MQTT 연결 실패: {e}")
            self._log_mqtt_event('connect_error', message=str(e))
            return False

    def disconnect(self):
        """브로커 연결 해제"""
        self._stop_flag = True
        self.client.disconnect()
        logger.info("MQTT 브로커 연결 해제")

    def start(self):
        """백그라운드에서 MQTT 루프 시작"""
        if self.connect():
            self.client.loop_start()
            logger.info("MQTT 클라이언트 시작됨")

    def stop(self):
        """MQTT 클라이언트 중지"""
        self._stop_flag = True
        self.client.loop_stop()
        self.disconnect()
        logger.info("MQTT 클라이언트 중지됨")

    def subscribe(self, topics: List[str], qos: int = None):
        """
        토픽 구독

        Args:
            topics: 구독할 토픽 리스트
            qos: QoS 레벨 (미지정 시 기본값 사용)
        """
        if qos is None:
            qos = self.default_qos

        for topic in topics:
            self.client.subscribe(topic, qos)
            if topic not in self.subscribed_topics:
                self.subscribed_topics.append(topic)
            logger.info(f"토픽 구독: {topic} (QoS: {qos})")

    def unsubscribe(self, topic: str):
        """토픽 구독 해제"""
        self.client.unsubscribe(topic)
        if topic in self.subscribed_topics:
            self.subscribed_topics.remove(topic)
        logger.info(f"토픽 구독 해제: {topic}")

    def publish(
        self,
        topic: str,
        payload: Any,
        qos: int = None,
        retain: bool = False
    ) -> bool:
        """
        메시지 발행

        Args:
            topic: 발행할 토픽
            payload: 메시지 페이로드 (dict면 JSON으로 변환)
            qos: QoS 레벨
            retain: Retain 플래그

        Returns:
            발행 성공 여부
        """
        if qos is None:
            qos = self.default_qos

        try:
            # dict나 list면 JSON으로 변환
            if isinstance(payload, (dict, list)):
                payload = json.dumps(payload)

            result = self.client.publish(topic, payload, qos, retain)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"메시지 발행: {topic}")
                return True
            else:
                logger.error(f"메시지 발행 실패: {topic}, rc={result.rc}")
                return False

        except Exception as e:
            logger.error(f"메시지 발행 오류: {e}")
            return False

    def publish_processed_data(self, device_id: str, data_type: str, value: float, unit: str):
        """
        가공된 데이터 발행

        Args:
            device_id: 장치 ID
            data_type: 데이터 타입 (avg, min, max 등)
            value: 값
            unit: 단위
        """
        topic = f"processed/{device_id}/{data_type}"
        payload = {
            'device_id': device_id,
            'type': data_type,
            'value': round(value, 2),
            'unit': unit,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        self.publish(topic, payload, retain=True)

    def add_message_handler(self, handler: Callable[[str, str, int], None]):
        """
        메시지 수신 핸들러 추가

        Args:
            handler: 콜백 함수 (topic, payload, qos)
        """
        self._message_handlers.append(handler)

    # ===== 콜백 메소드 =====

    def _on_connect(self, client, userdata, flags, rc):
        """연결 완료 콜백"""
        if rc == 0:
            self.is_connected = True
            self._reconnect_delay = 1
            logger.info("MQTT 브로커 연결 성공")
            self._log_mqtt_event('connect', message='연결 성공')

            # 구독 토픽 재등록 (재연결 시)
            if self.subscribed_topics:
                for topic in self.subscribed_topics:
                    client.subscribe(topic, self.default_qos)
                logger.info(f"토픽 재구독: {self.subscribed_topics}")
        else:
            self.is_connected = False
            error_msg = self._get_connect_error_message(rc)
            logger.error(f"MQTT 연결 실패: {error_msg}")
            self._log_mqtt_event('connect_error', message=error_msg)

    def _on_disconnect(self, client, userdata, rc):
        """연결 해제 콜백"""
        self.is_connected = False

        if rc != 0:
            logger.warning(f"MQTT 연결 끊김 (rc={rc}), 재연결 시도...")
            self._log_mqtt_event('disconnect', message=f'비정상 종료 (rc={rc})')
            self._schedule_reconnect()
        else:
            logger.info("MQTT 정상 종료")
            self._log_mqtt_event('disconnect', message='정상 종료')

    def _on_message(self, client, userdata, msg):
        """메시지 수신 콜백"""
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        qos = msg.qos

        logger.debug(f"메시지 수신: {topic} (QoS: {qos})")

        try:
            # 데이터 파싱 (환경 센서 또는 단일 센서 자동 감지)
            parsed = parse_mqtt_data(payload, topic, qos)

            if parsed:
                # 데이터 타입에 따라 처리
                if isinstance(parsed, ParsedEnvironmentData):
                    self._save_environment_data(parsed, topic, qos, payload)
                else:
                    # 단일 센서 데이터 (기존 로직)
                    logger.warning("단일 센서 데이터 포맷은 더 이상 지원되지 않습니다.")

            # 외부 핸들러 호출
            for handler in self._message_handlers:
                try:
                    handler(topic, payload, qos)
                except Exception as e:
                    logger.error(f"메시지 핸들러 오류: {e}")

        except Exception as e:
            logger.error(f"메시지 처리 오류: {e}")
            self._log_mqtt_event('error', topic=topic, message=str(e))

    def _on_subscribe(self, client, userdata, mid, granted_qos):
        """구독 완료 콜백"""
        logger.debug(f"구독 완료 (mid={mid}, granted_qos={granted_qos})")

    def _on_publish(self, client, userdata, mid):
        """발행 완료 콜백"""
        logger.debug(f"발행 완료 (mid={mid})")

    # ===== 유틸리티 메소드 =====

    def _save_environment_data(
        self,
        parsed: ParsedEnvironmentData,
        topic: str,
        qos: int,
        raw_payload: str
    ):
        """환경 센서 데이터를 데이터베이스에 저장"""
        try:
            db = get_db()

            # 현장 정보 생성/업데이트
            site = Site(
                site_code=parsed.site_code,
                h_cd=parsed.h_cd,
                s_cd=parsed.s_cd
            )
            db.create_site(site)

            # 장치 정보 생성/업데이트
            device = Device(
                device_id=parsed.device_id,
                site_code=parsed.site_code,
                dv_no=parsed.dv_no
            )
            db.create_device(device)

            # 환경 데이터 저장
            env_data = parsed.to_environment_data(qos)
            db.save_environment_data(env_data)

            logger.debug(
                f"환경 데이터 저장: {parsed.device_id} "
                f"(온도: {parsed.temp}, 습도: {parsed.humi}, CO2: {parsed.co2})"
            )

            # SocketIO로 실시간 전송
            if self.socketio:
                self._emit_environment_data(parsed, topic)

        except Exception as e:
            logger.error(f"환경 데이터 저장 오류: {e}")

    def _emit_environment_data(self, parsed: ParsedEnvironmentData, topic: str):
        """환경 데이터를 SocketIO로 전송"""
        if not self.socketio:
            return

        # 센서 데이터를 개별적으로 전송
        sensor_data = {
            'device_id': parsed.device_id,
            'site_code': parsed.site_code,
            'h_cd': parsed.h_cd,
            's_cd': parsed.s_cd,
            'dv_no': parsed.dv_no,
            'check_time': parsed.check_time,
            'topic': topic,
            'sensors': {}
        }

        # 각 센서별 데이터 추가
        for sensor_type, info in SENSOR_TYPES.items():
            value = getattr(parsed, sensor_type, None)
            if value is not None:
                sensor_data['sensors'][sensor_type] = {
                    'value': value,
                    'unit': info['unit'],
                    'name': info['name'],
                    'name_en': info['name_en']
                }

        self.socketio.emit('environment_data', sensor_data)

    def _log_mqtt_event(self, event_type: str, topic: str = None, message: str = None):
        """MQTT 이벤트 로깅"""
        try:
            db = get_db()
            log = MqttLog(event_type=event_type, topic=topic, message=message)
            db.save_mqtt_log(log)
        except Exception as e:
            logger.error(f"MQTT 로그 저장 오류: {e}")

    def _schedule_reconnect(self):
        """재연결 스케줄링 (지수 백오프)"""
        if self._stop_flag:
            return

        def reconnect():
            time.sleep(self._reconnect_delay)
            if not self._stop_flag and not self.is_connected:
                logger.info(f"재연결 시도 ({self._reconnect_delay}초 후)...")
                self.connect()
                # 지수 백오프
                self._reconnect_delay = min(
                    self._reconnect_delay * 2,
                    self._max_reconnect_delay
                )

        thread = threading.Thread(target=reconnect, daemon=True)
        thread.start()

    def _get_connect_error_message(self, rc: int) -> str:
        """연결 에러 코드를 메시지로 변환"""
        messages = {
            1: "프로토콜 버전 불일치",
            2: "클라이언트 ID 거부",
            3: "서버 사용 불가",
            4: "잘못된 사용자명/비밀번호",
            5: "인증 거부"
        }
        return messages.get(rc, f"알 수 없는 오류 ({rc})")

    def get_status(self) -> Dict[str, Any]:
        """클라이언트 상태 반환"""
        return {
            'connected': self.is_connected,
            'broker': f"{self.broker_host}:{self.broker_port}",
            'client_id': self.client_id,
            'subscribed_topics': self.subscribed_topics,
        }


# 전역 MQTT 클라이언트 인스턴스
_mqtt_client: Optional[MQTTClient] = None


def get_mqtt_client() -> MQTTClient:
    """MQTT 클라이언트 인스턴스 반환"""
    global _mqtt_client
    if _mqtt_client is None:
        from app.config import get_config
        config = get_config()
        _mqtt_client = MQTTClient(
            broker_host=config.MQTT_BROKER_HOST,
            broker_port=config.MQTT_BROKER_PORT,
            client_id=config.MQTT_CLIENT_ID,
            username=config.MQTT_USERNAME or None,
            password=config.MQTT_PASSWORD or None,
            keepalive=config.MQTT_KEEPALIVE,
            qos=config.MQTT_QOS
        )
    return _mqtt_client


def init_mqtt_client(app=None, socketio=None):
    """MQTT 클라이언트 초기화 및 시작"""
    from app.config import get_config
    config = get_config()

    client = get_mqtt_client()

    if socketio:
        client.set_socketio(socketio)

    # 연결 및 구독
    client.start()
    client.subscribe(config.MQTT_SUBSCRIBE_TOPICS)

    return client
