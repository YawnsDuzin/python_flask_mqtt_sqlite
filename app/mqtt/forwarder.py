"""
MQTT 포워더 모듈
수신한 MQTT 데이터를 다른 브로커로 전송합니다.
설정된 간격에 따라 장치별로 데이터를 버퍼링하고 평균값을 계산하여 전송합니다.
"""

import json
import logging
import threading
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
from collections import defaultdict

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

# 평균 계산 대상 센서 필드
SENSOR_FIELDS = [
    'o2', 'no2', 'co', 'co2', 'h2s', 'ch4', 'ch2o', 'o3',
    'voc', 'pm1', 'pm25', 'pm10', 'temp', 'humi'
]


class MQTTForwarder:
    """
    MQTT 데이터 포워더 클래스

    수신한 데이터를 버퍼에 저장하고, 설정된 간격마다
    두 번째 브로커로 전송합니다.
    """

    def __init__(
        self,
        host: str,
        port: int = 1883,
        client_id: str = 'flask_mqtt_forwarder',
        username: str = None,
        password: str = None,
        topic_prefix: str = 'forwarded',
        interval: int = 10
    ):
        """
        포워더 초기화

        Args:
            host: 포워딩 대상 브로커 호스트
            port: 브로커 포트
            client_id: 클라이언트 식별자
            username: 인증 사용자명 (선택)
            password: 인증 비밀번호 (선택)
            topic_prefix: 포워딩 토픽 접두사
            interval: 전송 간격 (초)
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.username = username
        self.password = password
        self.topic_prefix = topic_prefix
        self.interval = interval

        # MQTT 클라이언트 생성
        self.client = mqtt.Client(
            client_id=client_id,
            clean_session=True,
            protocol=mqtt.MQTTv311
        )

        # 콜백 설정
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish

        # 인증 설정
        if username and password:
            self.client.username_pw_set(username, password)

        # 상태 변수
        self.is_connected = False
        self._stop_flag = False
        self._reconnect_delay = 1
        self._max_reconnect_delay = 60

        # 장치별 데이터 버퍼 (스레드 안전)
        # 구조: {device_id: [parsed_data1, parsed_data2, ...]}
        self._device_buffers: Dict[str, List[Dict]] = defaultdict(list)
        self._buffer_lock = threading.Lock()

        # 전송 스레드
        self._forward_thread: Optional[threading.Thread] = None

        # 통계
        self._stats = {
            'total_forwarded': 0,
            'total_failed': 0,
            'total_averaged': 0,
            'last_forward_time': None
        }

        logger.info(f"MQTT 포워더 초기화: {host}:{port} (간격: {interval}초)")

    def connect(self) -> bool:
        """브로커에 연결"""
        try:
            logger.info(f"포워딩 브로커 연결 시도: {self.host}:{self.port}")
            self.client.connect(self.host, self.port, keepalive=60)
            return True
        except Exception as e:
            logger.error(f"포워딩 브로커 연결 실패: {e}")
            return False

    def disconnect(self):
        """브로커 연결 해제"""
        self._stop_flag = True
        self.client.disconnect()
        logger.info("포워딩 브로커 연결 해제")

    def start(self):
        """포워더 시작"""
        if self.connect():
            self.client.loop_start()
            self._start_forward_thread()
            logger.info("MQTT 포워더 시작됨")

    def stop(self):
        """포워더 중지"""
        self._stop_flag = True

        # 전송 스레드 종료 대기
        if self._forward_thread and self._forward_thread.is_alive():
            self._forward_thread.join(timeout=5)

        self.client.loop_stop()
        self.disconnect()
        logger.info("MQTT 포워더 중지됨")

    def queue_data(self, topic: str, payload: str, original_qos: int = 1, parsed_data: Dict = None):
        """
        데이터를 장치별 버퍼에 추가

        Args:
            topic: 원본 토픽
            payload: 원본 페이로드
            original_qos: 원본 QoS
            parsed_data: 파싱된 환경 데이터 (센서값 포함)
        """
        if not parsed_data:
            # JSON 파싱 시도
            try:
                parsed_data = json.loads(payload)
            except json.JSONDecodeError:
                logger.warning(f"JSON 파싱 실패, 포워딩 스킵: {topic}")
                return

        # device_id 추출 (파싱된 데이터에서)
        device_id = parsed_data.get('device_id')
        if not device_id:
            # hCd + sCd + dvNo로 device_id 생성
            h_cd = parsed_data.get('hCd') or parsed_data.get('h_cd', '')
            s_cd = parsed_data.get('sCd') or parsed_data.get('s_cd', '')
            dv_no = parsed_data.get('dvNo') or parsed_data.get('dv_no', '')
            device_id = f"{h_cd}{s_cd}_{dv_no}"

        data = {
            'device_id': device_id,
            'original_topic': topic,
            'payload': payload,
            'parsed_data': parsed_data,
            'original_qos': original_qos,
            'queued_at': datetime.utcnow().isoformat() + 'Z'
        }

        with self._buffer_lock:
            self._device_buffers[device_id].append(data)
            buffer_count = sum(len(v) for v in self._device_buffers.values())

        logger.debug(f"포워딩 큐 추가: {device_id} (총 버퍼: {buffer_count}건)")

    def _start_forward_thread(self):
        """전송 스레드 시작"""
        self._forward_thread = threading.Thread(
            target=self._forward_loop,
            daemon=True,
            name="mqtt-forwarder"
        )
        self._forward_thread.start()

    def _forward_loop(self):
        """주기적으로 버퍼의 데이터를 전송"""
        logger.info(f"포워딩 루프 시작 (간격: {self.interval}초)")

        while not self._stop_flag:
            try:
                time.sleep(self.interval)

                if self._stop_flag:
                    break

                self._flush_buffer()

            except Exception as e:
                logger.error(f"포워딩 루프 오류: {e}")

    def _flush_buffer(self):
        """장치별 버퍼의 데이터 평균을 계산하여 전송"""
        # 버퍼에서 데이터 추출 및 클리어
        with self._buffer_lock:
            if not self._device_buffers:
                return

            # 버퍼 복사 후 클리어
            buffers_to_process = dict(self._device_buffers)
            self._device_buffers = defaultdict(list)

        total_devices = len(buffers_to_process)
        total_samples = sum(len(v) for v in buffers_to_process.values())

        if total_samples == 0:
            return

        logger.info(f"평균 계산 시작: {total_devices}개 장치, {total_samples}건 데이터")

        # 장치별 평균 계산 및 전송
        success_count = 0
        fail_count = 0

        for device_id, data_list in buffers_to_process.items():
            if not data_list:
                continue

            # 평균 데이터 계산
            averaged_data = self._calculate_average(device_id, data_list)

            if averaged_data:
                # 포워딩 브로커로 전송
                if self.is_connected:
                    if self._forward_averaged(device_id, averaged_data, data_list[0]):
                        success_count += 1
                    else:
                        fail_count += 1
                else:
                    logger.warning("포워딩 브로커 미연결, MQTT 전송 스킵")

        # 통계 업데이트
        self._stats['total_forwarded'] += success_count
        self._stats['total_failed'] += fail_count
        self._stats['total_averaged'] += total_devices
        self._stats['last_forward_time'] = datetime.utcnow().isoformat() + 'Z'

        logger.info(f"평균 처리 완료: {total_devices}개 장치, 포워딩 성공 {success_count}건, 실패 {fail_count}건")

    def _calculate_average(self, device_id: str, data_list: List[Dict]) -> Optional[Dict]:
        """장치별 센서 데이터의 평균 계산"""
        if not data_list:
            return None

        # 첫 번째 데이터에서 메타 정보 추출
        first_data = data_list[0].get('parsed_data', {})

        # 센서별 값 수집
        sensor_values: Dict[str, List[float]] = defaultdict(list)

        for item in data_list:
            parsed = item.get('parsed_data', {})

            for field in SENSOR_FIELDS:
                # 다양한 키 이름 지원 (data1~data14 또는 직접 필드명)
                value = parsed.get(field)
                if value is not None:
                    try:
                        sensor_values[field].append(float(value))
                    except (ValueError, TypeError):
                        pass

        # 평균 계산
        averaged = {
            'device_id': device_id,
            'site_code': first_data.get('site_code') or f"{first_data.get('hCd', '')}{first_data.get('sCd', '')}",
            'h_cd': first_data.get('h_cd') or first_data.get('hCd', ''),
            's_cd': first_data.get('s_cd') or first_data.get('sCd', ''),
            'dv_no': first_data.get('dv_no') or first_data.get('dvNo', ''),
            'sample_count': len(data_list),
            'averaged_at': datetime.utcnow().isoformat() + 'Z',
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

    def _forward_averaged(self, device_id: str, averaged_data: Dict, original_data: Dict) -> bool:
        """평균 데이터를 포워딩 브로커로 전송"""
        try:
            original_topic = original_data.get('original_topic', '')

            # 토픽 변환: {prefix}/{original_topic}
            forward_topic = f"{self.topic_prefix}/{original_topic}"

            # 포워딩용 페이로드 구성
            forward_payload = {
                **averaged_data,
                '_forwarded': {
                    'original_topic': original_topic,
                    'sample_count': averaged_data.get('sample_count', 1),
                    'interval_seconds': self.interval,
                    'forwarded_at': datetime.utcnow().isoformat() + 'Z'
                }
            }

            result = self.client.publish(forward_topic, json.dumps(forward_payload), qos=1)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"평균 데이터 포워딩 성공: {forward_topic}")
                return True
            else:
                logger.error(f"평균 데이터 포워딩 실패: {forward_topic}, rc={result.rc}")
                return False

        except Exception as e:
            logger.error(f"평균 데이터 포워딩 오류: {e}")
            return False

    def _forward_single(self, data: Dict[str, Any]) -> bool:
        """단일 데이터 전송"""
        try:
            original_topic = data['original_topic']
            payload = data['payload']

            # 토픽 변환: {prefix}/{original_topic}
            forward_topic = f"{self.topic_prefix}/{original_topic}"

            # 페이로드에 메타데이터 추가
            try:
                payload_dict = json.loads(payload)
                payload_dict['_forwarded'] = {
                    'original_topic': original_topic,
                    'queued_at': data['queued_at'],
                    'forwarded_at': datetime.utcnow().isoformat() + 'Z'
                }
                forward_payload = json.dumps(payload_dict)
            except json.JSONDecodeError:
                # JSON이 아닌 경우 원본 그대로 전송
                forward_payload = payload

            result = self.client.publish(forward_topic, forward_payload, qos=1)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"포워딩 성공: {forward_topic}")
                return True
            else:
                logger.error(f"포워딩 실패: {forward_topic}, rc={result.rc}")
                return False

        except Exception as e:
            logger.error(f"포워딩 오류: {e}")
            return False

    # ===== 콜백 메소드 =====

    def _on_connect(self, client, userdata, flags, rc):
        """연결 완료 콜백"""
        if rc == 0:
            self.is_connected = True
            self._reconnect_delay = 1
            logger.info("포워딩 브로커 연결 성공")
        else:
            self.is_connected = False
            logger.error(f"포워딩 브로커 연결 실패: rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        """연결 해제 콜백"""
        self.is_connected = False

        if rc != 0 and not self._stop_flag:
            logger.warning(f"포워딩 브로커 연결 끊김 (rc={rc}), 재연결 시도...")
            self._schedule_reconnect()
        else:
            logger.info("포워딩 브로커 정상 종료")

    def _on_publish(self, client, userdata, mid):
        """발행 완료 콜백"""
        logger.debug(f"포워딩 발행 완료 (mid={mid})")

    def _schedule_reconnect(self):
        """재연결 스케줄링"""
        if self._stop_flag:
            return

        def reconnect():
            time.sleep(self._reconnect_delay)
            if not self._stop_flag and not self.is_connected:
                logger.info(f"포워딩 브로커 재연결 시도...")
                self.connect()
                self._reconnect_delay = min(
                    self._reconnect_delay * 2,
                    self._max_reconnect_delay
                )

        thread = threading.Thread(target=reconnect, daemon=True)
        thread.start()

    def get_status(self) -> Dict[str, Any]:
        """포워더 상태 반환"""
        with self._buffer_lock:
            device_count = len(self._device_buffers)
            buffer_size = sum(len(v) for v in self._device_buffers.values())

        return {
            'enabled': True,
            'connected': self.is_connected,
            'broker': f"{self.host}:{self.port}",
            'client_id': self.client_id,
            'topic_prefix': self.topic_prefix,
            'interval': self.interval,
            'device_count': device_count,
            'buffer_size': buffer_size,
            'stats': self._stats.copy()
        }


# 전역 포워더 인스턴스
_mqtt_forwarder: Optional[MQTTForwarder] = None


def get_mqtt_forwarder() -> Optional[MQTTForwarder]:
    """MQTT 포워더 인스턴스 반환 (비활성화 시 None)"""
    return _mqtt_forwarder


def init_mqtt_forwarder() -> Optional[MQTTForwarder]:
    """MQTT 포워더 초기화 및 시작"""
    global _mqtt_forwarder

    from app.config import get_config
    config = get_config()

    # 포워딩 비활성화 시 None 반환
    if not config.MQTT_FORWARD_ENABLED:
        logger.info("MQTT 포워딩 비활성화됨")
        return None

    # 호스트 미설정 시 경고
    if not config.MQTT_FORWARD_HOST:
        logger.warning("MQTT 포워딩 호스트 미설정, 포워딩 비활성화")
        return None

    _mqtt_forwarder = MQTTForwarder(
        host=config.MQTT_FORWARD_HOST,
        port=config.MQTT_FORWARD_PORT,
        client_id=config.MQTT_FORWARD_CLIENT_ID,
        username=config.MQTT_FORWARD_USERNAME or None,
        password=config.MQTT_FORWARD_PASSWORD or None,
        topic_prefix=config.MQTT_FORWARD_TOPIC_PREFIX,
        interval=config.MQTT_FORWARD_INTERVAL
    )

    _mqtt_forwarder.start()
    logger.info("MQTT 포워더 시작됨")

    return _mqtt_forwarder
