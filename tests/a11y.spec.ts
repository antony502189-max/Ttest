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
    await page.locator(".leaflet-map-canvas").waitFor({ state: "visible" });
};

const assertNoSeriousViolations = async (page: Page) => {
  const results = await new AxeBuilder({ page })
    .exclude(".leaflet-map-canvas")
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

test("delta contact dialog supports keyboard focus and axe", async ({ page }) => {
  await page.goto("/#/habitacion/arme%C3%B1ime-luminosa-01");
  const trigger = page.getByRole("button", { name: "Enviar mensaje" }).first();
  await trigger.focus();
  await trigger.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Enviar un mensaje local" });
  await expect(dialog).toBeVisible();
  const results = await new AxeBuilder({ page }).include(".contact-message-dialog").analyze();
  expect(results.violations.filter((item) => item.impact === "serious" || item.impact === "critical")).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
});

test("delta fullscreen location flow has no serious or critical axe issues", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/#/");
  await page.getByRole("button", { name: /Abrir selección de ubicación/ }).first().click();
  await expect(page.getByRole("dialog", { name: "¿Dónde buscas?" })).toBeVisible();
  const results = await new AxeBuilder({ page }).include(".location-selector-dialog").analyze();
  expect(results.violations.filter((item) => item.impact === "serious" || item.impact === "critical")).toEqual([]);
});

test("delta drawing announcement and controls have no serious or critical axe issues", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/#/buscar?q=Tenerife&vista=mapa&dibujar=1");
  await expect(page.locator(".leaflet-map-shell")).toHaveAttribute("data-drawing", "true", { timeout: 15_000 });
  const results = await new AxeBuilder({ page }).include(".mobile-map-screen").exclude(".leaflet-map-canvas").analyze();
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
