/**
 * Smart Shade Scheduler — sidebar panel
 *
 * Condition text format (space-separated, case-insensitive):
 *   az>150      sun azimuth above 150°
 *   el>5        sun elevation above 5°
 *   el<30       sun elevation below 30°
 *   az>185 el<45 el>5   combined
 *   (empty)     catch-all — always matches
 */

function parseCondition(str) {
  const result = {};
  for (const token of str.trim().split(/\s+/)) {
    const m = token.match(
      /^(az(?:imuth)?|el(?:evation)?)(>|<)(-?\d+(?:\.\d+)?)$/i
    );
    if (!m) continue;
    const [, key, op, val] = m;
    const v = parseFloat(val);
    const isAz = key[0].toLowerCase() === 'a';
    if (isAz  &&  op === '>') result.azimuth_above   = v;
    if (!isAz &&  op === '>') result.elevation_above = v;
    if (!isAz &&  op === '<') result.elevation_below = v;
  }
  return result;
}

function formatCondition(rule) {
  const parts = [];
  if (rule.azimuth_above   != null) parts.push(`az>${rule.azimuth_above}`);
  if (rule.elevation_above != null) parts.push(`el>${rule.elevation_above}`);
  if (rule.elevation_below != null) parts.push(`el<${rule.elevation_below}`);
  return parts.join(' ');
}

// ─────────────────────────────────────────────────────────────────────────────

const CSS = `
  * { box-sizing: border-box; }
  :host {
    display: block;
    padding: 16px 20px;
    min-height: 100vh;
    background: var(--primary-background-color);
    color: var(--primary-text-color);
    font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
    font-size: 14px;
  }
  h1 {
    margin: 0 0 16px;
    font-size: 22px;
    font-weight: 400;
    color: var(--primary-text-color);
  }
  .error-banner {
    background: var(--error-color, #b00020);
    color: #fff;
    padding: 10px 14px;
    border-radius: 8px;
    margin-bottom: 14px;
    font-size: 13px;
  }

  /* ── Mode tabs ─────────────────────────────────────── */
  .mode-tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
  .mode-tab {
    padding: 6px 18px;
    border-radius: 20px;
    border: 2px solid var(--divider-color);
    background: var(--card-background-color);
    color: var(--primary-text-color);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: border-color .15s, background .15s;
  }
  .mode-tab:hover { border-color: var(--primary-color); }
  .mode-tab.active {
    background: var(--primary-color);
    border-color: var(--primary-color);
    color: var(--text-primary-color, #fff);
  }
  .live-dot {
    display: inline-block;
    width: 7px; height: 7px;
    border-radius: 50%;
    background: #4caf50;
    margin-left: 6px;
    vertical-align: middle;
  }

  /* ── Card / table ──────────────────────────────────── */
  .card {
    background: var(--card-background-color);
    border-radius: 12px;
    box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0,0,0,.12));
    overflow: hidden;
  }
  table { width: 100%; border-collapse: collapse; }
  thead th {
    padding: 9px 10px;
    text-align: left;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: .04em;
    color: var(--secondary-text-color);
    background: var(--secondary-background-color, rgba(0,0,0,.04));
    border-bottom: 1px solid var(--divider-color);
  }
  tbody td {
    padding: 5px 8px;
    border-bottom: 1px solid var(--divider-color);
    vertical-align: middle;
  }
  tbody tr:last-child td { border-bottom: none; }
  tbody tr:hover { background: var(--secondary-background-color, rgba(0,0,0,.03)); }
  tr.has-override { background: rgba(255,152,0,.08) !important; }

  /* ── Inputs ────────────────────────────────────────── */
  input {
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 5px 7px;
    width: 100%;
    background: transparent;
    color: inherit;
    font-size: 13px;
    transition: border-color .15s, background .15s;
  }
  input:hover {
    border-color: var(--divider-color);
    background: var(--primary-background-color);
  }
  input:focus {
    outline: none;
    border-color: var(--primary-color);
    background: var(--primary-background-color);
  }
  input.narrow { width: 58px; text-align: center; }
  input::placeholder { color: var(--secondary-text-color); opacity: .6; }

  /* ── Row actions ───────────────────────────────────── */
  .row-btns { display: flex; gap: 2px; align-items: center; }
  .icon-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: 3px 6px;
    border-radius: 4px;
    font-size: 13px;
    line-height: 1.2;
    color: var(--secondary-text-color);
    transition: background .12s, color .12s;
  }
  .icon-btn:hover { background: var(--secondary-background-color); color: var(--primary-text-color); }
  .icon-btn:disabled { opacity: .25; cursor: default; }
  .icon-btn.del:hover { background: var(--error-color, #b00020); color: #fff; }
  .override-icon { color: #ff9800; cursor: default; font-size: 14px; }

  /* ── Add row ───────────────────────────────────────── */
  .add-row td { padding: 0; }
  .add-btn {
    display: block;
    width: 100%;
    padding: 10px 14px;
    background: none;
    border: none;
    border-top: 1px dashed var(--divider-color);
    color: var(--primary-color);
    font-size: 13px;
    text-align: left;
    cursor: pointer;
  }
  .add-btn:hover { background: var(--secondary-background-color); }

  /* ── Footer ────────────────────────────────────────── */
  .footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 14px;
    flex-wrap: wrap;
    gap: 8px;
  }
  .hint { font-size: 11px; color: var(--secondary-text-color); line-height: 1.6; }
  code {
    background: var(--secondary-background-color);
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 11px;
  }
  .save-btn {
    padding: 9px 28px;
    background: var(--primary-color);
    color: var(--text-primary-color, #fff);
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: opacity .15s;
  }
  .save-btn:disabled { opacity: .45; cursor: default; }
  .unsaved-dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #ff9800;
    margin-left: 7px;
    vertical-align: middle;
  }
`;

