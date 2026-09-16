export function compareAppsByCategory(
  a: { categories?: string[] },
  b: { categories?: string[] },
  direction: 'asc' | 'desc'
): number {
  const catA = (a.categories || []).join(', ');
  const catB = (b.categories || []).join(', ');
  return direction === 'asc' ? catA.localeCompare(catB, 'ja') : catB.localeCompare(catA, 'ja');
}
