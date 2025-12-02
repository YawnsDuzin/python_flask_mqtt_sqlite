"""
Flask 라우트 모듈
웹 페이지 및 REST API 엔드포인트를 정의합니다.
환경 센서 (가스, 온도, 습도, 미세먼지 등) 데이터를 다룹니다.
"""

import logging
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request

from app.models import get_db, SENSOR_TYPES, ALARM_LEVELS, ALARM_SENSOR_TYPES
from app.mqtt import get_mqtt_client

logger = logging.getLogger(__name__)

# 블루프린트 생성
main_bp = Blueprint('main', __name__)
api_bp = Blueprint('api', __name__)


# ===== 웹 페이지 라우트 =====

@main_bp.route('/')
def index():
    """메인 대시보드 페이지"""
    return render_template('dashboard.html', sensor_types=SENSOR_TYPES)


@main_bp.route('/sites')
def sites_page():
    """현장 목록 페이지"""
    db = get_db()
    sites = db.get_all_sites()
    return render_template('sites.html', sites=sites)


@main_bp.route('/sites/<site_code>')
def site_detail(site_code):
    """현장 상세 페이지"""
    db = get_db()
    site = db.get_site(site_code)
    if not site:
        return render_template('error.html', message='현장을 찾을 수 없습니다.'), 404

    devices = db.get_devices_by_site(site_code)
    return render_template(
        'site_detail.html',
        site=site,
        devices=devices,
        sensor_types=SENSOR_TYPES
    )


@main_bp.route('/devices')
def devices_page():
    """장치 목록 페이지"""
    db = get_db()
    devices = db.get_all_devices()
    return render_template('devices.html', devices=devices, sensor_types=SENSOR_TYPES)


@main_bp.route('/devices/<device_no>')
def device_detail(device_no):
    """장치 상세 페이지"""
    db = get_db()
    device = db.get_device(device_no)
    if not device:
        return render_template('error.html', message='장치를 찾을 수 없습니다.'), 404

    recent_data = db.get_environment_data(device_no=device_no, limit=100)

    return render_template(
        'device_detail.html',
        device=device,
        recent_data=recent_data,
        sensor_types=SENSOR_TYPES
    )


@main_bp.route('/alarms')
def alarms_page():
    """알람 목록 페이지"""
    db = get_db()
    alarms = db.get_alarm_logs(limit=100)
    unacknowledged = db.get_unacknowledged_alarms(limit=100)
    stats = db.get_alarm_stats()

    return render_template(
        'alarms.html',
        alarms=alarms,
        unacknowledged=unacknowledged,
        stats=stats,
        alarm_levels=ALARM_LEVELS,
        sensor_types=SENSOR_TYPES
    )


# ===== REST API 라우트 =====

