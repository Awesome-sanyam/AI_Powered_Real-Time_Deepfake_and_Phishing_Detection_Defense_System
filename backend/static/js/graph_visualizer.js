/**
 * ThreatGraphVisualizer — Vis.js Interactive Threat Network
 * ==========================================================
 * Renders Neo4j threat entities as a dark-mode interactive force graph
 * using the Vis.js Network library (loaded via CDN).
 *
 * Node colours by type:
 *   email   → blue   (#3b82f6)
 *   domain  → orange (#f97316)
 *   ip      → red    (#ef4444)
 *   session → purple (#a855f7)
 *   default → slate  (#64748b)
 *
 * Usage:
 *   const viz = new ThreatGraphVisualizer({
 *     container:     document.getElementById('threat-network'),
 *     sidebarEl:     document.getElementById('node-details'),
 *     dataUrl:       '/api/graph/data/',
 *     refreshMs:     30000,
 *   });
 *   viz.init();
 *   viz.setFilter('domain');   // filter to show only domain nodes
 *   viz.clearFilter();
 *   viz.destroy();
 */

class ThreatGraphVisualizer {
    /**
     * @param {Object}          opts
     * @param {HTMLElement}     opts.container   - Container div for the Vis.js canvas
     * @param {HTMLElement}     [opts.sidebarEl] - Sidebar element for node details
     * @param {string}          [opts.dataUrl]   - REST endpoint returning {nodes, edges}
     * @param {number}          [opts.refreshMs] - Auto-refresh interval in ms (default 30000)
     */
    constructor(opts) {
        this._container  = opts.container;
        this._sidebarEl  = opts.sidebarEl || null;
        this._dataUrl    = opts.dataUrl || '/api/graph/data/';
        this._refreshMs  = opts.refreshMs || 30000;
        this._network    = null;
        this._nodes      = null;
        this._edges      = null;
        this._allNodes   = [];
        this._allEdges   = [];
        this._filterType = null;
        this._refreshTimer = null;
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

        // Node click → show metadata in sidebar
        this._network.on('click', (params) => {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                const node = this._allNodes.find((n) => n.id === nodeId);
                if (node) this._showNodeDetails(node);
            } else {
                this._clearSidebar();
            }
        });

