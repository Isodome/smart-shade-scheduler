import { parseCondition, validateCondition, formatCondition } from './conditions.js';

test('parses all operators', () => {
  expect(parseCondition('az>150')).toEqual([{ var: 'azimuth', op: '>', val: 150 }]);
  expect(parseCondition('el>=5')).toEqual([{ var: 'elevation', op: '>=', val: 5 }]);
  expect(parseCondition('t==8:00')).toEqual([{ var: 'time', op: '==', val: 800 }]);
  expect(parseCondition('mo<=8')).toEqual([{ var: 'month', op: '<=', val: 8 }]);
  expect(parseCondition('home')).toEqual([{ var: 'presence', op: '==', val: 'home' }]);
});

test('parses multiple conditions', () => {
  expect(parseCondition('t>6:00 t<10:00')).toEqual([
    { var: 'time', op: '>', val: 600 },
    { var: 'time', op: '<', val: 1000 }
  ]);
});

test('handles arbitrary spacing', () => {
  expect(parseCondition('  az>150   el>=5   ')).toEqual([
    { var: 'azimuth', op: '>', val: 150 },
    { var: 'elevation', op: '>=', val: 5 }
  ]);
});

test('handles spaces around operators', () => {
  expect(parseCondition('az > 150 el <= 5 t == 8:00')).toEqual([
    { var: 'azimuth', op: '>', val: 150 },
    { var: 'elevation', op: '<=', val: 5 },
    { var: 'time', op: '==', val: 800 }
  ]);
});

test('round-trips cleanly', () => {
  const str = 'az>185 el>=5 t>6:00 t<10:00';
  expect(formatCondition(parseCondition(str))).toBe(str);
});

test('validates bad tokens', () => {
  expect(validateCondition('az>150 foo').ok).toBe(false);
  expect(validateCondition('az>150').ok).toBe(true);
  expect(validateCondition('').ok).toBe(true);
});
