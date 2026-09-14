/**
 * WebcamStreamManager / WebcamStreamController — Real-Time Deepfake Frame Streamer
 * ===============================================================================
 * Handles the full webcam → WebSocket → verdict pipeline on the client side.
 * Supports both hardware webcam streams and synthetic simulation feeds.
 *
 * Pipeline:
 *   getUserMedia (video+audio) / Synthetic Canvas Stream
 *     → HTMLVideoElement (visible, shown to user)
 *     → Offscreen HTMLCanvasElement (hidden, JPEG encoding)
 *     → base64 JPEG strings → SOCWebSocketClient (text frames)
 *     → AudioContext ScriptProcessorNode → Int16 PCM → base64 audio chunks
 *
 * HUD Overlay:
 *   A second canvas is drawn on top of the video element showing:
 *     - Confidence badge (top-right corner)
 *     - FPS counter + Live indicator (top-left corner)
 *     - Colour-coded threat border (green/yellow/red)
 *     - Cryptographic ECDSA Attestation pill (bottom-right)
 */

class WebcamStreamManager {
    /**
     * @param {Object} opts
     * @param {HTMLVideoElement}  [opts.videoEl]       - Visible video element
     * @param {HTMLVideoElement}  [opts.videoElement] - Alias for videoEl
     * @param {HTMLCanvasElement} opts.hudCanvas      - Canvas overlaid on video for HUD
     * @param {string}            [opts.sessionId]    - Scan session UUID
     * @param {number}            [opts.targetFps=12] - Target capture FPS (10–15 recommended)
     * @param {number}            [opts.jpegQuality]  - JPEG quality 0.0–1.0
     * @param {boolean}           [opts.captureAudio] - Also stream audio PCM chunks
     * @param {Function}          [opts.onVerdict]    - Callback receiving verdict objects
     * @param {Function}          [opts.onStatusChange] - Callback receiving stream status
     * @param {Function}          [opts.onFpsUpdate]  - Callback receiving (fps, resolution)
     */
    constructor(opts = {}) {
        this._videoEl       = opts.videoEl || opts.videoElement || null;
        this._hudCanvas     = opts.hudCanvas || null;
        this._sessionId     = opts.sessionId || this._generateSessionId();
        this._targetFps     = opts.targetFps || 12;
        this._jpegQuality   = opts.jpegQuality || 0.75;
        this._captureAudio  = opts.captureAudio !== undefined ? Boolean(opts.captureAudio) : true;
        this.onVerdict      = opts.onVerdict || null;
        this.onStatusChange = opts.onStatusChange || null;
        this.onFpsUpdate    = opts.onFpsUpdate || null;

        // Internal state
        this._stream          = null;
        this._isSynthetic     = false;
        this._syntheticCanvas = null;
        this._syntheticTimer  = null;
        this._offscreenCanvas = null;
        this._offscreenCtx    = null;
        this._captureTimer    = null;
        this._wsClient        = null;
        this._audioCtx        = null;
        this._audioProcessor  = null;
        this._isStreaming     = false;

        // HUD state
        this._hudCtx        = this._hudCanvas ? this._hudCanvas.getContext('2d') : null;
        this._lastVerdict   = null;
        this._frameCount    = 0;
        this._fpsStartTime  = Date.now();
        this._displayFps    = 0;
        this._hudAnimFrame  = null;
    }

    get sessionId() {
        return this._sessionId;
    }

    get isStreaming() {
        return this._isStreaming;
    }

    get isSynthetic() {
        return this._isSynthetic;
    }

    get captureAudio() {
        return this._captureAudio;
    }

    set captureAudio(val) {
        this._captureAudio = Boolean(val);
    }

    // ── Public API ──────────────────────────────────────────────────────────────

    /**
     * Initialise physical webcam, audio, WebSocket and begin streaming.
     * @returns {Promise<void>}
     */
    async start() {
        if (this._isStreaming) return;
        this._isSynthetic = false;
        try {
            await this._initMediaStream();
            this._initOffscreenCanvas();
            this._initWebSocket();
            if (this._captureAudio && !this._isSynthetic) {
                this._initAudioCapture();
            }
            this._startCapture();
            this._startHUD();
            this._isStreaming = true;
            this._setStatus('streaming');
        } catch (err) {
            this.stop();
            this._setStatus('error');
            throw err;
        }
    }

    /**
     * Initialise synthetic simulated multi-modal video stream (ideal for testing or
     * when camera permissions are unavailable).
     * @returns {Promise<void>}
     */
    async startSyntheticStream() {
        if (this._isStreaming) {
            this.stop();
        }
        this._isSynthetic = true;
        try {
            this._initSyntheticMediaStream();
            this._initOffscreenCanvas();
            this._initWebSocket();
            this._startCapture();
            this._startHUD();
            this._isStreaming = true;
            this._setStatus('streaming');
        } catch (err) {
            this.stop();
            this._setStatus('error');
            throw err;
        }
    }

