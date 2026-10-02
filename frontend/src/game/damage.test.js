import { formatDamage } from './damage';

describe('formatDamage', () => {
  it('shows a non-negative integer without changing server-side combat values', () => {
    expect(formatDamage(9.99999)).toBe('9');
    expect(formatDamage(10)).toBe('10');
    expect(formatDamage(-3.7)).toBe('0');
    expect(formatDamage(Number.NaN)).toBe('0');
  });
});
