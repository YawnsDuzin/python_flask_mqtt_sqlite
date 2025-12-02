#!/usr/bin/env python3
"""
MQTT 센서 시뮬레이터
테스트용 가상 센서 데이터를 MQTT로 발행합니다.
"""

import sys
import os
import json
import time
import random
import argparse
from datetime import datetime

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import paho.mqtt.client as mqtt


class SensorSimulator:
    """센서 시뮬레이터 클래스"""

    def __init__(self, broker_host='localhost', broker_port=1883):
        """시뮬레이터 초기화"""
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = mqtt.Client(client_id=f"simulator_{random.randint(1000, 9999)}")
        self.is_running = False

        # 센서 정의
        self.sensors = {
            'TEMP_001': {
                'type': 'temperature',
                'base_value': 25.0,
                'variance': 5.0,
                'unit': 'celsius',
                'topic': 'sensors/temperature/TEMP_001'
            },
            'TEMP_002': {
                'type': 'temperature',
                'base_value': 22.0,
                'variance': 3.0,
                'unit': 'celsius',
                'topic': 'sensors/temperature/TEMP_002'
            },
            'HUM_001': {
                'type': 'humidity',
                'base_value': 45.0,
                'variance': 15.0,
                'unit': 'percent',
                'topic': 'sensors/humidity/HUM_001'
            },
            'VIB_001': {
                'type': 'vibration',
                'base_value': 2.0,
                'variance': 3.0,
                'unit': 'mm/s',
                'topic': 'sensors/vibration/VIB_001'
            }
        }

    def connect(self):
        """브로커에 연결"""
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            print(f"✓ MQTT 브로커 연결 성공: {self.broker_host}:{self.broker_port}")
            return True
        except Exception as e:
            print(f"✗ MQTT 브로커 연결 실패: {e}")
            return False

    def disconnect(self):
        """브로커 연결 해제"""
        self.client.disconnect()
        print("MQTT 연결 해제")

    def generate_value(self, sensor_id):
        """센서 값 생성"""
        sensor = self.sensors[sensor_id]
        base = sensor['base_value']
        variance = sensor['variance']

        # 랜덤 값 생성 (정규 분포)
        value = base + random.gauss(0, variance / 3)

        # 범위 제한
        if sensor['type'] == 'humidity':
            value = max(0, min(100, value))
        elif sensor['type'] == 'vibration':
            value = max(0, value)

        return round(value, 2)

    def create_payload(self, sensor_id):
        """센서 데이터 페이로드 생성"""
        sensor = self.sensors[sensor_id]
        value = self.generate_value(sensor_id)

        payload = {
            'sensor_id': sensor_id,
            'type': sensor['type'],
            'value': value,
            'unit': sensor['unit'],
            'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        }

        return payload

    def publish_single(self, sensor_id):
        """단일 센서 데이터 발행"""
        if sensor_id not in self.sensors:
            print(f"알 수 없는 센서: {sensor_id}")
            return False

        sensor = self.sensors[sensor_id]
        payload = self.create_payload(sensor_id)

        self.client.publish(sensor['topic'], json.dumps(payload))
        print(f"[{payload['timestamp']}] {sensor_id}: {payload['value']} {payload['unit']}")

        return True

    def run(self, interval=2.0, duration=None, sensors=None):
        """
        시뮬레이터 실행

        Args:
            interval: 발행 간격 (초)
            duration: 실행 시간 (초), None이면 무한
            sensors: 발행할 센서 목록, None이면 전체
        """
        if not self.connect():
            return

        if sensors is None:
            sensors = list(self.sensors.keys())

        self.is_running = True
        start_time = time.time()
        count = 0

        print(f"\n센서 시뮬레이션 시작 (간격: {interval}초)")
        print(f"대상 센서: {', '.join(sensors)}")
        print("Ctrl+C로 중지\n")
        print("-" * 60)

        try:
            while self.is_running:
                for sensor_id in sensors:
                    if sensor_id in self.sensors:
                        self.publish_single(sensor_id)
                        count += 1

                # 종료 조건 확인
                if duration and (time.time() - start_time) >= duration:
                    break

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n\n시뮬레이션 중지됨")

        finally:
            self.is_running = False
            self.disconnect()
            elapsed = time.time() - start_time
            print(f"\n총 {count}개 메시지 발행 ({elapsed:.1f}초)")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='MQTT 센서 시뮬레이터')
    parser.add_argument('--host', default='localhost', help='MQTT 브로커 호스트')
    parser.add_argument('--port', type=int, default=1883, help='MQTT 브로커 포트')
    parser.add_argument('--interval', type=float, default=2.0, help='발행 간격 (초)')
    parser.add_argument('--duration', type=int, default=None, help='실행 시간 (초)')
    parser.add_argument('--sensors', nargs='+', default=None, help='발행할 센서 ID 목록')

    args = parser.parse_args()

    simulator = SensorSimulator(args.host, args.port)
    simulator.run(
        interval=args.interval,
        duration=args.duration,
        sensors=args.sensors
    )


if __name__ == '__main__':
    main()
