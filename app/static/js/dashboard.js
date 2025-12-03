/**
 * 환경 센서 대시보드 JavaScript
 * Socket.IO를 통한 실시간 데이터 업데이트 및 UI 관리
 */

// Socket.IO 연결
let socket = null;
let isConnected = false;

// 센서 타입 정보
const SENSOR_TYPES = {
    o2: { name: '산소', unit: '%' },
    no2: { name: '이산화질소', unit: 'ppm' },
    co: { name: '일산화탄소', unit: 'ppm' },
    co2: { name: '이산화탄소', unit: 'ppm' },
    h2s: { name: '황화수소', unit: 'ppm' },
    ch4: { name: '메탄', unit: '%LEL' },
    ch2o: { name: '폼알데하이드', unit: 'ppm' },
    o3: { name: '오존', unit: 'ppm' },
    pm25: { name: 'PM2.5', unit: 'ug/m3' },
    pm10: { name: 'PM10', unit: 'ug/m3' },
    pm1: { name: 'PM1.0', unit: 'ug/m3' },
    temp: { name: '온도', unit: 'C' },
    humi: { name: '습도', unit: '%' },
    voc: { name: 'VOC', unit: 'ppm' }
};

// DOM 요소
const elements = {
    mqttStatus: document.getElementById('mqtt-status'),
    mqttConnectionStatus: document.getElementById('mqtt-connection-status'),
    activeSitesCount: document.getElementById('active-sites-count'),
    activeDevicesCount: document.getElementById('active-devices-count'),
    totalDataCount: document.getElementById('total-data-count'),
    deviceCards: document.getElementById('device-cards'),
    recentDataBody: document.getElementById('recent-data-body'),
    realtimeLog: document.getElementById('realtime-log'),
    refreshBtn: document.getElementById('refresh-btn'),
    lastUpdate: document.getElementById('last-update')
};

/**
 * Socket.IO 연결 초기화
 */
function initSocketIO() {
    socket = io();

    socket.on('connect', () => {
        console.log('WebSocket 연결됨');
        isConnected = true;
        addLog('WebSocket 연결 성공', 'success');
        updateMqttStatus();
    });

    socket.on('disconnect', () => {
        console.log('WebSocket 연결 끊김');
        isConnected = false;
        addLog('WebSocket 연결 끊김', 'warning');
        updateMqttStatusUI(false);
    });

    socket.on('connection_response', (data) => {
        console.log('연결 응답:', data);
    });

    // 실시간 환경 데이터 수신
    socket.on('environment_data', (data) => {
        console.log('환경 데이터 수신:', data);
        updateDeviceCard(data);
        addRecentDataRow(data);
        updateSensorValues(data);
        addLog(`데이터 수신: ${data.device_id} (${data.site_code})`, 'info');
        updateLastUpdateTime();
    });

    // 기존 센서 데이터도 지원 (하위 호환)
    socket.on('sensor_data', (data) => {
        console.log('센서 데이터 수신:', data);
        addLog(`센서 데이터: ${data.sensor_id} = ${data.value} ${data.unit}`, 'info');
    });

    socket.on('latest_data', (data) => {
        console.log('최신 데이터:', data);
    });

    socket.on('error', (data) => {
        console.error('오류:', data);
        addLog(`오류: ${data.message}`, 'error');
    });

    // 실시간 알람 수신 (모든 페이지에서 동작)
    socket.on('alarm', (data) => {
        console.log('알람 수신:', data);
        showAlarmNotification(data);
        addLog(`알람: ${data.sensor_name || data.sensor_type} - ${data.value} (레벨: ${data.level})`, 'warning');
    });
}

/**
 * MQTT 상태 업데이트
 */
async function updateMqttStatus() {
    try {
        const response = await fetch('/api/mqtt/status');
        const result = await response.json();

        if (result.success) {
            updateMqttStatusUI(result.data.connected);
        }
    } catch (error) {
        console.error('MQTT 상태 조회 실패:', error);
        updateMqttStatusUI(false);
    }
}

/**
 * MQTT 상태 UI 업데이트
 */
