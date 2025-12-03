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
    is_alarm_topic,
    ParsedEnvironmentData,
    ParsedAlarmData
)
from app.models import get_db, Site, Device, EnvironmentData, MqttLog, AlarmLog, SENSOR_TYPES, ALARM_LEVELS
from collections import defaultdict

logger = logging.getLogger(__name__)

# 평균 계산 대상 센서 필드
SENSOR_FIELDS = [
    'o2', 'no2', 'co', 'co2', 'h2s', 'ch4', 'ch2o', 'o3',
    'voc', 'pm1', 'pm25', 'pm10', 'temp', 'humi'
]


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

        # MQTT 포워더 인스턴스
        self.forwarder = None

        # DB 저장용 데이터 버퍼 (장치별로 데이터 수집 후 평균 저장)
        self._data_buffer: Dict[str, List[Dict]] = defaultdict(list)
        self._buffer_lock = threading.Lock()
        self._save_interval = 10  # 기본 10초 (init_mqtt_client에서 설정)
        self._save_thread: Optional[threading.Thread] = None

        logger.info(f"MQTT 클라이언트 초기화: {broker_host}:{broker_port}")

    def set_socketio(self, socketio):
        """SocketIO 인스턴스 설정"""
        self.socketio = socketio

    def set_forwarder(self, forwarder):
        """MQTT 포워더 인스턴스 설정"""
        self.forwarder = forwarder

    def set_save_interval(self, interval: int):
        """DB 저장 간격 설정 (초)"""
        self._save_interval = interval
        logger.info(f"DB 저장 간격 설정: {interval}초")

    def _start_save_thread(self):
        """평균 데이터 DB 저장 스레드 시작"""
        self._save_thread = threading.Thread(
            target=self._save_loop,
            daemon=True,
            name="mqtt-data-saver"
        )
        self._save_thread.start()
        logger.info(f"DB 저장 스레드 시작됨 (간격: {self._save_interval}초)")

    def _save_loop(self):
        """주기적으로 버퍼의 데이터를 평균 계산하여 DB에 저장"""
        while not self._stop_flag:
            try:
                time.sleep(self._save_interval)

                if self._stop_flag:
                    break

                self._flush_and_save_buffer()

            except Exception as e:
                logger.error(f"DB 저장 루프 오류: {e}")

    def _flush_and_save_buffer(self):
        """버퍼의 데이터를 평균 계산하여 DB에 저장"""
        # 버퍼에서 데이터 추출 및 클리어
        with self._buffer_lock:
            if not self._data_buffer:
                return

            # 버퍼 복사 후 클리어
            buffers_to_process = dict(self._data_buffer)
            self._data_buffer = defaultdict(list)

        total_devices = len(buffers_to_process)
        total_samples = sum(len(v) for v in buffers_to_process.values())

        if total_samples == 0:
            return

        logger.info(f"평균 DB 저장 시작: {total_devices}개 장치, {total_samples}건 데이터")

        # 장치별 평균 계산 및 저장
        saved_count = 0

        for device_id, data_list in buffers_to_process.items():
            if not data_list:
                continue

            try:
                # 평균 데이터 계산
                averaged_data = self._calculate_average(device_id, data_list)

                if averaged_data:
                    # DB에 저장
                    self._save_averaged_to_db(averaged_data, data_list[0])
                    saved_count += 1

            except Exception as e:
                logger.error(f"장치 {device_id} 평균 저장 오류: {e}")

        logger.info(f"평균 DB 저장 완료: {saved_count}개 장치 저장됨")

    def _calculate_average(self, device_id: str, data_list: List[Dict]) -> Optional[Dict]:
        """장치별 센서 데이터의 평균 계산"""
        if not data_list:
            return None

        # 첫 번째 데이터에서 메타 정보 추출
        first_data = data_list[0]

        # 센서별 값 수집
        sensor_values: Dict[str, List[float]] = defaultdict(list)

        for item in data_list:
            for field in SENSOR_FIELDS:
                value = item.get(field)
                if value is not None:
                    try:
                        sensor_values[field].append(float(value))
                    except (ValueError, TypeError):
                        pass

        # 평균 계산
        averaged = {
            'device_id': device_id,
            'site_code': first_data.get('site_code', ''),
            'h_cd': first_data.get('h_cd', ''),
            's_cd': first_data.get('s_cd', ''),
            'dv_no': first_data.get('dv_no', ''),
            'sample_count': len(data_list),
        }

        # 각 센서별 평균값 계산
        for field, values in sensor_values.items():
            if values:
                avg_value = sum(values) / len(values)
                # 적절한 소수점 자리수로 반올림
                if field in ['co2', 'pm1', 'pm25', 'pm10']:
                    averaged[field] = round(avg_value)
                else:
                    averaged[field] = round(avg_value, 2)

        logger.debug(f"평균 계산 완료: {device_id} ({len(data_list)}건 → 평균)")

        return averaged

    def _save_averaged_to_db(self, averaged_data: Dict, first_raw: Dict):
        """평균 데이터를 DB에 저장"""
        try:
            db = get_db()

            # 현장 정보 생성/업데이트
            site = Site(
                site_code=averaged_data['site_code'],
                h_cd=averaged_data['h_cd'],
                s_cd=averaged_data['s_cd']
            )
            db.create_site(site)

            # 장치 정보 생성/업데이트
            device = Device(
                device_id=averaged_data['device_id'],
                site_code=averaged_data['site_code'],
                dv_no=averaged_data['dv_no']
            )
            db.create_device(device)

            # 환경 데이터 저장 (평균값)
            env_data = EnvironmentData(
                device_id=averaged_data['device_id'],
                site_code=averaged_data['site_code'],
                h_cd=averaged_data['h_cd'],
                s_cd=averaged_data['s_cd'],
                dv_no=averaged_data['dv_no'],
                o2=averaged_data.get('o2'),
                no2=averaged_data.get('no2'),
                co=averaged_data.get('co'),
                co2=averaged_data.get('co2'),
                h2s=averaged_data.get('h2s'),
                ch4=averaged_data.get('ch4'),
                ch2o=averaged_data.get('ch2o'),
                o3=averaged_data.get('o3'),
                voc=averaged_data.get('voc'),
                pm1=averaged_data.get('pm1'),
                pm25=averaged_data.get('pm25'),
                pm10=averaged_data.get('pm10'),
                temp=averaged_data.get('temp'),
                humi=averaged_data.get('humi'),
                check_time=first_raw.get('check_time'),
                raw_payload=f"averaged:{averaged_data.get('sample_count', 1)} samples",
                topic=first_raw.get('topic', ''),
                qos=first_raw.get('qos', 0)
            )
            db.save_environment_data(env_data)

            logger.debug(
                f"평균 데이터 DB 저장: {averaged_data['device_id']} "
                f"({averaged_data.get('sample_count', 1)}건 평균)"
            )

        except Exception as e:
            logger.error(f"평균 데이터 DB 저장 오류: {e}")

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
            # DB 저장 스레드 시작
            self._start_save_thread()
            logger.info("MQTT 클라이언트 시작됨")

    def stop(self):
        """MQTT 클라이언트 중지"""
        self._stop_flag = True

        # 저장 스레드 종료 대기
        if self._save_thread and self._save_thread.is_alive():
            self._save_thread.join(timeout=5)

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
            # 데이터 파싱 (환경 센서 또는 알람 자동 감지)
            parsed = parse_mqtt_data(payload, topic, qos)

            if parsed:
                # 데이터 타입에 따라 처리
                if isinstance(parsed, ParsedAlarmData):
                    # 알람 데이터는 즉시 저장
                    self._save_alarm_data(parsed, topic, payload)
                elif isinstance(parsed, ParsedEnvironmentData):
                    # 환경 센서 데이터: 버퍼에 추가 (평균 계산 후 저장)
                    self._buffer_environment_data(parsed, topic, qos)

                    # SocketIO로 실시간 전송 (UI 업데이트용)
                    if self.socketio:
                        self._emit_environment_data(parsed, topic)

            # 포워더로 데이터 전송 (활성화된 경우)
            if self.forwarder:
                parsed_dict = self._parsed_to_dict(parsed) if isinstance(parsed, ParsedEnvironmentData) else None
                self.forwarder.queue_data(topic, payload, qos, parsed_dict)

            # 외부 핸들러 호출
            for handler in self._message_handlers:
                try:
                    handler(topic, payload, qos)
                except Exception as e:
                    logger.error(f"메시지 핸들러 오류: {e}")

        except Exception as e:
            logger.error(f"메시지 처리 오류: {e}")
            self._log_mqtt_event('error', topic=topic, message=str(e))

    def _parsed_to_dict(self, parsed: ParsedEnvironmentData) -> Dict:
        """ParsedEnvironmentData를 딕셔너리로 변환"""
        return {
            'device_id': parsed.device_id,
            'site_code': parsed.site_code,
            'h_cd': parsed.h_cd,
            's_cd': parsed.s_cd,
            'dv_no': parsed.dv_no,
            'check_time': parsed.check_time,
            'o2': parsed.o2,
            'no2': parsed.no2,
            'co': parsed.co,
            'co2': parsed.co2,
            'h2s': parsed.h2s,
            'ch4': parsed.ch4,
            'ch2o': parsed.ch2o,
            'o3': parsed.o3,
            'voc': parsed.voc,
            'pm1': parsed.pm1,
            'pm25': parsed.pm25,
            'pm10': parsed.pm10,
            'temp': parsed.temp,
            'humi': parsed.humi,
        }

    def _buffer_environment_data(self, parsed: ParsedEnvironmentData, topic: str, qos: int):
        """환경 센서 데이터를 버퍼에 추가"""
        data = {
            'device_id': parsed.device_id,
            'site_code': parsed.site_code,
            'h_cd': parsed.h_cd,
            's_cd': parsed.s_cd,
            'dv_no': parsed.dv_no,
            'check_time': parsed.check_time,
            'topic': topic,
            'qos': qos,
            'o2': parsed.o2,
            'no2': parsed.no2,
            'co': parsed.co,
            'co2': parsed.co2,
            'h2s': parsed.h2s,
            'ch4': parsed.ch4,
            'ch2o': parsed.ch2o,
            'o3': parsed.o3,
            'voc': parsed.voc,
            'pm1': parsed.pm1,
            'pm25': parsed.pm25,
            'pm10': parsed.pm10,
            'temp': parsed.temp,
            'humi': parsed.humi,
        }

        with self._buffer_lock:
            self._data_buffer[parsed.device_id].append(data)
            buffer_count = sum(len(v) for v in self._data_buffer.values())

        logger.debug(f"버퍼 추가: {parsed.device_id} (총 버퍼: {buffer_count}건)")

    def _on_subscribe(self, client, userdata, mid, granted_qos):
        """구독 완료 콜백"""
        logger.debug(f"구독 완료 (mid={mid}, granted_qos={granted_qos})")

    def _on_publish(self, client, userdata, mid):
        """발행 완료 콜백"""
        logger.debug(f"발행 완료 (mid={mid})")

    # ===== 유틸리티 메소드 =====

    def _emit_environment_data(self, parsed: ParsedEnvironmentData, topic: str):
        """환경 데이터를 SocketIO로 전송"""
        if not self.socketio:
            return

        from datetime import datetime

        # 브라우저 dashboard.js가 기대하는 평면 구조로 전송
        sensor_data = {
            'device_id': parsed.device_id,
            'site_code': parsed.site_code,
            'h_cd': parsed.h_cd,
            's_cd': parsed.s_cd,
            'dv_no': parsed.dv_no,
            'check_time': parsed.check_time,
            'topic': topic,
            'received_at': datetime.now().isoformat(),
            # 센서 값들을 직접 포함 (dashboard.js에서 data.o2, data.co2 등으로 접근)
            'o2': parsed.o2,
            'no2': parsed.no2,
            'co': parsed.co,
            'co2': parsed.co2,
            'h2s': parsed.h2s,
            'ch4': parsed.ch4,
            'ch2o': parsed.ch2o,
            'o3': parsed.o3,
            'voc': parsed.voc,
            'pm1': parsed.pm1,
            'pm25': parsed.pm25,
            'pm10': parsed.pm10,
            'temp': parsed.temp,
            'humi': parsed.humi,
        }

        # 백그라운드 스레드에서 SocketIO emit을 위해 namespace 명시
        try:
            self.socketio.emit('environment_data', sensor_data, namespace='/')
            logger.debug(f"SocketIO 전송 완료: {parsed.device_id}")
        except Exception as e:
            logger.error(f"SocketIO emit 오류: {e}")

    def _save_alarm_data(
        self,
        parsed: ParsedAlarmData,
        topic: str,
        raw_payload: str
    ):
        """알람 데이터를 데이터베이스에 저장"""
        try:
            db = get_db()

            # 알람 로그 저장
            alarm_log = parsed.to_alarm_log()
            alarm_log.raw_payload = raw_payload
            db.save_alarm_log(alarm_log)

            logger.info(
                f"알람 데이터 저장: {parsed.device_id} "
                f"({parsed.sensor_type}: {parsed.value}, 레벨: {parsed.level})"
            )

            # SocketIO로 실시간 전송
            if self.socketio:
                self._emit_alarm_data(parsed, topic)

        except Exception as e:
            logger.error(f"알람 데이터 저장 오류: {e}")

    def _emit_alarm_data(self, parsed: ParsedAlarmData, topic: str):
        """알람 데이터를 SocketIO로 전송"""
        if not self.socketio:
            return

        # 알람 데이터 변환
        alarm_data = parsed.to_dict()
        alarm_data['timestamp'] = datetime.utcnow().isoformat() + 'Z'

        # 알람 이벤트 전송
        self.socketio.emit('alarm', alarm_data)

        logger.debug(f"알람 SocketIO 전송: {parsed.device_id}/{parsed.sensor_type}")

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
    from app.mqtt.forwarder import init_mqtt_forwarder

    config = get_config()

    client = get_mqtt_client()

    if socketio:
        client.set_socketio(socketio)

    # DB 저장 간격 설정
    client.set_save_interval(config.MQTT_DATA_SAVE_INTERVAL)

    # MQTT 포워더 초기화 (활성화된 경우)
    forwarder = init_mqtt_forwarder()
    if forwarder:
        client.set_forwarder(forwarder)
        logger.info("MQTT 포워딩 활성화됨")

    # 연결 및 구독
    client.start()
    client.subscribe(config.MQTT_SUBSCRIBE_TOPICS)

    return client
