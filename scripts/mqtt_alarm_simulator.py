#!/usr/bin/env python3
"""
MQTT 알람 시뮬레이터
테스트용 가상 센서 알람 데이터를 MQTT로 발행합니다.

토픽 형식: {site_code}/W/{sensor}
예: H001S0001/W/O2, H001S0001/W/CO

데이터 포맷:
{
    "dvNo": "DEV001",
    "value": "23.5",
    "level": "2",
    "etc": "테스트 알람",
    "time": "2025-01-15 10:30:00"
}

알람 레벨:
  0: 정상 (Normal)
  1: 주의 (Caution)
  2: 경고 (Warning)
  3: 위험 (Danger)
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


# 알람 레벨 정의
ALARM_LEVELS = {
    0: {'name': '정상', 'name_en': 'Normal', 'color': '#28a745'},
    1: {'name': '주의', 'name_en': 'Caution', 'color': '#ffc107'},
    2: {'name': '경고', 'name_en': 'Warning', 'color': '#fd7e14'},
    3: {'name': '위험', 'name_en': 'Danger', 'color': '#dc3545'},
}

# 센서별 알람 임계값 및 정보
ALARM_SENSOR_CONFIG = {
    'O2': {
        'name': '산소',
        'unit': '%',
        'normal_range': (19.5, 23.5),
        'caution': {'low': 19.5, 'high': None},
        'warning': {'low': 18.0, 'high': None},
        'danger': {'low': 16.0, 'high': None},
    },
    'CO': {
        'name': '일산화탄소',
        'unit': 'ppm',
        'normal_range': (0, 25),
        'caution': {'low': None, 'high': 25},
        'warning': {'low': None, 'high': 50},
        'danger': {'low': None, 'high': 100},
    },
    'CO2': {
        'name': '이산화탄소',
        'unit': 'ppm',
        'normal_range': (350, 1000),
        'caution': {'low': None, 'high': 1000},
        'warning': {'low': None, 'high': 2000},
        'danger': {'low': None, 'high': 5000},
    },
    'H2S': {
        'name': '황화수소',
        'unit': 'ppm',
        'normal_range': (0, 10),
        'caution': {'low': None, 'high': 10},
        'warning': {'low': None, 'high': 15},
        'danger': {'low': None, 'high': 20},
    },
    'CH4': {
        'name': '메탄',
        'unit': '%LEL',
        'normal_range': (0, 10),
        'caution': {'low': None, 'high': 10},
        'warning': {'low': None, 'high': 25},
        'danger': {'low': None, 'high': 50},
    },
    'NO2': {
        'name': '이산화질소',
        'unit': 'ppm',
        'normal_range': (0, 1),
        'caution': {'low': None, 'high': 1},
        'warning': {'low': None, 'high': 3},
        'danger': {'low': None, 'high': 5},
    },
}


class AlarmSimulator:
    """알람 시뮬레이터 클래스"""

    def __init__(self, broker_host='localhost', broker_port=1883):
        """시뮬레이터 초기화"""
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = mqtt.Client(client_id=f"alarm_simulator_{random.randint(1000, 9999)}")
        self.is_running = False

        # 가상 장치/현장 정의
        self.sites = {
            'H001S0001': {
                'name': '본사 지하 1층',
                'devices': ['1', '2']
            },
            'H002S0001': {
                'name': '건물 A 지하실',
                'devices': ['3']
            }
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

    def generate_alarm_value(self, sensor_type: str, level: int) -> float:
        """알람 레벨에 맞는 센서 값 생성"""
        config = ALARM_SENSOR_CONFIG.get(sensor_type, {})

        if level == 0:  # 정상
            low, high = config.get('normal_range', (0, 100))
            return round(random.uniform(low, high), 2)

        # 알람 임계값 기준으로 값 생성
        threshold_key = {1: 'caution', 2: 'warning', 3: 'danger'}.get(level, 'warning')
        threshold = config.get(threshold_key, {})

        if threshold.get('high'):
            # 상한 초과 알람 (CO, CO2, H2S 등)
            base = threshold['high']
            return round(base + random.uniform(0, base * 0.3), 2)
        elif threshold.get('low'):
            # 하한 미달 알람 (O2)
            base = threshold['low']
            return round(base - random.uniform(0, base * 0.1), 2)

        return round(random.uniform(0, 100), 2)

    def create_alarm_payload(self, device_id: str, sensor_type: str, level: int, etc: str = '') -> dict:
        """알람 페이로드 생성"""
        value = self.generate_alarm_value(sensor_type, level)

        return {
            'dvNo': device_id,
            'value': str(value),
            'level': str(level),
            'etc': etc,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def get_alarm_topic(self, site_code: str, sensor_type: str) -> str:
        """알람 토픽 생성"""
        return f"{site_code}/W/{sensor_type}"

    def publish_alarm(self, site_code: str, device_id: str, sensor_type: str, level: int, etc: str = ''):
        """알람 발행"""
        topic = self.get_alarm_topic(site_code, sensor_type)
        payload = self.create_alarm_payload(device_id, sensor_type, level, etc)

        self.client.publish(topic, json.dumps(payload))

        # 출력
        level_info = ALARM_LEVELS.get(level, {})
        sensor_config = ALARM_SENSOR_CONFIG.get(sensor_type, {})
        timestamp = datetime.now().strftime('%H:%M:%S')

        level_name = level_info.get('name', '알 수 없음')
        sensor_name = sensor_config.get('name', sensor_type)
        unit = sensor_config.get('unit', '')

        print(f"[{timestamp}] 알람 발행: {topic}")
        print(f"  장치: {device_id}, 센서: {sensor_name}({sensor_type})")
        print(f"  값: {payload['value']}{unit}, 레벨: {level}({level_name})")
        if etc:
            print(f"  메시지: {etc}")

        return True

    def publish_random_alarm(self):
        """랜덤 알람 발행"""
        # 랜덤 현장 선택
        site_code = random.choice(list(self.sites.keys()))
        site_info = self.sites[site_code]

        # 랜덤 장치 선택
        device_id = random.choice(site_info['devices'])

        # 랜덤 센서 선택
        sensor_type = random.choice(list(ALARM_SENSOR_CONFIG.keys()))

        # 랜덤 레벨 (정상은 제외하고 1~3만)
        level = random.choices([1, 2, 3], weights=[50, 35, 15])[0]

        # 알람 메시지
        messages = [
            '센서 임계값 초과',
            '점검 필요',
            '환기 시스템 확인 요망',
            '작업자 대피 필요',
            '긴급 점검 요청',
            ''
        ]
        etc = random.choice(messages)

        return self.publish_alarm(site_code, device_id, sensor_type, level, etc)

    def run_random(self, interval=10.0, duration=None):
        """랜덤 알람 시뮬레이션 실행"""
        if not self.connect():
            return

        self.is_running = True
        start_time = time.time()
        count = 0

        print(f"\n알람 시뮬레이션 시작 (간격: {interval}초)")
        print("Ctrl+C로 중지\n")
        print("-" * 70)

        try:
            while self.is_running:
                self.publish_random_alarm()
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
            print(f"\n총 {count}개 알람 발행 ({elapsed:.1f}초)")

    def run_specific(self, site_code: str, device_id: str, sensor_type: str, level: int, etc: str = ''):
        """특정 알람 1회 발행"""
        if not self.connect():
            return

        print("\n특정 알람 발행")
        print("-" * 70)

        self.publish_alarm(site_code, device_id, sensor_type, level, etc)

        print("-" * 70)
        self.disconnect()

    def run_sequence(self, interval=3.0):
        """알람 시퀀스 테스트 (정상 → 주의 → 경고 → 위험 → 정상)"""
        if not self.connect():
            return

        site_code = 'H001S0001'
        device_id = 'DEV001'
        sensor_type = 'CO'

        print(f"\n알람 시퀀스 테스트 시작")
        print(f"현장: {site_code}, 장치: {device_id}, 센서: {sensor_type}")
        print(f"시퀀스: 정상(0) → 주의(1) → 경고(2) → 위험(3) → 정상(0)")
        print("-" * 70)

        sequence = [
            (0, '정상 상태'),
            (1, '주의 단계 진입'),
            (2, '경고 단계 상승'),
            (3, '위험! 즉시 대피'),
            (0, '정상 복귀'),
        ]

        try:
            for level, etc in sequence:
                self.publish_alarm(site_code, device_id, sensor_type, level, etc)
                print("-" * 70)
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n시퀀스 중단됨")

        finally:
            self.disconnect()
            print("\n시퀀스 테스트 완료")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description='MQTT 알람 시뮬레이터',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 랜덤 알람 발행 (10초 간격)
  python mqtt_alarm_simulator.py --mode random --interval 10

  # 특정 알람 1회 발행
  python mqtt_alarm_simulator.py --mode single --site H001S0001 --device DEV001 --sensor CO --level 2

  # 알람 레벨 시퀀스 테스트
  python mqtt_alarm_simulator.py --mode sequence

알람 레벨:
  0: 정상 (Normal)
  1: 주의 (Caution)
  2: 경고 (Warning)
  3: 위험 (Danger)

지원 센서:
  O2, CO, CO2, H2S, CH4, NO2
        """
    )

    parser.add_argument('--host', default=os.getenv('MQTT_BROKER_HOST', 'localhost'),
                       help='MQTT 브로커 호스트')
    parser.add_argument('--port', type=int, default=int(os.getenv('MQTT_BROKER_PORT', 1883)),
                       help='MQTT 브로커 포트')
    parser.add_argument('--mode', choices=['random', 'single', 'sequence'], default='random',
                       help='실행 모드 (random: 랜덤 알람, single: 단일 알람, sequence: 시퀀스)')
    parser.add_argument('--interval', type=float, default=10.0, help='발행 간격 (초)')
    parser.add_argument('--duration', type=int, default=None, help='실행 시간 (초)')

    # 단일 알람 모드용 옵션
    parser.add_argument('--site', default='H001S0001', help='현장 코드')
    parser.add_argument('--device', default='DEV001', help='장치 ID')
    parser.add_argument('--sensor', default='CO', choices=list(ALARM_SENSOR_CONFIG.keys()),
                       help='센서 타입')
    parser.add_argument('--level', type=int, default=2, choices=[0, 1, 2, 3],
                       help='알람 레벨 (0:정상, 1:주의, 2:경고, 3:위험)')
    parser.add_argument('--message', default='', help='알람 메시지')

    args = parser.parse_args()

    print("=" * 70)
    print("MQTT 알람 시뮬레이터")
    print("=" * 70)
    print(f"브로커: {args.host}:{args.port}")
    print(f"모드: {args.mode}")

    simulator = AlarmSimulator(args.host, args.port)

    if args.mode == 'random':
        print(f"발행 간격: {args.interval}초")
        simulator.run_random(
            interval=args.interval,
            duration=args.duration
        )
    elif args.mode == 'single':
        print(f"현장: {args.site}, 장치: {args.device}")
        print(f"센서: {args.sensor}, 레벨: {args.level}")
        simulator.run_specific(
            site_code=args.site,
            device_id=args.device,
            sensor_type=args.sensor,
            level=args.level,
            etc=args.message
        )
    elif args.mode == 'sequence':
        simulator.run_sequence(interval=args.interval)


if __name__ == '__main__':
    main()
