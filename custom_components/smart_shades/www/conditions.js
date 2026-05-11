// ── JS-only display data, keyed by short name ─────────────────────────────────
// Everything else (short, long, type) comes from the server via initConditionSpec.
const _DISPLAY = {
  az: { hintExamples: ['az&gt;150', 'az&gt;=150', 'az==180'], llm: '"az" / "azimuth" (degrees 0–360)' },
  el: { hintExamples: ['el&gt;5', 'el&lt;30'],                llm: '"el" / "elevation" (degrees, negative when below horizon)' },
  t:  { hintExamples: ['t&gt;=8:30', 't&lt;22:00'],          llm: '"t" / "time" (HHMM integer — 08:30 → 830, 19:00 → 1900)' },
  mo: { hintExamples: ['mo&gt;=6', 'mo&lt;=8'],               llm: '"mo" / "month" (1–12)' },
  d:  { hintExamples: ['d&lt;=4', 'd==0'],                   llm: '"d" / "day" (weekday: 0=Mon … 6=Sun)' },
};

// ── Mutable spec — seeded with built-in defaults, refined by initConditionSpec ─
export let CONDITION_SPEC = [];
let _LONG_TO_SHORT = {};
let _TIME_VARS     = new Set();

// Called from the panel after ws_get_config returns built_in_vars.
// Also called immediately below with the seed so parsing works before first load.
export function initConditionSpec(builtInVars) {
  CONDITION_SPEC = builtInVars.map(v => ({ ...v, ...(_DISPLAY[v.short] ?? {}) }));
  _LONG_TO_SHORT = Object.fromEntries(CONDITION_SPEC.map(s => [s.long, s.short]));
  _TIME_VARS     = new Set(CONDITION_SPEC.filter(s => s.type === 'time').map(s => s.short));
}

// Seed: lets parsing/validation work before the server responds.
initConditionSpec([
  { short: 'az', long: 'azimuth',   type: 'number' },
  { short: 'el', long: 'elevation', type: 'number' },
  { short: 't',  long: 'time',      type: 'time'   },
  { short: 'mo', long: 'month',     type: 'number' },
]);

// ── Rendered outputs (imported by the panel) ──────────────────────────────────

export function conditionHintHtml() {
  const rangeItems = CONDITION_SPEC
    .filter(s => s.hintExamples)
    .map(s => s.hintExamples.map(e => `<code>${e}</code>`).join(' ') + ' ' + s.long)
    .join(' &nbsp;\n          ');

  return `Conditions (space-separated, empty = catch-all):<br>
          ${rangeItems}<br>
          Crossing (fires once): <code>=</code> either &nbsp; <code>=^</code> rising &nbsp; <code>=v</code> falling<br>`;
}

export function conditionLlmText() {
  const varList = CONDITION_SPEC
    .filter(s => s.llm)
    .map(s => s.llm)
    .join(', ');

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

// ── Parsing / validation / formatting ────────────────────────────────────────

// The var-name part is a generic identifier — all name knowledge lives in
// _LONG_TO_SHORT (derived from the server spec via initConditionSpec).
// Operators: longest alternatives first so =^, =v, == aren't shadowed by =.
// \s* around the operator so "az > 150" parses the same as "az>150".
const _TOKEN_RE = /([a-z][a-z0-9_]*)\s*(>=|<=|==|=\^|=v|>|<|=)\s*(-?\d+(?::\d+)?(?:\.\d+)?)/gi;

function _normalizeVar(raw) {
  const lower = raw.toLowerCase();
  return _LONG_TO_SHORT[lower] ?? lower;
}

export function parseCondition(str) {
  const conditions = [];
  for (const [, rawVar, rawOp, val] of str.matchAll(_TOKEN_RE)) {
    conditions.push({
      var: _normalizeVar(rawVar),
      op:  rawOp,
      val: parseFloat(val.replace(':', ''))
    });
  }
  return conditions;
}

/** Returns {ok: bool, bad: string[]} */
export function validateCondition(str) {
  if (!str.trim()) return { ok: true, bad: [] };
  const remaining = str
    .replace(_TOKEN_RE, '')
    .replace(/\s+/g, '');
  return remaining ? { ok: false, bad: [remaining] } : { ok: true, bad: [] };
}

export function formatCondition(conditions) {
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
