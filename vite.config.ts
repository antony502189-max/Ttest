import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

const legacyMockOwnerExpression = "legacy.ownerUserId ?? (legacy.userCreated ? 'host-demo' : undefined)"

function isolateMockOwnerFromProduction(): Plugin {
  const mockMode = process.env.VITE_ENABLE_MOCK_MODE === '1'
  return {
    name: 'isolate-mock-owner-from-production',
    enforce: 'pre',
    transform(code, id) {
      if (mockMode || !id.replaceAll('\\', '/').endsWith('/src/lib/listings.ts')) return null
      if (!code.includes(legacyMockOwnerExpression)) {
        throw new Error('Expected legacy mock owner expression was not found')
      }
      return {
        code: code.replace(legacyMockOwnerExpression, 'legacy.ownerUserId'),
        map: null,
      }
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  base: process.env.VITE_BASE_PATH || '/',
  plugins: [isolateMockOwnerFromProduction(), react(), tailwindcss()],
  server: {
    watch: {
      ignored: ['**/artifacts/**', '**/test-results/**'],
    },
  },
  resolve: {
    alias: {
      'shadcn/tailwind.css': path.resolve(__dirname, './src/styles/shadcn-tailwind.css'),
      '@/components/marketplace': path.resolve(__dirname, './src/components/marketplace-localized.tsx'),
      '@': path.resolve(__dirname, './src'),
    },
  },
})
