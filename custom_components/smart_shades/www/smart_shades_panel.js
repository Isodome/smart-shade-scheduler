/**
 * Smart Shade Scheduler — sidebar panel
 *
 * Condition tokens (space-separated, case-insensitive):
 *   az>150  az>=150  az<200  az<=200  az==180   azimuth
 *   el>5    el>=5    el<30   el<=30   el==10    elevation
 *   h>8     h>=8     h<22    h<=22    h==8      hour (0-23)
 *   m>30    m>=30    m<45    m<=45    m==0      minute
 *   mo>=6   mo<=8    mo==12                     month (1-12)
 *   home    away                                presence (requires presence entity)
 *   (empty) catch-all — always matches
 */

// To add a new variable: one entry in _VARS (token regex → field prefix).
// To add a new operator: one entry in _OPS (symbol → field suffix).
// mo must appear before m in the regex alternation to avoid mis-parsing.
// Spaces are stripped before parsing so "az > 150" and "az>150" are identical.
const _TOKEN_RE = /(az(?:imuth)?|el(?:evation)?|mo(?:n(?:th)?)?|h(?:our)?|m(?:in(?:ute)?)?)(>=|<=|==|>|<)(-?\d+(?:\.\d+)?)/gi;

const _VARS = [
  [/^az/i,  'azimuth'],
  [/^el/i,  'elevation'],
  [/^mo/i,  'month'],
  [/^h/i,   'hour'],
  [/^m/i,   'minute'],
];
const _OPS = { '>': 'above', '<': 'below', '>=': 'min', '<=': 'max', '==': 'eq' };
const _FMT = { above: '>', below: '<', min: '>=', max: '<=', eq: '==' };

function _varName(raw) {
  for (const [re, name] of _VARS) if (re.test(raw)) return name;
}

function parseCondition(str) {
  const clean = str.replace(/\s+/g, '');
  const result = {};
  for (const [, rawVar, rawOp, val] of clean.matchAll(_TOKEN_RE))
    result[`${_varName(rawVar)}_${_OPS[rawOp]}`] = parseFloat(val);
  // bare presence tokens — check original space-separated tokens
  const tokens = str.trim().split(/\s+/);
  if (tokens.some(t => /^home$/i.test(t))) result.require_home = true;
  if (tokens.some(t => /^away$/i.test(t))) result.require_away = true;
  return result;
}

/** Returns {ok: bool, bad: string[]} */
function validateCondition(str) {
  if (!str.trim()) return { ok: true, bad: [] };
  const remaining = str.replace(/\s+/g, '').replace(_TOKEN_RE, '').replace(/home|away/gi, '');
  return remaining ? { ok: false, bad: [remaining] } : { ok: true, bad: [] };
}

const _TOKEN = { azimuth: 'az', elevation: 'el', month: 'mo', hour: 'h', minute: 'm' };

function formatCondition(rule) {
  const parts = [];
  if (rule.require_home) parts.push('home');
  if (rule.require_away) parts.push('away');
  for (const [, varName] of _VARS)
    for (const [suffix, opStr] of Object.entries(_FMT)) {
      const v = rule[`${varName}_${suffix}`];
      if (v != null) parts.push(`${_TOKEN[varName]}${opStr}${v}`);
    }
  return parts.join(' ');
}

