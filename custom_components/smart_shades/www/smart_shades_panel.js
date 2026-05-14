/**
 * Smart Shade Scheduler — sidebar panel
 *
 * Condition tokens (space-separated, case-insensitive):
 *
 * Range (continuous):
 *   az>150  az>=150  az<200  az<=200  az==180   azimuth
 *   el>5    el>=5    el<30   el<=30   el==10    elevation
 *   t>8:30  t>=8:30  t<22:00 t<=22:00 t==8:00   time (HH:MM)
 *   mo>=6   mo<=8    mo==12                     month (1-12)
 *   name>val                                    custom sensor variable
 *   (empty) catch-all — always matches
 *
 * Crossing (fires once when threshold is crossed between evaluations):
 *   az=185  el=10   t=7:30   either direction
 *   az=^185 el=^10           rising only  (e.g. el=^10 = sunrise above 10°)
 *   az=v185 el=v10           falling only (e.g. el=v10 = sunset below 10°)
 */

// ── Condition logic (inlined from conditions.js to avoid async-import timing issues) ──

const _DISPLAY = {
  az: { hintExamples: ['az&gt;150', 'az&gt;=150', 'az==180'], llm: '"az" / "azimuth" (degrees 0–360)' },
  el: { hintExamples: ['el&gt;5', 'el&lt;30'],                llm: '"el" / "elevation" (degrees, negative when below horizon)' },
  t:  { hintExamples: ['t&gt;=8:30', 't&lt;22:00'],          llm: '"t" / "time" (HHMM integer — 08:30 → 830, 19:00 → 1900)' },
  mo: { hintExamples: ['mo&gt;=6', 'mo&lt;=8'],               llm: '"mo" / "month" (1–12)' },
  d:  { hintExamples: ['d&lt;=4', 'd==0'],                   llm: '"d" / "day" (weekday: 0=Mon … 6=Sun)' },
};

let CONDITION_SPEC = [];
let _LONG_TO_SHORT = {};
let _TIME_VARS     = new Set();

function initConditionSpec(builtInVars) {
  CONDITION_SPEC = builtInVars.map(v => ({ ...v, ...(_DISPLAY[v.short] ?? {}) }));
  _LONG_TO_SHORT = Object.fromEntries(CONDITION_SPEC.map(s => [s.long, s.short]));
  _TIME_VARS     = new Set(CONDITION_SPEC.filter(s => s.type === 'time').map(s => s.short));
}

initConditionSpec([
  { short: 'az', long: 'azimuth',   type: 'number' },
  { short: 'el', long: 'elevation', type: 'number' },
  { short: 't',  long: 'time',      type: 'time'   },
  { short: 'mo', long: 'month',     type: 'number' },
  { short: 'd',  long: 'day',       type: 'number' },
]);

function conditionHintHtml() {
  const rangeItems = CONDITION_SPEC
    .filter(s => s.hintExamples)
    .map(s => s.hintExamples.map(e => `<code>${e}</code>`).join(' ') + ' ' + s.long)
    .join(' &nbsp;\n          ');
  return `Conditions (space-separated, empty = catch-all):<br>
          ${rangeItems}<br>
          Crossing (fires once): <code>=</code> either &nbsp; <code>=^</code> rising &nbsp; <code>=v</code> falling<br>`;
}

function conditionLlmText() {
  const varList = CONDITION_SPEC.filter(s => s.llm).map(s => s.llm).join(', ');
  return `Condition variables: ${varList}.
Custom variables can be defined in the Variables panel (☰ → Custom Variables): bind a short name to any HA entity or Jinja2 template and use it as a condition token.

Range operators: ">", ">=", "<", "<=", "==". True continuously while the value satisfies the comparison.

Crossing operators (true only in the single evaluation cycle when the threshold is crossed between samples):
- "=" — threshold crossed in either direction
- "=^" — threshold crossed while rising (e.g. {"var":"el","op":"=^","val":10} = sunrise above 10°)
- "=v" — threshold crossed while falling; not applicable to time variables
Crossing conditions never fire on the first evaluation after HA restarts. If a value skips over a threshold between evaluations, the crossing is still detected.

All conditions in a rule are ANDed.`;
}

