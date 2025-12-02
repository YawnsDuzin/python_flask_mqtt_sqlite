"""
Flask 라우트 모듈
웹 페이지 및 REST API 엔드포인트를 정의합니다.
"""

import logging
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request

from app.models import get_db
from app.mqtt import get_mqtt_client

logger = logging.getLogger(__name__)

# 블루프린트 생성
main_bp = Blueprint('main', __name__)
api_bp = Blueprint('api', __name__)


# ===== 웹 페이지 라우트 =====

@main_bp.route('/')
def index():
    """메인 대시보드 페이지"""
    return render_template('dashboard.html')


@main_bp.route('/sensors')
def sensors_page():
    """센서 목록 페이지"""
    db = get_db()
    sensors = db.get_all_sensors()
    return render_template('sensors.html', sensors=sensors)


@main_bp.route('/sensors/<sensor_id>')
def sensor_detail(sensor_id):
    """센서 상세 페이지"""
    db = get_db()
    sensor = db.get_sensor(sensor_id)
    if not sensor:
        return render_template('error.html', message='센서를 찾을 수 없습니다.'), 404

    stats = db.get_sensor_stats(sensor_id)
    recent_data = db.get_sensor_data(sensor_id=sensor_id, limit=50)

    return render_template(
        'sensor_detail.html',
        sensor=sensor,
        stats=stats,
        recent_data=recent_data
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


@api_bp.route('/sensors')
def get_sensors():
    """모든 센서 목록 조회 API"""
    db = get_db()
    active_only = request.args.get('active', 'false').lower() == 'true'
    sensors = db.get_all_sensors(active_only=active_only)

    return api_response(True, {
        'sensors': [
            {
                'sensor_id': s.sensor_id,
                'sensor_type': s.sensor_type,
                'location': s.location,
                'is_active': s.is_active,
                'created_at': s.created_at
            }
            for s in sensors
        ],
        'count': len(sensors)
    })


@api_bp.route('/sensors/<sensor_id>')
def get_sensor(sensor_id):
    """특정 센서 정보 조회 API"""
    db = get_db()
    sensor = db.get_sensor(sensor_id)

    if not sensor:
        return api_response(False, message='센서를 찾을 수 없습니다.', status_code=404)

    stats = db.get_sensor_stats(sensor_id)

    return api_response(True, {
        'sensor': {
            'sensor_id': sensor.sensor_id,
            'sensor_type': sensor.sensor_type,
            'location': sensor.location,
            'description': sensor.description,
            'is_active': sensor.is_active,
            'created_at': sensor.created_at,
            'updated_at': sensor.updated_at
        },
        'stats': stats
    })


@api_bp.route('/sensors/<sensor_id>/data')
def get_sensor_data(sensor_id):
    """센서 데이터 조회 API (필터링 지원)"""
    db = get_db()

    # 쿼리 파라미터
    limit = min(int(request.args.get('limit', 100)), 1000)
    offset = int(request.args.get('offset', 0))
    start_time = request.args.get('start')
    end_time = request.args.get('end')

    data = db.get_sensor_data(
        sensor_id=sensor_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset
    )

    return api_response(True, {
        'sensor_id': sensor_id,
        'data': [
            {
                'id': d.id,
                'value': d.value,
                'unit': d.unit,
                'timestamp': d.timestamp,
                'received_at': d.received_at
            }
            for d in data
        ],
        'count': len(data),
        'limit': limit,
        'offset': offset
    })


@api_bp.route('/data/latest')
def get_latest_data():
    """최신 데이터 조회 API"""
    db = get_db()
    limit = min(int(request.args.get('limit', 10)), 100)

    data = db.get_latest_data(limit=limit)

    return api_response(True, {
        'data': [
            {
                'sensor_id': d.sensor_id,
                'sensor_type': d.sensor_type,
                'value': d.value,
                'unit': d.unit,
                'timestamp': d.timestamp,
                'received_at': d.received_at
            }
            for d in data
        ],
        'count': len(data)
    })


@api_bp.route('/data/latest-by-sensor')
def get_latest_by_sensor():
    """센서별 최신 데이터 조회 API"""
    db = get_db()
    data = db.get_latest_by_sensor()

    return api_response(True, {
        'data': data,
        'count': len(data)
    })


@api_bp.route('/data/stats')
def get_all_stats():
    """전체 통계 데이터 조회 API"""
    db = get_db()
    stats = db.get_all_stats()

    return api_response(True, {
        'stats': stats,
        'count': len(stats)
    })


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
