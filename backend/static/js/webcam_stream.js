/**
 * WebcamStreamManager — Real-Time Deepfake Frame Streamer
 * =========================================================
 * Handles the full webcam → WebSocket → verdict pipeline on the client side.
 *
 * Pipeline:
 *   getUserMedia (video+audio)
 *     → HTMLVideoElement (visible, shown to user)
 *     → Offscreen HTMLCanvasElement (hidden, JPEG encoding)
 *     → base64 JPEG strings → SOCWebSocketClient (text frames)
 *     → AudioContext ScriptProcessorNode → Int16 PCM → base64 audio chunks
 *
 * HUD Overlay:
 *   A second canvas is drawn on top of the video element showing:
 *     - Confidence badge (top-right corner)
 *     - FPS counter (top-left corner)
 *     - Status indicator
 *     - Colour-coded threat border (green/yellow/red)
 *
 * Usage:
 *   const mgr = new WebcamStreamManager({
 *     videoEl:     document.getElementById('webcam-video'),
 *     hudCanvas:   document.getElementById('hud-canvas'),
 *     sessionId:   'session-abc-123',
 *     targetFps:   12,
 *     jpegQuality: 0.75,
 *     captureAudio: true,
 *     onVerdict:   (v) => updateMetricsPanel(v),
 *   });
 *   await mgr.start();
 *   mgr.stop();
 */

class WebcamStreamManager {
    /**
     * @param {Object} opts
     * @param {HTMLVideoElement}  opts.videoEl       - Visible video element
     * @param {HTMLCanvasElement} opts.hudCanvas      - Canvas overlaid on video for HUD
     * @param {string}            opts.sessionId      - Scan session UUID
     * @param {number}            [opts.targetFps=12] - Target capture FPS (10–15 recommended)
     * @param {number}            [opts.jpegQuality]  - JPEG quality 0.0–1.0
     * @param {boolean}           [opts.captureAudio] - Also stream audio PCM chunks
     * @param {Function}          [opts.onVerdict]    - Callback receiving verdict objects
     * @param {Function}          [opts.onStatusChange] - Callback receiving stream status
     */
    constructor(opts) {
        this._videoEl       = opts.videoEl;
        this._hudCanvas     = opts.hudCanvas;
        this._sessionId     = opts.sessionId;
        this._targetFps     = opts.targetFps || 12;
        this._jpegQuality   = opts.jpegQuality || 0.75;
        this._captureAudio  = opts.captureAudio !== undefined ? opts.captureAudio : true;
        this.onVerdict      = opts.onVerdict || null;
        this.onStatusChange = opts.onStatusChange || null;

        // Internal state
        this._stream        = null;
        this._offscreenCanvas = null;
        this._offscreenCtx  = null;
        this._captureTimer  = null;
        this._wsClient      = null;
        this._audioCtx      = null;
        this._audioProcessor = null;
        this._isStreaming   = false;

        // HUD state
        this._hudCtx        = this._hudCanvas ? this._hudCanvas.getContext('2d') : null;
        this._lastVerdict   = null;
        this._frameCount    = 0;
        this._fpsStartTime  = Date.now();
        this._displayFps    = 0;
        this._hudAnimFrame  = null;
    }

    // ── Public API ──────────────────────────────────────────────────────────────

    /**
     * Initialise webcam, audio, WebSocket and begin streaming.
     * @returns {Promise<void>}
     */
    async start() {
        if (this._isStreaming) return;
        try {
            await this._initMediaStream();
            this._initOffscreenCanvas();
            this._initWebSocket();
            if (this._captureAudio) this._initAudioCapture();
            this._startCapture();
            this._startHUD();
            this._isStreaming = true;
            this._setStatus('streaming');
        } catch (err) {
            this._setStatus('error');
            throw err;
        }
    }

    /** Stop streaming, release camera and microphone. */
    stop() {
        this._isStreaming = false;
        this._stopCapture();
        this._stopAudioCapture();
        this._stopHUD();
        this._releaseMediaStream();
        if (this._wsClient) {
            this._wsClient.disconnect();
            this._wsClient = null;
        }
        this._setStatus('stopped');
    }

    /** Pause frame capture (keeps camera open, stops sending frames). */
    pause() {
        this._stopCapture();
        this._setStatus('paused');
    }

