import { defineConfig, loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

type ProductionReplacement = {
  sourceSuffix: string
  mockExpression: string
  productionExpression: string
}

const productionReplacements: ProductionReplacement[] = [
  {
    sourceSuffix: '/src/lib/listings.ts',
    mockExpression: "legacy.ownerUserId ?? (legacy.userCreated ? 'host-demo' : undefined)",
    productionExpression: 'legacy.ownerUserId',
  },
  {
    sourceSuffix: '/src/data/listings.ts',
    mockExpression: "ownerUserId: index < 3 ? 'host-demo' : undefined",
    productionExpression: 'ownerUserId: undefined',
  },
]

function isolateMockDataFromProduction(mockMode: boolean, requireAll = true): Plugin {
  const transformedSources = new Set<string>()
  return {
    name: 'isolate-mock-data-from-production',
    enforce: 'pre',
    transform(code, id) {
      if (mockMode) return null
      const sourceId = id.split('?', 1)[0].replaceAll('\\', '/')
      const replacement = productionReplacements.find(({ sourceSuffix }) => sourceId.includes(sourceSuffix))
      if (!replacement) return null
      if (!code.includes(replacement.mockExpression)) {
        throw new Error(`Expected mock expression was not found in ${replacement.sourceSuffix}`)
      }
      transformedSources.add(replacement.sourceSuffix)
      return {
        code: code.replace(replacement.mockExpression, replacement.productionExpression),
        map: null,
      }
    },
    buildEnd(error) {
      if (requireAll && !mockMode && !error && transformedSources.size !== productionReplacements.length) {
        this.error(
          `Expected ${productionReplacements.length} production mock-data transformations, got ${transformedSources.size}`,
        )
      }
    },
  }
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const syntheticLab = mode === 'ai-synthetic-lab'
  const privateDemo = mode === 'ai-private-demo'
  const sitePilot = mode === 'ai-site-pilot'
  if (sitePilot) {
    const env = loadEnv(mode, process.cwd(), 'VITE_')
    for (const [name, expected] of Object.entries({ VITE_BASE_PATH: '/ai-pilot/', VITE_API_BASE_URL: '/ai-pilot/api/v1', VITE_ENABLE_MOCK_MODE: '0' })) {
      const supplied = process.env[name] ?? env[name]
      if (supplied !== undefined && supplied !== expected) throw new Error(`PILOT_BUILD_CONFIGURATION_REJECTED: ${name}`)
    }
  }
  const labMode = syntheticLab ? (process.env.VITE_AI_CLOSED_LAB
    || loadEnv(mode, process.cwd(), 'VITE_').VITE_AI_CLOSED_LAB || 'finite') : ''
  const labSource = syntheticLab ? (process.env.VITE_AI_LAB_SOURCE_SHA
    || loadEnv(mode, process.cwd(), 'VITE_').VITE_AI_LAB_SOURCE_SHA || '') : ''
  if (syntheticLab && (!['finite', 'decision-transport-fixture', 'closed-live-synthetic'].includes(labMode)
    || !/^[0-9a-f]{40}$/.test(labSource))) throw new Error('Explicit valid lab mode and source SHA required')
  const closedLiveSynthetic = syntheticLab && labMode === 'closed-live-synthetic'
  const labNotice = closedLiveSynthetic
    ? 'Закрытый LIVE synthetic smoke · Настоящая модель, синтетический каталог. Только три согласованные фразы corpus; личные данные запрещены. Карта локальная, без провайдера карт.'
    : 'Закрытый synthetic стенд · Тестовый parser, не LLM. Фразы: «все варианты», «с маленькой собакой», «до 600 евро в месяц», «до 400 евро в месяц», «без ограничения бюджета», «желательно с балконом», «обязательно с балконом». Карта локальная, без провайдера.'
  const mockMode = !sitePilot && loadEnv(mode, process.cwd(), 'VITE_').VITE_ENABLE_MOCK_MODE === '1'
  const mockProviderModule = mockMode
    ? './src/contexts/mock-app-provider.tsx'
    : './src/contexts/mock-app-provider.production.tsx'

  return {
    define: {
      ...(sitePilot ? { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('/ai-pilot/api/v1'), 'import.meta.env.VITE_ENABLE_MOCK_MODE': JSON.stringify('0') } : {}),
      'import.meta.env.VITE_AI_CLOSED_LAB': JSON.stringify(labMode),
      'import.meta.env.VITE_AI_LAB_SOURCE_SHA': JSON.stringify(labSource),
    },
    base: sitePilot ? '/ai-pilot/' : process.env.VITE_BASE_PATH || '/',
    plugins: [isolateMockDataFromProduction(mockMode, !sitePilot), react(), tailwindcss(), ...(sitePilot ? [{
      name: 'site-pilot-notice',
      transformIndexHtml: { order: 'pre', handler: (html: string) => html.replace('/src/main.tsx', '/src/lab/site-pilot-main.tsx') },
      transform: (code: string, id: string) => {
        const source = id.replaceAll('\\', '/')
        // Same-origin pilot tabs must not overwrite the ordinary site's guest
        // favorites, publication drafts, language or continuation storage.
        const output = source.includes('/src/') ? code.replaceAll('112233:', '112233:site-pilot:') : code
        return output === code ? null : output
      },
    }] : []), ...(privateDemo ? [{
      name: 'private-demo-notice',
      transformIndexHtml: (html: string) => html.replace(/<body[^>]*>/, '$&<aside style="padding:12px;background:#e8f2e1;color:#173d20;text-align:center" data-i18n-exempt>Закрытая демонстрация · DeepSeek + снимок реальных публичных объявлений PisoCompartido. Выберите долгосрочную аренду. Фразы по порядку: «до 600 евро в месяц» → «теперь до 400 евро в месяц» → «убери ограничение бюджета». Лимит: 3 обращения к модели. Карта — координатная сетка без внешних тайлов.</aside>'),
    }] : []), ...(syntheticLab ? [{
      name: 'synthetic-lab-notice',
      transformIndexHtml: (html: string) => html.replace(/<body[^>]*>/, `$&<aside style="padding:12px;background:#fff3cd;color:#332600;text-align:center" data-i18n-exempt>${labNotice}</aside>`),
      transform: (code: string, id: string) => /\/src\/(pages\/HomePage|data\/listings)\.tsx?$/.test(id.replaceAll('\\', '/'))
        ? code.replace(/https:\/\/images\.unsplash\.com\/[^'"\s]+/g, '/lab-placeholder.svg') : null,
    }] : [])],
    // Audit artifacts contain HTML fixtures and copied applications. Only the
    // application entry point belongs in dependency discovery.
    optimizeDeps: { entries: ['index.html'] },
    server: {
      watch: {
        ignored: ['**/artifacts/**', '**/test-results/**', '**/output/**', '**/var/**', '**/.venv/**', '**/.audit-venv/**', '**/.smoke-venv/**', '**/backend/**'],
      },
    },
    resolve: {
      alias: {
        ...(sitePilot ? { '@/contexts/app-context': path.resolve(import.meta.dirname, './src/lab/site-pilot-context.ts') } : {}),
        '@/components/private-demo-status': path.resolve(import.meta.dirname, sitePilot ? './src/lab/site-pilot-status.tsx' : privateDemo ? './src/lab/private-demo-status.tsx' : './src/components/private-demo-status.tsx'),
        ...(syntheticLab || privateDemo || sitePilot ? { '@/components/ai-result-map': path.resolve(import.meta.dirname, './src/lab/ai-synthetic-map.tsx') } : {}),
        'shadcn/tailwind.css': path.resolve(import.meta.dirname, './src/styles/shadcn-tailwind.css'),
        '@/components/marketplace': path.resolve(import.meta.dirname, sitePilot ? './src/lab/site-pilot-card.tsx' : './src/components/marketplace-localized.tsx'),
        '@/contexts/mock-app-provider': path.resolve(import.meta.dirname, mockProviderModule),
        '@': path.resolve(import.meta.dirname, './src'),
      },
    },
  }
})
