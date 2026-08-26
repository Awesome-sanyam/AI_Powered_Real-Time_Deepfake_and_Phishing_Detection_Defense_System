/**
 * Modular WebSocket client for Django Channels
 */
class ThreatWSClient {
    constructor(path) {
        // e.g. "alerts/" or "deepfake/1234/"
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.url = `${protocol}//${window.location.host}/ws/${path}`;
        this.socket = null;
        this.isConnected = false;
        
        // Callbacks
        this.onAlert = null;
        this.onMessage = null;
    }

    connect() {
        console.log(`[WS] Connecting to ${this.url}`);
        this.socket = new WebSocket(this.url);

        this.socket.onopen = () => {
            console.log(`[WS] Connected to ${this.url}`);
            this.isConnected = true;
            
            // Send initial ping/handshake
            this.send({ type: 'ping', timestamp: new Date().toISOString() });
        };

        this.socket.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                console.log(`[WS] Received:`, data);
                
                if (data.type === 'pong') {
                    console.log(`[WS] Handshake successful.`);
                }
                
                // Route to appropriate callback
                if (['deepfake', 'phishing', 'info'].includes(data.type)) {
                    if (this.onAlert) this.onAlert(data);
                }
                if (this.onMessage) {
                    this.onMessage(data);
                }
            } catch (err) {
                console.error("[WS] Parse error:", err);
            }
        };

        this.socket.onclose = (e) => {
            console.log(`[WS] Disconnected from ${this.url} (Code: ${e.code})`);
            this.isConnected = false;
            // Optionally implement reconnect logic here
        };

        this.socket.onerror = (err) => {
            console.error(`[WS] Error:`, err);
        };
    }

    send(data) {
        if (this.isConnected && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(data));
        } else {
            console.warn(`[WS] Cannot send, not connected.`);
        }
    }
}
