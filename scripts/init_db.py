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

from app.models import init_db, get_db, Site, Device


def main():
    """데이터베이스 초기화 실행"""
    print("=" * 60)
    print("환경 센서 데이터베이스 초기화")
    print("=" * 60)
    print()

    # 테이블 생성
    init_db()
    print("[OK] 테이블 생성 완료")

    # 샘플 현장/장치 등록 (선택사항)
    db = get_db()

    # 샘플 현장 등록
    sample_sites = [
        Site(h_cd="H001", s_cd="S0001", name="지하공간 A동", description="A동 지하 환경 모니터링"),
        Site(h_cd="H001", s_cd="S0002", name="지하공간 B동", description="B동 지하 환경 모니터링"),
        Site(h_cd="H002", s_cd="S0001", name="밀폐공간 1구역", description="밀폐공간 1구역 모니터링"),
    ]

    print("\n현장 등록:")
    for site in sample_sites:
        try:
            db.create_site(site)
            print(f"  [OK] {site.h_cd}{site.s_cd} - {site.name}")
        except Exception as e:
            print(f"  [SKIP] {site.h_cd}{site.s_cd} ({e})")

    # 샘플 장치 등록
    sample_devices = [
        Device(device_no="DEV001", site_code="H001S0001", name="1층 기계실 센서", description="기계실 환경 모니터링"),
        Device(device_no="DEV002", site_code="H001S0001", name="2층 주차장 센서", description="지하주차장 환경 모니터링"),
        Device(device_no="DEV003", site_code="H001S0002", name="B동 창고 센서", description="창고 환경 모니터링"),
        Device(device_no="DEV004", site_code="H002S0001", name="밀폐공간 센서 A", description="밀폐공간 가스 모니터링"),
    ]

    print("\n장치 등록:")
    for device in sample_devices:
        try:
            db.create_device(device)
            print(f"  [OK] {device.device_no} - {device.name}")
        except Exception as e:
            print(f"  [SKIP] {device.device_no} ({e})")

    # 기본 알람 임계값 설정
    print("\n기본 알람 임계값 설정:")
    default_thresholds = [
        ('o2', 19.5, 23.5),        # 산소: 19.5% ~ 23.5%
        ('co', None, 25),          # 일산화탄소: 25ppm 이하
        ('co2', None, 1000),       # 이산화탄소: 1000ppm 이하
        ('h2s', None, 10),         # 황화수소: 10ppm 이하
        ('ch4', None, 10),         # 메탄: 10%LEL 이하
        ('no2', None, 5),          # 이산화질소: 5ppm 이하
        ('pm25', None, 35),        # PM2.5: 35ug/m3 이하
        ('pm10', None, 75),        # PM10: 75ug/m3 이하
    ]

    for sensor_type, min_val, max_val in default_thresholds:
        try:
            db.set_alarm_threshold(sensor_type, min_val, max_val)
            range_str = f"{min_val or '-'} ~ {max_val or '-'}"
            print(f"  [OK] {sensor_type}: {range_str}")
        except Exception as e:
            print(f"  [SKIP] {sensor_type} ({e})")

    print("\n" + "=" * 60)
    print("데이터베이스 초기화 완료!")
    print("=" * 60)

    # 상태 확인
    counts = db.get_data_count()
    print(f"\n테이블 현황:")
    for table, count in counts.items():
        print(f"  - {table}: {count}개")


if __name__ == '__main__':
    main()
