# Mosquitto MQTT 브로커 설치 및 설정 가이드

## 1. Mosquitto 소개

Eclipse Mosquitto는 MQTT 프로토콜 버전 3.1, 3.1.1, 5.0을 지원하는
오픈소스 메시지 브로커입니다. 가볍고 설치가 쉬워 개발 및 프로덕션 환경에서
널리 사용됩니다.

---

## 2. Windows 설치

### 2.1 다운로드 설치 (권장)

1. **다운로드**
   - https://mosquitto.org/download/ 접속
   - Windows 64-bit 또는 32-bit 설치파일 다운로드

2. **설치**
   ```
   - mosquitto-2.x.x-install-windows-x64.exe 실행
   - 설치 경로: C:\Program Files\mosquitto (기본값)
   - "Service" 옵션 체크하면 Windows 서비스로 등록
   ```

3. **환경 변수 설정**
   ```
   시스템 환경 변수 → Path에 추가:
   C:\Program Files\mosquitto
   ```

4. **서비스 시작**
   ```cmd
   # 서비스로 설치된 경우
   net start mosquitto

   # 또는 직접 실행
   mosquitto -v
   ```

### 2.2 Chocolatey 사용 (패키지 관리자)
```powershell
# Chocolatey 설치 후
choco install mosquitto
```

### 2.3 Windows 설치 확인
```cmd
# 버전 확인
mosquitto -h

# 브로커 실행 (verbose 모드)
mosquitto -v

# 기본 포트 1883에서 실행됨
```

---

## 3. Linux 설치 (Ubuntu/Debian)

### 3.1 apt 패키지 설치
```bash
# 패키지 목록 업데이트
sudo apt update

# Mosquitto 브로커 및 클라이언트 설치
sudo apt install -y mosquitto mosquitto-clients

# 서비스 시작
sudo systemctl start mosquitto

# 부팅 시 자동 시작 설정
sudo systemctl enable mosquitto

# 상태 확인
sudo systemctl status mosquitto
```

### 3.2 최신 버전 설치 (PPA)
```bash
# Mosquitto 공식 PPA 추가
sudo apt-add-repository ppa:mosquitto-dev/mosquitto-ppa
sudo apt update
sudo apt install mosquitto mosquitto-clients
```

---

## 4. Raspberry Pi 설치

```bash
# 업데이트
sudo apt update && sudo apt upgrade -y

# 설치
sudo apt install -y mosquitto mosquitto-clients

# 서비스 시작 및 활성화
sudo systemctl start mosquitto
sudo systemctl enable mosquitto

# 외부 접속 허용 설정
sudo nano /etc/mosquitto/mosquitto.conf
```

**mosquitto.conf 추가:**
```
listener 1883
allow_anonymous true
```

```bash
# 재시작
sudo systemctl restart mosquitto
```

---

## 5. Docker 설치 (권장 - 개발 환경)

### 5.1 기본 실행
```bash
# 최신 Mosquitto 이미지 실행
docker run -d \
  --name mosquitto \
  -p 1883:1883 \
  -p 9001:9001 \
  eclipse-mosquitto

# 로그 확인
docker logs mosquitto
```

### 5.2 설정 파일과 함께 실행

**디렉토리 구조:**
```
mosquitto/
├── config/
│   └── mosquitto.conf
├── data/
└── log/
```

**mosquitto.conf:**
```conf
# 기본 리스너
listener 1883

# WebSocket 리스너 (웹 클라이언트용)
listener 9001
protocol websockets

# 익명 접속 허용 (개발용)
allow_anonymous true

# 로그 설정
log_dest file /mosquitto/log/mosquitto.log
log_type all

# 데이터 영속성
persistence true
persistence_location /mosquitto/data/
```

**Docker 실행:**
```bash
docker run -d \
  --name mosquitto \
  -p 1883:1883 \
  -p 9001:9001 \
  -v $(pwd)/mosquitto/config:/mosquitto/config \
  -v $(pwd)/mosquitto/data:/mosquitto/data \
  -v $(pwd)/mosquitto/log:/mosquitto/log \
  eclipse-mosquitto
```

### 5.3 Docker Compose

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  mosquitto:
    image: eclipse-mosquitto:latest
    container_name: mosquitto
    ports:
      - "1883:1883"    # MQTT
      - "9001:9001"    # WebSocket
    volumes:
      - ./mosquitto/config:/mosquitto/config
      - ./mosquitto/data:/mosquitto/data
      - ./mosquitto/log:/mosquitto/log
    restart: unless-stopped
```

```bash
# 실행
docker-compose up -d

# 중지
docker-compose down

# 로그 확인
docker-compose logs -f mosquitto
```

---

## 6. 설정 파일 상세

### 6.1 기본 설정 (mosquitto.conf)

```conf
# ===========================================
# Mosquitto 설정 파일
# ===========================================

# --- 네트워크 설정 ---
# 기본 MQTT 리스너
listener 1883
# 특정 IP에서만 수신 (0.0.0.0 = 모든 인터페이스)
# bind_address 0.0.0.0

# --- 인증 설정 ---
# 익명 접속 (개발용: true, 운영용: false)
allow_anonymous true

# 비밀번호 파일 사용 시
# password_file /etc/mosquitto/passwd

# --- 로깅 ---
log_dest stderr
# log_dest file /var/log/mosquitto/mosquitto.log
log_type error
log_type warning
log_type notice
log_type information
# log_type debug  # 상세 디버깅

# 타임스탬프 포함
log_timestamp true

# --- 영속성 ---
persistence true
persistence_location /var/lib/mosquitto/

# --- 성능 튜닝 ---
# 최대 연결 수 (-1 = 무제한)
max_connections -1

