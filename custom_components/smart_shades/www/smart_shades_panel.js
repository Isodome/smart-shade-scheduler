/**
 * Smart Shade Scheduler — sidebar panel
 *
 * Condition tokens (space-separated, case-insensitive):
 *   az>150  az>=150  az<200  az<=200  az==180   azimuth
 *   el>5    el>=5    el<30   el<=30   el==10    elevation
 *   t>8:30  t>=8:30  t<22:00 t<=22:00 t==8:00   time (HH:MM)
 *   mo>=6   mo<=8    mo==12                     month (1-12)
 *   home    away                                presence (requires presence entity)
 *   (empty) catch-all — always matches
 */

import { parseCondition, validateCondition, formatCondition } from './conditions.js';

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

  /* ── Mode tabs (sticky) ────────────────────────────── */
  .tab-bar-wrap {
    position: sticky;
    top: 0;
    z-index: 20;
    background: var(--primary-background-color);
    margin: 0 -20px;
    padding: 8px 20px;
    box-shadow: 0 2px 6px rgba(0,0,0,.1);
    margin-bottom: 16px;
  }
  .mode-tabs { display: flex; gap: 8px; flex-wrap: wrap; }
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
  .mode-tab.orphaned {
    border-style: dashed;
    opacity: .75;
  }
  .mode-tab.orphaned.active {
    background: #e65100;
    border-color: #e65100;
    opacity: 1;
  }
  .mode-tab.special {
    border-style: dotted;
    font-style: italic;
    color: var(--secondary-text-color);
  }
  .mode-tab.special.active {
    background: #5c6bc0;
    border-color: #5c6bc0;
    color: #fff;
    font-style: italic;
  }
  .orphan-warn { font-size: 11px; margin-left: 4px; vertical-align: middle; }
  .section-special { color: #5c6bc0; }
  .live-dot {
    display: inline-block;
    width: 7px; height: 7px;
    border-radius: 50%;
    background: #4caf50;
    margin-left: 6px;
    vertical-align: middle;
  }

  /* ── Mode sections ─────────────────────────────────── */
  .mode-section { margin-bottom: 24px; scroll-margin-top: 60px; }
  .section-heading {
    font-size: 13px; font-weight: 700; letter-spacing: .06em;
    color: var(--secondary-text-color);
    margin-bottom: 8px; text-transform: uppercase;
  }

  /* ── Card / table ──────────────────────────────────── */
  .table-card {
    background: var(--card-background-color);
    border-radius: 12px;
    box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0,0,0,.12));
    overflow: hidden;
    margin-bottom: 12px;
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
  tbody.cover-group {
    border-bottom: 3px solid var(--divider-color);
  }
  tbody.cover-group:last-child {
    border-bottom: none;
  }
  td.covers-cell {
    vertical-align: top;
    background: rgba(0,0,0,.015);
    border-right: 1px solid var(--divider-color);
    padding: 10px;
  }
  tbody td {
    padding: 5px 8px;
    border-bottom: 1px solid var(--divider-color);
    vertical-align: middle;
  }
  tbody tr:last-child td { border-bottom: none; }
  tbody tr:hover { background: var(--secondary-background-color, rgba(0,0,0,.03)); }
  tr.has-override { background: rgba(255,152,0,.08) !important; }
  tr.row-invalid  { opacity: .55; }
  tr.row-invalid .f-pos, tr.row-invalid .f-tilt { border-color: var(--error-color, #b00020); }

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
  .override-icon { color: #ff9800; cursor: default; font-size: 14px; margin-left: 4px; }

  /* ── Cover chip picker ─────────────────────────────── */
  .cover-picker { display: flex; flex-direction: column; gap: 4px; }
  .chips { display: flex; flex-wrap: wrap; gap: 4px; min-height: 4px; }
  .chip {
    display: inline-flex; align-items: center; gap: 3px;
    background: var(--primary-color); color: var(--text-primary-color, #fff);
    border-radius: 12px; padding: 2px 6px 2px 8px; font-size: 13px;
    white-space: nowrap;
  }
  .chip-rm {
    background: none; border: none; cursor: pointer; padding: 0 1px;
    color: inherit; opacity: .7; font-size: 12px; line-height: 1;
  }
  .chip-rm:hover { opacity: 1; }
  .chip-warn { background: #e65100; }
  .cover-add {
    border: 1px solid transparent; border-radius: 6px; padding: 3px 6px;
    min-width: 120px; flex: 1;
    background: transparent; color: inherit; font-size: 12px;
  }
  .cover-add:hover { border-color: var(--divider-color); background: var(--primary-background-color); }
  .cover-add:focus { outline: none; border-color: var(--primary-color); background: var(--primary-background-color); }

  /* ── Condition validation badge ───────────────────── */
  .cond-wrap { display: flex; align-items: center; gap: 4px; }
  .cond-badge {
    flex-shrink: 0; font-size: 13px; line-height: 1;
    transition: color .15s;
  }
  .cond-badge.ok    { color: #4caf50; }
  .cond-badge.error { color: var(--error-color, #b00020); }

  /* ── Helpers link ──────────────────────────────────── */
  .helpers-link {
    font-size: 12px; color: var(--primary-color);
    text-decoration: none; opacity: .8;
  }
  .helpers-link:hover { opacity: 1; text-decoration: underline; }

  /* ── Mode options (toggle switches) ───────────────── */
  .mode-opts {
    display: flex; gap: 20px; padding: 6px 12px 10px;
    font-size: 12px; color: var(--secondary-text-color);
  }
  .mode-opts label {
    display: flex; align-items: center; gap: 8px; cursor: pointer;
    user-select: none;
  }
  .mode-opts input[type=checkbox] { display: none; }
  .toggle-track {
    position: relative;
    width: 36px; height: 20px; flex-shrink: 0;
    background: var(--divider-color);
    border-radius: 10px;
    transition: background .2s;
  }
  .toggle-track::after {
    content: '';
    position: absolute;
    top: 3px; left: 3px;
    width: 14px; height: 14px;
    border-radius: 50%;
    background: #fff;
    box-shadow: 0 1px 3px rgba(0,0,0,.3);
    transition: transform .2s;
  }
  input[type=checkbox]:checked + .toggle-track {
    background: var(--primary-color);
  }
  input[type=checkbox]:checked + .toggle-track::after {
    transform: translateX(16px);
  }

  /* ── Add buttons ───────────────────────────────────── */
  .add-row td { padding: 0; }
  .add-rule-btn {
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
  .add-rule-btn:hover { background: var(--secondary-background-color); }
  
  .add-group-btn {
    display: inline-flex;
    align-items: center;
    padding: 6px 14px;
    background: transparent;
    border: 1px solid var(--primary-color);
    color: var(--primary-color);
    border-radius: 16px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    margin-bottom: 24px;
    transition: background .15s, color .15s;
    line-height: 1;
  }
  .add-group-btn:hover {
    background: var(--primary-color);
    color: var(--text-primary-color, #fff);
  }

  /* ── Footer ────────────────────────────────────────── */
  .footer {
    margin-top: 14px;
  }

  /* ── Header actions (save + hamburger) ─────────────── */
  .tab-bar-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .mode-tabs { flex: 1; }
  .header-actions { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
  .hamburger-wrap { position: relative; }
  .hamburger-btn {
    background: var(--card-background-color);
    border: 1px solid var(--divider-color);
    border-radius: 8px;
    padding: 7px 11px;
    font-size: 16px;
    cursor: pointer;
    color: var(--primary-text-color);
    line-height: 1;
    transition: background .12s;
  }
  .hamburger-btn:hover { background: var(--secondary-background-color); }
  .hamburger-menu {
    display: none;
    position: absolute;
    right: 0;
    top: calc(100% + 6px);
    background: var(--card-background-color);
    border-radius: 10px;
    box-shadow: 0 4px 20px rgba(0,0,0,.2);
    min-width: 190px;
    z-index: 100;
    overflow: hidden;
  }
  .hamburger-menu.open { display: block; }
  .hamburger-menu button {
    display: block; width: 100%; padding: 11px 16px;
    text-align: left; background: none; border: none; border-bottom: 1px solid var(--divider-color);
    color: var(--primary-text-color); cursor: pointer; font-size: 13px;
  }
  .hamburger-menu button:last-child { border-bottom: none; }
  .hamburger-menu button:hover { background: var(--secondary-background-color); }
  dialog {
    border: none;
    border-radius: 12px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.2);
    padding: 24px;
    background: var(--primary-background-color);
    color: var(--primary-text-color);
    width: 90%;
    max-width: 600px;
  }
  dialog::backdrop {
    background: rgba(0,0,0,0.5);
  }
  .dialog-title {
    margin: 0 0 16px 0;
    font-size: 18px;
    font-weight: 500;
  }
  .dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 16px;
  }
  textarea.dialog-textarea {
    width: 100%;
    height: 300px;
    padding: 12px;
    border: 1px solid var(--divider-color);
    border-radius: 8px;
    background: var(--card-background-color);
    color: var(--primary-text-color);
    font-family: monospace;
    font-size: 13px;
    resize: vertical;
  }
  textarea.dialog-textarea:focus {
    outline: none;
    border-color: var(--primary-color);
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

  /* ── Undo toast ────────────────────────────────────── */
  .undo-toast {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%);
    background: #323232;
    color: #fff;
    padding: 12px 20px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    gap: 20px;
    font-size: 14px;
    box-shadow: 0 4px 16px rgba(0,0,0,.35);
    z-index: 200;
    white-space: nowrap;
  }
  .undo-toast-btn {
    background: none; border: none;
    color: #90caf9; font-weight: 600;
    font-size: 14px; cursor: pointer; padding: 0;
  }
  .undo-toast-btn:hover { text-decoration: underline; }
`;

// ─────────────────────────────────────────────────────────────────────────────

class SmartShadesPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._hass        = null;
    this._cfg         = null;   // data from ws_get_config
    this._groups      = [];     // working copy of rule groups
    this._modes       = [];     // ordered mode tab list
    this._mode        = null;   // selected tab
    this._orphaned    = new Set();
    this._special     = new Set();
    this._dirty         = false;
    this._saving        = false;
    this._error         = null;
    this._pendingDelete = null; // { group, gIdx, timer }
    this._modeConfig    = {};   // mode → { block_fallback, force }
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._cfg) this._load();
  }

  async _load() {
    try {
      const cfg = await this._ws('smart_shades/get_config');
      this._cfg        = cfg;
      this._groups     = JSON.parse(JSON.stringify(cfg.rules || []));
      this._modeConfig = JSON.parse(JSON.stringify(cfg.mode_config || {}));
      this._modes      = cfg.mode_options || [];
      this._orphaned = new Set(cfg.orphaned_modes || []);
      this._special  = new Set(cfg.special_modes  || []);
      this._mode     = this._modes.includes(cfg.current_mode)
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

  _collect() {
    const root = this.shadowRoot;
    const newGroups = [];
    
    // Maintain exact order from memory, just update properties from DOM where DOM exists
    for (let gIdx = 0; gIdx < this._groups.length; gIdx++) {
      const gObj = this._groups[gIdx];
      const groupEl = root.querySelector(`tbody.cover-group[data-gidx="${gIdx}"]`);
      if (!groupEl) {
        newGroups.push(gObj); // Keep if not currently rendered (wrong tab)
        continue;
      }
      
      const picker = groupEl.querySelector('.cover-picker');
      const covers = picker ? JSON.parse(picker.dataset.covers || '[]') : [];
      
      const rules = [];
      for (const row of groupEl.querySelectorAll('tr.rule-row')) {
        const condStr = row.querySelector('.f-cond').value;
        const conditions = parseCondition(condStr);
        
        const action = {};
        const pos = row.querySelector('.f-pos').value;
        if (pos !== '') action.position = parseInt(pos, 10);
        
        const tilt = row.querySelector('.f-tilt').value;
        if (tilt !== '') action.tilt = parseInt(tilt, 10);
        
        rules.push({ conditions, action });
      }
      
      newGroups.push({ ...gObj, covers, rules });
    }
    
    this._groups = newGroups;
  }

  _coverPickerHtml(covers) {
    const states = this._hass?.states || {};
    const chips = (covers || []).map(c => {
      const known = c in states;
      const cls = known ? 'chip' : 'chip chip-warn';
      const title = known ? '' : ` title="Entity not found"`;
      return `<span class="${cls}"${title}>${c}<button class="chip-rm" data-cover="${c}">✕</button></span>`;
    }).join('');
    return `<div class="cover-picker" data-covers='${JSON.stringify(covers || [])}'>
      <div class="chips">${chips}</div>
      <input class="cover-add" list="covers-list" placeholder="add cover…" autocomplete="off" />
    </div>`;
  }

  _addGroup(mode) {
    this._collect();
    this._groups.push({ mode, covers: [], rules: [] });
    this._dirty = true;
    this._render();
  }

  _deleteGroup(gIdx) {
    this._collect();
    // Clear any previous pending delete
    if (this._pendingDelete) clearTimeout(this._pendingDelete.timer);
    const group = JSON.parse(JSON.stringify(this._groups[gIdx]));
    this._groups.splice(gIdx, 1);
    this._dirty = true;
    const timer = setTimeout(() => { this._pendingDelete = null; this._removeToast(); }, 5000);
    this._pendingDelete = { group, gIdx, timer };
    this._render();
  }

  _undoDelete() {
    if (!this._pendingDelete) return;
    clearTimeout(this._pendingDelete.timer);
    const { group, gIdx } = this._pendingDelete;
    this._pendingDelete = null;
    this._groups.splice(gIdx, 0, group);
    this._render();
  }

  _removeToast() {
    this.shadowRoot.querySelector('.undo-toast')?.remove();
  }

  _addRule(gIdx) {
    this._collect();
    if (!this._groups[gIdx].rules) this._groups[gIdx].rules = [];
    this._groups[gIdx].rules.push({ conditions: [], action: {} });
    this._dirty = true;
    this._render();
  }

  _deleteRule(gIdx, rIdx) {
    this._collect();
    this._groups[gIdx].rules.splice(rIdx, 1);
    this._dirty = true;
    this._render();
  }

  _moveRule(gIdx, rIdx, dir) {
    this._collect();
    const rules = this._groups[gIdx].rules;
    if (rIdx + dir < 0 || rIdx + dir >= rules.length) return;
    [rules[rIdx], rules[rIdx + dir]] = [rules[rIdx + dir], rules[rIdx]];
    this._dirty = true;
    this._render();
  }

  async _save() {
    if (this._saving) return;
    this._collect();
    this._saving = true;
    this._render();
    try {
      const outGroups = [];
      for (const g of this._groups) {
        const validRules = (g.rules || []).filter(r => 
          (r.action && r.action.position != null) || 
          (r.action && r.action.tilt != null) || 
          (r.conditions && r.conditions.length > 0)
        );
        if ((g.covers && g.covers.length > 0) || validRules.length > 0) {
          outGroups.push({ ...g, rules: validRules });
        }
      }

      await this._ws('smart_shades/save_rules', {
        entry_id: this._cfg.entry_id,
        rules: outGroups,
        mode_config: this._modeConfig,
      });
      this._dirty  = false;
      this._error  = null;
      this._saving = false;
      this._cfg = null;
      await this._load();
    } catch (e) {
      this._error  = `Save failed: ${e.message ?? e}`;
      this._saving = false;
      this._render();
    }
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

    const MODE_LABELS = { '_priority': '↑ Priority', '_fallback': '↓ Default' };
    const MODE_TITLES = {
      '_priority': 'Evaluated before all mode rules — overrides everything',
      '_fallback': 'Evaluated only when no mode rule matched a cover',
    };

    const tabsHtml = this._modes.map(m => {
      const orphaned = this._orphaned.has(m);
      const special  = this._special.has(m);
      const cls = [
        'mode-tab',
        m === this._mode ? 'active' : '',
        orphaned ? 'orphaned' : '',
        special  ? 'special'  : '',
      ].filter(Boolean).join(' ');
      const title = special  ? MODE_TITLES[m]
        : orphaned ? 'Not in input_select — removed when all groups deleted'
        : m;
      return `<button class="${cls}" data-mode="${m}" title="${title}">
        ${MODE_LABELS[m] || m}
        ${orphaned ? '<span class="orphan-warn">⚠</span>' : ''}
        ${m === curMode ? '<span class="live-dot"></span>' : ''}
      </button>`;
    }).join('');

    const sectionsHtml = this._modes.map(mode => {
      // Build mode tables containing multiple groups
      const groupsHtml = this._groups.map((group, gIdx) => {
        if (group.mode !== mode) return '';
        
        const hasGroupOv = (group.covers || []).some(c => overrides.has(c));
        const rules = group.rules || [];
        const rowspan = rules.length + 1; // +1 for the Add Action row

        let rowsHtml = '';

        for (let rIdx = 0; rIdx < rules.length; rIdx++) {
          const r = rules[rIdx];
          const hasContent = (r.conditions && r.conditions.length > 0) || r.action?.position != null || r.action?.tilt != null;
          const isInvalid = hasContent && r.action?.position == null && r.action?.tilt == null;
          const rowClass = isInvalid ? 'row-invalid' : '';
          const condStr = formatCondition(r.conditions);

          const isFirst = rIdx === 0;
          const coversTd = isFirst ? `
            <td rowspan="${rowspan}" class="covers-cell">
              <div style="display:flex; flex-direction:column; height:100%; gap:8px">
                <div>
                  ${this._coverPickerHtml(group.covers)}
                  ${hasGroupOv ? '<span class="override-icon" title="Manual override active">⚠</span>' : ''}
                </div>
                <div style="flex:1"></div>
                <button class="icon-btn del del-group-btn" data-gidx="${gIdx}" title="Delete Group" style="align-self:flex-start">✕ Delete Group</button>
              </div>
            </td>
          ` : '';

          rowsHtml += `
            <tr class="rule-row ${rowClass}" data-gidx="${gIdx}" data-ridx="${rIdx}">
              ${coversTd}
              <td>
                <div class="row-btns" style="flex-direction:column;gap:0">
                  <button class="icon-btn up-btn" data-gidx="${gIdx}" data-ridx="${rIdx}"
                    ${rIdx === 0 ? 'disabled' : ''} title="Move up">▲</button>
                  <button class="icon-btn dn-btn" data-gidx="${gIdx}" data-ridx="${rIdx}"
                    ${rIdx === rules.length - 1 ? 'disabled' : ''} title="Move down">▼</button>
                </div>
              </td>
              <td>
                <div class="cond-wrap">
                  <input class="f-cond" value="${condStr}" placeholder="az>150 el<30" />
                  <span class="cond-badge ${validateCondition(condStr).ok ? 'ok' : 'error'}">${condStr ? (validateCondition(condStr).ok ? '✓' : '✗') : ''}</span>
                </div>
              </td>
              <td><input class="f-pos narrow" type="number" min="0" max="100"
                value="${r.action?.position ?? ''}" placeholder="—" /></td>
              <td><input class="f-tilt narrow" type="number" min="0" max="100"
                value="${r.action?.tilt ?? ''}" placeholder="—" /></td>
              <td>
                <div class="row-btns" style="justify-content:flex-end">
                  <button class="icon-btn del del-rule-btn" data-gidx="${gIdx}" data-ridx="${rIdx}" title="Delete">✕</button>
                </div>
              </td>
            </tr>`;
        }

        const addRowCoversTd = rules.length === 0 ? `
            <td rowspan="${rowspan}" class="covers-cell">
              <div style="display:flex; flex-direction:column; height:100%; gap:8px">
                <div>
                  ${this._coverPickerHtml(group.covers)}
                  ${hasGroupOv ? '<span class="override-icon" title="Manual override active">⚠</span>' : ''}
                </div>
                <div style="flex:1"></div>
                <button class="icon-btn del del-group-btn" data-gidx="${gIdx}" title="Delete Group" style="align-self:flex-start">✕ Delete Group</button>
              </div>
            </td>
        ` : '';

        return `
          <tbody class="cover-group" data-mode="${mode}" data-gidx="${gIdx}">
            ${rowsHtml}
            <tr class="add-row">
              ${addRowCoversTd}
              <td colspan="5">
                <button class="add-rule-btn" data-gidx="${gIdx}">＋ Add Action</button>
              </td>
            </tr>
          </tbody>`;
      }).join('');

      const isSpecial = this._special.has(mode);
      const mc = this._modeConfig[mode] || {};
      const modeOptsHtml = isSpecial ? '' : `
        <div class="mode-opts">
          <label title="When this mode is active, covers not targeted by any rule in this mode are left completely untouched — the ↓ Default rules do not run. Use this for modes where you only want to control specific covers and leave everything else as-is.">
            <input type="checkbox" class="mc-block-fallback" data-mode="${mode}" ${mc.block_fallback ? 'checked' : ''}>
            <span class="toggle-track"></span>
            Block fallback</label>
          <label title="When the mode switches to this mode, manual overrides are cleared — but only for covers that have at least one rule in this mode (including ↑ Priority and ↓ Default rules). Other covers are left untouched. Cleared covers will immediately move to their scheduled positions.">
            <input type="checkbox" class="mc-force" data-mode="${mode}" ${mc.force ? 'checked' : ''}>
            <span class="toggle-track"></span>
            Force on switch</label>
        </div>`;

      return `
        <div class="mode-section" id="mode-sec-${mode}" data-mode="${mode}">
          <div class="section-heading${isSpecial ? ' section-special' : ''}">
            ${MODE_LABELS[mode] || mode}
            ${this._orphaned.has(mode) ? ' <span class="orphan-warn">⚠ not in input_select</span>' : ''}
          </div>
          ${modeOptsHtml}
          <div class="table-card">
            <table>
              <thead>
                <tr>
                  <th style="width: 30%">Covers</th>
                  <th style="width: 46px"></th>
                  <th style="width: 40%">Condition</th>
                  <th style="width: 15%">Pos%</th>
                  <th style="width: 15%">Tilt%</th>
                  <th style="width: 64px"></th>
                </tr>
              </thead>
              ${groupsHtml}
            </table>
          </div>
          <button class="add-group-btn" data-mode="${mode}">＋ Add Cover Group</button>
        </div>`;
    }).join('');

    const coverOptions = Object.keys(this._hass.states)
      .filter(e => e.startsWith('cover.'))
      .sort()
      .map(e => `<option value="${e}">`)
      .join('');

    const modeEntity = this._cfg.mode_entity;
    const helpersLink = modeEntity
      ? `<a class="helpers-link" id="helpers-link" href="#"
           title="Manage ${modeEntity} options">⚙ Mode options</a>`
      : '';

    root.innerHTML = `
      <style>${CSS}</style>
      <datalist id="covers-list">${coverOptions}</datalist>

      <div style="display:flex;align-items:baseline;gap:12px;padding:16px 20px 0">
        <h1 style="margin:0">Shade Scheduler</h1>
        ${helpersLink}
      </div>

      <div class="tab-bar-wrap">
        <div class="mode-tabs">${tabsHtml}</div>
        <div class="header-actions">
          <button class="save-btn" id="save-btn" ${this._saving ? 'disabled' : ''}>
            ${this._saving ? 'Saving…' : 'Save'}
            ${this._dirty && !this._saving ? '<span class="unsaved-dot"></span>' : ''}
          </button>
          <div class="hamburger-wrap">
            <button class="hamburger-btn" id="hamburger-btn" title="More options">☰</button>
            <div class="hamburger-menu" id="hamburger-menu">
              <button id="llm-btn">Generate LLM Prompt</button>
              <button id="export-btn">Export</button>
              <button id="import-btn">Import</button>
            </div>
          </div>
        </div>
      </div>

      ${this._error ? `<div class="error-banner" style="margin:0 0 16px">${this._error}</div>` : ''}

      ${sectionsHtml}

      <div class="footer">
        <span class="hint">
          Conditions (space-separated, empty = catch-all):<br>
          <code>az&gt;150</code> <code>az&gt;=150</code> <code>az==180</code> azimuth &nbsp;
          <code>el&gt;5</code> <code>el&lt;30</code> elevation &nbsp;
          <code>t&gt;=8:30</code> <code>t&lt;22:00</code> <code>t==8:00</code> time &nbsp;
          <code>mo&gt;=6</code> <code>mo&lt;=8</code> month (1–12) &nbsp;
          <code>home</code> <code>away</code> presence<br>
          First matching rule wins per cover. ⚠ = manual override active.<br>
          <strong>↑ Priority</strong> rules are evaluated before all mode rules and override everything. &nbsp;
          <strong>↓ Default</strong> rules are evaluated only when no rule in the current mode matched a cover.
        </span>
      </div>

      <dialog id="import-dialog">
        <h3 class="dialog-title">Import Rules</h3>
        <div style="margin-bottom:8px; font-size:13px; opacity:0.8;">Paste your JSON rules here. This will OVERWRITE all existing rules.</div>
        <textarea id="import-textarea" class="dialog-textarea" placeholder="[ { mode: '...', covers: [...], rules: [...] } ]"></textarea>
        <div class="dialog-actions">
          <button class="secondary-btn" id="import-cancel">Cancel</button>
          <button class="save-btn" id="import-confirm">Import & Replace</button>
        </div>
      </dialog>

      ${this._pendingDelete ? `
      <div class="undo-toast">
        <span>Cover group deleted</span>
        <button class="undo-toast-btn" id="undo-btn">Undo</button>
      </div>` : ''}

      <dialog id="fallback-dialog">
        <h3 class="dialog-title" id="fallback-title">Copy to Clipboard</h3>
        <div style="margin-bottom:8px; font-size:13px; opacity:0.8;">Your browser blocked automatic copying. Please copy the text below manually.</div>
        <textarea id="fallback-textarea" class="dialog-textarea" readonly></textarea>
        <div class="dialog-actions">
          <button class="save-btn" id="fallback-close">Close</button>
        </div>
      </dialog>`;

    // ── Event wiring ───────────────────────────────────────────────

    root.querySelectorAll('.mode-tab[data-mode]').forEach(btn =>
      btn.addEventListener('click', () => {
        this._mode = btn.dataset.mode;
        root.querySelectorAll('.mode-tab').forEach(t =>
          t.classList.toggle('active', t.dataset.mode === this._mode)
        );
        root.querySelector(`#mode-sec-${this._mode}`)
          ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      })
    );

    const io = new IntersectionObserver(entries => {
      for (const e of entries) {
        if (e.isIntersecting) {
          this._mode = e.target.dataset.mode;
          root.querySelectorAll('.mode-tab[data-mode]').forEach(t =>
            t.classList.toggle('active', t.dataset.mode === this._mode)
          );
        }
      }
    }, { threshold: 0.25 });
    root.querySelectorAll('.mode-section').forEach(s => io.observe(s));

    root.querySelector('#save-btn').addEventListener('click', () => this._save());

    root.querySelectorAll('.add-group-btn').forEach(btn =>
      btn.addEventListener('click', () => this._addGroup(btn.dataset.mode))
    );
    root.querySelectorAll('.del-group-btn').forEach(btn =>
      btn.addEventListener('click', () => this._deleteGroup(+btn.dataset.gidx))
    );
    root.querySelector('#undo-btn')?.addEventListener('click', () => this._undoDelete());
    
    root.querySelectorAll('.add-rule-btn').forEach(btn =>
      btn.addEventListener('click', () => this._addRule(+btn.dataset.gidx))
    );
    root.querySelectorAll('.del-rule-btn').forEach(btn =>
      btn.addEventListener('click', () => this._deleteRule(+btn.dataset.gidx, +btn.dataset.ridx))
    );
    root.querySelectorAll('.up-btn').forEach(btn =>
      btn.addEventListener('click', () => this._moveRule(+btn.dataset.gidx, +btn.dataset.ridx, -1))
    );
    root.querySelectorAll('.dn-btn').forEach(btn =>
      btn.addEventListener('click', () => this._moveRule(+btn.dataset.gidx, +btn.dataset.ridx, +1))
    );

    const markDirty = () => {
      if (this._dirty) return;
      this._dirty = true;
      const btn = root.querySelector('#save-btn');
      if (btn && !btn.querySelector('.unsaved-dot')) {
        const dot = document.createElement('span');
        dot.className = 'unsaved-dot';
        btn.appendChild(dot);
      }
    };

    const rebindChips = (picker) => {
      picker.querySelectorAll('.chip-rm').forEach(btn =>
        btn.addEventListener('click', () => {
          const covers = JSON.parse(picker.dataset.covers || '[]');
          picker.dataset.covers = JSON.stringify(
            covers.filter(c => c !== btn.dataset.cover)
          );
          picker.querySelector('.chips').innerHTML = JSON.parse(picker.dataset.covers)
            .map(c => `<span class="chip">${c}<button class="chip-rm" data-cover="${c}">✕</button></span>`)
            .join('');
          rebindChips(picker);
          markDirty();
        })
      );
    };

    root.querySelectorAll('.cover-picker').forEach(picker => {
      rebindChips(picker);
      const inp = picker.querySelector('.cover-add');
      const commit = () => {
        const val = inp.value.trim();
        if (!val) return;
        const covers = JSON.parse(picker.dataset.covers || '[]');
        if (!covers.includes(val)) {
          covers.push(val);
          picker.dataset.covers = JSON.stringify(covers);
          picker.querySelector('.chips').innerHTML = covers
            .map(c => `<span class="chip">${c}<button class="chip-rm" data-cover="${c}">✕</button></span>`)
            .join('');
          rebindChips(picker);
          markDirty();
        }
        inp.value = '';
      };
      inp.addEventListener('change', commit);
      inp.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); commit(); } });
    });

    root.querySelectorAll('.f-cond').forEach(inp => {
      const badge = inp.nextElementSibling;
      const update = () => {
        const v = validateCondition(inp.value);
        if (!inp.value.trim()) {
          badge.textContent = '';
          badge.className = 'cond-badge';
        } else {
          badge.textContent = v.ok ? '✓' : '✗';
          badge.className   = `cond-badge ${v.ok ? 'ok' : 'error'}`;
          badge.title       = v.ok ? '' : `Unknown token(s): ${v.bad.join(', ')}`;
        }
        markDirty();
      };
      inp.addEventListener('input', update);
    });

    root.querySelectorAll('.f-pos, .f-tilt').forEach(inp =>
      inp.addEventListener('input', markDirty)
    );

    root.querySelector('#helpers-link')?.addEventListener('click', e => {
      e.preventDefault();
      const entity = this._cfg?.mode_entity;
      if (entity) {
        history.pushState(null, '', `/?more-info-entity-id=${entity}`);
        window.dispatchEvent(new CustomEvent('location-changed'));
      }
    });

    // ── Mode config checkboxes ────────────────────────────────────────
    root.querySelectorAll('.mc-block-fallback').forEach(cb =>
      cb.addEventListener('change', () => {
        const m = cb.dataset.mode;
        this._modeConfig[m] = { ...(this._modeConfig[m] || {}), block_fallback: cb.checked };
        markDirty();
      })
    );
    root.querySelectorAll('.mc-force').forEach(cb =>
      cb.addEventListener('change', () => {
        const m = cb.dataset.mode;
        this._modeConfig[m] = { ...(this._modeConfig[m] || {}), force: cb.checked };
        markDirty();
      })
    );

    // ── Hamburger menu ────────────────────────────────────────────────
    const hamburgerBtn  = root.querySelector('#hamburger-btn');
    const hamburgerMenu = root.querySelector('#hamburger-menu');
    hamburgerBtn?.addEventListener('click', e => {
      e.stopPropagation();
      hamburgerMenu.classList.toggle('open');
    });
    root.addEventListener('click', () => hamburgerMenu?.classList.remove('open'));

    // ── Tools ─────────────────────────────────────────────────────────

    const copyToClipboard = async (text, title) => {
      try {
        if (!navigator.clipboard) throw new Error('No clipboard API');
        await navigator.clipboard.writeText(text);
        alert('Copied to clipboard!');
      } catch (e) {
        const d = root.querySelector('#fallback-dialog');
        root.querySelector('#fallback-title').textContent = title;
        root.querySelector('#fallback-textarea').value = text;
        d.showModal();
      }
    };

    root.querySelector('#export-btn')?.addEventListener('click', () => {
      this._collect();
      const json = JSON.stringify(this._groups, null, 2);
      copyToClipboard(json, 'Export Rules');
    });

    root.querySelector('#import-btn')?.addEventListener('click', () => {
      const d = root.querySelector('#import-dialog');
      root.querySelector('#import-textarea').value = '';
      d.showModal();
    });

    root.querySelector('#import-cancel')?.addEventListener('click', () => {
      root.querySelector('#import-dialog').close();
    });

    root.querySelector('#fallback-close')?.addEventListener('click', () => {
      root.querySelector('#fallback-dialog').close();
    });

    root.querySelector('#import-confirm')?.addEventListener('click', () => {
      const val = root.querySelector('#import-textarea').value;
      try {
        const parsed = JSON.parse(val);
        if (!Array.isArray(parsed)) throw new Error('Import must be an array of rule groups');
        this._groups = parsed;
        this._dirty = true;
        root.querySelector('#import-dialog').close();
        this._render();
      } catch (e) {
        alert('Invalid JSON: ' + e.message);
      }
    });

    root.querySelector('#llm-btn')?.addEventListener('click', () => {
      this._collect();

      // Group covers by device
      const entities = this._hass.entities || {};
      const devices = this._hass.devices || {};
      const states = this._hass.states || {};
      const covers = Object.keys(states).filter(e => e.startsWith('cover.'));
      
      const devicesMap = new Map();
      const noDeviceCovers = [];

      for (const e of covers) {
        const s = states[e];
        const friendly = s.attributes.friendly_name || e;
        const reg = entities[e];
        if (reg && reg.device_id) {
          if (!devicesMap.has(reg.device_id)) {
            const dev = devices[reg.device_id];
            const devName = dev ? (dev.name_by_user || dev.name || 'Unknown Device') : 'Unknown Device';
            devicesMap.set(reg.device_id, { name: devName, entities: [] });
          }
          devicesMap.get(reg.device_id).entities.push({ id: e, name: friendly });
        } else {
          noDeviceCovers.push({ id: e, name: friendly });
        }
      }

      let coversPrompt = '';
      for (const [id, dev] of devicesMap.entries()) {
        coversPrompt += `- Device: ${dev.name}\n`;
        for (const ent of dev.entities) {
          coversPrompt += `  - ${ent.id} (${ent.name})\n`;
        }
      }
      if (noDeviceCovers.length > 0) {
        coversPrompt += `- Other covers:\n`;
        for (const ent of noDeviceCovers) {
          coversPrompt += `  - ${ent.id} (${ent.name})\n`;
        }
      }

      const modeConfigSummary = Object.entries(this._modeConfig)
        .filter(([, v]) => v.block_fallback || v.force)
        .map(([m, v]) => {
          const flags = [];
          if (v.block_fallback) flags.push('block_fallback');
          if (v.force) flags.push('force_on_switch');
          return `- ${m}: ${flags.join(', ')}`;
        }).join('\n') || '(none)';

      const prompt = `I am building a system to automate my shades in Home Assistant.
Unlike standard Home Assistant automations which are event-driven and based on momentary triggers, this system operates as a continuous state engine. Declarative rules dictate the absolute position and tilt that covers should have based on current environmental inputs (time, sun azimuth/elevation, month, presence). The system evaluates rules periodically and on sun/mode changes, and moves covers to match the desired state.
The active set of rules is chosen based on a specific input_select entity (the "Mode").

### System State
Available Modes: ${this._modes.join(', ')}

Available Covers:
${coversPrompt}

### Data Structure
There are two top-level objects stored together:

**1. rules** — array of groups. Each group targets one mode and one set of covers, with an ordered list of condition→action rules. The first rule whose conditions all match is applied to the covers in that group; subsequent rules in the same group are ignored for those covers.

\`\`\`json
[
  {
    "mode": "COOLING",
    "covers": ["cover.blind_office", "cover.blind_office_2"],
    "rules": [
      {
        "conditions": [
          {"var": "azimuth",   "op": ">",  "val": 150},
          {"var": "elevation", "op": ">=", "val": 5},
          {"var": "time",      "op": ">",  "val": 830},
          {"var": "month",     "op": ">=", "val": 6},
          {"var": "presence",  "op": "==", "val": "home"}
        ],
        "action": {"position": 0, "tilt": 50}
      },
      {
        "conditions": [],
        "action": {"position": 100}
      }
    ]
  }
]
\`\`\`

Condition variables: "azimuth" (degrees 0–360), "elevation" (degrees, negative when below horizon), "time" (HHMM integer — 08:30 → 830, 19:00 → 1900), "month" (1–12), "presence" ("home" or "away", requires a presence entity configured at setup).
Operators: ">", ">=", "<", "<=", "==". All conditions in a rule are ANDed.
An empty conditions array ("conditions": []) is a catch-all — it always matches unconditionally. Place it as the last rule in a group to act as a default/fallback for that group's covers when no earlier rule's conditions were met.
Action fields: "position" (0–100, omit to leave position unchanged), "tilt" (0–100, omit to leave tilt unchanged). At least one must be present.

**2. mode_config** — optional per-mode flags, keyed by mode name:

\`\`\`json
{
  "RAIN":    { "block_fallback": true,  "force": true  },
  "COOLING": { "block_fallback": false, "force": false }
}
\`\`\`

- **block_fallback**: When true for the active mode, the _fallback pass is skipped entirely. Covers not matched by priority or mode rules are left untouched. Useful for modes like RAIN where you only want to control specific covers.
- **force**: When the mode switches to this mode, all manual overrides are immediately cleared before evaluation runs. Every cover moves to its scheduled position regardless of prior manual adjustments.

### Evaluation Order (3-pass)
1. **_priority** groups run first, regardless of which mode is active. Use for rules that must always apply (e.g. retract awnings at night or during rain).
2. **Current mode** groups run next. Groups are evaluated top-to-bottom; the first group whose conditions match claims its covers. A cover claimed here cannot be overwritten by later groups.
3. **_fallback** groups run last, only for covers not yet claimed by priority or mode rules. Skipped entirely if block_fallback is set for the active mode.

### Current Mode Config
${modeConfigSummary}

### Current Rules
\`\`\`json
${JSON.stringify(this._groups, null, 2)}
\`\`\`

Please help me write/modify the rules based on my requirements.`;

      copyToClipboard(prompt, 'LLM Prompt');
    });
  }
}

customElements.define('smart-shades-panel', SmartShadesPanel);
