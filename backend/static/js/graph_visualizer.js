/**
 * ThreatGraphVisualizer — Vis.js Ultra-Premium Threat Command Center
 * ===================================================================
 * Renders Neo4j threat entities as a color-coded, risk-tiered interactive
 * force graph using the Vis.js Network library (loaded via CDN).
 *
 * 4-Color Risk-Tiered Node Architecture:
 *   🔴 Rose   — High-threat: confirmed deepfakes, verified phishing IPs  (risk ≥ 0.70)
 *   🟡 Amber  — Suspicious: high-entropy URLs, unverified DKIM domains   (risk 0.40–0.69)
 *   🟢 Emerald— Verified:   ECDSA-attested sessions, confirmed safe       (risk < 0.40)
 *   🔵 Indigo — Target:     email addresses, organization endpoints        (type = email)
 *
 * Node shapes by entity type:
 *   email   → ellipse   (target endpoint)
 *   domain  → box       (web asset)
 *   ip      → diamond   (network node)
 *   session → dot       (scan session)
 *
 * Usage:
 *   const viz = new ThreatGraphVisualizer({
 *     container:  document.getElementById('threat-network'),
 *     sidebarEl:  document.getElementById('node-details'),
 *     dataUrl:    '/api/graph/data/',
 *     refreshMs:  30000,
 *   });
 *   await viz.init();
 *   viz.setFilter('domain');   // filter to show only domain nodes
 *   viz.setRiskFilter(0.7);    // show only nodes with risk ≥ 0.7
 *   viz.clearFilter();
 *   viz.destroy();
 */

class ThreatGraphVisualizer {
    /**
     * @param {Object}      opts
     * @param {HTMLElement} opts.container   - Container div for the Vis.js canvas
     * @param {HTMLElement} [opts.sidebarEl] - Sidebar element for node details
     * @param {string}      [opts.dataUrl]   - REST endpoint returning {nodes, edges}
     * @param {number}      [opts.refreshMs] - Auto-refresh interval in ms (default 30000)
     */
    constructor(opts) {
        this._container   = opts.container;
        this._sidebarEl   = opts.sidebarEl || null;
        this._dataUrl     = opts.dataUrl || '/api/graph/data/';
        this._refreshMs   = opts.refreshMs || 30000;
        this._network     = null;
        this._nodes       = null;
        this._edges       = null;
        this._allNodes    = [];
        this._allEdges    = [];
        this._filterType  = null;
        this._riskFilter  = null;   // minimum risk score to show
        this._refreshTimer = null;
        this._selectedNode = null;
    }

    // ── Public API ──────────────────────────────────────────────────────────────

    /** Initialise the network, load data, start auto-refresh. */
    async init() {
        if (typeof vis === 'undefined') {
            console.error('[Graph] Vis.js not loaded. Add CDN script before graph_visualizer.js.');
            return;
        }
        this._nodes = new vis.DataSet([]);
        this._edges = new vis.DataSet([]);

        const options = this._buildNetworkOptions();
        this._network = new vis.Network(
            this._container,
            { nodes: this._nodes, edges: this._edges },
            options
        );

        // Node click → show rich metadata in sidebar
        this._network.on('click', (params) => {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                const node = this._allNodes.find((n) => n.id === nodeId);
                if (node) {
                    this._selectedNode = node;
                    this._showNodeDetails(node);
                }
            } else {
                this._selectedNode = null;
                this._clearSidebar();
            }
        });

        // Hover: highlight connected edges
        this._network.on('hoverNode', (params) => {
            this._network.selectEdges(this._network.getConnectedEdges(params.node));
        });
        this._network.on('blurNode', () => {
            this._network.unselectAll();
        });

        // Freeze physics after initial layout stabilizes (CPU optimization)
        this._network.on('stabilizationIterationsDone', () => {
            this._network.setOptions({ physics: false });
            this._network.stopSimulation();
            console.log('[Graph] Physics frozen after stabilization');
        });

