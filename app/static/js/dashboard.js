/**
 * 대시보드 JavaScript
 * Socket.IO를 통한 실시간 데이터 업데이트 및 UI 관리
 */

// Socket.IO 연결
let socket = null;
let isConnected = false;

// DOM 요소
const elements = {
    mqttStatus: document.getElementById('mqtt-status'),
    mqttConnectionStatus: document.getElementById('mqtt-connection-status'),
    activeSensorsCount: document.getElementById('active-sensors-count'),
    totalDataCount: document.getElementById('total-data-count'),
    sensorCards: document.getElementById('sensor-cards'),
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

    // 실시간 센서 데이터 수신
    socket.on('sensor_data', (data) => {
        console.log('센서 데이터 수신:', data);
        updateSensorCard(data);
        addRecentDataRow(data);
        addLog(`데이터 수신: ${data.sensor_id} = ${data.value} ${data.unit}`, 'info');
        updateLastUpdateTime();
    });

    socket.on('latest_data', (data) => {
        console.log('최신 데이터:', data);
    });

    socket.on('error', (data) => {
        console.error('오류:', data);
        addLog(`오류: ${data.message}`, 'error');
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
                const totalData = healthResult.data.data_counts.sensor_data || 0;
                elements.totalDataCount.textContent = `${totalData.toLocaleString()}건`;
            }
        }

        // 센서 목록
        const sensorsResponse = await fetch('/api/sensors?active=true');
        const sensorsResult = await sensorsResponse.json();

        if (sensorsResult.success) {
            if (elements.activeSensorsCount) {
                elements.activeSensorsCount.textContent = `${sensorsResult.data.count}개`;
            }
        }

        // 센서별 최신 데이터
        const latestResponse = await fetch('/api/data/latest-by-sensor');
        const latestResult = await latestResponse.json();

        if (latestResult.success) {
            renderSensorCards(latestResult.data.data);
        }

        // 최근 데이터
        const recentResponse = await fetch('/api/data/latest?limit=20');
        const recentResult = await recentResponse.json();

        if (recentResult.success) {
            renderRecentData(recentResult.data.data);
        }

        updateLastUpdateTime();
        addLog('데이터 로드 완료', 'success');

    } catch (error) {
        console.error('데이터 로드 실패:', error);
        addLog(`데이터 로드 실패: ${error.message}`, 'error');
    }
}

/**
 * 센서 카드 렌더링
 */
function renderSensorCards(data) {
    if (!elements.sensorCards) return;

    if (!data || data.length === 0) {
        elements.sensorCards.innerHTML = '<p class="no-data-message">수신된 센서 데이터가 없습니다.</p>';
        return;
    }

    elements.sensorCards.innerHTML = data.map(sensor => `
        <div class="sensor-data-card" data-sensor-id="${sensor.sensor_id}">
            <div class="card-header">
                <h3>${sensor.sensor_id}</h3>
                <span class="sensor-type-badge ${sensor.sensor_type}">${sensor.sensor_type}</span>
            </div>
            <div class="card-body">
                <div class="sensor-value">${parseFloat(sensor.value).toFixed(2)}</div>
                <div class="sensor-unit">${sensor.unit}</div>
                <div class="sensor-timestamp">${formatTimestamp(sensor.received_at)}</div>
            </div>
        </div>
    `).join('');
}

/**
 * 센서 카드 업데이트 (실시간)
 */
function updateSensorCard(data) {
    if (!elements.sensorCards) return;

    const existingCard = elements.sensorCards.querySelector(`[data-sensor-id="${data.sensor_id}"]`);

    if (existingCard) {
        // 기존 카드 업데이트
        const valueEl = existingCard.querySelector('.sensor-value');
        const unitEl = existingCard.querySelector('.sensor-unit');
        const timestampEl = existingCard.querySelector('.sensor-timestamp');

        if (valueEl) valueEl.textContent = parseFloat(data.value).toFixed(2);
        if (unitEl) unitEl.textContent = data.unit;
        if (timestampEl) timestampEl.textContent = formatTimestamp(data.timestamp);

        // 업데이트 애니메이션
        existingCard.style.transform = 'scale(1.02)';
        setTimeout(() => {
            existingCard.style.transform = 'scale(1)';
        }, 200);
    } else {
        // 새 카드 추가
        const newCard = document.createElement('div');
        newCard.className = 'sensor-data-card';
        newCard.dataset.sensorId = data.sensor_id;
        newCard.innerHTML = `
            <div class="card-header">
                <h3>${data.sensor_id}</h3>
                <span class="sensor-type-badge ${data.sensor_type}">${data.sensor_type}</span>
            </div>
            <div class="card-body">
                <div class="sensor-value">${parseFloat(data.value).toFixed(2)}</div>
                <div class="sensor-unit">${data.unit}</div>
                <div class="sensor-timestamp">${formatTimestamp(data.timestamp)}</div>
            </div>
        `;

        // "데이터 없음" 메시지 제거
        const noDataMsg = elements.sensorCards.querySelector('.no-data-message');
        if (noDataMsg) noDataMsg.remove();

        elements.sensorCards.appendChild(newCard);
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
                <td colspan="5" class="no-data-message">수신된 데이터가 없습니다.</td>
            </tr>
        `;
        return;
    }

    elements.recentDataBody.innerHTML = data.map(item => `
        <tr>
            <td>${item.sensor_id}</td>
            <td><span class="sensor-type-badge ${item.sensor_type}">${item.sensor_type}</span></td>
            <td class="value-cell">${parseFloat(item.value).toFixed(2)}</td>
            <td>${item.unit}</td>
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
        <td>${data.sensor_id}</td>
        <td><span class="sensor-type-badge ${data.sensor_type}">${data.sensor_type}</span></td>
        <td class="value-cell">${parseFloat(data.value).toFixed(2)}</td>
        <td>${data.unit}</td>
        <td>${formatTimestamp(data.timestamp || new Date().toISOString())}</td>
    `;

    // 맨 앞에 추가
    elements.recentDataBody.insertBefore(newRow, elements.recentDataBody.firstChild);

    // 최대 20개 유지
    while (elements.recentDataBody.children.length > 20) {
        elements.recentDataBody.removeChild(elements.recentDataBody.lastChild);
    }

    // 하이라이트 효과
    newRow.style.backgroundColor = '#fff3cd';
    setTimeout(() => {
        newRow.style.backgroundColor = '';
    }, 1000);
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
    console.log('대시보드 초기화');

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
