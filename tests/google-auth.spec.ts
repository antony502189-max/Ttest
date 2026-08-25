import { expect, test } from '@playwright/test'

type GoogleCallback = (response: { credential: string }) => void

async function installMockGoogleIdentity(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    let callback: GoogleCallback | undefined
    window.google = {
      accounts: { id: {
        initialize: (options) => { callback = options.callback },
        renderButton: (parent) => {
          const button = document.createElement('button')
          button.type = 'button'
          button.textContent = 'Continuar con Google'
          button.setAttribute('aria-label', 'Continuar con Google')
          button.addEventListener('click', () => callback?.({ credential: 'mock-gis-credential' }))
          parent.replaceChildren(button)
        },
        cancel: () => undefined,
      } },
    }
    const markGoogleScriptAsLoaded = () => {
      if (document.getElementById('google-identity-services')) return
      const script = document.createElement('script')
      script.id = 'google-identity-services'
      document.head.append(script)
    }
    if (document.head) markGoogleScriptAsLoaded()
    else document.addEventListener('DOMContentLoaded', markGoogleScriptAsLoaded, { once: true })
  })
}

test('Google GIS callback posts the credential and returns to the requested route', async ({ page }) => {
  await installMockGoogleIdentity(page)
  let credential = ''
  await page.route('**/api/v1/auth/google', async (route) => {
    credential = JSON.parse(route.request().postData() ?? '{}').credential
    await route.fulfill({ json: { accessToken: 'test-access-token', user: { id: 'google-user', name: 'Google User', email: 'user@gmail.com', role: 'tenant', phone: '', whatsapp: '', telegram: '', about: '', initials: 'GU', showPhone: false, showWhatsApp: false, emailVerified: true } } })
  })

  await page.goto('/#/acceso', { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'Continuar con Google' }).click()
  await expect.poll(() => credential).toBe('mock-gis-credential')
  await expect(page).toHaveURL(/#\/$/)
})

test('Google login errors remain visible to the user', async ({ page }) => {
  await installMockGoogleIdentity(page)
  await page.route('**/api/v1/auth/google', (route) => route.fulfill({ status: 401, json: { detail: 'La credencial de Google no es válida.' } }))

  await page.goto('/#/acceso', { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'Continuar con Google' }).click()
  await expect(page.getByRole('alert')).toContainText('La credencial de Google no es válida.')
})