// Auto-generated from _VARS × _OPS plus bare presence tokens.
const CONDITION_KEYS = [
  'require_home', 'require_away',
  ..._VARS.flatMap(([, name]) => Object.values(_OPS).map(suffix => `${name}_${suffix}`)),
];

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
  .override-icon { color: #ff9800; cursor: default; font-size: 14px; }

  /* ── Cover chip picker ─────────────────────────────── */
  .cover-picker { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
  .chips { display: contents; }
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
    this._orphaned    = new Set();
    this._special     = new Set();
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
      this._cfg      = cfg;
      this._rules    = JSON.parse(JSON.stringify(cfg.rules || []));
      this._modes    = cfg.mode_options || [];
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

  /** Read DOM row inputs back into this._rules[]. */
  _collect() {
    const root = this.shadowRoot;
    for (const row of root.querySelectorAll('tr[data-idx]')) {
      const idx  = parseInt(row.dataset.idx, 10);
      const rule = this._rules[idx];
      if (!rule) continue;

      // covers come from the picker's data attribute (chips)
      const picker = row.querySelector('.cover-picker');
      rule.covers = picker
        ? JSON.parse(picker.dataset.covers || '[]')
        : [];

      const cond = parseCondition(row.querySelector('.f-cond').value);
      for (const k of CONDITION_KEYS) delete rule[k];
      Object.assign(rule, cond);

      const pos = row.querySelector('.f-pos').value;
      if (pos !== '') rule.position = parseInt(pos, 10); else delete rule.position;

      const tilt = row.querySelector('.f-tilt').value;
      if (tilt !== '') rule.tilt = parseInt(tilt, 10); else delete rule.tilt;
    }
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

  _addRule(mode = this._mode) {
    this._collect();
    const n = this._rules.filter(r => r.mode === mode).length + 1;
    this._rules.push({ name: `${mode} ${n}`, mode, covers: [] });
    this._dirty = true;
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
      const rules = this._rules.filter(r =>
        (r.covers && r.covers.length > 0) ||
        r.position != null ||
        r.tilt != null ||
        CONDITION_KEYS.some(k => r[k] != null)
      );
      await this._ws('smart_shades/save_rules', {
        entry_id: this._cfg.entry_id,
        rules,
      });
      this._dirty  = false;
      this._error  = null;
      this._saving = false;
      // Reload so orphaned tabs clean up and input_select changes are reflected
      this._cfg = null;
      await this._load();
      return;
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

    // ── Mode tabs ─────────────────────────────────────────────────
    const MODE_LABELS = {
      '_priority': '↑ Priority',
      '_fallback': '↓ Default',
    };
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
        : orphaned ? 'Not in input_select — removed when all rules deleted'
        : m;
      return `<button class="${cls}" data-mode="${m}" title="${title}">
        ${MODE_LABELS[m] || m}
        ${orphaned ? '<span class="orphan-warn">⚠</span>' : ''}
        ${m === curMode ? '<span class="live-dot"></span>' : ''}
      </button>`;
    }).join('');


    // ── One section per mode ───────────────────────────────────────
    const sectionsHtml = this._modes.map(mode => {
      const peers = this._rules
        .map((r, i) => ({ r, i }))
        .filter(({ r }) => r.mode === mode);

      const rowsHtml = peers.map(({ r, i }, pos) => {
        const hasOv = (r.covers || []).some(c => overrides.has(c));
        const hasContent = (r.covers && r.covers.length > 0) ||
          r.position != null || r.tilt != null ||
          CONDITION_KEYS.some(k => r[k] != null);
        const isInvalid = hasContent && r.position == null && r.tilt == null;
        const rowClass = hasOv ? 'has-override' : isInvalid ? 'row-invalid' : '';
        return `
          <tr data-idx="${i}"${rowClass ? ` class="${rowClass}"` : ''}>
            <td style="width:46px">
              <div class="row-btns" style="flex-direction:column;gap:0">
                <button class="icon-btn up-btn" data-idx="${i}"
                  ${pos === 0 ? 'disabled' : ''} title="Move up">▲</button>
                <button class="icon-btn dn-btn" data-idx="${i}"
                  ${pos === peers.length - 1 ? 'disabled' : ''} title="Move down">▼</button>
              </div>
            </td>
            <td>${this._coverPickerHtml(r.covers)}</td>
            <td>
              <div class="cond-wrap">
                <input class="f-cond" value="${formatCondition(r)}" placeholder="az>150 el<30" />
                <span class="cond-badge ${validateCondition(formatCondition(r)).ok ? 'ok' : 'error'}">${formatCondition(r) ? (validateCondition(formatCondition(r)).ok ? '✓' : '✗') : ''}</span>
              </div>
            </td>
            <td><input class="f-pos narrow" type="number" min="0" max="100"
              value="${r.position ?? ''}" placeholder="—" /></td>
            <td><input class="f-tilt narrow" type="number" min="0" max="100"
              value="${r.tilt ?? ''}" placeholder="—" /></td>
            <td style="width:64px">
              <div class="row-btns">
                ${hasOv ? '<span class="override-icon" title="Manual override active">⚠</span>' : ''}
                <button class="icon-btn del del-btn" data-idx="${i}" title="Delete">✕</button>
              </div>
            </td>
          </tr>`;
      }).join('');

      return `
        <div class="mode-section" id="mode-sec-${mode}" data-mode="${mode}">
          <div class="section-heading${this._special.has(mode) ? ' section-special' : ''}">
            ${MODE_LABELS[mode] || mode}
            ${this._orphaned.has(mode) ? ' <span class="orphan-warn">⚠ not in input_select</span>' : ''}
          </div>
          <div class="card">
            <table>
              <thead><tr>
                <th></th>
                <th style="width:38%">Covers</th>
                <th style="width:22%">Condition</th>
                <th style="width:8%">Pos%</th>
                <th style="width:8%">Tilt%</th>
                <th></th>
              </tr></thead>
              <tbody id="tbody-${mode}">${rowsHtml}</tbody>
              <tbody><tr class="add-row"><td colspan="6">
                <button class="add-btn" data-mode="${mode}">＋  Add rule for ${mode}</button>
              </td></tr></tbody>
            </table>
          </div>
        </div>`;
    }).join('');

    // ── Cover datalist (autocomplete) ──────────────────────────────
    const coverOptions = Object.keys(this._hass.states)
      .filter(e => e.startsWith('cover.'))
      .sort()
      .map(e => `<option value="${e}">`)
      .join('');

    // ── Helpers link ───────────────────────────────────────────────
    const modeEntity = this._cfg.mode_entity;
    const helpersLink = modeEntity
      ? `<a class="helpers-link" id="helpers-link" href="#"
           title="Manage ${modeEntity} options">⚙ Mode options</a>`
      : '';

    // ── Full HTML ──────────────────────────────────────────────────
    root.innerHTML = `
      <style>${CSS}</style>
      <datalist id="covers-list">${coverOptions}</datalist>

      <div style="display:flex;align-items:baseline;gap:12px;padding:16px 20px 0">
        <h1 style="margin:0">Shade Scheduler</h1>
        ${helpersLink}
      </div>

      <div class="tab-bar-wrap">
        <div class="mode-tabs">${tabsHtml}</div>
      </div>

      ${this._error ? `<div class="error-banner" style="margin:0 0 16px">${this._error}</div>` : ''}

      ${sectionsHtml}

      <div class="footer">
        <span class="hint">
          Conditions (space-separated, empty = catch-all):<br>
          <code>az&gt;150</code> <code>az&gt;=150</code> <code>az==180</code> azimuth &nbsp;
          <code>el&gt;5</code> <code>el&lt;30</code> elevation &nbsp;
          <code>h&gt;=8</code> <code>h&lt;22</code> <code>h==8</code> hour &nbsp;
          <code>m&gt;30</code> minute &nbsp;
          <code>mo&gt;=6</code> <code>mo&lt;=8</code> month (1–12) &nbsp;
          <code>home</code> <code>away</code> presence<br>
          First matching rule wins per cover. ⚠ = manual override active.<br>
          <strong>↑ Priority</strong> rules are evaluated before all mode rules and override everything. &nbsp;
          <strong>↓ Default</strong> rules are evaluated only when no rule in the current mode matched a cover.
        </span>
        <button class="save-btn" id="save-btn" ${this._saving ? 'disabled' : ''}>
          ${this._saving ? 'Saving…' : 'Save'}
          ${this._dirty && !this._saving ? '<span class="unsaved-dot"></span>' : ''}
        </button>
      </div>`;

    // ── Event wiring ───────────────────────────────────────────────

    // Tab click → scroll to section
    root.querySelectorAll('.mode-tab[data-mode]').forEach(btn =>
      btn.addEventListener('click', () => {
        this._mode = btn.dataset.mode;
        this._addingMode = false;
        root.querySelectorAll('.mode-tab').forEach(t =>
          t.classList.toggle('active', t.dataset.mode === this._mode)
        );
        root.querySelector(`#mode-sec-${this._mode}`)
          ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      })
    );

    // IntersectionObserver keeps active tab in sync while scrolling
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

    root.querySelectorAll('.add-btn[data-mode]').forEach(btn =>
      btn.addEventListener('click', () => this._addRule(btn.dataset.mode))
    );
    root.querySelectorAll('.del-btn').forEach(btn =>
      btn.addEventListener('click', () => this._deleteRule(+btn.dataset.idx))
    );
    root.querySelectorAll('.up-btn').forEach(btn =>
      btn.addEventListener('click', () => this._moveRule(+btn.dataset.idx, -1))
    );
    root.querySelectorAll('.dn-btn').forEach(btn =>
      btn.addEventListener('click', () => this._moveRule(+btn.dataset.idx, +1))
    );

    // ── Cover chip pickers ─────────────────────────────────────────
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

    // Live condition validation
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

    // Mark dirty on pos/tilt edits
    root.querySelectorAll('.f-pos, .f-tilt').forEach(inp =>
      inp.addEventListener('input', markDirty)
    );

    // ── Helpers link ───────────────────────────────────────────────
    root.querySelector('#helpers-link')?.addEventListener('click', e => {
      e.preventDefault();
      const entity = this._cfg?.mode_entity;
      if (entity) {
        history.pushState(null, '', `/?more-info-entity-id=${entity}`);
        window.dispatchEvent(new CustomEvent('location-changed'));
      }
    });
  }
}

customElements.define('smart-shades-panel', SmartShadesPanel);
