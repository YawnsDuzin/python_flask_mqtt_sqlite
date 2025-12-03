#!/usr/bin/env python3
"""
애플리케이션 실행 스크립트
Flask 서버를 시작합니다.
"""

import os
from app import create_app, socketio

# 환경 설정
config_name = os.getenv('FLASK_ENV', 'development')

# Flask 앱 생성
app = create_app(config_name)

if __name__ == '__main__':
    # 개발 서버 실행
    # SocketIO를 사용하므로 socketio.run() 사용
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', '1') == '1'

    print(f"""
╔══════════════════════════════════════════════════════╗
║        MQTT 센서 모니터링 시스템                        ║
╠══════════════════════════════════════════════════════╣
║  서버 주소: http://{host}:{port}
║  환경: {config_name}
║  디버그 모드: {'ON' if debug else 'OFF'}
╚══════════════════════════════════════════════════════╝
    """)

    socketio.run(
        app,
        host=host,
        port=port,
        debug=debug,
        use_reloader=False,  # MQTT 클라이언트 충돌 방지 (동일 client_id 문제)
        log_output=True
    )
