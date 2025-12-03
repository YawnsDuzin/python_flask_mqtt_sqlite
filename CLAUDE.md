# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Persona

당신은 **산업 안전 IoT 시스템 전문 개발자**입니다.

### 역할
- 지하/밀폐공간 환경 모니터링 시스템 개발 및 유지보수
- 14종 환경 센서(가스, 미세먼지, 온습도) 데이터 처리
- 실시간 알람 시스템 및 대시보드 구현

### 기술 전문성
- **Backend**: Python Flask, paho-mqtt, SQLite
- **Real-time**: MQTT 프로토콜, Flask-SocketIO
- **Frontend**: Jinja2 템플릿, JavaScript

### 도메인 지식
- 산업안전보건법 관련 밀폐공간 환경 기준
- 가스 센서 측정값 해석 (O2, CO, H2S, CH4 등)
- 알람 레벨별 대응 기준 (정상/주의/경고/위험)

### 커뮤니케이션
- 한국어로 응답
- 코드 주석 및 docstring은 한국어 사용
- 변수명/함수명은 영어, 설명은 한국어

---

## Project Overview

### 프로젝트 소개
지하/밀폐공간 작업자 안전을 위한 **환경 센서 모니터링 시스템**입니다.
현장에 설치된 복합 환경 센서에서 14종 데이터(가스 8종, 미세먼지 3종, 온습도, VOC)를
MQTT로 수신하여 저장하고, 실시간 대시보드와 알람 기능을 제공합니다.

### 주요 사용 사례
1. **실시간 모니터링**: 대시보드에서 모든 현장의 센서 데이터 실시간 확인
2. **위험 알람**: 가스 농도 이상 시 즉시 알람 발생 및 기록
3. **데이터 분석**: 과거 데이터 조회 및 통계 분석
4. **외부 연동**: MQTT 포워딩으로 상위 시스템에 데이터 전송

### 대상 사용자
- 밀폐공간 안전 관리자
- 현장 작업 감독관
- 안전 관리 시스템 운영자

---

## Tech Stack

| 구분 | 기술 | 용도 |
|------|------|------|
| Backend | Python 3.11+, Flask 3.x | 웹 서버, API |
| MQTT Client | paho-mqtt | 브로커 연결, 메시지 수신/발행 |
| MQTT Broker | Mosquitto | 메시지 중계 (Docker/로컬) |
| Database | SQLite3 | 센서 데이터, 알람 로그 저장 |
| Real-time | Flask-SocketIO | 브라우저 실시간 업데이트 |
| Frontend | Jinja2, JavaScript | 대시보드 UI |

---

## Development Commands

```bash
# 가상환경 활성화
cd python_flask_mqtt_sqlite
venv\Scripts\activate              # Windows
source venv/bin/activate           # Linux/Mac

# 의존성 설치
pip install -r requirements.txt

# 데이터베이스 초기화
python scripts/init_db.py

# 서버 실행 (http://localhost:5000)
python run.py

# 테스트 실행
pytest                             # 전체 테스트
pytest tests/test_database.py -v   # 특정 테스트
pytest --cov=app                   # 커버리지 포함

# 시뮬레이터 (개발/테스트용)
python scripts/mqtt_simulator.py --interval 2       # 환경 데이터
python scripts/mqtt_alarm_simulator.py --interval 5  # 알람 데이터
```

---

## Architecture

```
[환경 센서] → [MQTT Broker (Mosquitto:1883)] → [Flask App] → [SQLite]
                                                    ↓
                                           [SocketIO 실시간 대시보드]
                                                    ↓
                                           [MQTT Forwarder (선택)] → [외부 Broker]
```

### Core Modules

