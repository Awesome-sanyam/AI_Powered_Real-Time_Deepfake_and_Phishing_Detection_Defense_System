/**
 * ThreatGraphVisualizer — Vis.js Ultra-Premium Threat Command Center
 * ===================================================================
 * Renders Neo4j threat entities as a color-coded, risk-tiered interactive
 * force graph using the Vis.js Network library (loaded via CDN).
 *
 * Fully adapts to Dark and Light modes dynamically, responding to the
 * 'themeChanged' custom event dispatched by theme_toggle.js.
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
        this._container    = opts.container;
        this._sidebarEl    = opts.sidebarEl || null;
        this._dataUrl      = opts.dataUrl || '/api/graph/data/';
        this._refreshMs    = opts.refreshMs || 30000;
        this._network      = null;
        this._nodes        = null;
        this._edges        = null;
        this._allNodes     = [];
        this._allEdges     = [];
        this._filterType   = null;
        this._riskFilter   = null;
        this._refreshTimer = null;
        this._selectedNode = null;
    }

    _isDark() {
        return document.documentElement.classList.contains('dark');
    }

    // ── Public API ──────────────────────────────────────────────────────────────

    /** Initialise the network, load data, start auto-refresh. */
    async init() {
        if (typeof vis === 'undefined') {
            console.error('[Graph] Vis.js not loaded.');
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
        });

        // Theme change handler
        window.addEventListener('themeChanged', () => {
            if (this._network) {
                this._applyFilter();
                if (this._selectedNode) {
                    this._showNodeDetails(this._selectedNode);
                }
            }
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
        } catch (err) {
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

        if (this._network) {
            this._network.setOptions({ physics: { enabled: true } });
        }
    }

    _renderEmptyState() {
        const isDark = this._isDark();
        this._nodes.clear();
        this._edges.clear();
        this._nodes.add([{
            id: 'placeholder',
            label: 'No threat data\n(Neo4j offline or no scans yet)',
            color: {
                background: isDark ? '#18181b' : '#f8fafc',
                border:     isDark ? '#27272a' : '#e2e8f0'
            },
            font: {
                color: isDark ? '#a1a1aa' : '#94a3b8',
                size: 13,
                face: 'Inter, system-ui, sans-serif'
            },
            shape: 'box',
            margin: { top: 12, bottom: 12, left: 16, right: 16 },
        }]);
    }

    // ── Private: node/edge formatting ──────────────────────────────────────────

    _formatNode(raw) {
        const type  = (raw.node_type || raw.type || 'default').toLowerCase();
        const risk  = parseFloat(raw.risk_score || 0);
        const color = this._nodeColor(type, risk);
        const label = this._truncate(raw.label || raw.id || '?', 22);

        const isCritical = risk >= 0.70;
        const isWarning  = risk >= 0.40 && risk < 0.70;

        return {
            id:          raw.id,
            label:       label,
            title:       this._buildTooltip(raw),
            shape:       this._nodeShape(type),
            size:        isCritical ? 24 : (isWarning ? 19 : 15),
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
        const isDark = this._isDark();
        return {
            id:     raw.id || `${raw.from}-${raw.type || 'rel'}-${raw.to}`,
            from:   raw.from,
            to:     raw.to,
            label:  raw.type || '',
            arrows: { to: { enabled: true, scaleFactor: 0.65, type: 'arrow' } },
            color: {
                color:     isDark ? '#3f3f46' : '#cbd5e1',
                highlight: isDark ? '#818cf8' : '#6366f1',
                hover:     isDark ? '#a5b4fc' : '#4f46e5',
                opacity:   0.85
            },
            font: {
                color:   isDark ? '#a1a1aa' : '#64748b',
                size:    10,
                align:   'middle',
                vadjust: -5
            },
            smooth: { type: 'curvedCW', roundness: 0.15 },
            width:  1.5,
            selectionWidth: 3,
        };
    }

    _nodeColor(type, risk) {
        // Email nodes are always indigo (target classification)
        if (type === 'email') {
            return { bg: '#4338ca', border: '#6366f1', highlight: '#818cf8', shadow: 'rgba(99,102,241,0.5)' };
        }

        // Risk-tiered for domain, ip, session nodes
        if (risk >= 0.70) {
            // 🔴 High threat — Rose
            return { bg: '#be123c', border: '#f43f5e', highlight: '#fb7185', shadow: 'rgba(244,63,94,0.6)' };
        }
        if (risk >= 0.40) {
            // 🟡 Suspicious — Amber
            return { bg: '#b45309', border: '#f59e0b', highlight: '#fbbf24', shadow: 'rgba(245,158,11,0.5)' };
        }
        // 🟢 Verified / low risk — Emerald
        if (type === 'session') {
            return { bg: '#047857', border: '#10b981', highlight: '#34d399', shadow: 'rgba(16,185,129,0.45)' };
        }

        const fallbacks = {
            domain: { bg: '#1e40af', border: '#3b82f6', highlight: '#60a5fa', shadow: 'rgba(59,130,246,0.45)' },
            ip:     { bg: '#7c3aed', border: '#a78bfa', highlight: '#c4b5fd', shadow: 'rgba(167,139,250,0.45)' },
        };
        return fallbacks[type] || { bg: '#3f3f46', border: '#71717a', highlight: '#a1a1aa', shadow: 'rgba(113,113,122,0.3)' };
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
        const isDark = this._isDark();
        const risk   = parseFloat(raw.risk_score || 0);
        const pct    = Math.round(risk * 100);
        const riskColor = risk >= 0.70 ? '#f43f5e' : risk >= 0.40 ? '#f59e0b' : '#10b981';
        const riskLabel = risk >= 0.70 ? 'HIGH' : risk >= 0.40 ? 'MED' : 'LOW';

        const bg = isDark ? '#18181b' : '#ffffff';
        const border = isDark ? '#27272a' : '#e2e8f0';
        const textPri = isDark ? '#f4f4f5' : '#0f172a';
        const textSec = isDark ? '#a1a1aa' : '#475569';

        return `<div style="
            background:${bg};
            padding:10px 12px;
            border:1px solid ${border};
            border-left:3px solid ${riskColor};
            border-radius:8px;
            font-family:ui-monospace,Menlo,monospace;
            font-size:11px;
            color:${textPri};
            max-width:260px;
            box-shadow:0 8px 24px rgba(0,0,0,0.25);
            line-height:1.5;
        ">
            <div style="font-weight:700;font-size:12px;margin-bottom:3px;color:${textPri}">
                ${raw.node_type || 'Entity'}
            </div>
            <div style="word-break:break-all;color:${textSec};margin-bottom:6px">
                ${this._truncate(raw.label || raw.id || '', 45)}
            </div>
            <div style="
                display:inline-block;
                padding:2px 7px;
                border-radius:4px;
                background:${riskColor}15;
                color:${riskColor};
                border:1px solid ${riskColor}40;
                font-weight:700;
                font-size:10px;
            ">RISK ${riskLabel} · ${pct}%</div>
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
            nodes: { margin: 8 },
            edges: { smooth: { type: 'curvedCW', roundness: 0.15 } },
        };
    }

    // ── Private: sidebar ────────────────────────────────────────────────────────

    _showNodeDetails(node) {
        if (!this._sidebarEl) return;
        const isDark = this._isDark();
        const raw    = node._raw || node;
        const risk   = parseFloat(raw.risk_score || 0);
        const pct    = Math.round(risk * 100);

        const riskColor = risk >= 0.70 ? '#f43f5e' : risk >= 0.40 ? '#f59e0b' : '#10b981';
        const riskBg    = risk >= 0.70 ? (isDark ? 'rgba(244,63,94,0.18)' : '#fff1f2')
                        : risk >= 0.40 ? (isDark ? 'rgba(245,158,11,0.18)' : '#fffbeb')
                        :                (isDark ? 'rgba(16,185,129,0.18)' : '#f0fdf4');
        const riskLabel = risk >= 0.70 ? 'CRITICAL THREAT' : risk >= 0.40 ? 'SUSPICIOUS' : 'VERIFIED SAFE';

        // Signal chips
        const chipBg     = isDark ? '#27272a' : '#f1f5f9';
        const chipBorder = isDark ? '#3f3f46' : '#e2e8f0';
        const chipText   = isDark ? '#e4e4e7' : '#475569';

        const signalsHtml = raw.signals
            ? String(raw.signals).split(',').map(s => s.trim()).filter(Boolean).map(s =>
                `<span style="display:inline-block;padding:2px 8px;margin:2px;border-radius:5px;background:${chipBg};border:1px solid ${chipBorder};font-size:10px;font-family:monospace;color:${chipText}">${s}</span>`
              ).join('')
            : `<span style="color:${isDark ? '#71717a' : '#94a3b8'};font-size:11px">No anomalous signals</span>`;

        // Metadata rows
        const excludedKeys = ['id','label','node_type','risk_score','_raw','signals','signed_verdict','signature'];
        const borderSub = isDark ? '#27272a' : '#f1f5f9';
        const labelCol  = isDark ? '#a1a1aa' : '#64748b';
        const valCol    = isDark ? '#f4f4f5' : '#0f172a';

        const metaRows = Object.entries(raw)
            .filter(([k]) => !excludedKeys.includes(k))
            .map(([k, v]) => `
                <div style="display:flex;justify-content:space-between;gap:8px;padding:3px 0;border-bottom:1px solid ${borderSub}">
                    <span style="color:${labelCol};font-size:10px;white-space:nowrap">${k}</span>
                    <span style="color:${valCol};font-size:10px;font-family:monospace;text-align:right;word-break:break-all">${String(v).slice(0, 50)}</span>
                </div>
            `).join('');

        const labelBoxBg     = isDark ? '#27272a' : '#f8fafc';
        const labelBoxBorder = isDark ? '#3f3f46' : '#e2e8f0';
        const titleCol       = isDark ? '#fafafa' : '#0f172a';

        this._sidebarEl.innerHTML = `
            <div style="animation:sidebar-in 0.22s ease forwards">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
                    <span style="font-size:11px;font-weight:700;color:${labelCol};text-transform:uppercase;letter-spacing:0.04em">
                        ${raw.node_type || 'Entity'}
                    </span>
                    <span style="padding:2px 8px;border-radius:5px;font-size:10px;font-weight:700;background:${riskBg};color:${riskColor};border:1px solid ${riskColor}50">
                        ${riskLabel}
                    </span>
                </div>

                <div style="font-family:ui-monospace,Menlo,monospace;font-size:11px;font-weight:600;color:${titleCol};word-break:break-all;padding:10px;background:${labelBoxBg};border-radius:8px;border:1px solid ${labelBoxBorder};margin-bottom:12px">
                    ${raw.label || raw.id}
                </div>

                <div style="margin-bottom:12px">
                    <div style="display:flex;justify-content:space-between;font-size:11px;color:${labelCol};margin-bottom:4px">
                        <span>Risk Assessment</span><span style="font-weight:700;color:${riskColor}">${pct}%</span>
                    </div>
                    <div style="height:5px;background:${isDark ? '#27272a' : '#f1f5f9'};border-radius:3px;overflow:hidden">
                        <div style="height:100%;width:${pct}%;background:${riskColor};border-radius:3px;transition:width 0.5s ease"></div>
                    </div>
                </div>

                <div style="margin-bottom:12px">
                    <p style="font-size:10px;font-weight:700;color:${labelCol};margin-bottom:6px;text-transform:uppercase;letter-spacing:0.04em">Correlated Signals</p>
                    <div style="line-height:1.7">${signalsHtml}</div>
                </div>

                ${metaRows ? `
                <div style="border-top:1px solid ${labelBoxBorder};padding-top:10px">
                    <p style="font-size:10px;font-weight:700;color:${labelCol};margin-bottom:6px;text-transform:uppercase;letter-spacing:0.04em">Entity Telemetry</p>
                    ${metaRows}
                </div>` : ''}
            </div>`;
    }

    _clearSidebar() {
        if (this._sidebarEl) {
            const isDark = this._isDark();
            this._sidebarEl.innerHTML = `
                <div style="text-align:center;padding:32px 0;color:#94a3b8">
                    <div style="font-size:28px;margin-bottom:8px">🔍</div>
                    <p style="font-size:12px;font-weight:600;color:${isDark ? '#e4e4e7' : '#64748b'}">Select a Node to Inspect</p>
                    <p style="font-size:11px;color:#94a3b8;margin-top:4px">View cryptographic attestation,<br>risk telemetry, and correlated signals.</p>
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

    _truncate(str, maxLen) {
        const s = String(str);
        return s.length > maxLen ? s.slice(0, maxLen) + '…' : s;
    }
}