        await this._fetchAndRender();
        this._startAutoRefresh();
    }

    /** Filter graph to show only nodes of a specific type ('email', 'domain', 'ip', 'session'). */
    setFilter(type) {
        this._filterType = type;
        this._applyFilter();
    }

    /** Remove current filter and show all nodes. */
    clearFilter() {
        this._filterType = null;
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

        if (this._filterType) {
            const allowed = new Set(
                visNodes
                    .filter((n) => (n.node_type || '').toLowerCase() === this._filterType)
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
    }

    _renderEmptyState() {
        this._nodes.clear();
        this._edges.clear();
        // Show placeholder node
        this._nodes.add([{
            id: 'placeholder',
            label: 'No threat data\n(Neo4j offline or no scans yet)',
            color: { background: '#1e293b', border: '#475569' },
            font: { color: '#64748b', size: 14 },
            shape: 'box',
        }]);
    }

    // ── Private: node/edge formatting ──────────────────────────────────────────

    _formatNode(raw) {
        const type = (raw.node_type || raw.type || 'default').toLowerCase();
        const risk  = parseFloat(raw.risk_score || 0);
        const color = this._nodeColor(type, risk);
        const label = this._truncate(raw.label || raw.id || '?', 24);

        return {
            id:         raw.id,
            label:      label,
            title:      this._buildTooltip(raw),
            shape:      this._nodeShape(type),
            color:      { background: color.bg, border: color.border, highlight: { background: color.bg, border: '#ffffff' } },
            font:       { color: '#f8fafc', size: 13, face: 'monospace' },
            borderWidth: risk >= 0.7 ? 3 : 1,
            shadow:     risk >= 0.7 ? { enabled: true, color: color.border, size: 12 } : false,
            // Store raw for sidebar
            _raw:       raw,
        };
    }

    _formatEdge(raw) {
        return {
            id:     raw.id || `${raw.from}-${raw.type}-${raw.to}`,
            from:   raw.from,
            to:     raw.to,
            label:  raw.type || '',
            arrows: { to: { enabled: true, scaleFactor: 0.7 } },
            color:  { color: '#334155', highlight: '#60a5fa' },
            font:   { color: '#94a3b8', size: 10, align: 'middle' },
            smooth: { type: 'curvedCW', roundness: 0.2 },
        };
    }

    _nodeColor(type, risk) {
        const palette = {
            email:   { bg: '#1d4ed8', border: '#3b82f6' },
            domain:  { bg: '#c2410c', border: '#f97316' },
            ip:      { bg: '#991b1b', border: '#ef4444' },
            session: { bg: '#7e22ce', border: '#a855f7' },
        };
        const base = palette[type] || { bg: '#1e293b', border: '#64748b' };
        // Intensify border for high-risk nodes
        if (risk >= 0.8) base.border = '#fbbf24';
        return base;
    }

    _nodeShape(type) {
        const shapes = { email: 'ellipse', domain: 'box', ip: 'diamond', session: 'dot' };
        return shapes[type] || 'dot';
    }

    _buildTooltip(raw) {
        const risk = parseFloat(raw.risk_score || 0);
        const pct  = Math.round(risk * 100);
        return `<div style="background:#0f172a;padding:8px;border-radius:6px;font-family:monospace;font-size:12px;color:#f8fafc;max-width:220px">
          <b>${raw.node_type || 'Node'}</b><br>
          ${this._truncate(raw.label || raw.id || '', 40)}<br>
          Risk: <span style="color:${risk >= 0.7 ? '#ef4444' : '#22c55e'}">${pct}%</span>
        </div>`;
    }

    _buildNetworkOptions() {
        return {
            autoResize: true,
            height:    '100%',
            width:     '100%',
            physics: {
                enabled: true,
                barnesHut: {
                    gravitationalConstant: -3000,
                    centralGravity: 0.15,
                    springLength: 140,
                    springConstant: 0.04,
                    damping: 0.09,
                },
                stabilization: { iterations: 150 },
            },
            interaction: {
                hover: true,
                tooltipDelay: 100,
                navigationButtons: false,
                keyboard: false,
            },
        };
    }

    // ── Private: sidebar ────────────────────────────────────────────────────────

    _showNodeDetails(node) {
        if (!this._sidebarEl) return;
        const raw   = node._raw || node;
        const risk  = parseFloat(raw.risk_score || 0);
        const pct   = Math.round(risk * 100);
        const color = risk >= 0.7 ? 'text-red-400' : risk >= 0.4 ? 'text-amber-400' : 'text-green-400';

        this._sidebarEl.innerHTML = `
            <div class="space-y-3">
                <div class="flex items-center justify-between">
                    <span class="text-xs uppercase tracking-widest text-slate-500">${raw.node_type || 'Entity'}</span>
                    <span class="text-xs px-2 py-1 rounded-full bg-slate-700 ${color} font-mono">Risk: ${pct}%</span>
                </div>
                <div class="font-mono text-sm text-slate-200 break-all">${raw.label || raw.id}</div>
                ${raw.signals ? `<div class="text-xs text-slate-400">Signals: ${raw.signals}</div>` : ''}
                <div class="pt-2 border-t border-slate-700 text-xs text-slate-500 space-y-1">
                    ${Object.entries(raw)
                        .filter(([k]) => !['id','label','node_type','risk_score','_raw','signals'].includes(k))
                        .map(([k, v]) => `<div><span class="text-slate-500">${k}:</span> <span class="text-slate-300">${String(v).slice(0,60)}</span></div>`)
                        .join('')}
                </div>
            </div>`;
        this._sidebarEl.classList.remove('hidden');
    }

    _clearSidebar() {
        if (this._sidebarEl) {
            this._sidebarEl.innerHTML = '<p class="text-slate-500 text-sm">Click a node to inspect</p>';
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
        return str.length > maxLen ? str.slice(0, maxLen) + '…' : str;
    }
}