def api_response(success: bool, data=None, message: str = None, status_code: int = 200):
    """표준 API 응답 형식"""
    response = {
        'success': success,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    if data is not None:
        response['data'] = data
    if message:
        response['message'] = message
    return jsonify(response), status_code


@api_bp.route('/health')
def health_check():
    """헬스 체크 API"""
    mqtt_client = get_mqtt_client()
    db = get_db()

    return api_response(True, {
        'status': 'healthy',
        'mqtt_connected': mqtt_client.is_connected,
        'database': 'connected',
        'data_counts': db.get_data_count()
    })


@api_bp.route('/sensor-types')
def get_sensor_types():
    """센서 타입 목록 API"""
    return api_response(True, {
        'sensor_types': SENSOR_TYPES
    })


# ===== 현장(Site) API =====

@api_bp.route('/sites')
def get_sites():
    """현장 목록 조회 API"""
    db = get_db()
    sites = db.get_all_sites()

    return api_response(True, {
        'sites': [
            {
                'h_cd': s.h_cd,
                's_cd': s.s_cd,
                'name': s.name,
                'description': s.description,
                'is_active': s.is_active,
                'created_at': s.created_at
            }
            for s in sites
        ],
        'count': len(sites)
    })


@api_bp.route('/sites/<site_code>')
def get_site(site_code):
    """특정 현장 정보 조회 API"""
    db = get_db()
    site = db.get_site(site_code)

    if not site:
        return api_response(False, message='현장을 찾을 수 없습니다.', status_code=404)

    devices = db.get_devices_by_site(site_code)

    return api_response(True, {
        'site': {
            'h_cd': site.h_cd,
            's_cd': site.s_cd,
            'name': site.name,
            'description': site.description,
            'is_active': site.is_active,
            'created_at': site.created_at,
            'updated_at': site.updated_at
        },
        'devices': [
            {
                'device_no': d.device_no,
                'name': d.name,
                'is_active': d.is_active
            }
            for d in devices
        ]
    })


# ===== 장치(Device) API =====

@api_bp.route('/devices')
def get_devices():
    """장치 목록 조회 API"""
    db = get_db()
    site_code = request.args.get('site')

    if site_code:
        devices = db.get_devices_by_site(site_code)
    else:
        devices = db.get_all_devices()

    return api_response(True, {
        'devices': [
            {
                'device_no': d.device_no,
                'site_code': d.site_code,
                'name': d.name,
                'description': d.description,
                'is_active': d.is_active,
                'created_at': d.created_at
            }
            for d in devices
        ],
        'count': len(devices)
    })


@api_bp.route('/devices/<device_no>')
def get_device(device_no):
    """특정 장치 정보 조회 API"""
    db = get_db()
    device = db.get_device(device_no)

    if not device:
        return api_response(False, message='장치를 찾을 수 없습니다.', status_code=404)

    return api_response(True, {
        'device': {
            'device_no': device.device_no,
            'site_code': device.site_code,
            'name': device.name,
            'description': device.description,
            'is_active': device.is_active,
            'created_at': device.created_at,
            'updated_at': device.updated_at
        }
    })


@api_bp.route('/devices/<device_no>/data')
def get_device_data(device_no):
    """장치의 환경 데이터 조회 API"""
    db = get_db()

    limit = min(int(request.args.get('limit', 100)), 1000)
    offset = int(request.args.get('offset', 0))
    start_time = request.args.get('start')
    end_time = request.args.get('end')

    data = db.get_environment_data(
        device_no=device_no,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset
    )

    return api_response(True, {
        'device_no': device_no,
        'data': [
            {
                'id': d.id,
                'timestamp': d.timestamp,
                'o2': d.o2,
                'no2': d.no2,
                'co': d.co,
                'co2': d.co2,
                'h2s': d.h2s,
                'ch4': d.ch4,
                'ch2o': d.ch2o,
                'o3': d.o3,
                'pm25': d.pm25,
                'pm10': d.pm10,
                'temp': d.temp,
                'humi': d.humi,
                'voc': d.voc,
                'pm1': d.pm1,
                'received_at': d.received_at
            }
            for d in data
        ],
        'count': len(data),
        'limit': limit,
        'offset': offset
    })


# ===== 환경 데이터 API =====

@api_bp.route('/data/latest')
def get_latest_data():
    """최신 환경 데이터 조회 API"""
    db = get_db()
    limit = min(int(request.args.get('limit', 10)), 100)

    data = db.get_latest_data(limit=limit)

    return api_response(True, {
        'data': [
            {
                'id': d.id,
                'device_no': d.device_no,
                'site_code': d.site_code,
                'timestamp': d.timestamp,
                'o2': d.o2,
                'no2': d.no2,
                'co': d.co,
                'co2': d.co2,
                'h2s': d.h2s,
                'ch4': d.ch4,
                'ch2o': d.ch2o,
                'o3': d.o3,
                'pm25': d.pm25,
                'pm10': d.pm10,
                'temp': d.temp,
                'humi': d.humi,
                'voc': d.voc,
                'pm1': d.pm1,
                'received_at': d.received_at
            }
            for d in data
        ],
        'count': len(data)
    })


@api_bp.route('/data/latest-by-device')
def get_latest_by_device():
    """장치별 최신 데이터 조회 API"""
    db = get_db()
    data = db.get_latest_by_device()

    return api_response(True, {
        'data': data,
        'count': len(data)
    })


@api_bp.route('/data/stats')
def get_all_stats():
    """전체 통계 데이터 조회 API"""
    db = get_db()

    # 각 장치별 통계
    devices = db.get_all_devices()
    stats = []

    for device in devices:
        device_stats = db.get_device_stats(device.device_no)
        if device_stats:
            stats.append({
                'device_no': device.device_no,
                'site_code': device.site_code,
                'name': device.name,
                'stats': device_stats
            })

    return api_response(True, {
        'stats': stats,
        'count': len(stats)
    })


@api_bp.route('/data/stats/<device_no>')
def get_device_stats(device_no):
    """특정 장치 통계 조회 API"""
    db = get_db()

    device = db.get_device(device_no)
    if not device:
        return api_response(False, message='장치를 찾을 수 없습니다.', status_code=404)

    stats = db.get_device_stats(device_no)

    return api_response(True, {
        'device_no': device_no,
        'stats': stats
    })


# ===== MQTT API =====

@api_bp.route('/mqtt/status')
def mqtt_status():
    """MQTT 클라이언트 상태 조회 API"""
    mqtt_client = get_mqtt_client()

    return api_response(True, mqtt_client.get_status())


@api_bp.route('/mqtt/publish', methods=['POST'])
def mqtt_publish():
    """MQTT 메시지 발행 API"""
    mqtt_client = get_mqtt_client()

    if not mqtt_client.is_connected:
        return api_response(
            False,
            message='MQTT 브로커에 연결되어 있지 않습니다.',
            status_code=503
        )

    data = request.get_json()
    if not data:
        return api_response(False, message='JSON 데이터가 필요합니다.', status_code=400)

    topic = data.get('topic')
    payload = data.get('payload')
    qos = data.get('qos', 1)
    retain = data.get('retain', False)

    if not topic or payload is None:
        return api_response(
            False,
            message='topic과 payload가 필요합니다.',
            status_code=400
        )

    success = mqtt_client.publish(topic, payload, qos, retain)

    if success:
        return api_response(True, message='메시지 발행 성공')
    else:
        return api_response(False, message='메시지 발행 실패', status_code=500)


@api_bp.route('/mqtt/logs')
def get_mqtt_logs():
    """MQTT 로그 조회 API"""
    db = get_db()
    event_type = request.args.get('type')
    limit = min(int(request.args.get('limit', 50)), 500)

    logs = db.get_mqtt_logs(event_type=event_type, limit=limit)

    return api_response(True, {
        'logs': [
            {
                'id': log.id,
                'event_type': log.event_type,
                'topic': log.topic,
                'message': log.message,
                'created_at': log.created_at
            }
            for log in logs
        ],
        'count': len(logs)
    })


# ===== 알람 임계값 API =====

@api_bp.route('/alarms/thresholds')
def get_alarm_thresholds():
    """알람 임계값 조회 API"""
    db = get_db()
    site_code = request.args.get('site')
    device_no = request.args.get('device')

    thresholds = db.get_alarm_thresholds(site_code=site_code, device_no=device_no)

    return api_response(True, {
        'thresholds': thresholds,
        'count': len(thresholds)
    })


@api_bp.route('/alarms/thresholds', methods=['POST'])
def set_alarm_threshold():
    """알람 임계값 설정 API"""
    db = get_db()

    data = request.get_json()
    if not data:
        return api_response(False, message='JSON 데이터가 필요합니다.', status_code=400)

    sensor_type = data.get('sensor_type')
    min_value = data.get('min_value')
    max_value = data.get('max_value')

    if not sensor_type:
        return api_response(False, message='sensor_type이 필요합니다.', status_code=400)

    if sensor_type not in SENSOR_TYPES:
        return api_response(False, message=f'유효하지 않은 센서 타입: {sensor_type}', status_code=400)

    success = db.set_alarm_threshold(
        sensor_type=sensor_type,
        min_value=min_value,
        max_value=max_value,
        site_code=data.get('site_code'),
        device_no=data.get('device_no')
    )

    if success:
        return api_response(True, message='알람 임계값 설정 완료')
    else:
        return api_response(False, message='알람 임계값 설정 실패', status_code=500)


# ===== 알람 로그 API =====

@api_bp.route('/alarms')
def get_alarms():
    """알람 로그 목록 조회 API"""
    db = get_db()

    limit = min(int(request.args.get('limit', 100)), 1000)
    offset = int(request.args.get('offset', 0))
    site_code = request.args.get('site')
    device_id = request.args.get('device')
    sensor_type = request.args.get('sensor')
    level = request.args.get('level')
    is_acknowledged = request.args.get('acknowledged')

    # 파라미터 변환
    level_int = int(level) if level is not None else None
    ack_bool = None
    if is_acknowledged is not None:
        ack_bool = is_acknowledged.lower() in ('true', '1', 'yes')

    alarms = db.get_alarm_logs(
        site_code=site_code,
        device_id=device_id,
        sensor_type=sensor_type,
        level=level_int,
        is_acknowledged=ack_bool,
        limit=limit,
        offset=offset
    )

    return api_response(True, {
        'alarms': [
            {
                'id': a.id,
                'site_code': a.site_code,
                'device_id': a.device_id,
                'dv_no': a.dv_no,
                'sensor_type': a.sensor_type,
                'sensor_name': SENSOR_TYPES.get(a.sensor_type, {}).get('name', a.sensor_type),
                'value': a.value,
                'unit': SENSOR_TYPES.get(a.sensor_type, {}).get('unit', ''),
                'level': a.level,
                'level_name': ALARM_LEVELS.get(a.level, {}).get('name', ''),
                'level_color': ALARM_LEVELS.get(a.level, {}).get('color', '#999'),
                'etc': a.etc,
                'alarm_time': a.alarm_time,
                'is_acknowledged': a.is_acknowledged,
                'acknowledged_at': a.acknowledged_at,
                'acknowledged_by': a.acknowledged_by,
                'created_at': a.created_at
            }
            for a in alarms
        ],
        'count': len(alarms),
        'limit': limit,
        'offset': offset
    })


@api_bp.route('/alarms/unacknowledged')
def get_unacknowledged_alarms():
    """미확인 알람 조회 API"""
    db = get_db()
    limit = min(int(request.args.get('limit', 100)), 500)

    alarms = db.get_unacknowledged_alarms(limit=limit)

    return api_response(True, {
        'alarms': [
            {
                'id': a.id,
                'site_code': a.site_code,
                'device_id': a.device_id,
                'dv_no': a.dv_no,
                'sensor_type': a.sensor_type,
                'sensor_name': SENSOR_TYPES.get(a.sensor_type, {}).get('name', a.sensor_type),
                'value': a.value,
                'unit': SENSOR_TYPES.get(a.sensor_type, {}).get('unit', ''),
                'level': a.level,
                'level_name': ALARM_LEVELS.get(a.level, {}).get('name', ''),
                'level_color': ALARM_LEVELS.get(a.level, {}).get('color', '#999'),
                'etc': a.etc,
                'alarm_time': a.alarm_time,
                'created_at': a.created_at
            }
            for a in alarms
        ],
        'count': len(alarms)
    })


@api_bp.route('/alarms/stats')
def get_alarm_stats():
    """알람 통계 조회 API"""
    db = get_db()
    stats = db.get_alarm_stats()

    return api_response(True, {
        'stats': stats,
        'alarm_levels': ALARM_LEVELS,
        'alarm_sensor_types': ALARM_SENSOR_TYPES
    })


@api_bp.route('/alarms/recent-by-device')
def get_recent_alarms_by_device():
    """장치별 최근 알람 조회 API"""
    db = get_db()
    alarms = db.get_recent_alarms_by_device()

    return api_response(True, {
        'alarms': alarms,
        'count': len(alarms)
    })


@api_bp.route('/alarms/<int:alarm_id>/acknowledge', methods=['POST'])
def acknowledge_alarm(alarm_id):
    """알람 확인 처리 API"""
    db = get_db()

    data = request.get_json() or {}
    acknowledged_by = data.get('acknowledged_by', 'system')

    success = db.acknowledge_alarm(alarm_id, acknowledged_by)

    if success:
        return api_response(True, message='알람 확인 처리 완료')
    else:
        return api_response(False, message='알람을 찾을 수 없거나 이미 확인 처리됨', status_code=404)


@api_bp.route('/alarms/acknowledge-all', methods=['POST'])
def acknowledge_all_alarms():
    """모든 미확인 알람 확인 처리 API"""
    db = get_db()

    data = request.get_json() or {}
    site_code = data.get('site_code')
    acknowledged_by = data.get('acknowledged_by', 'system')

    count = db.acknowledge_all_alarms(site_code=site_code, acknowledged_by=acknowledged_by)

    return api_response(True, {
        'acknowledged_count': count,
        'message': f'{count}개의 알람이 확인 처리되었습니다.'
    })


# ===== 에러 핸들러 =====

@main_bp.app_errorhandler(404)
def not_found_error(error):
    """404 에러 핸들러"""
    if request.path.startswith('/api/'):
        return api_response(False, message='리소스를 찾을 수 없습니다.', status_code=404)
    return render_template('error.html', message='페이지를 찾을 수 없습니다.'), 404


@main_bp.app_errorhandler(500)
def internal_error(error):
    """500 에러 핸들러"""
    logger.error(f"내부 서버 오류: {error}")
    if request.path.startswith('/api/'):
        return api_response(False, message='내부 서버 오류가 발생했습니다.', status_code=500)
    return render_template('error.html', message='서버 오류가 발생했습니다.'), 500
