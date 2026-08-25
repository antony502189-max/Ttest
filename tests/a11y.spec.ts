import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const routes = [
  { name: "inicio", path: "/#/" },
  { name: "resultados", path: "/#/buscar?q=Tenerife&alquiler=long" },
  {
    name: "mapa",
    path: "/#/buscar?q=Tenerife&alquiler=long&vista=mapa",
  },
  { name: "detalle", path: "/#/habitacion/armeñime-luminosa-01" },
  { name: "acceso", path: "/#/acceso" },
  { name: "registro", path: "/#/registro" },
  { name: "recuperar", path: "/#/recuperar-contrasena" },
  { name: "restablecer", path: "/#/restablecer-contrasena?token=demo" },
  { name: "favoritos", path: "/#/favoritos" },
  { name: "ayuda", path: "/#/ayuda" },
  {
    name: "guardadas",
    path: "/#/busquedas-guardadas",
    session: "host-demo",
  },
  { name: "perfil", path: "/#/perfil", session: "host-demo" },
  { name: "mis anuncios", path: "/#/mis-anuncios", session: "host-demo" },
  { name: "publicar", path: "/#/publicar", session: "host-demo" },
  { name: "administración", path: "/#/admin", session: "admin-demo" },
];

const openRoute = async (page: Page, route: (typeof routes)[number]) => {
  await page.addInitScript(() => {
    localStorage.setItem("112233:mobile-onboarding:v1", "done");
    localStorage.setItem("112233:listing-access-profile:v1", JSON.stringify({
      occupant: "any",
      pets: "Cualquiera",
      smoking: "Cualquiera",
    }));
  });
  if (route.session) {
    await page.addInitScript(
      (session) =>
        localStorage.setItem("112233:session:v1", JSON.stringify(session)),
      route.session,
    );
  }
  await page.goto(route.path);
  await page
    .locator(".route-loading")
    .waitFor({ state: "detached" })
    .catch(() => undefined);
  if (route.name === "mapa")
    await page.locator('.google-map-canvas, [data-testid="google-map"]').waitFor({ state: "visible" });
};

const assertNoSeriousViolations = async (page: Page) => {
  const results = await new AxeBuilder({ page })
    .exclude(".google-map-canvas")
    .exclude(".mandatory-home-search__rental .rental-switch strong")
    .exclude(".mandatory-home-search__rental .rental-switch small")
    .analyze();
  expect(
    results.violations.filter(
      (item) => item.impact === "serious" || item.impact === "critical",
    ),
  ).toEqual([]);
};

for (const route of routes) {
  test(`axe sin impactos serious/critical: ${route.name}`, async ({ page }) => {
    test.setTimeout(60_000);
    await openRoute(page, route);
    await assertNoSeriousViolations(page);
  });
}

for (const route of routes.filter((item) =>
  [
    "inicio",
    "resultados",
    "mapa",
    "detalle",
    "publicar",
    "administración",
  ].includes(item.name),
)) {
  test(`axe móvil 390px sin impactos serious/critical: ${route.name}`, async ({
    page,
  }) => {
    test.setTimeout(60_000);
    await page.setViewportSize({ width: 390, height: 844 });
    await openRoute(page, route);
    await assertNoSeriousViolations(page);
  });
}

test("delta remaining contact controls support keyboard operation and axe while internal messaging stays removed", async ({ page }) => {
  await openRoute(page, { name: "detalle", path: "/#/habitacion/arme%C3%B1ime-luminosa-01" });
  const panel = page.getByRole("complementary", { name: "Contactar con el anunciante" });
  const confirmation = panel.locator('.condition-confirm [role="checkbox"]').first();
  await expect(confirmation).toHaveAttribute("aria-checked", "false");
  await confirmation.press("Space");
  await expect(confirmation).toHaveAttribute("aria-checked", "true");
  await expect(panel.getByRole("button", { name: "Enviar mensaje" })).toHaveCount(0);
  const results = await new AxeBuilder({ page }).include(".contact-panel").analyze();
  expect(results.violations.filter((item) => item.impact === "serious" || item.impact === "critical")).toEqual([]);
});

test("delta fullscreen location flow has no serious or critical axe issues", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openRoute(page, { name: "inicio", path: "/#/" });
  await page.getByRole("button", { name: "Buscar en Tenerife" }).click();
  await expect(page.getByTestId("location-screen")).toBeVisible();
  const results = await new AxeBuilder({ page }).include(".m2-location").analyze();
  expect(results.violations.filter((item) => item.impact === "serious" || item.impact === "critical")).toEqual([]);
});

test("delta drawing announcement and controls have no serious or critical axe issues", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openRoute(page, { name: "mapa", path: "/#/buscar?q=Tenerife&vista=mapa&dibujar=1" });
  const drawZone = page.getByRole("button", { name: "Dibujar tu zona" });
  if (await drawZone.isDisabled()) {
    await expect(page.getByRole("alert")).toContainText("No se pudo cargar Google Maps");
    await assertNoSeriousViolations(page);
    return;
  }
  await drawZone.click();
  await expect(page.getByTestId("freehand-overlay")).toBeVisible();
  const results = await new AxeBuilder({ page }).include(".m2-map-screen").exclude(".m2-map-canvas").analyze();
  expect(results.violations.filter((item) => item.impact === "serious" || item.impact === "critical")).toEqual([]);
});

test("delta avatar uploader has no serious or critical axe issues", async ({ page }) => {
  await openRoute(page, { name: "perfil", path: "/#/perfil", session: "host-demo" });
  await page.getByRole("button", { name: "Editar perfil" }).click();
  const results = await new AxeBuilder({ page }).include(".profile-layout").analyze();
  expect(results.violations.filter((item) => item.impact === "serious" || item.impact === "critical")).toEqual([]);
});

test("delta image uploader has no serious or critical axe issues", async ({ page }) => {
  await openRoute(page, { name: "publicar", path: "/#/publicar", session: "host-demo" });
  for (let step = 0; step < 6; step += 1) await page.getByRole("button", { name: "Continuar" }).click();
  const results = await new AxeBuilder({ page }).include(".image-uploader").analyze();
  expect(results.violations.filter((item) => item.impact === "serious" || item.impact === "critical")).toEqual([]);
});

test("delta approximate location map and controls have no serious or critical axe issues", async ({ page }) => {
  await openRoute(page, { name: "publicar", path: "/#/publicar", session: "host-demo" });
  await page.getByRole("button", { name: "Continuar" }).click();
  await expect(page.locator(".approximate-location-map")).toBeVisible();
  const results = await new AxeBuilder({ page }).include(".approximate-location-selector").analyze();
  expect(results.violations.filter((item) => item.impact === "serious" || item.impact === "critical")).toEqual([]);
});

test("delta account deletion confirmation has no serious or critical axe issues", async ({ page }) => {
  await openRoute(page, { name: "perfil", path: "/#/perfil", session: "host-demo" });
  await page.getByRole("button", { name: "Eliminar cuenta" }).click();
  const dialog = page.getByRole("alertdialog", { name: "¿Eliminar tu cuenta?" });
  await expect(dialog).toBeVisible();
  const results = await new AxeBuilder({ page }).include('[role="alertdialog"]').analyze();
  expect(results.violations.filter((item) => item.impact === "serious" || item.impact === "critical")).toEqual([]);
});