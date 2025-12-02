# MQTT 개념 설명서

## 1. MQTT란?

**MQTT (Message Queuing Telemetry Transport)**는 경량 메시지 프로토콜로,
IoT(사물인터넷) 환경에서 장치 간 통신을 위해 설계되었습니다.

### 1.1 특징
- **경량 프로토콜**: 최소한의 네트워크 대역폭 사용
- **발행/구독 모델**: 느슨한 결합(loose coupling)으로 확장성 우수
- **저전력**: 배터리 기반 IoT 장치에 적합
- **신뢰성**: QoS 레벨로 메시지 전달 보장

### 1.2 역사
- 1999년 IBM의 Andy Stanford-Clark와 Arlen Nipper가 개발
- 2014년 OASIS 표준으로 채택
- 현재 버전: MQTT 5.0 (MQTT 3.1.1도 널리 사용)

---

## 2. 핵심 구성요소

### 2.1 브로커 (Broker)
```
메시지 중개 서버. 모든 메시지가 브로커를 통해 라우팅됨

[Publisher] → [BROKER] → [Subscriber]
                 ↓
           [Subscriber 2]
```

**역할:**
- 클라이언트 연결 관리
- 메시지 수신 및 필터링
- 구독자에게 메시지 전달
- 세션 상태 유지

**대표적인 브로커:**
- **Mosquitto**: 가장 널리 사용되는 오픈소스 브로커
- **HiveMQ**: 엔터프라이즈급 브로커
- **EMQX**: 대규모 IoT 플랫폼용
- **AWS IoT Core**: 클라우드 기반

### 2.2 클라이언트 (Client)
브로커에 연결하여 메시지를 발행하거나 구독하는 장치/애플리케이션

- **Publisher (발행자)**: 메시지를 토픽에 발행
- **Subscriber (구독자)**: 토픽을 구독하여 메시지 수신
- 하나의 클라이언트가 동시에 발행자/구독자 역할 가능

### 2.3 토픽 (Topic)
메시지를 분류하는 계층적 문자열. 슬래시(/)로 레벨 구분

```
예시:
sensors/temperature/room1
sensors/humidity/room1
home/livingroom/light/status
factory/line1/machine1/vibration
```

**토픽 설계 권장사항:**
- 의미 있는 계층 구조 사용
- 소문자와 언더스코어 권장
- 선행 슬래시(/) 사용 금지 (예: /sensors는 좋지 않음)

---

## 3. 와일드카드 (Wildcards)

구독 시 여러 토픽을 한 번에 구독할 수 있는 특수 문자

### 3.1 단일 레벨 와일드카드: `+`
해당 레벨의 모든 값과 매칭

```
구독: sensors/+/temperature
매칭: sensors/room1/temperature ✓
      sensors/room2/temperature ✓
      sensors/building1/room1/temperature ✗ (레벨 불일치)
```

### 3.2 다중 레벨 와일드카드: `#`
해당 레벨 이하 모든 토픽과 매칭 (토픽 끝에만 사용)

```
구독: sensors/#
매칭: sensors/temperature ✓
      sensors/room1/temperature ✓
      sensors/building/floor1/room1/temp ✓
```

### 3.3 조합 사용
```
구독: sensors/+/temperature/#
매칭: sensors/room1/temperature/celsius ✓
      sensors/room2/temperature/fahrenheit/raw ✓
```

---

## 4. QoS (Quality of Service)

메시지 전달 보장 수준. 세 가지 레벨 존재

### 4.1 QoS 0: At most once (최대 1회)
```
Publisher → Broker → Subscriber
   PUBLISH →
            ← (응답 없음)
```
- "Fire and forget" 방식
- 메시지 손실 가능
- 가장 빠르고 오버헤드 최소
- **사용 사례**: 주기적 센서 데이터 (일부 손실 허용)

### 4.2 QoS 1: At least once (최소 1회)
```
Publisher → Broker
   PUBLISH →
         ← PUBACK
```
- 메시지 전달 보장
- 중복 전달 가능
- **사용 사례**: 알람, 로그 데이터

### 4.3 QoS 2: Exactly once (정확히 1회)
```
Publisher → Broker
   PUBLISH →
         ← PUBREC
   PUBREL →
         ← PUBCOMP
```
- 메시지 정확히 한 번 전달
- 4-way handshake로 오버헤드 큼
- **사용 사례**: 과금 데이터, 중요 명령

### QoS 선택 가이드
| 상황 | 권장 QoS |
|------|----------|
| 빈번한 센서 데이터 | 0 |
| 중요하지만 중복 허용 | 1 |
| 절대 중복/손실 불가 | 2 |

---

## 5. Retain (보존 메시지)