// ─────────────────────────────────────────────────────────────────────────────

class SmartShadesPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._hass        = null;
    this._cfg         = null;   // data from ws_get_config
    this._rules       = [];     // working copy
    this._modes       = [];     // ordered mode tab list
    this._mode        = null;   // selected tab
    this._addingMode  = false;  // show new-mode input
    this._dirty       = false;
    this._saving      = false;
    this._error       = null;
  }

  // HA calls this every time any entity state changes — we only care on first set
  set hass(hass) {
    this._hass = hass;
    if (!this._cfg) this._load();
  }

  async _load() {
    try {
      const cfg = await this._ws('smart_shades/get_config');
      this._cfg   = cfg;
      this._rules = JSON.parse(JSON.stringify(cfg.rules || []));
      this._modes = cfg.mode_options || [];
      this._mode  = this._modes.includes(cfg.current_mode)
        ? cfg.current_mode
        : (this._modes[0] ?? null);
      this._dirty = false;
      this._render();
    } catch (e) {
      this._error = `Could not load config: ${e.message ?? e}`;
      this._render();
    }
  }

  _ws(type, extra = {}) {
    return this._hass.connection.sendMessagePromise({ type, ...extra });
  }

  // ── Mutation helpers ──────────────────────────────────────────────────────

  _rulesForMode() {
    return this._rules
      .map((r, i) => ({ r, i }))
      .filter(({ r }) => r.mode === this._mode);
  }

  /** Read DOM row inputs back into this._rules[]. */
  _collect() {
    const tbody = this.shadowRoot.querySelector('#tbody');
    if (!tbody) return;
    for (const row of tbody.querySelectorAll('tr[data-idx]')) {
      const idx  = parseInt(row.dataset.idx, 10);
      const rule = this._rules[idx];
      if (!rule) continue;

      rule.covers = row.querySelector('.f-covers').value
        .split(',').map(s => s.trim()).filter(Boolean);

      const cond = parseCondition(row.querySelector('.f-cond').value);
      delete rule.azimuth_above;
      delete rule.elevation_above;
      delete rule.elevation_below;
      Object.assign(rule, cond);

      const pos = row.querySelector('.f-pos').value;
      if (pos !== '') rule.position = parseInt(pos, 10); else delete rule.position;

      const tilt = row.querySelector('.f-tilt').value;
      if (tilt !== '') rule.tilt = parseInt(tilt, 10); else delete rule.tilt;
    }
  }

  _addRule() {
    this._collect();
    const n = this._rules.filter(r => r.mode === this._mode).length + 1;
    this._rules.push({ name: `${this._mode} ${n}`, mode: this._mode, covers: [] });
    this._dirty = true;
    this._render();
  }

  _confirmAddMode() {
    const input = this.shadowRoot.querySelector('#new-mode-input');
    const name = input?.value.trim().toUpperCase();
    if (!name || this._modes.includes(name)) return;
    this._collect();
    this._modes = [...this._modes, name];
    this._mode  = name;
    this._addingMode = false;
    this._render();
  }

  _deleteRule(idx) {
    this._collect();
    this._rules.splice(idx, 1);
    this._dirty = true;
    this._render();
  }

  _moveRule(idx, dir) {
    this._collect();
    const peers = this._rulesForMode();
    const pos   = peers.findIndex(p => p.i === idx);
    const swap  = peers[pos + dir];
    if (!swap) return;
    [this._rules[idx], this._rules[swap.i]] = [this._rules[swap.i], this._rules[idx]];
    this._dirty = true;
    this._render();
  }

  async _save() {
    if (this._saving) return;
    this._collect();
    this._saving = true;
    this._render();
    try {
      await this._ws('smart_shades/save_rules', {
        entry_id: this._cfg.entry_id,
        rules: this._rules,
      });
      this._cfg.rules = JSON.parse(JSON.stringify(this._rules));
      this._dirty = false;
      this._error = null;
    } catch (e) {
      this._error = `Save failed: ${e.message ?? e}`;
    }
    this._saving = false;
    this._render();
  }

  // ── Render ────────────────────────────────────────────────────────────────

  _render() {
    const root = this.shadowRoot;

    if (!this._cfg) {
      root.innerHTML = `<style>${CSS}</style>
        <h1>Shade Scheduler</h1>
        ${this._error
          ? `<div class="error-banner">${this._error}</div>`
          : `<div style="color:var(--secondary-text-color)">Loading…</div>`}`;
      return;
    }

    const curMode   = this._cfg.current_mode;
    const overrides = new Set(this._cfg.overrides || []);
    const peers     = this._rulesForMode();

    // ── Mode tabs ─────────────────────────────────────────────────
    const tabsHtml = this._modes.map(m => `
      <button class="mode-tab${m === this._mode ? ' active' : ''}" data-mode="${m}">
        ${m}${m === curMode ? '<span class="live-dot" title="Active mode"></span>' : ''}
      </button>`).join('');

    const addModeHtml = this._addingMode
      ? `<div style="display:flex;gap:6px;align-items:center">
           <input id="new-mode-input" style="width:110px;padding:5px 8px;border:1px solid var(--primary-color);border-radius:6px;background:var(--primary-background-color);color:inherit;font-size:13px" placeholder="MODE NAME" />
           <button class="mode-tab active" id="confirm-mode-btn">Add</button>
           <button class="mode-tab" id="cancel-mode-btn">✕</button>
         </div>`
      : `<button class="mode-tab" id="add-mode-btn" title="Add a new mode tab">＋</button>`;

    // ── Table rows ─────────────────────────────────────────────────
    const rowsHtml = peers.map(({ r, i }, pos) => {
      const hasOv = (r.covers || []).some(c => overrides.has(c));
      return `
        <tr data-idx="${i}"${hasOv ? ' class="has-override"' : ''}>
          <td style="width:46px">
            <div class="row-btns" style="flex-direction:column;gap:0">
              <button class="icon-btn up-btn" data-idx="${i}"
                ${pos === 0 ? 'disabled' : ''} title="Move up">▲</button>
              <button class="icon-btn dn-btn" data-idx="${i}"
                ${pos === peers.length - 1 ? 'disabled' : ''} title="Move down">▼</button>
            </div>
          </td>
          <td>
            <input class="f-covers"
              value="${(r.covers || []).join(', ')}"
              placeholder="cover.room, cover.other" />
          </td>
          <td>
            <input class="f-cond"
              value="${formatCondition(r)}"
              placeholder="az>150 el<30" />
          </td>
          <td><input class="f-pos narrow" type="number"
            min="0" max="100"
            value="${r.position ?? ''}" placeholder="—" /></td>
          <td><input class="f-tilt narrow" type="number"
            min="0" max="100"
            value="${r.tilt ?? ''}" placeholder="—" /></td>
          <td style="width:64px">
            <div class="row-btns">
              ${hasOv ? '<span class="override-icon" title="Manual override active">⚠</span>' : ''}
              <button class="icon-btn del del-btn" data-idx="${i}"
                title="Delete rule">✕</button>
            </div>
          </td>
        </tr>`;
    }).join('');

    // ── Full HTML ──────────────────────────────────────────────────
    root.innerHTML = `
      <style>${CSS}</style>
      <h1>Shade Scheduler</h1>
      ${this._error ? `<div class="error-banner">${this._error}</div>` : ''}

      <div class="mode-tabs">${tabsHtml}${addModeHtml}</div>

      <div class="card">
        <table>
          <thead>
            <tr>
              <th></th>
              <th style="width:38%">Covers <span style="font-weight:400;opacity:.5">(comma-separated)</span></th>
              <th style="width:22%">Condition</th>
              <th style="width:8%">Pos%</th>
              <th style="width:8%">Tilt%</th>
              <th></th>
            </tr>
          </thead>
          <tbody id="tbody">${rowsHtml}</tbody>
          <tbody>
            <tr class="add-row">
              <td colspan="6">
                <button class="add-btn" id="add-btn">
                  ＋  Add rule for ${this._mode ?? '…'}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="footer">
        <span class="hint">
          Conditions (space-separated):
          <code>az&gt;150</code> azimuth above &nbsp;
          <code>el&gt;5</code> elevation above &nbsp;
          <code>el&lt;30</code> elevation below<br>
          Leave empty for catch-all. First matching rule wins. ⚠ = manual override active.
        </span>
        <button class="save-btn" id="save-btn" ${this._saving ? 'disabled' : ''}>
          ${this._saving ? 'Saving…' : 'Save'}
          ${this._dirty && !this._saving ? '<span class="unsaved-dot"></span>' : ''}
        </button>
      </div>`;

    // ── Event wiring ───────────────────────────────────────────────
    root.querySelectorAll('.mode-tab[data-mode]').forEach(btn =>
      btn.addEventListener('click', () => {
        this._collect();
        this._mode = btn.dataset.mode;
        this._addingMode = false;
        this._render();
      })
    );

    root.querySelector('#add-mode-btn')?.addEventListener('click', () => {
      this._addingMode = true;
      this._render();
      root.querySelector('#new-mode-input')?.focus();
    });

    root.querySelector('#confirm-mode-btn')?.addEventListener('click', () => {
      this._confirmAddMode();
    });

    root.querySelector('#cancel-mode-btn')?.addEventListener('click', () => {
      this._addingMode = false;
      this._render();
    });

    root.querySelector('#new-mode-input')?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this._confirmAddMode();
      if (e.key === 'Escape') { this._addingMode = false; this._render(); }
    });

    root.querySelector('#add-btn')
      .addEventListener('click', () => this._addRule());

    root.querySelector('#save-btn')
      .addEventListener('click', () => this._save());

    root.querySelectorAll('.del-btn').forEach(btn =>
      btn.addEventListener('click', () => this._deleteRule(+btn.dataset.idx))
    );

    root.querySelectorAll('.up-btn').forEach(btn =>
      btn.addEventListener('click', () => this._moveRule(+btn.dataset.idx, -1))
    );

    root.querySelectorAll('.dn-btn').forEach(btn =>
      btn.addEventListener('click', () => this._moveRule(+btn.dataset.idx, +1))
    );

    // Mark dirty on any edit
    root.querySelectorAll('input').forEach(inp =>
      inp.addEventListener('input', () => {
        if (!this._dirty) {
          this._dirty = true;
          const dot = document.createElement('span');
          dot.className = 'unsaved-dot';
          const btn = root.querySelector('#save-btn');
          if (btn && !btn.querySelector('.unsaved-dot')) btn.appendChild(dot);
        }
      })
    );
  }
}

customElements.define('smart-shades-panel', SmartShadesPanel);
