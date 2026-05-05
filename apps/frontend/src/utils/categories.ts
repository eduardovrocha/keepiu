const CATEGORY_NORMALIZATION: Record<string, string> = {
  'tecnologia':              'Tecnologia',
  'negocios':                'Negócios',
  'negócios':                'Negócios',
  'saude':                   'Saúde',
  'saúde':                   'Saúde',
  'saude mental':            'Saúde',
  'saúde mental':            'Saúde',
  'marketing':               'Marketing',
  'educacao':                'Educação',
  'educação':                'Educação',
  'financas':                'Finanças',
  'finanças':                'Finanças',
  'produtividade':           'Produtividade',
  'entretenimento':          'Entretenimento',
  'ciencia':                 'Ciência',
  'ciência':                 'Ciência',
  'politica':                'Política',
  'política':                'Política',
  'esportes':                'Esportes',
  'cultura':                 'Cultura',
  'desenvolvimento pessoal': 'Desenvolvimento',
  'desenvolvimento':         'Desenvolvimento',
}

function capitalize(word: string): string {
  return word.charAt(0).toUpperCase() + word.slice(1)
}

export function normalizeCategory(category: string): string {
  const key = category.trim().toLowerCase()
  if (CATEGORY_NORMALIZATION[key]) return CATEGORY_NORMALIZATION[key]
  // fallback: first word only, capitalized — enforces single-word rule
  return capitalize(key.split(' ')[0])
}

export interface NormalizedCategory {
  label: string
  value: string
  count: number
}

export function normalizeCategories(
  categories: { category: string; count: number }[]
): NormalizedCategory[] {
  const grouped = new Map<string, { value: string; count: number }>()
  for (const cat of categories) {
    const label = normalizeCategory(cat.category)
    const existing = grouped.get(label)
    if (!existing) {
      grouped.set(label, { value: cat.category, count: cat.count })
    } else {
      existing.count += cat.count
    }
  }
  return Array.from(grouped.entries())
    .sort(([a], [b]) => a.localeCompare(b, 'pt'))
    .map(([label, { value, count }]) => ({ label, value, count }))
}