# Keep Alive 최대값 (초)
max_keepalive 65535

# 메시지 크기 제한 (bytes)
message_size_limit 0

# --- 보안 (TLS) ---
# listener 8883
# cafile /etc/mosquitto/certs/ca.crt
# certfile /etc/mosquitto/certs/server.crt
# keyfile /etc/mosquitto/certs/server.key
# require_certificate false
```

### 6.2 비밀번호 인증 설정

```bash
# 비밀번호 파일 생성
sudo mosquitto_passwd -c /etc/mosquitto/passwd admin
# 비밀번호 입력 프롬프트

# 사용자 추가
sudo mosquitto_passwd /etc/mosquitto/passwd sensor_user

# mosquitto.conf 수정
allow_anonymous false
password_file /etc/mosquitto/passwd
```

### 6.3 ACL (접근 제어 목록) 설정

**acl.conf:**
```conf
# 기본 정책: 모든 접근 거부
# user별 권한 설정

# admin 사용자: 모든 권한
user admin
topic readwrite #

# sensor 사용자: sensors/ 토픽에 쓰기만
user sensor_user
topic write sensors/#

# dashboard 사용자: 읽기만
user dashboard
topic read sensors/#
topic read processed/#

# 익명 사용자 권한 (allow_anonymous true일 때)
pattern read $SYS/#
```

**mosquitto.conf에 추가:**
```conf
acl_file /etc/mosquitto/acl.conf
```

---

## 7. 테스트 방법

### 7.1 커맨드라인 클라이언트

**터미널 1 - 구독:**
```bash
# 모든 sensors 토픽 구독
mosquitto_sub -h localhost -p 1883 -t "sensors/#" -v

# 특정 토픽 구독
mosquitto_sub -h localhost -t "sensors/temperature/room1"

# 인증 필요 시
mosquitto_sub -h localhost -u admin -P password -t "sensors/#"
```

**터미널 2 - 발행:**
```bash
# 메시지 발행
mosquitto_pub -h localhost -p 1883 -t "sensors/temperature/room1" -m "25.5"

# JSON 발행
mosquitto_pub -h localhost -t "sensors/temp/001" -m '{"value": 23.5, "unit": "celsius"}'

# Retain 메시지
mosquitto_pub -h localhost -t "device/status" -m "online" -r

# QoS 1로 발행
mosquitto_pub -h localhost -t "sensors/temp" -m "24.0" -q 1
```

### 7.2 Python 테스트 스크립트

**test_publisher.py:**
```python
import paho.mqtt.client as mqtt
import json
import time

client = mqtt.Client()
client.connect("localhost", 1883, 60)

# 테스트 데이터 발행
for i in range(5):
    data = {
        "sensor_id": "TEMP_001",
        "type": "temperature",
        "value": 20 + i * 0.5,
        "unit": "celsius"
    }
    client.publish("sensors/temperature/room1", json.dumps(data))
    print(f"Published: {data}")
    time.sleep(1)

client.disconnect()
```

**test_subscriber.py:**
```python
import paho.mqtt.client as mqtt

def on_message(client, userdata, msg):
    print(f"Topic: {msg.topic}")
    print(f"Payload: {msg.payload.decode()}")
    print("-" * 40)

client = mqtt.Client()
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("sensors/#")

print("Waiting for messages...")
client.loop_forever()
```

---

## 8. 문제 해결

### 8.1 연결 거부
```bash
# 방화벽 확인 (Linux)
sudo ufw allow 1883/tcp

# Windows 방화벽
netsh advfirewall firewall add rule name="MQTT" dir=in action=allow protocol=tcp localport=1883

# 브로커 실행 확인
netstat -an | grep 1883
```

### 8.2 인증 실패
```bash
# 로그 확인
sudo tail -f /var/log/mosquitto/mosquitto.log

# 비밀번호 파일 권한 확인
sudo chmod 600 /etc/mosquitto/passwd
sudo chown mosquitto:mosquitto /etc/mosquitto/passwd
```

### 8.3 Docker 권한 문제
```bash
# 볼륨 디렉토리 권한 설정
sudo chown -R 1883:1883 ./mosquitto/data
sudo chown -R 1883:1883 ./mosquitto/log
```

### 8.4 연결 끊김 (Timeout)
```conf
# mosquitto.conf
# Keep Alive 설정 조정
max_keepalive 120
```

---

## 9. 모니터링

### 9.1 시스템 토픽 ($SYS)
```bash
# 브로커 상태 모니터링
mosquitto_sub -h localhost -t '$SYS/#' -v

# 주요 시스템 토픽
# $SYS/broker/version - 브로커 버전
# $SYS/broker/uptime - 가동 시간
# $SYS/broker/clients/connected - 연결된 클라이언트 수
# $SYS/broker/messages/received - 수신 메시지 수
# $SYS/broker/messages/sent - 발신 메시지 수
```

### 9.2 MQTT Explorer (GUI 도구)
- http://mqtt-explorer.com/ 에서 다운로드
- 토픽 구조 시각화
- 실시간 메시지 모니터링
- Retain 메시지 관리

---

## 10. 프로덕션 체크리스트

- [ ] 익명 접속 비활성화 (`allow_anonymous false`)
- [ ] 강력한 비밀번호 설정
- [ ] TLS/SSL 활성화 (포트 8883)
- [ ] ACL로 토픽별 권한 설정
- [ ] 로그 로테이션 설정
- [ ] 모니터링 설정 ($SYS 토픽)
- [ ] 백업 전략 수립
- [ ] 방화벽 규칙 설정
- [ ] Keep Alive 값 최적화
