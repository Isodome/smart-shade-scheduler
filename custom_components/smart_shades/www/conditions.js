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
let _BOOL_VARS     = new Set();

// Called from the panel after ws_get_config returns built_in_vars + custom_var_specs.
// Also called immediately below with the seed so parsing works before first load.
export function initConditionSpec(builtInVars, customVarSpecs = []) {
  const allVars = [...builtInVars, ...customVarSpecs];
  CONDITION_SPEC = allVars.map(v => ({ ...v, ...(_DISPLAY[v.short] ?? {}) }));
  _LONG_TO_SHORT = Object.fromEntries(CONDITION_SPEC.map(s => [s.long, s.short]));
  _TIME_VARS     = new Set(CONDITION_SPEC.filter(s => s.type === 'time').map(s => s.short));
  _BOOL_VARS     = new Set(CONDITION_SPEC.filter(s => s.type === 'bool').map(s => s.short));
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

  const boolItems = [..._BOOL_VARS].map(s => `<code>${s}</code> <code>!${s}</code>`).join(' &nbsp; ');
  const boolHint  = boolItems ? `Bool vars (no operator): ${boolItems}<br>` : '';

  return `Conditions (space-separated, empty = catch-all):<br>
          ${rangeItems}<br>
          ${boolHint}Crossing (fires once): <code>=</code> either &nbsp; <code>=^</code> rising &nbsp; <code>=v</code> falling<br>`;
}

export function conditionLlmText() {
  const varList = CONDITION_SPEC
    .filter(s => s.llm)
    .map(s => s.llm)
    .join(', ');

  const boolVarList = [..._BOOL_VARS].map(s => `"${s}" (bool — use bare "${s}" or "!${s}")`).join(', ');
  const boolSection = boolVarList
    ? `\nBool custom vars: ${boolVarList}. Write the var name alone (no operator/value) — it fires when truthy. Prefix with ! for falsy.\n`
    : '';

  return `Condition variables: ${varList}.${boolSection}
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

// Standard condition token: var op val (op required, val required).
// Operators: longest alternatives first so =^, =v, == aren't shadowed by =.
// \s* around the operator so "az > 150" parses the same as "az>150".
const _TOKEN_RE = /([a-z][a-z0-9_]*)\s*(>=|<=|==|=\^|=v|>|<|=)\s*(-?\d+(?::\d+)?(?:\.\d+)?)/gi;

// Bool token: optional ! prefix + identifier. Only valid for vars in _BOOL_VARS.
const _BOOL_TOKEN_RE = /(!?)([a-z][a-z0-9_]*)/gi;

function _normalizeVar(raw) {
  const lower = raw.toLowerCase();
  return _LONG_TO_SHORT[lower] ?? lower;
}

export function parseCondition(str) {
  const conditions = [];
  // Pass 1: standard op+val tokens
  for (const [, rawVar, rawOp, val] of str.matchAll(_TOKEN_RE)) {
    conditions.push({
      var: _normalizeVar(rawVar),
      op:  rawOp,
      val: parseFloat(val.replace(':', ''))
    });
  }
  // Pass 2: bare bool tokens from remainder
  const remainder = str.replace(_TOKEN_RE, ' ');
  _BOOL_TOKEN_RE.lastIndex = 0;
  for (const [, neg, rawVar] of remainder.matchAll(_BOOL_TOKEN_RE)) {
    const short = _normalizeVar(rawVar);
    if (_BOOL_VARS.has(short)) {
      conditions.push({ var: short, op: neg ? '!bool' : 'bool' });
    }
  }
  return conditions;
}

/** Returns {ok: bool, bad: string[]} */
export function validateCondition(str) {
  if (!str.trim()) return { ok: true, bad: [] };
  // Remove standard tokens
  let remaining = str.replace(_TOKEN_RE, ' ');
  // Remove valid bool tokens
  _BOOL_TOKEN_RE.lastIndex = 0;
  remaining = remaining.replace(_BOOL_TOKEN_RE, (match, neg, rawVar) => {
    return _BOOL_VARS.has(_normalizeVar(rawVar)) ? ' ' : match;
  });
  const leftover = remaining.replace(/\s+/g, '');
  return leftover ? { ok: false, bad: [leftover] } : { ok: true, bad: [] };
}

export function formatCondition(conditions) {
  if (!conditions || !Array.isArray(conditions)) return '';
  return conditions.map(cond => {
    const short = _normalizeVar(cond.var);
    if (cond.op === 'bool')  return short;
    if (cond.op === '!bool') return `!${short}`;
    let v = cond.val;
    if (_TIME_VARS.has(short)) {
      const strV = String(v).padStart(3, '0');
      v = strV.slice(0, -2) + ':' + strV.slice(-2);
    }
    return `${short}${cond.op}${v}`;
  }).join(' ');
}