const _TOKEN_RE = /([a-z][a-z0-9_]*)\s*(>=|<=|==|=\^|=v|>|<|=)\s*(-?\d+(?::\d+)?(?:\.\d+)?)/gi;

function _normalizeVar(raw) {
  const lower = raw.toLowerCase();
  return _LONG_TO_SHORT[lower] ?? lower;
}

function parseCondition(str) {
  const conditions = [];
  for (const [, rawVar, rawOp, val] of str.matchAll(_TOKEN_RE)) {
    conditions.push({ var: _normalizeVar(rawVar), op: rawOp, val: parseFloat(val.replace(':', '')) });
  }
  return conditions;
}

function validateCondition(str) {
  if (!str.trim()) return { ok: true, bad: [] };
  const remaining = str.replace(_TOKEN_RE, '').replace(/\s+/g, '');
  return remaining ? { ok: false, bad: [remaining] } : { ok: true, bad: [] };
}

function formatCondition(conditions) {
  if (!conditions || !Array.isArray(conditions)) return '';
  return conditions.map(cond => {
    const short = _normalizeVar(cond.var);
    let v = cond.val;
    if (_TIME_VARS.has(short)) {
      const strV = String(v).padStart(3, '0');
      v = strV.slice(0, -2) + ':' + strV.slice(-2);
    }
    return `${short}${cond.op}${v}`;
  }).join(' ');
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
    display: flex; align-items: center; justify-content: space-between;
    font-size: 13px; font-weight: 700; letter-spacing: .06em;
    color: var(--secondary-text-color);
    margin-bottom: 8px; text-transform: uppercase; cursor: pointer;
    user-select: none;
  }
  .section-heading:hover { color: var(--primary-text-color); }
  .collapse-btn {
    background: none; border: none; cursor: pointer; padding: 2px 6px;
    color: var(--secondary-text-color); font-size: 12px; border-radius: 4px;
    transition: background .12s;
  }
  .collapse-btn:hover { background: var(--secondary-background-color); color: var(--primary-text-color); }
  .mode-section.collapsed .table-card,
  .mode-section.collapsed .mode-opts,
  .mode-section.collapsed .add-group-btn { display: none; }
  .mode-section.collapsed .section-heading { opacity: .5; font-style: italic; }
  .collapsed-summary {
    display: none; font-size: 12px; color: var(--secondary-text-color);
    padding: 2px 0 8px; cursor: pointer; font-style: normal;
  }
  .collapsed-summary:hover { color: var(--primary-color); }
  .mode-section.collapsed .collapsed-summary { display: block; }

  /* ── Card / table ──────────────────────────────────── */
  .table-card {
    background: var(--card-background-color);
    border-radius: 12px;
    box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0,0,0,.12));
    overflow: hidden;
    margin-bottom: 12px;
    max-width: 1120px;
  }
  table { width: 100%; border-collapse: collapse; table-layout: fixed; }
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
    border-bottom: 1px solid var(--divider-color);
  }
  tbody.cover-group:last-child {
    border-bottom: none;
  }
  td.covers-cell {
    vertical-align: top;
    background: rgba(0,0,0,.015);
    border-right: 1px solid var(--divider-color);
    padding: 10px;
    height: 1px; /* makes height:100% on covers-inner resolve to full row height */
  }
  .covers-inner { display: flex; flex-direction: column; height: 100%; gap: 8px; }
  .covers-content { flex: 1; min-width: 0; }
  .covers-bottom { display: flex; align-items: center; gap: 4px; }
  .covers-bottom .cover-add { flex: 1; }
  tbody td {
    padding: 3px 8px;
    border-bottom: 1px solid var(--divider-color);
    vertical-align: middle;
  }
  tbody tr:last-child td { border-bottom: none; }
  tr.has-override { background: rgba(255,152,0,.08) !important; }

  /* ── Inputs ────────────────────────────────────────── */
  input {
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px 6px;
    width: 100%;
    background: transparent;
    color: inherit;
    font-size: 14px;
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
  input.narrow { width: 53px; text-align: center; }
  input.narrow::-webkit-inner-spin-button,
  input.narrow::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
  input.narrow[type=number] { -moz-appearance: textfield; appearance: textfield; }
  input::placeholder { color: var(--secondary-text-color); opacity: .6; }

  /* ── Row actions ───────────────────────────────────── */
  .row-btns { display: flex; gap: 2px; align-items: center; justify-content: flex-end; opacity: 0; transition: opacity .15s; flex-shrink: 0; width: 108px; }
  .rule-card:hover .row-btns { opacity: 1; }
  .icon-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: 5px 8px;
    border-radius: 4px;
    font-size: 15px;
    line-height: 1.2;
    color: var(--secondary-text-color);
    transition: background .12s, color .12s;
  }
  .icon-btn:hover { background: var(--secondary-background-color); color: var(--primary-text-color); }
  .up-btn:hover, .dn-btn:hover, .up-group-btn:hover, .dn-group-btn:hover { background: var(--primary-color); color: var(--text-primary-color, #fff); }
  .icon-btn:disabled { opacity: .12; cursor: default; }
  .up-btn:disabled, .dn-btn:disabled { visibility: hidden; }
  .up-group-btn:disabled, .dn-group-btn:disabled { display: none; }
  .icon-btn.del:hover { background: var(--error-color, #b00020); color: #fff; }
  .override-icon { color: #ff9800; cursor: default; font-size: 14px; margin-left: 4px; }
  /* ── Group action buttons ──────────────────────────── */
  .group-btns {
    display: flex; flex-direction: row; gap: 2px; justify-content: flex-end;
    opacity: 0; transition: opacity .15s;
  }
  .cover-group:hover .group-btns { opacity: 1; }
  /* ── Pos/tilt bars ─────────────────────────────────── */
  .pt-cell { width: 80px; }
  .pt-row { display: flex; align-items: center; justify-content: center; gap: 4px; }
  /* vertical position bar */
  .pos-bar-track {
    width: 14px; height: 36px; flex-shrink: 0;
    background: var(--divider-color); border-radius: 2px; overflow: hidden;
    display: flex; flex-direction: column; justify-content: flex-start;
  }
  .pos-bar-fill { width: 100%; min-height: 3px; background: linear-gradient(to bottom, rgba(81,110,137,.25), #516E89); transition: height .2s; }
  /* rotating tilt bar */
  .tilt-bar-wrap { width: 28px; height: 36px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; }
  .tilt-bar-wrap svg path { transition: transform .3s; }

  /* ── Cover chip picker ─────────────────────────────── */
  .cover-picker { display: flex; flex-direction: column; gap: 4px; }
  .chips { display: flex; flex-wrap: wrap; gap: 4px; min-height: 4px; }
  .chip {
    display: inline-flex; align-items: center; gap: 3px;
    background: color-mix(in srgb, var(--primary-color) 75%, #000); color: #fff;
    border-radius: 12px; padding: 2px 6px 2px 8px; font-size: 14px;
    max-width: 100%; min-width: 0;
  }
  .chip-label {
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    max-width: 200px;
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

  /* ── Rule cards ────────────────────────────────────── */
  .rules-cell { vertical-align: middle; padding: 6px 8px; }
  .rule-card {
    display: flex; align-items: center; gap: 8px;
    background: var(--secondary-background-color, rgba(0,0,0,.03));
    border-radius: 8px; padding: 5px 8px; margin-bottom: 4px;
    border: 1px solid transparent; transition: border-color .15s;
  }
  .rule-card:hover { border-color: var(--divider-color); }
  .rule-card:last-of-type { margin-bottom: 0; }
  .rule-card.row-invalid { opacity: .55; }
  .rule-card .cond-wrap { flex: 1; }
  /* ── Add action button ─────────────────────────────── */
  .add-col { width: 64px; text-align: center; vertical-align: middle; }
  .add-action-btn {
    background: none; border: none; cursor: pointer;
    color: var(--primary-color); font-size: 22px; line-height: 1;
    padding: 4px 8px; border-radius: 50%;
    transition: background .12s;
  }
  .add-action-btn:hover { background: var(--secondary-background-color); }
  
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
    min-width: 200px;
    z-index: 100;
    overflow: hidden;
  }
  .hamburger-menu.open { display: block; }
  .menu-section { border-top: 1px solid var(--divider-color); }
  .menu-section:first-child { border-top: none; }
  .menu-section-label {
    font-size: 10px; text-transform: uppercase; letter-spacing: 0.07em;
    opacity: 0.5; padding: 8px 16px 3px; pointer-events: none;
  }
  .hamburger-menu button {
    display: block; width: 100%; padding: 9px 16px;
    text-align: left; background: none; border: none;
    color: var(--primary-text-color); cursor: pointer; font-size: 13px;
  }
  .hamburger-menu button:hover { background: var(--secondary-background-color); }
  .hamburger-menu .menu-external::after { content: ' ↗'; opacity: 0.5; font-size: 11px; }
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
    this._modeConfig      = {};   // mode → { block_fallback, force }
    this._customVars = "";   // raw text bindings
    this._varValues  = {};   // all var values (built-ins + custom) from last eval
    this._collapsedModes = new Set();
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
      this._customVars = cfg.custom_vars || "";
      this._varValues  = cfg.var_values  || {};
      initConditionSpec(cfg.built_in_vars || []);
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
      const covers = (picker ? JSON.parse(picker.dataset.covers || '[]') : [])
        .sort((a,b) => (a.slice(6)||a).localeCompare(b.slice(6)||b));
      
      const rules = [];
      for (const row of groupEl.querySelectorAll('.rule-row')) {
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
      const friendlyName = states[c]?.attributes?.friendly_name;
      const tooltipParts = known
        ? [friendlyName, c].filter(Boolean)
        : ['Entity not found', c];
      const label = c.startsWith('cover.') ? c.slice('cover.'.length) : c;
      return `<span class="${cls}" title="${tooltipParts.join('\n')}"><span class="chip-label">${label}</span><button class="chip-rm" data-cover="${c}">✕</button></span>`;
    }).join('');
    return `<div class="cover-picker" data-covers='${JSON.stringify(covers || [])}'>
      <div class="chips">${chips}</div>
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

  _moveGroup(gIdx, dir) {
    this._collect();
    const groups = this._groups;
    const mode = groups[gIdx].mode;
    const modeIdxs = groups.map((g, i) => g.mode === mode ? i : -1).filter(i => i >= 0);
    const pos = modeIdxs.indexOf(gIdx);
    if (pos + dir < 0 || pos + dir >= modeIdxs.length) return;
    const swapIdx = modeIdxs[pos + dir];
    [groups[gIdx], groups[swapIdx]] = [groups[swapIdx], groups[gIdx]];
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
        custom_vars: this._customVars,
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

    const posBarHtml = (val) => {
      const v = (val != null && val !== '') ? parseInt(val, 10) : null;
      const fill = v != null ? (100 - v) : 0;
      const opacity = v == null ? ' opacity:.12;' : '';
      return `<div class="pos-bar-track" style="${opacity}"><div class="pos-bar-fill" style="height:${fill}%"></div></div>`;
    };
    const tiltBarHtml = (val) => {
      const v = (val != null && val !== '') ? parseInt(val, 10) : null;
      const deg = v != null ? ((100 - v) * 0.72) : 36;
      const opacity = v == null ? 'opacity:.12;' : '';
      return `<div class="tilt-bar-wrap" style="${opacity}">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" overflow="visible">
          <path d="M 4 4 Q 12 2 20 4" stroke="var(--secondary-text-color)" stroke-width="2" stroke-linecap="round"
                style="transform-origin:12px 4px;transform:rotate(${deg}deg)"/>
          <path d="M 4 18 Q 12 16 20 18" stroke="var(--secondary-text-color)" stroke-width="2" stroke-linecap="round"
                style="transform-origin:12px 18px;transform:rotate(${deg}deg)"/>
        </svg>
      </div>`;
    };

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
      const modeGroupIdxs = this._groups.map((g, i) => g.mode === mode ? i : -1).filter(i => i >= 0);
      const groupsHtml = this._groups.map((group, gIdx) => {
        if (group.mode !== mode) return '';

        const posInMode = modeGroupIdxs.indexOf(gIdx);
        const isFirstInMode = posInMode === 0;
        const isLastInMode  = posInMode === modeGroupIdxs.length - 1;
        const hasGroupOv = (group.covers || []).some(c => overrides.has(c));
        const rules = group.rules || [];

        const cardsHtml = rules.map((r, rIdx) => {
          const hasContent = (r.conditions && r.conditions.length > 0) || r.action?.position != null || r.action?.tilt != null;
          const isInvalid = hasContent && r.action?.position == null && r.action?.tilt == null;
          const condStr = formatCondition(r.conditions);
          return `
            <div class="rule-card rule-row${isInvalid ? ' row-invalid' : ''}" data-gidx="${gIdx}" data-ridx="${rIdx}">
              <div class="cond-wrap">
                <input class="f-cond" value="${condStr}" placeholder="condition…" />
                <span class="cond-badge ${validateCondition(condStr).ok ? '' : 'error'}">${condStr && !validateCondition(condStr).ok ? '✗' : ''}</span>
              </div>
              <div class="pt-row">
                <input class="f-pos narrow" type="number" min="0" max="100" inputmode="numeric"
                  value="${r.action?.position ?? ''}" placeholder="—" />
                ${posBarHtml(r.action?.position)}
              </div>
              <div class="pt-row">
                ${tiltBarHtml(r.action?.tilt)}
                <input class="f-tilt narrow" type="number" min="0" max="100" inputmode="numeric"
                  value="${r.action?.tilt ?? ''}" placeholder="—" />
              </div>
              <div class="row-btns">
                <button class="icon-btn up-btn" data-gidx="${gIdx}" data-ridx="${rIdx}"
                  ${rIdx === 0 ? 'disabled' : ''} title="Move rule up">▲</button>
                <button class="icon-btn dn-btn" data-gidx="${gIdx}" data-ridx="${rIdx}"
                  ${rIdx === rules.length - 1 ? 'disabled' : ''} title="Move rule down">▼</button>
                <button class="icon-btn del del-rule-btn" data-gidx="${gIdx}" data-ridx="${rIdx}" title="Delete rule">✕</button>
              </div>
            </div>`;
        }).join('');

        return `
          <tbody class="cover-group" data-mode="${mode}" data-gidx="${gIdx}">
            <tr>
              <td class="covers-cell">
                <div class="covers-inner">
                  <div class="covers-content">
                    ${this._coverPickerHtml(group.covers)}
                    ${hasGroupOv ? '<span class="override-icon" title="Manual override active">⚠</span>' : ''}
                  </div>
                  <div class="covers-bottom">
                    <input class="cover-add" list="covers-list" placeholder="add cover…" autocomplete="off" />
                    <div class="group-btns">
                    <button class="icon-btn up-group-btn" data-gidx="${gIdx}" ${isFirstInMode ? 'disabled' : ''} title="Move group up">▲</button>
                    <button class="icon-btn dn-group-btn" data-gidx="${gIdx}" ${isLastInMode  ? 'disabled' : ''} title="Move group down">▼</button>
                    <button class="icon-btn del del-group-btn" data-gidx="${gIdx}" title="Delete group">✕</button>
                  </div>
                  </div>
                </div>
              </td>
              <td class="rules-cell" colspan="4">
                ${cardsHtml}
              </td>
              <td class="add-col">
                <button class="add-action-btn" data-gidx="${gIdx}" title="Add rule">＋</button>
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

      const isCollapsed = this._collapsedModes.has(mode);
      const modeGroups = this._groups.filter(g => g.mode === mode);
      const groupCount = modeGroups.length;
      const ruleCount = modeGroups.reduce((s, g) => s + (g.rules?.length ?? 0), 0);
      const summaryText = groupCount === 0 ? 'No groups' :
        `${groupCount} ${groupCount === 1 ? 'group' : 'groups'}, ${ruleCount} ${ruleCount === 1 ? 'rule' : 'rules'}`;
      return `
        <div class="mode-section${isCollapsed ? ' collapsed' : ''}" id="mode-sec-${mode}" data-mode="${mode}">
          <div class="section-heading${isSpecial ? ' section-special' : ''}" data-mode="${mode}">
            <span>${MODE_LABELS[mode] || mode}${this._orphaned.has(mode) ? ' <span class="orphan-warn">⚠ not in input_select</span>' : ''}</span>
            <button class="collapse-btn" data-mode="${mode}" title="${isCollapsed ? 'Expand section' : 'Collapse section'}">${isCollapsed ? '▶' : '▼'}</button>
          </div>
          <div class="collapsed-summary" data-mode="${mode}">${summaryText} — click to expand</div>
          ${modeOptsHtml}
          <div class="table-card">
            <table>
              <thead>
                <tr>
                  <th style="width:340px">Covers</th>
                  <th>Condition</th>
                  <th style="width:88px;text-align:center;padding-left:10px;padding-right:28px">Pos</th>
                  <th style="width:88px;text-align:center;padding-left:10px;padding-right:66px">Tilt</th>
                  <th style="width:96px"></th>
                  <th style="width:64px"></th>
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
              <div class="menu-section">
                <div class="menu-section-label">Options</div>
                <button id="vars-btn" title="Bind short names to HA entities or templates for use in conditions">Custom Variables</button>
                <button id="integration-btn" title="Open the HA integrations page for this integration">Integration Settings</button>
              </div>
              <div class="menu-section">
                <div class="menu-section-label">Tools</div>
                <button id="export-btn" title="Copy all rules as JSON to the clipboard">Export Rules</button>
                <button id="import-btn" title="Replace all rules by pasting JSON — this overwrites everything">Import Rules</button>
                <button id="llm-btn" title="Copy a full system prompt + current rules to the clipboard, ready to paste into an AI assistant">Generate LLM Prompt</button>
              </div>
              <div class="menu-section">
                <button id="github-btn" class="menu-external">GitHub</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      ${this._error ? `<div class="error-banner" style="margin:0 0 16px">${this._error}</div>` : ''}

      ${sectionsHtml}

      <div class="footer">
        <span class="hint">
          ${conditionHintHtml()}
          First matching rule wins per cover. ⚠ = manual override active.<br>
          <strong>↑ Priority</strong> rules are evaluated before all mode rules and override everything. &nbsp;
          <strong>↓ Default</strong> rules are evaluated only when no rule in the current mode matched a cover.
        </span>
      </div>

      <dialog id="vars-dialog">
        <h3 class="dialog-title">Custom Variables</h3>
        <div style="margin-bottom:8px; font-size:13px; opacity:0.8;">
          One binding per line: <code>name=sensor.entity_id</code> or <code>name={{jinja2}}</code><br>
          Use the name as a condition token, e.g. <code>alarm&lt;800</code>. Lines starting with # are ignored.
        </div>
        <textarea id="vars-textarea" class="dialog-textarea" rows="8"
          placeholder="alarm=sensor.next_alarm_time&#10;temp=sensor.living_room_temperature&#10;motion={{states('binary_sensor.motion') == 'on' and 1 or 0}}"></textarea>
        <div id="vars-resolved" style="margin:8px 0; font-size:12px; font-family:monospace; opacity:0.8; white-space:pre;"></div>
        <div class="dialog-actions">
          <button class="secondary-btn" id="vars-cancel">Cancel</button>
          <button class="save-btn" id="vars-save">Save & Apply</button>
        </div>
      </dialog>

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
        const m = btn.dataset.mode;
        this._mode = m;
        for (const mode of this._modes) {
          if (mode !== '_priority' && mode !== '_fallback' && mode !== m) {
            this._collapsedModes.add(mode);
          } else {
            this._collapsedModes.delete(mode);
          }
        }
        this._render();
        this.shadowRoot.querySelector(`#mode-sec-${m}`)
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

    root.querySelectorAll('.collapse-btn').forEach(btn =>
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const m = btn.dataset.mode;
        if (this._collapsedModes.has(m)) {
          this._collapsedModes.delete(m);
        } else {
          this._collapsedModes.add(m);
        }
        this._render();
      })
    );
    root.querySelectorAll('.section-heading[data-mode]').forEach(el =>
      el.addEventListener('click', () => {
        const m = el.dataset.mode;
        if (this._collapsedModes.has(m)) {
          this._collapsedModes.delete(m);
        } else {
          this._collapsedModes.add(m);
        }
        this._render();
      })
    );
    root.querySelectorAll('.collapsed-summary').forEach(el =>
      el.addEventListener('click', () => {
        this._collapsedModes.delete(el.dataset.mode);
        this._render();
      })
    );
    root.querySelectorAll('.up-group-btn').forEach(btn =>
      btn.addEventListener('click', () => this._moveGroup(+btn.dataset.gidx, -1))
    );
    root.querySelectorAll('.dn-group-btn').forEach(btn =>
      btn.addEventListener('click', () => this._moveGroup(+btn.dataset.gidx, +1))
    );

    root.querySelector('#save-btn').addEventListener('click', () => this._save());

    root.querySelectorAll('.add-group-btn').forEach(btn =>
      btn.addEventListener('click', () => this._addGroup(btn.dataset.mode))
    );
    root.querySelectorAll('.del-group-btn').forEach(btn =>
      btn.addEventListener('click', () => this._deleteGroup(+btn.dataset.gidx))
    );
    root.querySelector('#undo-btn')?.addEventListener('click', () => this._undoDelete());
    
    root.querySelectorAll('.add-action-btn').forEach(btn =>
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
            covers.filter(c => c !== btn.dataset.cover).sort((a,b) => (a.slice(6)||a).localeCompare(b.slice(6)||b))
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
      const inp = picker.closest('.covers-inner')?.querySelector('.cover-add');
      const commit = () => {
        const val = inp.value.trim();
        if (!val) return;
        const covers = JSON.parse(picker.dataset.covers || '[]');
        if (!covers.includes(val)) {
          covers.push(val);
          covers.sort((a,b) => (a.slice(6)||a).localeCompare(b.slice(6)||b));
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
      inp.addEventListener('keydown', e => {
        if (e.key !== 'Enter') return;
        e.preventDefault();
        const typed = inp.value.trim();
        if (typed) {
          const datalist = document.getElementById('covers-list');
          const match = datalist && Array.from(datalist.options)
            .find(o => o.value.toLowerCase().startsWith(typed.toLowerCase()));
          if (match) inp.value = match.value;
        }
        commit();
      });
    });

    root.querySelectorAll('.f-cond').forEach(inp => {
      const badge = inp.nextElementSibling;
      const update = () => {
        const v = validateCondition(inp.value);
        if (!inp.value.trim() || v.ok) {
          badge.textContent = '';
          badge.className = 'cond-badge';
          badge.title = '';
        } else {
          badge.textContent = '✗';
          badge.className   = 'cond-badge error';
          badge.title       = `Unknown token(s): ${v.bad.join(', ')}`;
        }
        markDirty();
      };
      inp.addEventListener('input', update);
    });

    const ALLOWED_KEYS = new Set(['Backspace','Delete','Tab','ArrowLeft','ArrowRight','Home','End']);
    root.querySelectorAll('.f-pos, .f-tilt').forEach(inp => {
      inp.addEventListener('keydown', e => {
        if (!/^\d$/.test(e.key) && !ALLOWED_KEYS.has(e.key) && !e.ctrlKey && !e.metaKey)
          e.preventDefault();
      });
      inp.addEventListener('blur', () => {
        if (inp.value === '') return;
        const v = parseInt(inp.value, 10);
        inp.value = isNaN(v) ? '' : Math.min(100, Math.max(0, v));
        inp.dispatchEvent(new Event('input'));
      });
    });

    root.querySelectorAll('.f-pos').forEach(inp =>
      inp.addEventListener('input', () => {
        markDirty();
        const track = inp.nextElementSibling;
        if (!track?.classList.contains('pos-bar-track')) return;
        const v = parseInt(inp.value, 10);
        const valid = !isNaN(v) && v >= 0 && v <= 100;
        track.style.opacity = valid ? '' : '0.12';
        track.querySelector('.pos-bar-fill').style.height = valid ? (100 - v) + '%' : '0%';
      })
    );
    root.querySelectorAll('.f-tilt').forEach(inp =>
      inp.addEventListener('input', () => {
        markDirty();
        const wrap = inp.previousElementSibling;
        if (!wrap?.classList.contains('tilt-bar-wrap')) return;
        const v = parseInt(inp.value, 10);
        const valid = !isNaN(v) && v >= 0 && v <= 100;
        wrap.style.opacity = valid ? '' : '0.12';
        const deg = valid ? (100 - v) * 0.72 : 36;
        wrap.querySelectorAll('path').forEach(p => p.style.transform = `rotate(${deg}deg)`);
      })
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

    root.querySelector('#vars-btn')?.addEventListener('click', () => {
      const d = root.querySelector('#vars-dialog');
      root.querySelector('#vars-textarea').value = this._customVars;
      const entries = Object.entries(this._varValues);
      root.querySelector('#vars-resolved').textContent = entries.length
        ? 'Current values (last evaluation):\n' + entries.map(([k, v]) => `  ${k} = ${v ?? 'unavailable'}`).join('\n')
        : '(no values yet — wait for first evaluation cycle)';
      d.showModal();
    });

    root.querySelector('#vars-cancel')?.addEventListener('click', () => {
      root.querySelector('#vars-dialog').close();
    });

    root.querySelector('#vars-save')?.addEventListener('click', async () => {
      this._customVars = root.querySelector('#vars-textarea').value;
      root.querySelector('#vars-dialog').close();
      this._dirty = true;
      this._render();
    });

    root.querySelector('#export-btn')?.addEventListener('click', () => {
      this._collect();
      const json = JSON.stringify(this._groups, null, 2);
      copyToClipboard(json, 'Export Rules');
    });

    root.querySelector('#integration-btn')?.addEventListener('click', () => {
      window.history.pushState(null, '', '/config/integrations/integration/smart_shades');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });

    root.querySelector('#github-btn')?.addEventListener('click', () => {
      window.open('https://github.com/Isodome/smart-shade-scheduler', '_blank');
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

      const liveValuesSection = Object.entries(this._varValues)
        .map(([k, v]) => `  ${k}: ${v == null ? 'unavailable' : v}`)
        .join('\n') || '  (no values yet)';

      const prompt = `I am building a system to automate my shades in Home Assistant.
Unlike standard Home Assistant automations which are event-driven and based on momentary triggers, this system operates as a continuous state engine. Declarative rules dictate the absolute position and tilt that covers should have based on current environmental inputs (time, sun azimuth/elevation, month, presence, workday). The system evaluates rules periodically and on sun/mode changes, and moves covers to match the desired state.
The active set of rules is chosen based on a specific input_select entity (the "Mode").

### System State
Available Modes: ${this._modes.join(', ')}

Available Covers:
${coversPrompt}
### Current Live Values
${liveValuesSection}

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

${conditionLlmText()}
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
