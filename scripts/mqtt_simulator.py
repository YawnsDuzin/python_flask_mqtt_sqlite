#!/usr/bin/env python3
"""
MQTT 환경 센서 시뮬레이터
테스트용 가상 환경 센서 데이터를 MQTT로 발행합니다.

데이터 포맷:
{
    "hCd": "H001",
    "sCd": "S0001",
    "dvNo": "DEV001",
    "data1": 20.8,   # O2 (산소) %
    "data2": 0.02,   # NO2 (이산화질소) ppm
    "data3": 1.5,    # CO (일산화탄소) ppm
    "data4": 450,    # CO2 (이산화탄소) ppm
    "data5": 0.01,   # H2S (황화수소) ppm
    "data6": 5.0,    # CH4 (메탄) %LEL
    "data7": 0.05,   # CH2O (폼알데하이드) ppm
    "data8": 0.03,   # O3 (오존) ppm
    "data9": 25,     # PM2.5 ug/m3
    "data10": 45,    # PM10 ug/m3
    "data11": 23.5,  # Temperature C
    "data12": 55.0,  # Humidity %
    "data13": 0.1,   # VOC ppm
    "data14": 15     # PM1.0 ug/m3
}
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


class EnvironmentSensorSimulator:
    """환경 센서 시뮬레이터 클래스"""

    def __init__(self, broker_host='localhost', broker_port=1883):
        """시뮬레이터 초기화"""
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = mqtt.Client(client_id=f"env_simulator_{random.randint(1000, 9999)}")
        self.is_running = False

        # 가상 장치 정의
        self.devices = {
            'DEV001': {
                'h_cd': 'H001',
                's_cd': 'S0001',
                'location': '지하 1층 기계실'
            },
            'DEV002': {
                'h_cd': 'H001',
                's_cd': 'S0001',
                'location': '지하 2층 주차장'
            },
            'DEV003': {
                'h_cd': 'H002',
                's_cd': 'S0001',
                'location': '건물 A 지하실'
            }
        }

        # 센서 값 범위 정의
        self.sensor_ranges = {
            'data1': {'base': 20.8, 'variance': 0.5, 'min': 18.0, 'max': 23.0},    # O2
            'data2': {'base': 0.02, 'variance': 0.01, 'min': 0, 'max': 1.0},       # NO2
            'data3': {'base': 1.5, 'variance': 1.0, 'min': 0, 'max': 25},          # CO
            'data4': {'base': 450, 'variance': 100, 'min': 350, 'max': 1000},      # CO2
            'data5': {'base': 0.01, 'variance': 0.02, 'min': 0, 'max': 5},         # H2S
            'data6': {'base': 5.0, 'variance': 3.0, 'min': 0, 'max': 100},         # CH4
            'data7': {'base': 0.05, 'variance': 0.03, 'min': 0, 'max': 1.0},       # CH2O
            'data8': {'base': 0.03, 'variance': 0.02, 'min': 0, 'max': 0.2},       # O3
            'data9': {'base': 25, 'variance': 15, 'min': 0, 'max': 150},           # PM2.5
            'data10': {'base': 45, 'variance': 20, 'min': 0, 'max': 200},          # PM10
            'data11': {'base': 23.5, 'variance': 5.0, 'min': -10, 'max': 50},      # Temp
            'data12': {'base': 55.0, 'variance': 15.0, 'min': 0, 'max': 100},      # Humi
            'data13': {'base': 0.1, 'variance': 0.1, 'min': 0, 'max': 5.0},        # VOC
            'data14': {'base': 15, 'variance': 10, 'min': 0, 'max': 100},          # PM1
        }

    def connect(self):
        """브로커에 연결"""
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            print(f"[OK] MQTT 브로커 연결 성공: {self.broker_host}:{self.broker_port}")
            return True
        except Exception as e:
            print(f"[ERR] MQTT 브로커 연결 실패: {e}")
            return False

    def disconnect(self):
        """브로커 연결 해제"""
        self.client.disconnect()
        print("MQTT 연결 해제")

    def generate_sensor_value(self, sensor_key):
        """센서 값 생성"""
        config = self.sensor_ranges[sensor_key]
        base = config['base']
        variance = config['variance']

        # 랜덤 값 생성 (정규 분포)
        value = base + random.gauss(0, variance / 2)

        # 범위 제한
        value = max(config['min'], min(config['max'], value))

        # 적절한 소수점 자리수로 반올림
        if sensor_key in ['data4', 'data9', 'data10', 'data14']:  # 정수형
            return round(value)
        elif sensor_key in ['data1', 'data3', 'data6', 'data11', 'data12', 'data13']:  # 소수점 1자리
            return round(value, 1)
        else:  # 소수점 2자리
            return round(value, 2)

    def create_payload(self, device_id):
        """환경 센서 데이터 페이로드 생성"""
        device = self.devices[device_id]

        payload = {
            'hCd': device['h_cd'],
            'sCd': device['s_cd'],
            'dvNo': device_id
        }

        # 각 센서 데이터 생성
        for i in range(1, 15):
            key = f'data{i}'
            payload[key] = self.generate_sensor_value(key)

        return payload

    def get_topic(self, device_id):
        """MQTT 토픽 생성"""
        device = self.devices[device_id]
        site_code = device['h_cd'] + device['s_cd']
        return f"{site_code}/U"

    def publish_single(self, device_id):
        """단일 장치 데이터 발행"""
        if device_id not in self.devices:
            print(f"알 수 없는 장치: {device_id}")
            return False

        topic = self.get_topic(device_id)
        payload = self.create_payload(device_id)

        self.client.publish(topic, json.dumps(payload))

        # 요약 출력
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {device_id} -> {topic}")
        print(f"  O2: {payload['data1']}%, CO: {payload['data3']}ppm, "
              f"CO2: {payload['data4']}ppm, Temp: {payload['data11']}C, "
              f"Humi: {payload['data12']}%, PM2.5: {payload['data9']}ug/m3")

        return True

    def run(self, interval=2.0, duration=None, devices=None):
        """
        시뮬레이터 실행

        Args:
            interval: 발행 간격 (초)
            duration: 실행 시간 (초), None이면 무한
            devices: 발행할 장치 목록, None이면 전체
        """
        if not self.connect():
            return

        if devices is None:
            devices = list(self.devices.keys())

        self.is_running = True
        start_time = time.time()
        count = 0

        print(f"\n환경 센서 시뮬레이션 시작 (간격: {interval}초)")
        print(f"대상 장치: {', '.join(devices)}")
        print("Ctrl+C로 중지\n")
        print("-" * 70)

        try:
            while self.is_running:
                for device_id in devices:
                    if device_id in self.devices:
                        self.publish_single(device_id)
                        count += 1

                print("-" * 70)

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
    parser = argparse.ArgumentParser(description='MQTT 환경 센서 시뮬레이터')
    parser.add_argument('--host', default=os.getenv('MQTT_BROKER_HOST', 'localhost'),
                       help='MQTT 브로커 호스트')
    parser.add_argument('--port', type=int, default=int(os.getenv('MQTT_BROKER_PORT', 1883)),
                       help='MQTT 브로커 포트')
    parser.add_argument('--interval', type=float, default=5.0, help='발행 간격 (초)')
    parser.add_argument('--duration', type=int, default=None, help='실행 시간 (초)')
    parser.add_argument('--devices', nargs='+', default=None,
                       help='발행할 장치 ID 목록 (예: DEV001 DEV002)')

    args = parser.parse_args()

    print("=" * 70)
    print("MQTT 환경 센서 시뮬레이터")
    print("=" * 70)
    print(f"브로커: {args.host}:{args.port}")
    print(f"발행 간격: {args.interval}초")
    print()

    simulator = EnvironmentSensorSimulator(args.host, args.port)
    simulator.run(
        interval=args.interval,
        duration=args.duration,
        devices=args.devices
    )


if __name__ == '__main__':
    main()
