/**
 * SOCWebSocketClient — Production-Grade WebSocket Manager
 * =========================================================
 * Robust WebSocket wrapper for the AI Defence System SOC Dashboard.
 *
 * Features:
 *   - Auto-reconnect with exponential backoff (cap 10s)
 *   - Heartbeat ping every 25s to keep connection alive through proxies
 *   - Topic-based message routing via typed callbacks
 *   - Binary and text message support
 *   - Connection state machine with status change notifications
 *
 * Usage:
 *   const client = new SOCWebSocketClient('deepfake/session-abc-123/');
 *   client.onVerdict  = (v)  => renderVerdict(v);
 *   client.onAlert    = (a)  => showToast(a);
 *   client.onStatusChange = (s) => updateDot(s);
 *   client.connect();
 *   client.sendText({ type: 'ping' });
 *   client.sendBinary(jpegBytes);
 *   client.disconnect();
 *
 * Status values: 'connecting' | 'connected' | 'reconnecting' | 'disconnected'
 */

class SOCWebSocketClient {
    /**
     * @param {string} path - WS path relative to ws[s]://host/ws/
     *   e.g. "alerts/" or "deepfake/my-session-id/"
     */
    constructor(path) {
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this._url = `${proto}//${window.location.host}/ws/${path}`;
        this._path = path;
        this._socket = null;
        this._status = 'disconnected';

        // Reconnect state
        this._reconnectAttempts = 0;
        this._reconnectTimer = null;
        this._maxBackoffMs = 10000;
        this._intentionalClose = false;

        // Heartbeat state
        this._heartbeatTimer = null;
        this._heartbeatIntervalMs = 25000;
        this._missedPongs = 0;
        this._maxMissedPongs = 2;

        // ── Public callbacks ───────────────────────────────────────────────────
        /** Called with verdict payload when AI engine returns a signed verdict. */
        this.onVerdict = null;
        /** Called with alert payload for real-time threat events. */
        this.onAlert = null;
        /** Called with status string when connection state changes. */
        this.onStatusChange = null;
        /** Called with raw message data for any unhandled message types. */
        this.onMessage = null;
    }

    // ── Public API ─────────────────────────────────────────────────────────────

    /** Open the WebSocket connection. */
    connect() {
        if (this._socket && this._socket.readyState === WebSocket.OPEN) return;
        this._intentionalClose = false;
        this._setStatus('connecting');
        this._createSocket();
    }

    /** Gracefully close the connection without triggering reconnect. */
    disconnect() {
        this._intentionalClose = true;
        this._stopHeartbeat();
        this._clearReconnectTimer();
        if (this._socket) {
            this._socket.close(1000, 'Client disconnecting');
        }
        this._setStatus('disconnected');
    }

    /** Send a JSON-serialisable object as a text frame. */
    sendText(data) {
        if (!this._isOpen()) {
            console.warn(`[SOC-WS] Cannot send text — not connected (${this._path})`);
            return false;
        }
        this._socket.send(JSON.stringify(data));
        return true;
    }

    /** Send raw binary data (e.g. JPEG frame bytes). */
    sendBinary(buffer) {
        if (!this._isOpen()) {
            console.warn(`[SOC-WS] Cannot send binary — not connected (${this._path})`);
            return false;
        }
        this._socket.send(buffer);
        return true;
    }

    /** Returns true if the socket is currently open. */
    get isConnected() {
        return this._status === 'connected';
    }

    // ── Private: socket lifecycle ──────────────────────────────────────────────

    _createSocket() {
        const ws = new WebSocket(this._url);
        ws.binaryType = 'arraybuffer';
        this._socket = ws;

        ws.onopen = () => {
            console.log(`[SOC-WS] Connected: ${this._url}`);
            this._reconnectAttempts = 0;
            this._missedPongs = 0;
            this._setStatus('connected');
            this._startHeartbeat();
        };

        ws.onmessage = (evt) => {
            this._handleMessage(evt);
        };

        ws.onclose = (evt) => {
            this._stopHeartbeat();
            if (this._intentionalClose) {
                console.log(`[SOC-WS] Closed intentionally: ${this._path}`);
                return;
            }
            console.warn(`[SOC-WS] Connection lost (code=${evt.code}): ${this._path}`);
            this._setStatus('reconnecting');
            this._scheduleReconnect();
        };

        ws.onerror = (err) => {
            console.error(`[SOC-WS] Socket error on ${this._path}:`, err);
        };
    }

    _handleMessage(evt) {
        // Binary messages: pass raw to onMessage
        if (evt.data instanceof ArrayBuffer) {
            if (this.onMessage) this.onMessage({ _binary: true, data: evt.data });
            return;
        }

        let msg;
        try {
            msg = JSON.parse(evt.data);
        } catch (e) {
            console.warn('[SOC-WS] Non-JSON message received:', evt.data);
            return;
        }

        const type = msg.type || '';

        // Heartbeat pong
        if (type === 'pong' || type === 'connection.established') {
            this._missedPongs = 0;
            return;
        }

        // Signed deepfake/phishing verdict
        if (type === 'verdict' || msg.signed_verdict !== undefined) {
            if (this.onVerdict) { this.onVerdict(msg); return; }
        }

        // Threat alerts (alert_feed group messages)
        if (['deepfake', 'phishing', 'identity', 'info'].includes(type)) {
            if (this.onAlert) { this.onAlert(msg); return; }
        }

        // Fallthrough: raw handler
        if (this.onMessage) this.onMessage(msg);
    }

    // ── Private: reconnect ─────────────────────────────────────────────────────

    _scheduleReconnect() {
        this._clearReconnectTimer();
        const delay = Math.min(
            500 * Math.pow(2, this._reconnectAttempts),
            this._maxBackoffMs
        );
        this._reconnectAttempts++;
        console.log(`[SOC-WS] Reconnect in ${delay}ms (attempt ${this._reconnectAttempts}): ${this._path}`);
        this._reconnectTimer = setTimeout(() => {
            if (!this._intentionalClose) {
                this._createSocket();
            }
        }, delay);
    }

    _clearReconnectTimer() {
        if (this._reconnectTimer) {
            clearTimeout(this._reconnectTimer);
            this._reconnectTimer = null;
        }
    }

    // ── Private: heartbeat ─────────────────────────────────────────────────────

    _startHeartbeat() {
        this._stopHeartbeat();
        this._heartbeatTimer = setInterval(() => {
            if (!this._isOpen()) return;
            this._missedPongs++;
            if (this._missedPongs > this._maxMissedPongs) {
                console.warn(`[SOC-WS] Heartbeat timeout — forcing reconnect: ${this._path}`);
                this._socket.close();
                return;
            }
            this._socket.send(JSON.stringify({ type: 'ping', ts: Date.now() }));
        }, this._heartbeatIntervalMs);
    }

    _stopHeartbeat() {
        if (this._heartbeatTimer) {
            clearInterval(this._heartbeatTimer);
            this._heartbeatTimer = null;
        }
    }

    // ── Private: helpers ───────────────────────────────────────────────────────

    _isOpen() {
        return this._socket && this._socket.readyState === WebSocket.OPEN;
    }

    _setStatus(status) {
        this._status = status;
        if (this.onStatusChange) this.onStatusChange(status);
    }
}

// Keep legacy alias for backwards-compatibility with existing base.html
class ThreatWSClient extends SOCWebSocketClient {
    constructor(path) {
        super(path);
        // Map legacy onAlert callback
        this.onAlert = null;
        const _super_setStatus = this._setStatus.bind(this);
        this._setStatus = (s) => {
            _super_setStatus(s);
        };
    }
}
