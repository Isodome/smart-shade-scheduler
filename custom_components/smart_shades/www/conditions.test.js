import { parseCondition, validateCondition, formatCondition } from './conditions.js';

test('parses all range operators', () => {
  expect(parseCondition('az>150')).toEqual([{ var: 'az', op: '>', val: 150 }]);
  expect(parseCondition('el>=5')).toEqual([{ var: 'el', op: '>=', val: 5 }]);
  expect(parseCondition('t==8:00')).toEqual([{ var: 't', op: '==', val: 800 }]);
  expect(parseCondition('mo<=8')).toEqual([{ var: 'mo', op: '<=', val: 8 }]);
});

test('parses crossing operators', () => {
  expect(parseCondition('az=^185')).toEqual([{ var: 'az', op: '=^', val: 185 }]);
  expect(parseCondition('el=v10')).toEqual([{ var: 'el', op: '=v', val: 10 }]);
  expect(parseCondition('t=7:30')).toEqual([{ var: 't', op: '=', val: 730 }]);
  expect(parseCondition('az=185')).toEqual([{ var: 'az', op: '=', val: 185 }]);
});

test('crossing and range operators do not interfere', () => {
  // >= must not be parsed as = followed by >
  expect(parseCondition('az>=150')).toEqual([{ var: 'az', op: '>=', val: 150 }]);
  expect(parseCondition('el<=5')).toEqual([{ var: 'el', op: '<=', val: 5 }]);
});

test('parses multiple conditions', () => {
  expect(parseCondition('t>6:00 t<10:00')).toEqual([
    { var: 't', op: '>', val: 600 },
    { var: 't', op: '<', val: 1000 }
  ]);
});

test('handles arbitrary spacing', () => {
  expect(parseCondition('  az>150   el>=5   ')).toEqual([
    { var: 'az', op: '>', val: 150 },
    { var: 'el', op: '>=', val: 5 }
  ]);
});

test('handles spaces around operators', () => {
  expect(parseCondition('az > 150 el <= 5 t == 8:00')).toEqual([
    { var: 'az', op: '>', val: 150 },
    { var: 'el', op: '<=', val: 5 },
    { var: 't', op: '==', val: 800 }
  ]);
});

test('round-trips range conditions cleanly', () => {
  const str = 'az>185 el>=5 t>6:00 t<10:00';
  expect(formatCondition(parseCondition(str))).toBe(str);
});

test('crossing conditions round-trip', () => {
  expect(formatCondition(parseCondition('az=^185'))).toBe('az=^185');
  expect(formatCondition(parseCondition('el=v10'))).toBe('el=v10');
  expect(formatCondition(parseCondition('t=7:30'))).toBe('t=7:30');
});

test('validates bad tokens', () => {
  expect(validateCondition('').ok).toBe(true);
  // known vars
  expect(validateCondition('az>150').ok).toBe(true);
  expect(validateCondition('el>=5 t<22:00').ok).toBe(true);
  // custom vars with numeric value are valid
  expect(validateCondition('temp>26').ok).toBe(true);
  expect(validateCondition('alarm<800').ok).toBe(true);
  expect(validateCondition('az>150 temp>26').ok).toBe(true);
  // bare word with no op+value is invalid
  expect(validateCondition('az>150 foo').ok).toBe(false);
  expect(validateCondition('foo').ok).toBe(false);
  // non-numeric value is invalid
  expect(validateCondition('az>foo').ok).toBe(false);
  // token starting with digit or special char is invalid
  expect(validateCondition('123>5').ok).toBe(false);
  expect(validateCondition('$x>5').ok).toBe(false);
});

test('validates crossing tokens', () => {
  expect(validateCondition('az=^185').ok).toBe(true);
  expect(validateCondition('el=v10').ok).toBe(true);
  expect(validateCondition('t=7:30').ok).toBe(true);
});

test('long names are accepted and normalised to short on parse', () => {
  expect(parseCondition('azimuth>150')).toEqual([{ var: 'az', op: '>', val: 150 }]);
  expect(parseCondition('elevation>=5')).toEqual([{ var: 'el', op: '>=', val: 5 }]);
  expect(parseCondition('time==800')).toEqual([{ var: 't', op: '==', val: 800 }]);
  expect(parseCondition('month<=9')).toEqual([{ var: 'mo', op: '<=', val: 9 }]);
});

test('formatCondition accepts long var names and outputs short form', () => {
  expect(formatCondition([{ var: 'azimuth', op: '>', val: 150 }])).toBe('az>150');
  expect(formatCondition([{ var: 'elevation', op: '<', val: 30 }])).toBe('el<30');
  expect(formatCondition([{ var: 'time', op: '>=', val: 830 }])).toBe('t>=8:30');
});

// ── Bool var tests ────────────────────────────────────────────────────────────

import { initConditionSpec } from './conditions.js';

const _ALL_BUILT_INS = [
  { short: 'az', long: 'azimuth',   type: 'number' },
  { short: 'el', long: 'elevation', type: 'number' },
  { short: 't',  long: 'time',      type: 'time'   },
  { short: 'mo', long: 'month',     type: 'number' },
  { short: 'd',  long: 'day',       type: 'number' },
];

describe('bool vars', () => {
  beforeEach(() => {
    initConditionSpec(_ALL_BUILT_INS, [{ short: 'motion', long: 'motion', type: 'bool' }]);
  });
  afterEach(() => {
    initConditionSpec(_ALL_BUILT_INS);  // restore default spec
  });

  test('parseCondition: bare bool var → bool op', () => {
    expect(parseCondition('motion')).toEqual([{ var: 'motion', op: 'bool' }]);
  });

  test('parseCondition: negated bool var → !bool op', () => {
    expect(parseCondition('!motion')).toEqual([{ var: 'motion', op: '!bool' }]);
  });

  test('parseCondition: bool var mixed with standard condition', () => {
    expect(parseCondition('az>150 motion')).toEqual([
      { var: 'az', op: '>', val: 150 },
      { var: 'motion', op: 'bool' },
    ]);
  });

  test('validateCondition: bare bool var is valid', () => {
    expect(validateCondition('motion').ok).toBe(true);
    expect(validateCondition('!motion').ok).toBe(true);
    expect(validateCondition('az>150 motion').ok).toBe(true);
  });

  test('validateCondition: bare unknown var is still invalid', () => {
    expect(validateCondition('foo').ok).toBe(false);
    expect(validateCondition('!foo').ok).toBe(false);
  });

  test('formatCondition: bool op → bare name', () => {
    expect(formatCondition([{ var: 'motion', op: 'bool' }])).toBe('motion');
    expect(formatCondition([{ var: 'motion', op: '!bool' }])).toBe('!motion');
  });

  test('formatCondition: bool round-trip', () => {
    const parsed = parseCondition('az>150 !motion');
    expect(formatCondition(parsed)).toBe('az>150 !motion');
  });
});