    /** Resume frame capture after pause. */
    resume() {
        if (this._isStreaming) {
            this._startCapture();
            this._setStatus('streaming');
        }
    }

    // ── Private: media stream ───────────────────────────────────────────────────

    async _initMediaStream() {
        const constraints = {
            video: { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { max: 30 } },
            audio: this._captureAudio,
        };
        this._stream = await navigator.mediaDevices.getUserMedia(constraints);
        this._videoEl.srcObject = this._stream;
        await new Promise((resolve) => { this._videoEl.onloadedmetadata = resolve; });
        this._videoEl.play();
        console.log('[Webcam] Stream started:', this._stream.id);
    }

    _releaseMediaStream() {
        if (this._stream) {
            this._stream.getTracks().forEach((t) => t.stop());
            this._stream = null;
        }
        this._videoEl.srcObject = null;
    }

    // ── Private: offscreen canvas ───────────────────────────────────────────────

    _initOffscreenCanvas() {
        const w = this._videoEl.videoWidth  || 640;
        const h = this._videoEl.videoHeight || 480;
        this._offscreenCanvas = document.createElement('canvas');
        this._offscreenCanvas.width  = w;
        this._offscreenCanvas.height = h;
        this._offscreenCtx = this._offscreenCanvas.getContext('2d');
    }

    // ── Private: frame capture loop ─────────────────────────────────────────────

    _startCapture() {
        this._stopCapture();
        const interval = Math.round(1000 / this._targetFps);
        this._captureTimer = setInterval(() => this._captureFrame(), interval);
    }

    _stopCapture() {
        if (this._captureTimer) {
            clearInterval(this._captureTimer);
            this._captureTimer = null;
        }
    }

    _captureFrame() {
        if (!this._wsClient || !this._wsClient.isConnected) return;
        if (!this._videoEl.videoWidth) return;

        try {
            // Draw current video frame onto offscreen canvas
            this._offscreenCtx.drawImage(
                this._videoEl,
                0, 0,
                this._offscreenCanvas.width,
                this._offscreenCanvas.height
            );

            // Encode as JPEG base64
            const dataUrl = this._offscreenCanvas.toDataURL('image/jpeg', this._jpegQuality);
            const b64 = dataUrl.split(',')[1];

            // Send as JSON text frame (server expects frames_b64 list, we stream one at a time)
            this._wsClient.sendText({
                type: 'video_frame',
                data: b64,
                session_id: this._sessionId,
                fps: this._targetFps,
                ts: Date.now(),
            });

            // Track FPS
            this._frameCount++;
            const elapsed = (Date.now() - this._fpsStartTime) / 1000;
            if (elapsed >= 1.0) {
                this._displayFps = Math.round(this._frameCount / elapsed);
                this._frameCount = 0;
                this._fpsStartTime = Date.now();
            }
        } catch (err) {
            console.warn('[Webcam] Frame capture error:', err);
        }
    }

    // ── Private: audio capture ──────────────────────────────────────────────────

    _initAudioCapture() {
        try {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            this._audioCtx = new AudioCtx({ sampleRate: 16000 });
            const source = this._audioCtx.createMediaStreamSource(this._stream);

            // ScriptProcessorNode: capture raw PCM samples
            const bufferSize = 4096;
            this._audioProcessor = this._audioCtx.createScriptProcessor(bufferSize, 1, 1);
            this._audioProcessor.onaudioprocess = (evt) => {
                if (!this._wsClient || !this._wsClient.isConnected) return;
                const float32 = evt.inputBuffer.getChannelData(0);
                const int16 = this._float32ToInt16(float32);
                const b64 = this._int16ToBase64(int16);
                this._wsClient.sendText({
                    type: 'audio_chunk',
                    data: b64,
                    session_id: this._sessionId,
                    sample_rate: 16000,
                });
            };

            source.connect(this._audioProcessor);
            this._audioProcessor.connect(this._audioCtx.destination);
            console.log('[Webcam] Audio capture started');
        } catch (err) {
            console.warn('[Webcam] Audio capture init failed (non-critical):', err);
        }
    }

