# MQTT 멀티센서 데이터 수집/중계 웹 시스템

Python Flask 기반의 MQTT 센서 데이터 수집 및 중계 웹 애플리케이션입니다.
IoT 센서에서 발행되는 데이터를 MQTT 브로커를 통해 수신하고, 파싱 후 SQLite에 저장하며,
가공된 데이터를 다시 MQTT로 발행하는 시스템입니다.

## 시스템 구조

```
[IoT 센서들] → [MQTT Broker] → [Flask App] → [SQLite DB]
                    ↑                ↓
              [가공 데이터 재발행] ← [데이터 파싱/처리]
```

## 주요 기능

- **MQTT 수신**: 다중 토픽 구독, QoS 설정, 자동 재연결
- **데이터 파싱**: 센서 타입별 파서 (온도, 습도, 진동)
- **데이터 저장**: SQLite 데이터베이스, 자동 인덱싱
- **MQTT 발행**: 가공/집계 데이터 재발행
- **웹 대시보드**: 실시간 모니터링, Socket.IO 기반

## 기술 스택

- **Backend**: Python 3.11+, Flask
- **MQTT Client**: paho-mqtt
- **Database**: SQLite3
- **Real-time**: Flask-SocketIO
- **MQTT Broker**: Mosquitto

## 프로젝트 구조

```
python_flask_mqtt_sqlite/
├── app/                    # Flask 애플리케이션
│   ├── __init__.py         # 앱 팩토리
│   ├── config.py           # 설정 관리
│   ├── routes.py           # API 및 웹 라우트
│   ├── mqtt/               # MQTT 클라이언트 모듈
│   ├── parsers/            # 데이터 파서 모듈
│   ├── models/             # 데이터베이스 모델
│   ├── templates/          # HTML 템플릿
│   └── static/             # CSS, JavaScript
├── docs/                   # 문서
├── tests/                  # 테스트
├── scripts/                # 유틸리티 스크립트
├── mosquitto/              # Mosquitto 설정
├── requirements.txt        # 의존성
├── docker-compose.yml      # Docker Compose
└── run.py                  # 실행 스크립트
```

## 설치 및 실행

### 1. 요구사항

- Python 3.11 이상
- Mosquitto MQTT 브로커 (또는 Docker)

### 2. 설치

```bash
# 저장소 클론
git clone <repository-url>
cd python_flask_mqtt_sqlite

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 3. 환경 설정

```bash
# .env 파일 복사 및 수정
cp .env.example .env

# .env 파일 편집
# MQTT_BROKER_HOST, MQTT_BROKER_PORT 등 설정
```

### 4. MQTT 브로커 실행

**옵션 A: Docker Compose 사용 (권장)**
```bash
docker-compose up -d
```

**옵션 B: 로컬 Mosquitto**
```bash
# 설치 (Ubuntu)
sudo apt install mosquitto mosquitto-clients

# 시작
sudo systemctl start mosquitto
```

### 5. 데이터베이스 초기화

```bash
python scripts/init_db.py
```

### 6. 애플리케이션 실행

```bash
python run.py
```

서버가 http://localhost:5000 에서 실행됩니다.

### 7. 테스트 데이터 생성 (선택)

```bash
# 센서 시뮬레이터 실행 (별도 터미널)
python scripts/mqtt_simulator.py --interval 2
```

## API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/health` | 시스템 상태 확인 |
| GET | `/api/sensors` | 센서 목록 조회 |
| GET | `/api/sensors/<id>` | 센서 정보 조회 |
| GET | `/api/sensors/<id>/data` | 센서 데이터 조회 |
| GET | `/api/data/latest` | 최신 데이터 조회 |
| GET | `/api/data/stats` | 통계 데이터 조회 |
| GET | `/api/mqtt/status` | MQTT 상태 조회 |
| POST | `/api/mqtt/publish` | MQTT 메시지 발행 |

## MQTT 토픽 구조

### 수신 토픽 (Subscribe)
```
sensors/{sensor_type}/{sensor_id}
예: sensors/temperature/TEMP_001
    sensors/humidity/HUM_001
    sensors/vibration/VIB_001
```

### 발행 토픽 (Publish)
```
processed/{sensor_id}/{metric_type}
예: processed/TEMP_001/average
    processed/TEMP_001/status
```

## 센서 데이터 형식

```json
{
  "sensor_id": "TEMP_001",
  "type": "temperature",
  "value": 23.5,
  "unit": "celsius",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

## 테스트 실행

```bash
# 모든 테스트 실행
pytest

# 커버리지 포함
pytest --cov=app --cov-report=html
```

## 배포

### Raspberry Pi 배포

1. 라즈베리파이에 코드 복사
2. 의존성 설치
3. Mosquitto 설치 및 설정
4. systemd 서비스 등록

```bash
# /etc/systemd/system/mqtt-sensor.service
[Unit]
Description=MQTT Sensor Monitoring
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/mqtt-sensor
ExecStart=/home/pi/mqtt-sensor/venv/bin/python run.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## 문서

- [MQTT 개념 설명서](docs/01_MQTT_개념설명서.md)
- [Mosquitto 설치 가이드](docs/02_Mosquitto_설치가이드.md)
- [시스템 설계 문서](docs/03_시스템설계문서.md)

## 라이선스

MIT License
