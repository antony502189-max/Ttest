import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

type ProductionReplacement = {
  sourceSuffix: string
  mockExpression: string
  productionExpression: string
}

const mockMode = process.env.VITE_ENABLE_MOCK_MODE === '1'
const mockProviderModule = mockMode
  ? './src/contexts/mock-app-provider.tsx'
  : './src/contexts/mock-app-provider.production.tsx'

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

function isolateMockDataFromProduction(): Plugin {
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
export default defineConfig({
  base: process.env.VITE_BASE_PATH || '/',
  plugins: [isolateMockDataFromProduction(), react(), tailwindcss()],
  server: {
    watch: {
      ignored: ['**/artifacts/**', '**/test-results/**'],
    },
  },
  resolve: {
    alias: {
      'shadcn/tailwind.css': path.resolve(__dirname, './src/styles/shadcn-tailwind.css'),
      '@/components/marketplace': path.resolve(__dirname, './src/components/marketplace-localized.tsx'),
      '@/contexts/mock-app-provider': path.resolve(__dirname, mockProviderModule),
      '@': path.resolve(__dirname, './src'),
    },
  },
})
