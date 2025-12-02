#!/usr/bin/env python3
"""
데이터베이스 초기화 스크립트
테이블 생성 및 초기 데이터 설정을 수행합니다.
"""

import sys
import os

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.models import init_db, get_db, Sensor


def main():
    """데이터베이스 초기화 실행"""
    print("데이터베이스 초기화 시작...")

    # 테이블 생성
    init_db()
    print("✓ 테이블 생성 완료")

    # 샘플 센서 등록 (선택사항)
    db = get_db()

    sample_sensors = [
        Sensor(sensor_id="TEMP_001", sensor_type="temperature", location="서버실"),
        Sensor(sensor_id="TEMP_002", sensor_type="temperature", location="회의실"),
        Sensor(sensor_id="HUM_001", sensor_type="humidity", location="서버실"),
        Sensor(sensor_id="VIB_001", sensor_type="vibration", location="공장라인1"),
    ]

    for sensor in sample_sensors:
        try:
            db.create_sensor(sensor)
            print(f"✓ 센서 등록: {sensor.sensor_id}")
        except Exception as e:
            print(f"  센서 등록 건너뜀: {sensor.sensor_id} ({e})")

    print("\n데이터베이스 초기화 완료!")

    # 상태 확인
    counts = db.get_data_count()
    print(f"\n테이블 현황:")
    for table, count in counts.items():
        print(f"  - {table}: {count}개")


if __name__ == '__main__':
    main()
