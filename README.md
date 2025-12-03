# 지하/밀폐공간 환경 센서 MQTT 모니터링 시스템

Python Flask 기반의 **지하 및 밀폐공간 환경 센서** 데이터 수집 및 모니터링 웹 애플리케이션입니다.
가스 센서, 미세먼지 센서, 온습도 센서 등 **14종 환경 센서** 데이터를 MQTT 브로커를 통해 수신하고,
파싱 후 SQLite에 저장하며, 실시간 대시보드와 알람 관리 기능을 제공합니다.

## 시스템 구조

```
[환경 센서들] → [MQTT Broker] → [Flask App] → [SQLite DB]
                    ↑                ↓
              [포워딩 브로커] ← [실시간 대시보드/알람]
```

## 주요 기능

- **MQTT 수신**: 다중 토픽 구독 (`{site_code}/U`, `{site_code}/W/{sensor}`), QoS 설정, 자동 재연결
- **14종 센서 지원**: O2, NO2, CO, CO2, H2S, CH4, CH2O, O3, PM1, PM2.5, PM10, 온도, 습도, VOC
- **데이터 저장**: SQLite 데이터베이스, 현장/장치 관리
- **알람 관리**: 센서별 임계값 설정, 4단계 알람 레벨
- **MQTT 포워딩**: 수신 데이터를 다른 브로커로 전송 (설정 가능)
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
│   │   ├── client.py       # MQTT 클라이언트
│   │   └── forwarder.py    # MQTT 포워더
│   ├── parsers/            # 데이터 파서 모듈
│   │   ├── environment.py  # 환경 센서 파서
│   │   └── alarm.py        # 알람 파서
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
| GET | `/api/sites` | 현장 목록 조회 |
| GET | `/api/devices` | 장치 목록 조회 |
| GET | `/api/devices/<device_id>` | 장치 상세 조회 |
| GET | `/api/devices/<device_id>/data` | 장치 센서 데이터 조회 |
| GET | `/api/data/latest` | 최신 데이터 조회 |
| GET | `/api/data/latest-by-device` | 장치별 최신 데이터 |
| GET | `/api/data/stats` | 통계 데이터 조회 |
| GET | `/api/alarms` | 알람 로그 조회 |
| GET | `/api/alarms/unacknowledged` | 미확인 알람 조회 |
| POST | `/api/alarms/<id>/acknowledge` | 알람 확인 처리 |
| GET | `/api/mqtt/status` | MQTT 상태 조회 |
| POST | `/api/mqtt/publish` | MQTT 메시지 발행 |

## MQTT 토픽 구조

### 수신 토픽 (Subscribe)
```
{site_code}/U           # 환경 데이터
{site_code}/W/{sensor}  # 알람 데이터

예: H001S0001/U         # H001S0001 현장 환경 데이터
    H001S0001/W/O2      # 산소 알람
    H001S0001/W/CO      # 일산화탄소 알람
```

### 포워딩 토픽 (Publish - 포워딩 활성화 시)
```
{prefix}/{original_topic}
예: forwarded/H001S0001/U
```

## 센서 데이터 형식

### 환경 데이터 (토픽: {site_code}/U)
```json
{
  "hCd": "H001",
  "sCd": "S0001",
  "dvNo": "1",
  "data1": "20.9",   // O2 (%)
  "data2": "0.1",    // NO2 (ppm)
  "data3": "5.0",    // CO (ppm)
  "data4": "450",    // CO2 (ppm)
  "data5": "0.5",    // H2S (ppm)
  "data6": "0.0",    // CH4 (%LEL)
  "data7": "0.02",   // CH2O (ppm)
  "data8": "0.03",   // O3 (ppm)
  "data9": "15",     // PM2.5 (μg/m³)
  "data10": "25",    // PM10 (μg/m³)
  "data11": "25.5",  // 온도 (°C)
  "data12": "60",    // 습도 (%)
  "data13": "0.1",   // VOC (ppm)
  "data14": "10",    // PM1 (μg/m³)
  "checkTime": "2025-01-15 10:30:00"
}
```

### 알람 데이터 (토픽: {site_code}/W/{sensor})
```json
{
  "dvNo": "1",
  "value": "23.5",
  "level": "2",      // 0:정상, 1:주의, 2:경고, 3:위험
  "etc": "",
  "time": "2025-01-15 10:30:00"
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
