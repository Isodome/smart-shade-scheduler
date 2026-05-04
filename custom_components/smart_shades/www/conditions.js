const _TOKEN_RE = /(az(?:imuth)?|el(?:evation)?|mo(?:n(?:th)?)?|t(?:ime)?)(>=|<=|==|>|<)(-?\d+(?::\d+)?(?:\.\d+)?)/gi;

const _VARS = [
  [/^az/i,  'azimuth'],
  [/^el/i,  'elevation'],
  [/^mo/i,  'month'],
  [/^t/i,   'time'],
];

function _varName(raw) {
  for (const [re, name] of _VARS) if (re.test(raw)) return name;
}

export function parseCondition(str) {
  const clean = str.replace(/\s+/g, '');
  const conditions = [];
  for (const [, rawVar, rawOp, val] of clean.matchAll(_TOKEN_RE)) {
    conditions.push({
      var: _varName(rawVar),
      op: rawOp,
      val: parseFloat(val.replace(':', ''))
    });
  }
  const tokens = str.trim().split(/\s+/);
  if (tokens.some(t => /^home$/i.test(t))) conditions.push({var: 'presence', op: '==', val: 'home'});
  if (tokens.some(t => /^away$/i.test(t))) conditions.push({var: 'presence', op: '==', val: 'away'});
  return conditions;
}

/** Returns {ok: bool, bad: string[]} */
export function validateCondition(str) {
  if (!str.trim()) return { ok: true, bad: [] };
  const remaining = str.replace(/\s+/g, '').replace(_TOKEN_RE, '').replace(/home|away/gi, '');
  return remaining ? { ok: false, bad: [remaining] } : { ok: true, bad: [] };
}

const _TOKEN = { azimuth: 'az', elevation: 'el', month: 'mo', time: 't' };

export function formatCondition(conditions) {
  if (!conditions || !Array.isArray(conditions)) return '';
  const parts = [];
  
  // Handle presence
  const hasHome = conditions.some(c => c.var === 'presence' && c.val === 'home');
  const hasAway = conditions.some(c => c.var === 'presence' && c.val === 'away');
  if (hasHome) parts.push('home');
  if (hasAway) parts.push('away');

  for (const cond of conditions) {
    if (cond.var === 'presence') continue;
    let v = cond.val;
    if (cond.var === 'time') {
      const strV = String(v).padStart(3, '0');
      v = strV.slice(0, -2) + ':' + strV.slice(-2);
    }
    const token = _TOKEN[cond.var] || cond.var;
    parts.push(`${token}${cond.op}${v}`);
  }
  return parts.join(' ');
}