브로커가 토픽의 마지막 메시지를 저장하여 새 구독자에게 즉시 전달

### 동작 방식
```
1. Publisher가 retain=True로 메시지 발행
2. Broker가 해당 토픽의 메시지 저장
3. 새 구독자가 연결하면 즉시 저장된 메시지 수신
```

### 사용 예시
```python
# 장치 상태를 retain으로 발행
client.publish("device/sensor1/status", "online", retain=True)
```

**주의사항:**
- 토픽당 하나의 retain 메시지만 저장
- 빈 메시지로 retain 삭제 가능
- 와일드카드 구독 시에도 retain 메시지 수신

---

## 6. Clean Session / Persistent Session

### 6.1 Clean Session (clean_session=True)
- 연결 시 이전 세션 정보 삭제
- 연결 끊김 동안의 메시지 보관 안 함
- **사용 사례**: 임시 클라이언트, 상태 비저장 센서

### 6.2 Persistent Session (clean_session=False)
- 브로커가 세션 정보 유지
  - 구독 목록
  - QoS 1, 2의 미전달 메시지
  - 클라이언트의 미확인 메시지
- **사용 사례**: 간헐적 연결 장치, 중요 데이터 수신

```python
# Persistent Session 설정
client = mqtt.Client(client_id="sensor_001", clean_session=False)
```

---

## 7. Last Will and Testament (LWT)

클라이언트가 비정상 종료될 때 브로커가 자동 발행하는 메시지

### 설정 방법
```python
client.will_set(
    topic="devices/sensor1/status",
    payload="offline",
    qos=1,
    retain=True
)
```

### 동작 시나리오
```
1. 클라이언트 연결 시 LWT 설정
2. 정상 종료: LWT 발행 안 함
3. 비정상 종료 (keepalive 타임아웃, 네트워크 끊김): 브로커가 LWT 발행
```

---

## 8. Keep Alive

클라이언트-브로커 간 연결 유지 확인 메커니즘

### 동작 원리
```
Keep Alive = 60초 설정 시

[Client] ← 60초 내 통신 없음 → [Broker]
   ↓                              ↓
PINGREQ 전송 →              ← PINGRESP 응답
```

- 설정된 시간의 1.5배 동안 응답 없으면 연결 종료
- Keep Alive = 0 이면 비활성화 (권장하지 않음)

---

## 9. MQTT 5.0 주요 신기능

### 9.1 Reason Code
모든 응답에 상세한 이유 코드 포함

### 9.2 Shared Subscriptions
동일 토픽을 여러 클라이언트가 로드밸런싱하여 구독
```
$share/group1/sensors/temperature
```

### 9.3 Message Expiry
메시지에 만료 시간 설정
```python
publish(topic, payload, properties={'message_expiry_interval': 3600})
```

### 9.4 Topic Alias
긴 토픽 이름을 숫자로 대체하여 대역폭 절약

### 9.5 User Properties
사용자 정의 메타데이터 추가

---

## 10. MQTT vs 다른 프로토콜

| 특성 | MQTT | HTTP | CoAP | AMQP |
|------|------|------|------|------|
| 패턴 | Pub/Sub | Req/Res | Req/Res | Pub/Sub |
| 헤더 크기 | 2 bytes | ~700 bytes | 4 bytes | 많음 |
| 전송 | TCP | TCP | UDP | TCP |
| IoT 적합성 | 최적 | 보통 | 좋음 | 보통 |
| QoS | 0,1,2 | 없음 | 확인형 | 있음 |

---

## 11. 보안 고려사항

### 11.1 인증
- 사용자명/비밀번호 인증
- 클라이언트 인증서 (TLS)
- 토큰 기반 인증

### 11.2 암호화
- TLS/SSL 사용 (포트 8883)
- 페이로드 암호화 (애플리케이션 레벨)

### 11.3 권한 관리
- ACL (Access Control List)로 토픽별 권한 설정
- 발행/구독 권한 분리

---

## 12. 일반적인 토픽 구조 예시

### IoT 센서 네트워크
```
sensors/{location}/{sensor_type}/{sensor_id}
sensors/building1/temperature/temp_001
sensors/building1/humidity/humid_001

commands/{device_id}/{action}
commands/light_001/toggle

status/{device_id}
status/light_001
```

### 스마트홈
```
home/{room}/{device}/{property}
home/livingroom/light/brightness
home/bedroom/ac/temperature
home/kitchen/sensor/motion
```

---

## 13. 참고 자료

- [MQTT.org 공식 사이트](https://mqtt.org/)
- [MQTT 5.0 스펙](https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html)
- [Eclipse Mosquitto](https://mosquitto.org/)
- [paho-mqtt Python 라이브러리](https://pypi.org/project/paho-mqtt/)