    _stopAudioCapture() {
        if (this._audioProcessor) {
            this._audioProcessor.disconnect();
            this._audioProcessor = null;
        }
        if (this._audioCtx) {
            this._audioCtx.close();
            this._audioCtx = null;
        }
    }

    _float32ToInt16(float32Array) {
        const int16 = new Int16Array(float32Array.length);
        for (let i = 0; i < float32Array.length; i++) {
            const clamped = Math.max(-1.0, Math.min(1.0, float32Array[i]));
            int16[i] = clamped < 0 ? clamped * 32768 : clamped * 32767;
        }
        return int16;
    }

    _int16ToBase64(int16Array) {
        const bytes = new Uint8Array(int16Array.buffer);
        let binary = '';
        for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    }

    // ── Private: WebSocket ──────────────────────────────────────────────────────

    _initWebSocket() {
        this._wsClient = new SOCWebSocketClient(`deepfake/${this._sessionId}/`);
        this._wsClient.onVerdict = (v) => {
            this._lastVerdict = v;
            if (this.onVerdict) this.onVerdict(v);
        };
        this._wsClient.onStatusChange = (s) => {
            console.log(`[Webcam] WS status: ${s}`);
        };
        this._wsClient.connect();
    }

    // ── Private: HUD overlay ────────────────────────────────────────────────────

    _startHUD() {
        if (!this._hudCtx) return;
        const draw = () => {
            this._drawHUD();
            this._hudAnimFrame = requestAnimationFrame(draw);
        };
        this._hudAnimFrame = requestAnimationFrame(draw);
    }

    _stopHUD() {
        if (this._hudAnimFrame) {
            cancelAnimationFrame(this._hudAnimFrame);
            this._hudAnimFrame = null;
        }
        if (this._hudCtx) {
            this._hudCtx.clearRect(0, 0, this._hudCanvas.width, this._hudCanvas.height);
        }
    }

    _drawHUD() {
        const ctx = this._hudCtx;
        const w = this._hudCanvas.width;
        const h = this._hudCanvas.height;

        ctx.clearRect(0, 0, w, h);

        const v = this._lastVerdict;
        const confidence = v ? (v.confidence || 0) : 0;
        const isFake = v ? v.is_deepfake : false;

        // Border glow colour based on verdict
        let borderColor = '#22c55e'; // green: real / no verdict
        if (isFake && confidence >= 0.8)  borderColor = '#ef4444'; // red: high-conf fake
        else if (isFake)                  borderColor = '#f59e0b'; // amber: uncertain

        // Draw coloured border
        ctx.strokeStyle = borderColor;
        ctx.lineWidth = 4;
        ctx.shadowColor = borderColor;
        ctx.shadowBlur = 12;
        ctx.strokeRect(2, 2, w - 4, h - 4);
        ctx.shadowBlur = 0;

        // FPS counter (top-left)
        ctx.fillStyle = 'rgba(0,0,0,0.6)';
        ctx.fillRect(8, 8, 80, 24);
        ctx.fillStyle = '#94a3b8';
        ctx.font = '13px monospace';
        ctx.fillText(`${this._displayFps} FPS`, 14, 25);

        // Confidence badge (top-right)
        if (v) {
            const label = isFake ? '⚠ FAKE' : '✓ REAL';
            const badgeColor = isFake ? '#ef4444' : '#22c55e';
            const badgeW = 90;
            ctx.fillStyle = 'rgba(0,0,0,0.7)';
            ctx.fillRect(w - badgeW - 8, 8, badgeW, 24);
            ctx.fillStyle = badgeColor;
            ctx.font = 'bold 13px monospace';
            ctx.fillText(`${label} ${Math.round(confidence * 100)}%`, w - badgeW - 2, 25);
        }

        // ECDSA badge (bottom-right)
        if (v && v.signed_verdict) {
            ctx.fillStyle = 'rgba(0,0,0,0.7)';
            ctx.fillRect(w - 132, h - 32, 124, 22);
            ctx.fillStyle = '#60a5fa';
            ctx.font = '11px monospace';
            ctx.fillText('🔐 ECDSA VERIFIED', w - 128, h - 16);
        }
    }

    // ── Private: helpers ────────────────────────────────────────────────────────

    _setStatus(status) {
        if (this.onStatusChange) this.onStatusChange(status);
    }
}