function updateMqttStatusUI(connected) {
    if (elements.mqttStatus) {
        elements.mqttStatus.textContent = connected ? 'MQTT: 연결됨' : 'MQTT: 연결 끊김';
        elements.mqttStatus.className = `status-indicator ${connected ? 'connected' : 'disconnected'}`;
    }

    if (elements.mqttConnectionStatus) {
        elements.mqttConnectionStatus.textContent = connected ? '연결됨' : '연결 끊김';
        elements.mqttConnectionStatus.style.color = connected ? '#2ecc71' : '#e74c3c';
    }
}

/**
 * 대시보드 데이터 로드
 */
async function loadDashboardData() {
    try {
        // 헬스 체크 및 시스템 상태
        const healthResponse = await fetch('/api/health');
        const healthResult = await healthResponse.json();

        if (healthResult.success) {
            updateMqttStatusUI(healthResult.data.mqtt_connected);

            if (elements.totalDataCount) {
                const totalData = healthResult.data.data_counts.environment_data || 0;
                elements.totalDataCount.textContent = `${totalData.toLocaleString()}건`;
            }
        }

        // 현장 목록
        const sitesResponse = await fetch('/api/sites');
        const sitesResult = await sitesResponse.json();

        if (sitesResult.success && elements.activeSitesCount) {
            elements.activeSitesCount.textContent = `${sitesResult.data.count}개`;
        }

        // 장치 목록
        const devicesResponse = await fetch('/api/devices');
        const devicesResult = await devicesResponse.json();

        if (devicesResult.success && elements.activeDevicesCount) {
            elements.activeDevicesCount.textContent = `${devicesResult.data.count}개`;
        }

        // 장치별 최신 데이터
        const latestByDeviceResponse = await fetch('/api/data/latest-by-device');
        const latestByDeviceResult = await latestByDeviceResponse.json();

        if (latestByDeviceResult.success) {
            renderDeviceCards(latestByDeviceResult.data.data);
        }

        // 최근 데이터
        const recentResponse = await fetch('/api/data/latest?limit=20');
        const recentResult = await recentResponse.json();

        if (recentResult.success) {
            renderRecentData(recentResult.data.data);
            // 첫 번째 데이터로 센서 값 업데이트
            if (recentResult.data.data && recentResult.data.data.length > 0) {
                updateSensorValues(recentResult.data.data[0]);
            }
        }

        updateLastUpdateTime();
        addLog('데이터 로드 완료', 'success');

    } catch (error) {
        console.error('데이터 로드 실패:', error);
        addLog(`데이터 로드 실패: ${error.message}`, 'error');
    }
}

/**
 * 센서 값 업데이트 (센서 타입별 현재 상태)
 */
function updateSensorValues(data) {
    const sensorKeys = ['o2', 'no2', 'co', 'co2', 'h2s', 'ch4', 'ch2o', 'o3', 'pm25', 'pm10', 'pm1', 'temp', 'humi', 'voc'];

    sensorKeys.forEach(key => {
        const el = document.getElementById(`val-${key}`);
        if (el && data[key] !== null && data[key] !== undefined) {
            const value = parseFloat(data[key]);
            el.textContent = value.toFixed(key === 'co2' || key.startsWith('pm') ? 0 : 1);

            // 값 변경 애니메이션
            el.style.color = '#3498db';
            setTimeout(() => {
                el.style.color = '';
            }, 500);
        }
    });
}

/**
 * 장치 카드 센서 그룹 HTML 생성
 */
