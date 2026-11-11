import { PrivateDemoStatus as PilotStatus } from '@/lab/site-pilot-status'
export const PRIVATE_DEMO = import.meta.env.VITE_PUBLIC_AI_BETA === '1'
export function PrivateDemoStatus(props: { refreshKey: string; onBlocked: (blocked: boolean) => void; onReason?: (reason: string) => void }) {
  return PRIVATE_DEMO ? <PilotStatus {...props} /> : null
}
