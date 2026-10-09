import { PublishAddressLifecycle } from '@/components/publish-address-lifecycle'
import { PublishLocationEnhancer } from '@/components/publish-location-enhancer'

export function PublishRouteEnhancers() {
  return <>
    <PublishLocationEnhancer />
    <PublishAddressLifecycle />
  </>
}
