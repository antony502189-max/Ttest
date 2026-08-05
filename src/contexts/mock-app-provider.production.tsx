import type { Context, ReactNode } from 'react'

export function MockAppProvider<T>({ context: _context, children: _children }: {
  context: Context<T>
  children: ReactNode
}) {
  throw new Error('Mock mode is unavailable in production')
}
