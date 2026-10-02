import { CHAPTERS, findChapter, searchGuide, LUCK_ODDS } from './playerDocs';

test('guide links resolve to unique, complete chapters and headings', () => {
  const ids = CHAPTERS.flatMap(ch => [ch.id, ...ch.sections.map(s => s.id)]);
  expect(new Set(ids).size).toBe(ids.length);
  expect(CHAPTERS).toHaveLength(11);
  CHAPTERS.forEach(ch => ch.sections.forEach(s => {
    expect(s.text.length).toBeGreaterThan(50);
    (s.related || []).forEach(id => expect(findChapter(id).id).toBe(id));
  }));
  expect(findChapter('missing').id).toBe('getting-started');
});

test('search finds relevant instructions and the economy labels unavailable features honestly', () => {
  expect(searchGuide('  MEDKIT  ').some(r => r.section.id === 'healing-supplies')).toBe(true);
  expect(searchGuide('24 hours').some(r => r.chapter.id === 'soldiers')).toBe(true);
  expect(searchGuide('not-a-real-guide-term')).toEqual([]);
  expect(searchGuide('   ')).toEqual([]);
  expect(LUCK_ODDS.reduce((sum, row) => sum + parseFloat(row[4]), 0)).toBe(100);
  const market = findChapter('market');
  expect(market.sections.find(s => s.id === 'luck-box-odds').text).toContain('five independent');
  expect(market.sections.find(s => s.id === 'economy-status').table.rows).toContainEqual(['Gold → LastZ exchange / token claims', 'Not configured']);
});