function createDeviceSensorGroupsHTML(device) {
    return `
        <div class="device-sensor-layout">
            <!-- 왼쪽 열: 가스 센서 -->
            <div class="device-sensor-column">
                <div class="device-sensor-group gas-group">
                    <h4><span class="group-icon">⚗️</span>가스 센서</h4>
                    <div class="device-sensor-list">
                        <div class="device-sensor-item">
                            <span class="sensor-label">산소 (O2)</span>
                            <span><span class="sensor-value">${formatValue(device.o2, 1)}</span><span class="sensor-unit">%</span></span>
                        </div>
                        <div class="device-sensor-item">
                            <span class="sensor-label">이산화질소 (NO2)</span>
                            <span><span class="sensor-value">${formatValue(device.no2, 2)}</span><span class="sensor-unit">ppm</span></span>
                        </div>
                        <div class="device-sensor-item">
                            <span class="sensor-label">일산화탄소 (CO)</span>
                            <span><span class="sensor-value">${formatValue(device.co, 1)}</span><span class="sensor-unit">ppm</span></span>
                        </div>
                        <div class="device-sensor-item">
                            <span class="sensor-label">이산화탄소 (CO2)</span>
                            <span><span class="sensor-value">${formatValue(device.co2, 0)}</span><span class="sensor-unit">ppm</span></span>
                        </div>
                        <div class="device-sensor-item">
                            <span class="sensor-label">황화수소 (H2S)</span>
                            <span><span class="sensor-value">${formatValue(device.h2s, 1)}</span><span class="sensor-unit">ppm</span></span>
                        </div>
                        <div class="device-sensor-item">
                            <span class="sensor-label">메탄 (CH4)</span>
                            <span><span class="sensor-value">${formatValue(device.ch4, 1)}</span><span class="sensor-unit">%LEL</span></span>
                        </div>
                        <div class="device-sensor-item">
                            <span class="sensor-label">폼알데하이드 (CH2O)</span>
                            <span><span class="sensor-value">${formatValue(device.ch2o, 2)}</span><span class="sensor-unit">ppm</span></span>
                        </div>
                        <div class="device-sensor-item">
                            <span class="sensor-label">오존 (O3)</span>
                            <span><span class="sensor-value">${formatValue(device.o3, 2)}</span><span class="sensor-unit">ppm</span></span>
                        </div>
                        <div class="device-sensor-item">
                            <span class="sensor-label">VOC</span>
                            <span><span class="sensor-value">${formatValue(device.voc, 1)}</span><span class="sensor-unit">ppm</span></span>
                        </div>
                    </div>
                </div>
            </div>
            <!-- 오른쪽 열: 미세먼지 + 환경 -->
            <div class="device-sensor-column">
                <div class="device-sensor-group dust-group">
                    <h4><span class="group-icon">🌫️</span>미세먼지</h4>
                    <div class="device-sensor-list">
                        <div class="device-sensor-item">
                            <span class="sensor-label">PM1.0</span>
                            <span><span class="sensor-value">${formatValue(device.pm1, 0)}</span><span class="sensor-unit">μg/m³</span></span>
                        </div>
                        <div class="device-sensor-item">
                            <span class="sensor-label">PM2.5</span>
                            <span><span class="sensor-value">${formatValue(device.pm25, 0)}</span><span class="sensor-unit">μg/m³</span></span>
                        </div>
                        <div class="device-sensor-item">
                            <span class="sensor-label">PM10</span>
                            <span><span class="sensor-value">${formatValue(device.pm10, 0)}</span><span class="sensor-unit">μg/m³</span></span>
                        </div>
                    </div>
                </div>
                <div class="device-sensor-group env-group">
                    <h4><span class="group-icon">🌡️</span>환경</h4>
                    <div class="device-sensor-list">
                        <div class="device-sensor-item">
                            <span class="sensor-label">온도</span>
                            <span><span class="sensor-value">${formatValue(device.temp, 1)}</span><span class="sensor-unit">°C</span></span>
                        </div>
                        <div class="device-sensor-item">
                            <span class="sensor-label">습도</span>
                            <span><span class="sensor-value">${formatValue(device.humi, 1)}</span><span class="sensor-unit">%</span></span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * 장치 카드 렌더링
 */
function renderDeviceCards(data) {
    if (!elements.deviceCards) return;

    if (!data || data.length === 0) {
        elements.deviceCards.innerHTML = '<p class="no-data-message">수신된 장치 데이터가 없습니다.</p>';
        return;
    }

    elements.deviceCards.innerHTML = data.map(device => `
        <div class="device-data-card" data-device-id="${device.device_id}">
            <div class="card-header">
                <h3>${device.device_id}</h3>
                <span class="site-code-badge">${device.site_code || '-'}</span>
            </div>
            <div class="card-body">
                ${createDeviceSensorGroupsHTML(device)}
                <div class="device-timestamp">${formatTimestamp(device.received_at)}</div>
            </div>
        </div>
    `).join('');
}

/**
 * 장치 카드 업데이트 (실시간)
 */
function updateDeviceCard(data) {
    if (!elements.deviceCards) return;

    const existingCard = elements.deviceCards.querySelector(`[data-device-id="${data.device_id}"]`);

    if (existingCard) {
        // 기존 카드 업데이트 - 센서 그룹 레이아웃 교체
        const sensorLayout = existingCard.querySelector('.device-sensor-layout');
        if (sensorLayout) {
            sensorLayout.outerHTML = createDeviceSensorGroupsHTML(data);
        }

        const timestampEl = existingCard.querySelector('.device-timestamp');
        if (timestampEl) {
            timestampEl.textContent = formatTimestamp(data.received_at || new Date().toISOString());
        }

        // 업데이트 애니메이션
        existingCard.style.transform = 'scale(1.02)';
        existingCard.style.boxShadow = '0 4px 15px rgba(52, 152, 219, 0.3)';
        setTimeout(() => {
            existingCard.style.transform = 'scale(1)';
            existingCard.style.boxShadow = '';
        }, 300);
    } else {
        // 새 카드 추가
        const noDataMsg = elements.deviceCards.querySelector('.no-data-message');
        if (noDataMsg) noDataMsg.remove();

        const newCard = document.createElement('div');
        newCard.className = 'device-data-card';
        newCard.dataset.deviceId = data.device_id;
        newCard.innerHTML = `
            <div class="card-header">
                <h3>${data.device_id}</h3>
                <span class="site-code-badge">${data.site_code || '-'}</span>
            </div>
            <div class="card-body">
                ${createDeviceSensorGroupsHTML(data)}
                <div class="device-timestamp">${formatTimestamp(data.received_at || new Date().toISOString())}</div>
            </div>
        `;

        elements.deviceCards.appendChild(newCard);
    }
}

/**
 * 최근 데이터 테이블 렌더링
 */
function renderRecentData(data) {
    if (!elements.recentDataBody) return;

    if (!data || data.length === 0) {
        elements.recentDataBody.innerHTML = `
            <tr>
                <td colspan="9" class="no-data-message">수신된 데이터가 없습니다.</td>
            </tr>
        `;
        return;
    }

    elements.recentDataBody.innerHTML = data.map(item => `
        <tr>
            <td>${item.device_id}</td>
            <td>${item.site_code || '-'}</td>
            <td>${formatValue(item.o2, 1)}</td>
            <td>${formatValue(item.co, 1)}</td>
            <td>${formatValue(item.co2, 0)}</td>
            <td>${formatValue(item.temp, 1)}</td>
            <td>${formatValue(item.humi, 1)}</td>
            <td>${formatValue(item.pm25, 0)}</td>
            <td>${formatTimestamp(item.received_at)}</td>
        </tr>
    `).join('');
}

/**
 * 최근 데이터 행 추가 (실시간)
 */
function addRecentDataRow(data) {
    if (!elements.recentDataBody) return;

    // "데이터 없음" 메시지 제거
    const noDataRow = elements.recentDataBody.querySelector('.no-data-message');
    if (noDataRow) {
        noDataRow.parentElement.remove();
    }

    // 새 행 추가
    const newRow = document.createElement('tr');
    newRow.innerHTML = `
        <td>${data.device_id}</td>
        <td>${data.site_code || '-'}</td>
        <td>${formatValue(data.o2, 1)}</td>
        <td>${formatValue(data.co, 1)}</td>
        <td>${formatValue(data.co2, 0)}</td>
        <td>${formatValue(data.temp, 1)}</td>
        <td>${formatValue(data.humi, 1)}</td>
        <td>${formatValue(data.pm25, 0)}</td>
        <td>${formatTimestamp(data.received_at || new Date().toISOString())}</td>
    `;

    // 맨 앞에 추가
    elements.recentDataBody.insertBefore(newRow, elements.recentDataBody.firstChild);

    // 최대 20개 유지
    while (elements.recentDataBody.children.length > 20) {
        elements.recentDataBody.removeChild(elements.recentDataBody.lastChild);
    }

    // 하이라이트 효과
    newRow.style.backgroundColor = '#d4edda';
    setTimeout(() => {
        newRow.style.backgroundColor = '';
    }, 1000);
}

/**
 * 알람 알림 팝업 표시
 */
function showAlarmNotification(data) {
    // 알람 레벨 정보
    const levelInfo = {
        0: { name: '정상', color: '#28a745' },
        1: { name: '주의', color: '#ffc107' },
        2: { name: '경고', color: '#fd7e14' },
        3: { name: '위험', color: '#dc3545' }
    };

    const level = parseInt(data.level) || 0;
    const levelData = levelInfo[level] || levelInfo[0];
    const sensorName = data.sensor_name || data.sensor_type || '알 수 없음';
    const sensorUnit = data.sensor_unit || '';
    const deviceId = data.device_id || '-';

    // 알림 요소 생성
    const notification = document.createElement('div');
    notification.className = 'alarm-notification';
    notification.style.borderLeftColor = levelData.color;
    notification.innerHTML = `
        <strong style="color: ${levelData.color}">새 알람! [${levelData.name}]</strong>
        <p><b>${sensorName}</b>: ${data.value} ${sensorUnit}</p>
        <p>장치: ${deviceId}</p>
        ${data.etc ? `<p>메모: ${data.etc}</p>` : ''}
    `;

    // 기존 알림들 위치 조정
    const existingNotifications = document.querySelectorAll('.alarm-notification');
    existingNotifications.forEach((el, index) => {
        el.style.top = `${80 + (index + 1) * 110}px`;
    });

    document.body.appendChild(notification);

    // 5초 후 알림 제거
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-in forwards';
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 5000);
}

/**
 * 로그 추가
 */
function addLog(message, type = 'info') {
    if (!elements.realtimeLog) return;

    const timestamp = new Date().toLocaleTimeString('ko-KR');
    const logEntry = document.createElement('p');
    logEntry.className = `log-message ${type}`;
    logEntry.textContent = `[${timestamp}] ${message}`;

    elements.realtimeLog.appendChild(logEntry);

    // 최대 100개 로그 유지
    while (elements.realtimeLog.children.length > 100) {
        elements.realtimeLog.removeChild(elements.realtimeLog.firstChild);
    }

    // 스크롤 아래로
    elements.realtimeLog.scrollTop = elements.realtimeLog.scrollHeight;
}

/**
 * 마지막 업데이트 시간 표시
 */
function updateLastUpdateTime() {
    if (elements.lastUpdate) {
        const now = new Date().toLocaleTimeString('ko-KR');
        elements.lastUpdate.textContent = `마지막 업데이트: ${now}`;
    }
}

/**
 * 값 포맷
 */
function formatValue(value, decimals = 1) {
    if (value === null || value === undefined) return '-';
    return parseFloat(value).toFixed(decimals);
}

/**
 * 타임스탬프 포맷
 */
function formatTimestamp(timestamp) {
    if (!timestamp) return '-';

    try {
        const date = new Date(timestamp);
        return date.toLocaleString('ko-KR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    } catch (e) {
        return timestamp;
    }
}

/**
 * 초기화
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('환경 센서 대시보드 초기화');

    // Socket.IO 연결
    initSocketIO();

    // 초기 데이터 로드
    loadDashboardData();

    // 새로고침 버튼
    if (elements.refreshBtn) {
        elements.refreshBtn.addEventListener('click', () => {
            addLog('데이터 새로고침...', 'info');
            loadDashboardData();
        });
    }

    // 주기적 상태 업데이트 (30초마다)
    setInterval(() => {
        updateMqttStatus();
    }, 30000);
});