        await this._fetchAndRender();
        this._startAutoRefresh();
    }

    /** Filter graph to show only nodes of a specific entity type. */
    setFilter(type) {
        this._filterType = type;
        this._riskFilter = null;
        this._applyFilter();
    }

    /** Filter to show only nodes with risk score >= minRisk. */
    setRiskFilter(minRisk) {
        this._filterType = null;
        this._riskFilter = minRisk;
        this._applyFilter();
    }

    /** Remove all filters and show all nodes. */
    clearFilter() {
        this._filterType = null;
        this._riskFilter = null;
        this._applyFilter();
    }

    /** Force an immediate data refresh. */
    async refresh() {
        await this._fetchAndRender();
    }

    /** Tear down the network and stop timers. */
    destroy() {
        this._stopAutoRefresh();
        if (this._network) {
            this._network.destroy();
            this._network = null;
        }
    }

    // ── Private: data fetching ──────────────────────────────────────────────────

    async _fetchAndRender() {
        try {
            const resp = await fetch(this._dataUrl, {
                headers: { 'Accept': 'application/json' },
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            this._allNodes = data.nodes || [];
            this._allEdges = data.edges || [];
            this._applyFilter();
            console.log(`[Graph] Rendered ${this._allNodes.length} nodes, ${this._allEdges.length} edges`);
        } catch (err) {
            console.warn('[Graph] Data fetch failed (Neo4j may be offline):', err);
            this._renderEmptyState();
        }
    }

    _applyFilter() {
        let visNodes = this._allNodes;
        let visEdges = this._allEdges;

        // Type filter
        if (this._filterType) {
            const allowed = new Set(
                visNodes
                    .filter((n) => (n.node_type || '').toLowerCase() === this._filterType)
                    .map((n) => n.id)
            );
            visNodes = visNodes.filter((n) => allowed.has(n.id));
            visEdges = visEdges.filter((e) => allowed.has(e.from) && allowed.has(e.to));
        }

        // Risk threshold filter
        if (this._riskFilter !== null) {
            const allowed = new Set(
                visNodes
                    .filter((n) => parseFloat(n.risk_score || 0) >= this._riskFilter)
                    .map((n) => n.id)
            );
            visNodes = visNodes.filter((n) => allowed.has(n.id));
            visEdges = visEdges.filter((e) => allowed.has(e.from) && allowed.has(e.to));
        }

        const formattedNodes = visNodes.map((n) => this._formatNode(n));
        const formattedEdges = visEdges.map((e) => this._formatEdge(e));

        this._nodes.clear();
        this._edges.clear();
        this._nodes.add(formattedNodes);
        this._edges.add(formattedEdges);

        // Re-enable physics only briefly to layout any new nodes
        if (this._network) {
            this._network.setOptions({ physics: { enabled: true } });
        }
    }

    _renderEmptyState() {
        this._nodes.clear();
        this._edges.clear();
        this._nodes.add([{
            id: 'placeholder',
            label: 'No threat data\n(Neo4j offline or no scans yet)',
            color: { background: '#f8fafc', border: '#e2e8f0' },
            font: { color: '#94a3b8', size: 13, face: 'Inter, system-ui, sans-serif' },
            shape: 'box',
            margin: { top: 10, bottom: 10, left: 14, right: 14 },
        }]);
    }

    // ── Private: node/edge formatting ──────────────────────────────────────────

    _formatNode(raw) {
        const type  = (raw.node_type || raw.type || 'default').toLowerCase();
        const risk  = parseFloat(raw.risk_score || 0);
        const color = this._nodeColor(type, risk);
        const label = this._truncate(raw.label || raw.id || '?', 22);

        // Glow shadow for high-threat nodes
        const isCritical = risk >= 0.70;
        const isWarning  = risk >= 0.40 && risk < 0.70;

        return {
            id:          raw.id,
            label:       label,
            title:       this._buildTooltip(raw),
            shape:       this._nodeShape(type),
            size:        isCritical ? 22 : (isWarning ? 18 : 15),
            color: {
                background: color.bg,
                border:     color.border,
                highlight:  { background: color.highlight, border: '#ffffff' },
                hover:      { background: color.highlight, border: '#ffffff' },
            },
            font: {
                color: '#ffffff',
                size:  isCritical ? 14 : 12,
                face:  'ui-monospace, Menlo, monospace',
                bold:  isCritical ? { color: '#ffffff', size: 14 } : undefined,
            },
            borderWidth:       isCritical ? 3 : (isWarning ? 2 : 1),
            borderWidthSelected: 4,
            shadow: isCritical
                ? { enabled: true, color: color.shadow, size: 16, x: 0, y: 0 }
                : (isWarning
                    ? { enabled: true, color: color.shadow, size: 8, x: 0, y: 0 }
                    : false),
            _raw: raw,
        };
    }

    _formatEdge(raw) {
        return {
            id:     raw.id || `${raw.from}-${raw.type || 'rel'}-${raw.to}`,
            from:   raw.from,
            to:     raw.to,
            label:  raw.type || '',
            arrows: { to: { enabled: true, scaleFactor: 0.65, type: 'arrow' } },
            color:  { color: '#cbd5e1', highlight: '#6366f1', hover: '#a78bfa', opacity: 0.8 },
            font:   { color: '#94a3b8', size: 10, align: 'middle', vadjust: -5 },
            smooth: { type: 'curvedCW', roundness: 0.15 },
            width:  1.5,
            selectionWidth: 3,
        };
    }

    /**
     * 4-color risk-tiered node palette:
     *   🔴 Rose    — threat (risk ≥ 0.70)   or deepfake/phishing confirmed
     *   🟡 Amber   — suspicious (risk 0.40–0.69)
     *   🟢 Emerald — verified / safe (risk < 0.40, or type=session with low risk)
     *   🔵 Indigo  — target endpoint (type=email)
     */
    _nodeColor(type, risk) {
        // Email nodes are always indigo (target classification)
        if (type === 'email') {
            return { bg: '#4338ca', border: '#6366f1', highlight: '#818cf8', shadow: 'rgba(99,102,241,0.5)' };
        }

        // Risk-tiered for domain, ip, session nodes
        if (risk >= 0.70) {
            // 🔴 High threat — Rose/Red
            return { bg: '#be123c', border: '#f43f5e', highlight: '#fb7185', shadow: 'rgba(244,63,94,0.55)' };
        }
        if (risk >= 0.40) {
            // 🟡 Suspicious — Amber
            return { bg: '#b45309', border: '#f59e0b', highlight: '#fbbf24', shadow: 'rgba(245,158,11,0.45)' };
        }
        // 🟢 Verified / low risk — Emerald
        if (type === 'session') {
            return { bg: '#047857', border: '#10b981', highlight: '#34d399', shadow: 'rgba(16,185,129,0.4)' };
        }
        // Domain, IP with low risk
        const fallbacks = {
            domain:  { bg: '#1e40af', border: '#3b82f6', highlight: '#60a5fa', shadow: 'rgba(59,130,246,0.4)' },
            ip:      { bg: '#7c3aed', border: '#a78bfa', highlight: '#c4b5fd', shadow: 'rgba(167,139,250,0.4)' },
        };
        return fallbacks[type] || { bg: '#475569', border: '#94a3b8', highlight: '#cbd5e1', shadow: 'rgba(148,163,184,0.3)' };
    }

    _nodeShape(type) {
        const shapes = {
            email:   'ellipse',
            domain:  'box',
            ip:      'diamond',
            session: 'dot',
        };
        return shapes[type] || 'dot';
    }

    _buildTooltip(raw) {
        const risk = parseFloat(raw.risk_score || 0);
        const pct  = Math.round(risk * 100);
        const riskColor = risk >= 0.70 ? '#f43f5e' : risk >= 0.40 ? '#f59e0b' : '#10b981';
        const riskLabel = risk >= 0.70 ? 'HIGH' : risk >= 0.40 ? 'MED' : 'LOW';

        return `<div style="
            background:#ffffff;
            padding:10px 12px;
            border:1px solid #e2e8f0;
            border-left:3px solid ${riskColor};
            border-radius:8px;
            font-family:ui-monospace,Menlo,monospace;
            font-size:11px;
            color:#1e293b;
            max-width:240px;
            box-shadow:0 4px 12px rgba(0,0,0,0.12);
            line-height:1.5;
        ">
            <div style="font-weight:600;font-size:12px;margin-bottom:4px;color:#0f172a">
                ${raw.node_type || 'Entity'}
            </div>
            <div style="word-break:break-all;color:#334155;margin-bottom:6px">
                ${this._truncate(raw.label || raw.id || '', 45)}
            </div>
            <div style="
                display:inline-block;
                padding:2px 7px;
                border-radius:4px;
                background:${riskColor}15;
                color:${riskColor};
                border:1px solid ${riskColor}40;
                font-weight:600;
                font-size:10px;
            ">⚠ RISK ${riskLabel} · ${pct}%</div>
        </div>`;
    }

    _buildNetworkOptions() {
        return {
            autoResize: true,
            height:     '100%',
            width:      '100%',
            physics: {
                enabled: true,
                barnesHut: {
                    gravitationalConstant: -4000,
                    centralGravity:        0.12,
                    springLength:          160,
                    springConstant:        0.035,
                    damping:               0.12,
                    avoidOverlap:          0.2,
                },
                stabilization: { iterations: 180, fit: true },
            },
            interaction: {
                hover:             true,
                tooltipDelay:      80,
                navigationButtons: false,
                keyboard:          false,
                zoomView:          true,
                dragView:          true,
            },
            nodes: {
                margin: 8,
            },
            edges: {
                smooth: { type: 'curvedCW', roundness: 0.15 },
            },
        };
    }

    // ── Private: sidebar ────────────────────────────────────────────────────────

    _showNodeDetails(node) {
        if (!this._sidebarEl) return;
        const raw   = node._raw || node;
        const risk  = parseFloat(raw.risk_score || 0);
        const pct   = Math.round(risk * 100);

        const riskColor  = risk >= 0.70 ? '#f43f5e' : risk >= 0.40 ? '#f59e0b' : '#10b981';
        const riskBg     = risk >= 0.70 ? '#fff1f2' : risk >= 0.40 ? '#fffbeb' : '#f0fdf4';
        const riskLabel  = risk >= 0.70 ? '🔴 HIGH THREAT' : risk >= 0.40 ? '🟡 SUSPICIOUS' : '🟢 VERIFIED';

        // Signals chips
        const signalsHtml = raw.signals
            ? String(raw.signals).split(',').map(s => s.trim()).filter(Boolean).map(s =>
                `<span style="display:inline-block;padding:2px 7px;margin:2px;border-radius:4px;background:#f1f5f9;border:1px solid #e2e8f0;font-size:10px;color:#475569">${s}</span>`
              ).join('')
            : '<span style="color:#94a3b8;font-size:11px">No signals</span>';

        // Metadata rows (exclude internal fields)
        const excludedKeys = ['id','label','node_type','risk_score','_raw','signals'];
        const metaRows = Object.entries(raw)
            .filter(([k]) => !excludedKeys.includes(k))
            .map(([k, v]) => `
                <div style="display:flex;justify-content:space-between;gap:8px;padding:3px 0;border-bottom:1px solid #f1f5f9">
                    <span style="color:#94a3b8;font-size:10px;white-space:nowrap">${k}</span>
                    <span style="color:#1e293b;font-size:10px;font-family:monospace;text-align:right;word-break:break-all">${String(v).slice(0, 60)}</span>
                </div>
            `).join('');

        // Risk bar
        const barWidth = Math.round(pct);
        const barColor = riskColor;

        this._sidebarEl.innerHTML = `
            <div style="animation:sidebar-in 0.22s ease forwards">
                <!-- Risk badge -->
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
                    <span style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.04em">
                        ${raw.node_type || 'Entity'}
                    </span>
                    <span style="padding:2px 8px;border-radius:5px;font-size:11px;font-weight:600;background:${riskBg};color:${riskColor};border:1px solid ${riskColor}40">
                        ${riskLabel}
                    </span>
                </div>

                <!-- Label -->
                <div style="font-family:ui-monospace,Menlo,monospace;font-size:12px;color:#0f172a;word-break:break-all;padding:8px;background:#f8fafc;border-radius:6px;border:1px solid #e2e8f0;margin-bottom:10px">
                    ${raw.label || raw.id}
                </div>

                <!-- Risk bar -->
                <div style="margin-bottom:10px">
                    <div style="display:flex;justify-content:space-between;font-size:10px;color:#64748b;margin-bottom:4px">
                        <span>Risk Score</span><span style="font-weight:600;color:${riskColor}">${pct}%</span>
                    </div>
                    <div style="height:4px;background:#f1f5f9;border-radius:2px;overflow:hidden">
                        <div style="height:100%;width:${barWidth}%;background:${barColor};border-radius:2px;transition:width 0.5s ease"></div>
                    </div>
                </div>

                <!-- Signals -->
                <div style="margin-bottom:10px">
                    <p style="font-size:10px;font-weight:600;color:#64748b;margin-bottom:5px;text-transform:uppercase">Detection Signals</p>
                    <div style="line-height:1.8">${signalsHtml}</div>
                </div>

                <!-- Metadata -->
                ${metaRows ? `
                <div style="border-top:1px solid #e2e8f0;padding-top:8px">
                    <p style="font-size:10px;font-weight:600;color:#64748b;margin-bottom:5px;text-transform:uppercase">Metadata</p>
                    ${metaRows}
                </div>` : ''}
            </div>`;
        this._sidebarEl.classList.remove('hidden');
    }

    _clearSidebar() {
        if (this._sidebarEl) {
            this._sidebarEl.innerHTML = `
                <div style="text-align:center;padding:24px 0;color:#94a3b8">
                    <div style="font-size:24px;margin-bottom:8px">🔍</div>
                    <p style="font-size:12px;font-weight:500;color:#64748b">Click a node to inspect</p>
                    <p style="font-size:11px;color:#94a3b8;margin-top:4px">View cryptographic details,<br>risk scores, and signals</p>
                </div>`;
        }
    }

    // ── Private: auto-refresh ───────────────────────────────────────────────────

    _startAutoRefresh() {
        this._stopAutoRefresh();
        this._refreshTimer = setInterval(() => this._fetchAndRender(), this._refreshMs);
    }

    _stopAutoRefresh() {
        if (this._refreshTimer) {
            clearInterval(this._refreshTimer);
            this._refreshTimer = null;
        }
    }

    // ── Private: helpers ────────────────────────────────────────────────────────

    _truncate(str, maxLen) {
        const s = String(str);
        return s.length > maxLen ? s.slice(0, maxLen) + '…' : s;
    }
}
