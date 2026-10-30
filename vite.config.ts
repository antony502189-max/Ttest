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

function isolateMockDataFromProduction(mockMode: boolean): Plugin {
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
      if (!mockMode && !error && transformedSources.size !== productionReplacements.length) {
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
  const mockMode = loadEnv(mode, process.cwd(), 'VITE_').VITE_ENABLE_MOCK_MODE === '1'
  const mockProviderModule = mockMode
    ? './src/contexts/mock-app-provider.tsx'
    : './src/contexts/mock-app-provider.production.tsx'

  return {
    base: process.env.VITE_BASE_PATH || '/',
    plugins: [isolateMockDataFromProduction(mockMode), react(), tailwindcss(), ...(syntheticLab ? [{
      name: 'synthetic-lab-notice',
      transformIndexHtml: (html: string) => html.replace('<body>', '<body><aside style="padding:12px;background:#fff3cd;color:#332600;text-align:center" data-i18n-exempt>Закрытый synthetic стенд · Тестовый parser, не LLM. Фразы: «все варианты», «с маленькой собакой», «до 600 евро в месяц», «до 400 евро в месяц», «без ограничения бюджета», «желательно с балконом», «обязательно с балконом». Карта локальная, без провайдера.</aside>'),
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
        ...(syntheticLab ? { '@/components/ai-result-map': path.resolve(import.meta.dirname, './src/lab/ai-synthetic-map.tsx') } : {}),
        'shadcn/tailwind.css': path.resolve(import.meta.dirname, './src/styles/shadcn-tailwind.css'),
        '@/components/marketplace': path.resolve(import.meta.dirname, './src/components/marketplace-localized.tsx'),
        '@/contexts/mock-app-provider': path.resolve(import.meta.dirname, mockProviderModule),
        '@': path.resolve(import.meta.dirname, './src'),
      },
    },
  }
})