- **app/__init__.py**: Flask 앱 팩토리 - SocketIO, 블루프린트, MQTT 클라이언트 초기화
- **app/mqtt/client.py**: MQTT 클라이언트 - 브로커 연결, 토픽 구독(`+/U`, `+/W/+`), 자동 재연결(지수 백오프), 데이터 버퍼링/평균 계산
- **app/mqtt/forwarder.py**: MQTT 포워더 - 버퍼링 후 설정 간격으로 외부 브로커 전송
- **app/parsers/environment.py**: 환경 데이터 파서 - data1~data14 필드를 14종 센서값으로 변환
- **app/parsers/alarm.py**: 알람 파서 - 토픽에서 센서 타입 추출, 4단계 레벨 처리
- **app/models/database.py**: SQLite ORM - Site, Device, EnvironmentData, AlarmLog 데이터클래스
- **app/routes.py**: API 엔드포인트 및 웹 라우트 (main_bp, api_bp 블루프린트)

### Data Flow

1. **환경 데이터**: MQTT 수신 → 파싱 → 버퍼 추가 → SocketIO 실시간 전송 → 주기적 평균 계산 → DB 저장
2. **알람 데이터**: MQTT 수신 → 파싱 → 즉시 DB 저장 → SocketIO 알람 전송
3. **포워딩** (선택): 수신 데이터 → 버퍼 큐잉 → 설정 간격마다 외부 브로커로 발행

---

## Project Structure

```
python_flask_mqtt_sqlite/
├── app/                    # Flask 애플리케이션
│   ├── __init__.py         # 앱 팩토리, SocketIO 초기화
│   ├── config.py           # 환경 설정 관리
│   ├── routes.py           # 웹/API 라우트 (main_bp, api_bp)
│   ├── mqtt/               # MQTT 클라이언트 모듈
│   │   ├── client.py       # 연결, 구독, 버퍼링, 평균 계산
│   │   └── forwarder.py    # 외부 브로커 포워딩
│   ├── parsers/            # 데이터 파서
│   │   ├── environment.py  # 환경 센서 (data1~14 → 센서값)
│   │   └── alarm.py        # 알람 (토픽 파싱, 레벨 처리)
│   ├── models/             # 데이터베이스
│   │   └── database.py     # SQLite ORM, 데이터클래스
│   ├── templates/          # Jinja2 HTML 템플릿
│   └── static/             # CSS, JavaScript
├── scripts/                # 유틸리티 스크립트
│   ├── init_db.py          # DB 초기화
│   ├── mqtt_simulator.py   # 환경 데이터 시뮬레이터
│   └── mqtt_alarm_simulator.py  # 알람 시뮬레이터
├── tests/                  # pytest 테스트
├── mosquitto/              # Mosquitto 설정
├── docs/                   # 문서
└── run.py                  # 서버 실행 진입점
```

---

## API Reference

### 주요 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/health` | 시스템 상태 (MQTT 연결, DB 상태) |
| GET | `/api/sites` | 현장 목록 조회 |
| GET | `/api/sites/<site_code>` | 특정 현장 정보 조회 |
| GET | `/api/devices` | 장치 목록 조회 (?site= 필터 가능) |
| GET | `/api/devices/<device_id>` | 특정 장치 정보 조회 |
| GET | `/api/devices/<device_id>/data` | 장치 센서 데이터 (?limit=, ?start=, ?end=) |
| GET | `/api/data/latest` | 최신 환경 데이터 |
| GET | `/api/data/latest-by-device` | 장치별 최신 데이터 |
| GET | `/api/data/stats` | 전체 통계 데이터 |
| GET | `/api/alarms` | 알람 로그 (?level=, ?sensor=, ?acknowledged=) |
| GET | `/api/alarms/unacknowledged` | 미확인 알람 목록 |
| POST | `/api/alarms/<id>/acknowledge` | 알람 확인 처리 |
| POST | `/api/alarms/acknowledge-all` | 모든 미확인 알람 확인 |
| GET | `/api/mqtt/status` | MQTT 클라이언트 상태 |
| POST | `/api/mqtt/publish` | MQTT 메시지 발행 |

### API 응답 형식

```json
{
  "success": true,
  "timestamp": "2025-01-15T10:30:00Z",
  "data": { ... },
  "message": "optional message"
}
```

---

## SocketIO Events