    /** Stop streaming, release camera, microphone and timers. */
    stop() {
        this._isStreaming = false;
        this._stopCapture();
        this._stopAudioCapture();
        this._stopHUD();
        this._stopSyntheticMediaStream();
        this._releaseMediaStream();
        if (this._wsClient) {
            try {
                this._wsClient.disconnect();
            } catch (e) {
                console.warn('[Webcam] Error disconnecting WS:', e);
            }
            this._wsClient = null;
        }
        this._setStatus('stopped');
    }

    /** Pause frame capture (keeps camera open, pauses dispatch). */
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
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error('navigator.mediaDevices.getUserMedia is not supported by your browser.');
        }

        const baseConstraints = {
            video: {
                width: { ideal: 640 },
                height: { ideal: 480 },
                frameRate: { max: 30 }
            }
        };

        let stream = null;

        // Attempt 1: Video + Audio if enabled
        if (this._captureAudio) {
            try {
                stream = await navigator.mediaDevices.getUserMedia({
                    ...baseConstraints,
                    audio: true
                });
            } catch (micErr) {
                console.warn('[Webcam] Audio access denied or missing; falling back to video-only stream:', micErr);
                this._captureAudio = false;
            }
        }

        // Attempt 2: Video-only fallback
        if (!stream) {
            stream = await navigator.mediaDevices.getUserMedia({
                ...baseConstraints,
                audio: false
            });
        }

        this._stream = stream;
        if (this._videoEl) {
            this._videoEl.srcObject = this._stream;
            await new Promise((resolve) => {
                if (this._videoEl.readyState >= 1) {
                    resolve();
                } else {
                    this._videoEl.onloadedmetadata = () => resolve();
                    setTimeout(resolve, 1200); // Safety timeout
                }
            });
            try {
                await this._videoEl.play();
            } catch (playErr) {
                console.warn('[Webcam] Video autoplay blocked; unmuting fallback:', playErr);
            }
        }
        console.log('[Webcam] Hardware media stream active:', stream.id);
    }

    _initSyntheticMediaStream() {
        const canvas = document.createElement('canvas');
        canvas.width = 640;
        canvas.height = 480;
        const ctx = canvas.getContext('2d');
        this._syntheticCanvas = canvas;

        let frameIdx = 0;
        const renderLoop = () => {
            if (!this._syntheticCanvas) return;
            frameIdx++;
            const t = Date.now() / 1000;

            // Dark background gradient
            const grad = ctx.createLinearGradient(0, 0, 640, 480);
            grad.addColorStop(0, '#09090b');
            grad.addColorStop(1, '#18181b');
            ctx.fillStyle = grad;
            ctx.fillRect(0, 0, 640, 480);

            // SOC Grid lines
            ctx.strokeStyle = 'rgba(99, 102, 241, 0.12)';
            ctx.lineWidth = 1;
            for (let x = 0; x < 640; x += 40) {
                ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, 480); ctx.stroke();
            }
            for (let y = 0; y < 480; y += 40) {
                ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(640, y); ctx.stroke();
            }

            // Animated Simulated Human Face Mesh
            const headX = 320 + Math.sin(t * 0.9) * 14;
            const headY = 225 + Math.cos(t * 0.6) * 8;

            // Face silhouette contour
            ctx.fillStyle = 'rgba(244, 244, 245, 0.06)';
            ctx.strokeStyle = 'rgba(99, 102, 241, 0.7)';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.ellipse(headX, headY, 95, 125, 0, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();

            // Eyes with simulated blinking
            const isBlinking = (frameIdx % 70 < 6);
            ctx.fillStyle = '#818cf8';
            if (isBlinking) {
                ctx.fillRect(headX - 45, headY - 25, 25, 2);
                ctx.fillRect(headX + 20, headY - 25, 25, 2);
            } else {
                ctx.beginPath();
                ctx.ellipse(headX - 32, headY - 25, 12, 7, 0, 0, Math.PI * 2);
                ctx.ellipse(headX + 32, headY - 25, 12, 7, 0, 0, Math.PI * 2);
                ctx.fill();
            }

            // Mouth with lip-sync speech motion
            const mouthHeight = 4 + Math.abs(Math.sin(t * 5.2)) * 14;
            ctx.strokeStyle = '#a855f7';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.ellipse(headX, headY + 52, 28, mouthHeight, 0, 0, Math.PI * 2);
            ctx.stroke();

            // Telemetry watermarks
            ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
            ctx.fillRect(20, 20, 290, 52);
            ctx.strokeStyle = 'rgba(99, 102, 241, 0.4)';
            ctx.strokeRect(20, 20, 290, 52);

            ctx.fillStyle = '#818cf8';
            ctx.font = 'bold 12px monospace';
            ctx.fillText('● AI SYNTHETIC TEST FEED ACTIVE', 32, 41);
            ctx.fillStyle = '#94a3b8';
            ctx.font = '10px monospace';
            ctx.fillText(`SESSION: ${this._sessionId.slice(0, 14)}… · 12 FPS`, 32, 58);
        };

        const interval = Math.round(1000 / this._targetFps);
        this._syntheticTimer = setInterval(renderLoop, interval);
        renderLoop();

        if (typeof canvas.captureStream === 'function') {
            this._stream = canvas.captureStream(this._targetFps);
        } else {
            throw new Error('HTMLCanvasElement.captureStream is not supported in this browser.');
        }

        if (this._videoEl) {
            this._videoEl.srcObject = this._stream;
            this._videoEl.play().catch(() => {});
        }
        console.log('[Webcam] Synthetic media feed active');
    }

    _stopSyntheticMediaStream() {
        if (this._syntheticTimer) {
            clearInterval(this._syntheticTimer);
            this._syntheticTimer = null;
        }
        this._syntheticCanvas = null;
    }

    _releaseMediaStream() {
        if (this._stream) {
            this._stream.getTracks().forEach((t) => t.stop());
            this._stream = null;
        }
        if (this._videoEl) {
            this._videoEl.srcObject = null;
        }
    }

    // ── Private: offscreen canvas ───────────────────────────────────────────────

    _initOffscreenCanvas() {
        const w = (this._videoEl && this._videoEl.videoWidth) ? this._videoEl.videoWidth : 640;
        const h = (this._videoEl && this._videoEl.videoHeight) ? this._videoEl.videoHeight : 480;
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
        if (!this._videoEl) return;

        const vw = this._videoEl.videoWidth || 640;
        const vh = this._videoEl.videoHeight || 480;

        try {
            if (!this._offscreenCanvas || this._offscreenCanvas.width !== vw || this._offscreenCanvas.height !== vh) {
                this._initOffscreenCanvas();
            }

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
            if (!b64) return;

            // Send as JSON text frame to DeepfakeStreamConsumer
            this._wsClient.sendText({
                type: 'video_frame',
                data: b64,
                session_id: this._sessionId,
                fps: this._targetFps,
                ts: Date.now(),
            });

            // Track FPS & Resolution
            this._frameCount++;
            const elapsed = (Date.now() - this._fpsStartTime) / 1000;
            if (elapsed >= 1.0) {
                this._displayFps = Math.round(this._frameCount / elapsed);
                this._frameCount = 0;
                this._fpsStartTime = Date.now();
                const resText = `${vw}x${vh}`;
                if (this.onFpsUpdate) {
                    this.onFpsUpdate(this._displayFps, resText);
                }
            }
        } catch (err) {
            console.warn('[Webcam] Frame capture error:', err);
        }
    }

    // ── Private: audio capture ──────────────────────────────────────────────────

    _initAudioCapture() {
        if (!this._stream || !this._stream.getAudioTracks().length) return;
        try {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (!AudioCtx) return;

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
            console.log('[Webcam] Audio capture started (16kHz PCM)');
        } catch (err) {
            console.warn('[Webcam] Audio capture init failed (non-critical):', err);
        }
    }

    _stopAudioCapture() {
        if (this._audioProcessor) {
            try { this._audioProcessor.disconnect(); } catch (e) {}
            this._audioProcessor = null;
        }
        if (this._audioCtx) {
            try { this._audioCtx.close(); } catch (e) {}
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
        if (typeof SOCWebSocketClient === 'undefined') {
            console.error('[Webcam] SOCWebSocketClient is not loaded.');
            return;
        }
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
        if (!this._hudCtx || !this._hudCanvas) return;
        const draw = () => {
            this._drawHUD();
            if (this._isStreaming) {
                this._hudAnimFrame = requestAnimationFrame(draw);
            }
        };
        this._hudAnimFrame = requestAnimationFrame(draw);
    }

    _stopHUD() {
        if (this._hudAnimFrame) {
            cancelAnimationFrame(this._hudAnimFrame);
            this._hudAnimFrame = null;
        }
        if (this._hudCtx && this._hudCanvas) {
            this._hudCtx.clearRect(0, 0, this._hudCanvas.width, this._hudCanvas.height);
        }
    }

    _drawHUD() {
        if (!this._hudCtx || !this._hudCanvas || !this._videoEl) return;
        const ctx = this._hudCtx;

        // Auto-sync canvas internal dimensions to video resolution for crisp display
        const vw = this._videoEl.videoWidth || this._videoEl.clientWidth || 640;
        const vh = this._videoEl.videoHeight || this._videoEl.clientHeight || 480;
        if (this._hudCanvas.width !== vw || this._hudCanvas.height !== vh) {
            this._hudCanvas.width = vw;
            this._hudCanvas.height = vh;
        }

        const w = this._hudCanvas.width;
        const h = this._hudCanvas.height;

        ctx.clearRect(0, 0, w, h);

        const v = this._lastVerdict;
        const confidence = v ? (v.confidence || 0) : 0;
        const isFake = v ? Boolean(v.is_deepfake) : false;

        // Border glow colour based on verdict
        let borderColor = '#22c55e'; // green: authentic
        if (isFake && confidence >= 0.7) borderColor = '#ef4444'; // red: high-conf fake
        else if (isFake)                 borderColor = '#f59e0b'; // amber: moderate

        // Draw HUD border
        ctx.strokeStyle = borderColor;
        ctx.lineWidth = 4;
        ctx.shadowColor = borderColor;
        ctx.shadowBlur = 10;
        ctx.strokeRect(2, 2, w - 4, h - 4);
        ctx.shadowBlur = 0;

        // FPS counter + Resolution badge (top-left)
        ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
        ctx.fillRect(8, 8, 160, 26);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
        ctx.lineWidth = 1;
        ctx.strokeRect(8, 8, 160, 26);

        // Pulsing dot
        ctx.fillStyle = this._isSynthetic ? '#818cf8' : '#22c55e';
        ctx.beginPath();
        ctx.arc(18, 21, 4, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#f8fafc';
        ctx.font = 'bold 11px monospace';
        ctx.fillText(`${this._displayFps} FPS`, 28, 25);

        // Resolution
        const resText = `${vw}x${vh}`;
        ctx.fillStyle = '#94a3b8';
        ctx.font = '10px monospace';
        ctx.fillText(resText, 92, 25);

        // Confidence badge (top-right)
        if (v) {
            const label = isFake ? '⚠ DEEPFAKE' : '✓ AUTHENTIC';
            const badgeColor = isFake ? '#ef4444' : '#22c55e';
            const badgeW = 140;
            ctx.fillStyle = 'rgba(15, 23, 42, 0.88)';
            ctx.fillRect(w - badgeW - 8, 8, badgeW, 26);
            ctx.strokeStyle = badgeColor;
            ctx.lineWidth = 1;
            ctx.strokeRect(w - badgeW - 8, 8, badgeW, 26);

            ctx.fillStyle = badgeColor;
            ctx.font = 'bold 11px monospace';
            ctx.fillText(`${label} ${Math.round(confidence * 100)}%`, w - badgeW + 8, 25);
        }

        // Animated ECDSA Cryptographic Attestation Badge (bottom-right)
        if (v && v.signed_verdict) {
            const pulse = (Math.sin(Date.now() / 250) + 1) / 2;
            const badgeW = 168;
            const badgeH = 26;
            const bx = w - badgeW - 8;
            const by = h - badgeH - 8;

            ctx.fillStyle = 'rgba(15, 23, 42, 0.88)';
            ctx.fillRect(bx, by, badgeW, badgeH);

            ctx.strokeStyle = `rgba(99, 102, 241, ${0.4 + pulse * 0.5})`;
            ctx.lineWidth = 1.5;
            ctx.strokeRect(bx, by, badgeW, badgeH);

            // Pulsing blue dot
            ctx.fillStyle = '#818cf8';
            ctx.beginPath();
            ctx.arc(bx + 12, by + 13, 3.5, 0, Math.PI * 2);
            ctx.fill();

            ctx.fillStyle = '#c7d2fe';
            ctx.font = 'bold 10px monospace';
            ctx.fillText('VERIFIED_BY_ECDSA', bx + 22, by + 17);
        }
    }

    // ── Private: helpers ────────────────────────────────────────────────────────

    _setStatus(status) {
        if (this.onStatusChange) this.onStatusChange(status);
    }

    _generateSessionId() {
        if (typeof crypto !== 'undefined' && crypto.randomUUID) {
            return crypto.randomUUID();
        }
        return 'session-' + Math.random().toString(36).substring(2, 10) + '-' + Date.now().toString(36);
    }
}

// Attach globally for browser templates
if (typeof window !== 'undefined') {
    window.WebcamStreamManager = WebcamStreamManager;
    window.WebcamStreamController = WebcamStreamManager;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        WebcamStreamManager,
        WebcamStreamController: WebcamStreamManager
    };
}