| Event | 방향 | 설명 |
|-------|------|------|
| `environment_data` | Server → Client | 환경 센서 실시간 데이터 |
| `alarm` | Server → Client | 알람 발생 알림 |
| `connection_response` | Server → Client | 연결 상태 응답 |
| `subscribe_sensor` | Client → Server | 특정 센서 구독 요청 |
| `request_latest` | Client → Server | 최신 데이터 요청 |
| `latest_data` | Server → Client | 최신 데이터 응답 |

---

## MQTT Topic Structure

```
수신: {site_code}/U              # 환경 데이터 (예: H001S0001/U)
수신: {site_code}/W/{sensor}     # 알람 (예: H001S0001/W/CO)
포워딩: {prefix}/{original_topic} # 설정 시 (예: forwarded/H001S0001/U)
```

### 환경 데이터 페이로드 (토픽: {site_code}/U)

```json
{
  "hCd": "H001",
  "sCd": "S0001",
  "dvNo": "1",
  "data1": "20.9",
  "data2": "0.1",
  "...": "...",
  "data14": "10",
  "checkTime": "2025-01-15 10:30:00"
}
```

### 알람 데이터 페이로드 (토픽: {site_code}/W/{sensor})

```json
{
  "dvNo": "1",
  "value": "23.5",
  "level": "2",
  "etc": "",
  "time": "2025-01-15 10:30:00"
}
```

---

## Sensor Types (14종)

| Field | Sensor | Unit | JSON Key |
|-------|--------|------|----------|
| o2 | 산소 | % | data1 |
| no2 | 이산화질소 | ppm | data2 |
| co | 일산화탄소 | ppm | data3 |
| co2 | 이산화탄소 | ppm | data4 |
| h2s | 황화수소 | ppm | data5 |
| ch4 | 메탄 | %LEL | data6 |
| ch2o | 폼알데하이드 | ppm | data7 |
| o3 | 오존 | ppm | data8 |
| pm25 | PM2.5 | μg/m³ | data9 |
| pm10 | PM10 | μg/m³ | data10 |
| temp | 온도 | °C | data11 |
| humi | 습도 | % | data12 |
| voc | VOC | ppm | data13 |
| pm1 | PM1.0 | μg/m³ | data14 |

---

## Alarm Levels

| Level | Name | Description |
|-------|------|-------------|
| 0 | 정상 (Normal) | 정상 범위 |
| 1 | 주의 (Caution) | 주의 필요 |
| 2 | 경고 (Warning) | 경고 수준 |
| 3 | 위험 (Danger) | 즉시 대피 필요 |

---

## Key Environment Variables (.env)

```env
# MQTT 브로커 연결
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_SUBSCRIBE_TOPICS=+/U,+/W/+
MQTT_QOS=1
MQTT_KEEPALIVE=60
MQTT_CLIENT_ID=flask_mqtt_client

# 데이터 저장
DATABASE_PATH=instance/sensors.db
MQTT_DATA_SAVE_INTERVAL=10       # 평균값 DB 저장 간격 (초)

# MQTT 포워딩 (선택적)
MQTT_FORWARD_ENABLED=false
MQTT_FORWARD_HOST=192.168.1.100
MQTT_FORWARD_PORT=1883
MQTT_FORWARD_INTERVAL=10         # 포워딩 간격 (초)
MQTT_FORWARD_TOPIC_PREFIX=forwarded
```

---

## Code Conventions

- PEP 8 준수, black 포맷터
- 타입 힌트 필수
- Google 스타일 docstring
- logging 모듈 사용 (print 금지)

---

## Important Notes

- **MQTT 연결**: 재연결 시 지수 백오프(최대 60초), QoS 1 권장
- **SQLite**: 동시 쓰기 제한, `db.cleanup_old_data(days=30)` 정기 실행 권장
- **SocketIO 이벤트**: `environment_data`, `alarm` - eventlet 사용 시 monkey_patch 필요
- **데이터 ID 형식**: site_code=`H001S0001`, device_id=`H001S0001_1`
- **버퍼링**: 환경 데이터는 `MQTT_DATA_SAVE_INTERVAL` 간격으로 평균 계산 후 DB 저장
