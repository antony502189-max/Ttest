import { expect, test, type Page } from "@playwright/test";

const runtimeErrors = new WeakMap<Page, string[]>();

const clean = async (page: Page) => {
  await page.goto("/#/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
};

const login = async (
  page: Page,
  role: "tenant" | "host" | "admin" = "tenant",
) => {
  const credentials =
    role === "admin"
      ? ["admin@112233.es", "admin112233"]
      : role === "host"
        ? ["anfitrion@112233.es", "demo112233"]
        : ["inquilina@112233.es", "demo112233"];
  await page.goto("/#/acceso");
  await page.getByLabel(/^email$/i).fill(credentials[0]);
  await page.locator("#login-password").fill(credentials[1]);
  await page.getByRole("button", { name: /^acceder$/i }).click();
  await expect(page).not.toHaveURL(/acceso/);
};

const resultCount = async (page: Page) =>
  Number.parseInt(
    (await page.locator("#results-title").innerText()).replace(/\D/g, ""),
  );

const clickFirstMapFeatureInViewport = async (page: Page, selector: string) => {
  const elements = page.locator(selector);
  const index = await elements.evaluateAll((nodes) => nodes.findIndex((node) => {
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && rect.right > 0 && rect.bottom > 0 && rect.left < window.innerWidth && rect.top < window.innerHeight;
  }));
  expect(index, `No visible ${selector}`).toBeGreaterThanOrEqual(0);
  await elements.nth(index).click();
};

test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  runtimeErrors.set(page, errors);
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const url = message.location().url;
    const externalMediaFailure = message.text().startsWith("Failed to load resource:")
      && ["images.unsplash.com", "maps.googleapis.com", "maps.gstatic.com"].some((host) => url.includes(host));
    if (!externalMediaFailure) errors.push(message.text().replace(/([?&]key=)[^&\s]+/gi, '$1[redacted]'));
  });
  page.on("pageerror", (error) => errors.push(error.message));
  await clean(page);
});

test.afterEach(async ({ page }) =>
  expect(runtimeErrors.get(page) ?? [], "Errores de consola o runtime").toEqual(
    [],
  ),
);

test("01–03 rental mode, búsqueda por fecha y selección de varias zonas", async ({
  page,
}) => {
  await page.getByRole("radio", { name: "Alquiler vacacional" }).click();
  await page.getByLabel("Ciudad, barrio o zona").fill("Tenerife");
  await page.getByLabel("Entrada").fill("2026-08-10");
  await page.getByRole("button", { name: /abrir selección de ubicación/i }).click();
  for (const area of ["El Médano", "Playa de las Américas"])
    await page
      .locator(".location-selector-option")
      .filter({ hasText: area })
      .getByRole("checkbox")
      .click();
  await page.getByRole("button", { name: /aplicar 2 zonas/i }).click();
  await page.getByRole("button", { name: /^buscar$/i }).click();
  await expect(page).toHaveURL(/alquiler=holiday/);
  await expect(page).toHaveURL(/zonas=/);
  await expect(page).toHaveURL(/fecha=2026-08-10/);
  await expect(
    page.locator(".results-list .price-block").first(),
  ).toContainText("/noche");
});

test("04 every visible filter is wired to data and URL", async ({ page }) => {
  test.setTimeout(120_000);
  const openSearch = async () => {
    await page.goto("/#/buscar?q=Tenerife&alquiler=long");
    await expect(page.locator("#results-title")).toContainText(
      "23 habitaciones",
    );
    return resultCount(page);
  };
  const changed = async (
    action: () => Promise<void>,
    expectedParam: RegExp,
  ) => {
    const before = await openSearch();
    await action();
    await expect(page).toHaveURL(expectedParam);
    await expect.poll(() => resultCount(page)).not.toBe(before);
  };
  const sidebar = () => page.locator(".filter-sidebar");
  const select = (label: string | RegExp, value: string) =>
    sidebar()
      .getByRole("combobox", { name: label, exact: typeof label === "string" })
      .selectOption(value);
  const check = (section: string, label: string) =>
    sidebar()
      .locator(".filter-section")
      .filter({ hasText: section })
      .getByText(label, { exact: true })
      .click();

  await changed(async () => {
    const slider = sidebar().getByRole("slider").first();
    await slider.focus();
    for (let index = 0; index < 16; index += 1)
      await page.keyboard.press("ArrowRight");
  }, /precioMin=/);
  await changed(
    () => page.getByRole("button", { name: /hasta 500/i }).click(),
    /precioMax=500/,
  );
  await changed(
    () => sidebar().getByText("Costa Adeje", { exact: true }).click(),
    /zonas=/,
  );
  await changed(
    () =>
      sidebar()
        .locator(".filter-section")
        .filter({ has: page.getByRole("heading", { name: "Habitación" }) })
        .getByRole("combobox")
        .first()
        .selectOption("Estudio"),
    /habitacion=Estudio/,
  );
  await changed(
    () => sidebar().getByLabel("Disponible para esta fecha").fill("2026-07-20"),
    /fecha=2026-07-20/,
  );
  await changed(() => select(/Estancia/i, "1"), /estancia=1/);
  await changed(
    () => check("Condiciones destacadas", "No fumar"),
    /condiciones=/,
  );
  await changed(
    () => select(/Requisito para la persona inquilina/i, "single-woman"),
    /requisito=single-woman/,
  );
  await changed(() => select(/^Baño$/, "Baño privado"), /bano=/);
  await changed(() => select(/^Cocina$/, "Cocina privada"), /cocina=/);
  await changed(
    () => check("Espacios y equipamiento", "Amueblada"),
    /amueblada=1/,
  );
  await changed(
    () => check("Espacios y equipamiento", "Gastos incluidos"),
    /gastos=1/,
  );
  await changed(() => select(/Depósito/i, "Sin fianza"), /fianza=/);
  await changed(() => select(/Residentes actuales/i, "1"), /residentes=1/);
  await changed(() => select(/Se puede fumar/i, "Sí"), /fumar=/);
  await changed(() => select(/^Mascotas$/, "Sí"), /mascotas=/);
  await changed(() => select(/^Niños$/, "Sí"), /ninos=/);
  await changed(() => select(/^Empadronamiento$/, "Sí"), /padron=/);
  await changed(() => select(/^Publicado$/, "24h"), /publicado=24h/);
  await changed(
    () => select(/Tipo de anunciante/i, "Profesional"),
    /anunciante=/,
  );
  await changed(() => check("Espacios y equipamiento", "Fibra"), /servicios=/);
});

test("05–08 filter count, individual chips, clear, URL reload and history navigation", async ({
  page,
}) => {
  await page.goto("/#/buscar?q=Tenerife&alquiler=long");
  await page.getByRole("button", { name: /hasta 500/i }).click();
  await page
    .locator(".filter-sidebar")
    .getByText("Costa Adeje", { exact: true })
    .click();
  await expect(page.locator(".applied-filters__clear")).toContainText("(2)");
  const filtered = await resultCount(page);
  await page.reload();
  await expect.poll(() => resultCount(page)).toBe(filtered);
  await page
    .locator(".applied-filters button")
    .filter({ hasText: "Costa Adeje" })
    .click();
  await expect(page).not.toHaveURL(/zonas=/);
  await page.goBack();
  await expect(page).toHaveURL(/zonas=/);
  await page.goForward();
  await page.locator(".applied-filters__clear").click();
  await expect(page).not.toHaveURL(/precioMax|zonas=/);
});

test("09 sorting by date and both prices plus real disjoint pagination", async ({
  page,
}) => {
  await page.goto("/#/buscar?q=Tenerife&alquiler=long");
  const ids = () =>
    page
      .locator(".results-list .property-card")
      .evaluateAll((cards) =>
        cards.map((card) => card.getAttribute("data-listing-id")),
      );
  const orderedDates = async () =>
    page.evaluate(
      (visibleIds) => {
        const listings = JSON.parse(
          localStorage.getItem("112233:listings:v2") || "[]",
        ) as { id: string; publishedAt: string }[];
        return visibleIds.map((id) =>
          new Date(
            listings.find((item) => item.id === id)?.publishedAt ?? 0,
          ).getTime(),
        );
      },
      await ids(),
    );
  await page.getByLabel("Ordenar resultados").selectOption("Más recientes");
  const recent = await orderedDates();
  expect(recent).toEqual([...recent].sort((a, b) => b - a));
  await page.getByLabel("Ordenar resultados").selectOption("Precio más alto");
  const high = (
    await page.locator(".results-list .price-block strong").allTextContents()
  ).map((value) => Number.parseInt(value.replace(/\D/g, "")));
  expect(high).toEqual([...high].sort((a, b) => b - a));
  await page.getByLabel("Ordenar resultados").selectOption("Precio más bajo");
  const low = (
    await page.locator(".results-list .price-block strong").allTextContents()
  ).map((value) => Number.parseInt(value.replace(/\D/g, "")));
  expect(low).toEqual([...low].sort((a, b) => a - b));
  const firstPage = await ids();
  await page.getByRole("button", { name: "2", exact: true }).click();
  await expect(page).toHaveURL(/pagina=2/);
  await expect(page.locator('.pagination [aria-current="page"]')).toHaveText(
    "2",
  );
  const secondPage = await ids();
  expect(secondPage.some((id) => firstPage.includes(id))).toBe(false);
  await expect(
    page.getByRole("button", { name: /página anterior/i }),
  ).toBeEnabled();
});

test("10–13 map marker/card sync, marker preview, bounds and polygon filtering", async ({
  page,
}) => {
  await page.goto("/#/buscar?q=Adeje&alquiler=long&vista=mapa");
  const googleMap = page.locator(".google-map-canvas");
  await expect(googleMap).toBeVisible();
  await expect(googleMap).toHaveAttribute('data-map-center', /-16\.7/);
  const before = await page
    .locator(".map-results-cards .property-card")
    .count();
  const firstCard = page.locator(".map-results-cards .property-card").first();
  await firstCard.getByRole("link").first().focus();
  await expect(page.locator(".price-marker.is-highlighted, .room-cluster.is-highlighted")).toHaveCount(1);
  await expect.poll(() => page.locator('.price-marker-shell').count()).toBeGreaterThan(0);
  await clickFirstMapFeatureInViewport(page, '.price-marker-shell');
  await expect(page.locator(".price-marker.is-selected")).toHaveCount(1);
  await expect(page.locator(".map-selected-card")).toBeVisible();
  await expect(page.locator(".map-selected-card a")).toHaveAttribute(
    "href",
    /habitacion/,
  );
  await page.locator(".google-map-canvas").hover();
  await page.mouse.wheel(0, -900);
  await page.getByRole("button", { name: /buscar en esta zona/i }).click();
  await expect
    .poll(() => page.locator(".map-results-cards .property-card").count())
    .toBeLessThan(before);
  const bounded = await page
    .locator(".map-results-cards .property-card")
    .count();
  await page.getByRole("button", { name: /dibujar zona/i }).click();
  for (let index = 0; index < 3; index += 1)
    await page.getByRole("button", { name: /añadir punto/i }).click();
  await page.getByRole("button", { name: /finalizar/i }).click();
  await expect(page).toHaveURL(/poligono=/);
  await expect
    .poll(() => page.locator(".map-results-cards .property-card").count())
    .toBeLessThanOrEqual(bounded);
});

test("14–15 favorites and complete saved-search restoration persist", async ({
  page,
}) => {
  await login(page);
  await page.goto("/#/buscar?q=Tenerife&alquiler=long");
  const card = page.locator(".results-list .property-card").first();
  const id = await card.getAttribute("data-listing-id");
  await card.locator(".favorite-button").click();
  await page.goto("/#/favoritos");
  await expect(page.locator(`[data-listing-id="${id}"]`)).toBeVisible();
  await page.reload();
  await expect(page.locator(`[data-listing-id="${id}"]`)).toBeVisible();
  await page.goto("/#/buscar?q=Tenerife&alquiler=long");
  await page.getByRole("button", { name: /hasta 500/i }).click();
  await page
    .getByRole("button", { name: /guardar búsqueda/i })
    .first()
    .click();
  await page.goto("/#/busquedas-guardadas");
  await expect(page.locator(".saved-search-card")).toHaveCount(1);
  await page.getByRole("button", { name: /desactivar avisos/i }).click();
  await page.getByRole("link", { name: /ver resultados/i }).click();
  await expect(page).toHaveURL(/precioMax=500/);
});

test("16–18 listing gallery keyboard, contact, share and report mutate state", async ({
  page,
}) => {
  await page.goto("/#/habitacion/armeñime-luminosa-01");
  const gallery = page.locator(".property-gallery");
  await gallery.focus();
  const firstCounter = await gallery
    .locator(".gallery-main > span")
    .innerText();
  await page.keyboard.press("ArrowRight");
  await expect(gallery.locator(".gallery-main > span")).not.toHaveText(
    firstCounter,
  );
  await page.evaluate(() => {
    Object.defineProperty(navigator, "share", {
      configurable: true,
      value: async () => {
        (window as typeof window & { shared?: boolean }).shared = true;
      },
    });
  });
  await page.getByRole("button", { name: /compartir/i }).click();
  expect(
    await page.evaluate(
      () => (window as typeof window & { shared?: boolean }).shared,
    ),
  ).toBe(true);
  const contact = page.locator(".listing-aside");
  await expect(
    contact.getByRole("button", { name: /whatsapp/i }),
  ).toBeDisabled();
  await contact.getByRole("checkbox").click();
  await expect(
    contact.getByRole("link", { name: /whatsapp/i }),
  ).toHaveAttribute("href", /^https:\/\/wa\.me\//);
  await page.getByRole("button", { name: /más acciones del anuncio/i }).click();
  await page.getByRole("menuitem", { name: /denunciar anuncio/i }).click();
  await page.getByLabel("Posible fraude").check();
  await page.getByRole("button", { name: /enviar denuncia/i }).click();
  expect(
    await page.evaluate(
      () =>
        JSON.parse(localStorage.getItem("112233:reports:v1") || "[]").length,
    ),
  ).toBe(1);
});

test("19–20 registration, login persistence, logout, recovery and reset flows", async ({
  page,
}) => {
  await page.goto("/#/registro");
  await page.getByLabel(/^nombre/i).fill("Usuario Flujo");
  await page.getByLabel(/^email/i).fill("flujo@example.es");
  await page.locator("#register-password").fill("segura112233");
  await page.locator("#register-confirm").fill("segura112233");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: /crear cuenta/i }).click();
  await page.getByRole("link", { name: /abrir mi perfil/i }).click();
  await page.reload();
  await expect(page.getByText("Usuario Flujo")).toBeVisible();
  await page.getByRole("button", { name: /cerrar sesión/i }).click();
  await expect(page).toHaveURL(/acceso/);
  expect(
    await page.evaluate(() => localStorage.getItem("112233:session:v1")),
  ).toBe("null");
  await page.goto("/#/recuperar-contrasena");
  await page.getByLabel(/email de tu cuenta/i).fill("flujo@example.es");
  await page.getByRole("button", { name: /solicitar enlace/i }).click();
  await page.getByRole("link", { name: /crear nueva contraseña/i }).click();
  await page.getByLabel(/^nueva contraseña/i).fill("nueva112233");
  await page.getByLabel(/repite la contraseña/i).fill("nueva112233");
  await page.getByRole("button", { name: /guardar contraseña/i }).click();
  await expect(page.getByText(/todo listo/i)).toBeVisible();
});

test("21–24 wizard validates, restores/reset draft, previews user data, creates and edits", async ({
  page,
}) => {
  await login(page, "host");
  await page.goto("/#/publicar");
  await page.getByRole("button", { name: /continuar/i }).click();
  await page.getByLabel(/zona o barrio/i).fill("");
  await page.getByRole("button", { name: /continuar/i }).click();
  await expect(page.getByRole("alert")).toContainText(/indica la zona/i);
  await page.getByLabel(/zona o barrio/i).fill("Zona Demo E2E");
  await page.reload();
  await page.getByRole("button", { name: /continuar/i }).click();
  await expect(page.getByLabel(/zona o barrio/i)).toHaveValue("Zona Demo E2E");
  await page.getByRole("button", { name: /restablecer/i }).click();
  await page
    .getByRole("button", { name: /^restablecer$/i })
    .last()
    .click();
  await expect(
    page.getByRole("heading", { name: /qué tipo de estancia/i }),
  ).toBeVisible();
  for (let index = 0; index < 7; index += 1)
    await page.getByRole("button", { name: /continuar/i }).click();
  await page
    .getByLabel(/título del anuncio/i)
    .fill("Habitación creada desde el flujo E2E");
  await page
    .getByLabel(/^descripción$/i)
    .fill(
      "Descripción completa introducida por el usuario para comprobar la vista previa dinámica del anuncio.",
    );
  await page.getByRole("button", { name: /continuar/i }).click();
  await page.getByRole("button", { name: /continuar/i }).click();
  await expect(page.locator(".preview-card-wrap")).toContainText(
    "Habitación creada desde el flujo E2E",
  );
  await page.getByRole("button", { name: /vista previa completa/i }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "Habitación creada desde el flujo E2E",
  );
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: /publicar anuncio/i }).click();
  await page.getByRole("link", { name: /mis anuncios/i }).click();
  const created = page
    .locator(".manage-card")
    .filter({ hasText: "Habitación creada desde el flujo E2E" });
  await expect(created).toBeVisible();
  await created.getByRole("link", { name: /editar/i }).click();
  await expect(
    page.getByRole("heading", { name: /editar habitación/i }),
  ).toBeVisible();
});

test("25–26 hide/show, renew and delete listing all change shared data", async ({
  page,
}) => {
  await login(page, "host");
  await page.goto("/#/mis-anuncios");
  const card = page.locator(".manage-card").first();
  const id = await card.locator("span").filter({ hasText: "Ref." }).innerText();
  const openActions = () =>
    card.getByRole("button", { name: /más acciones/i }).click();
  await openActions();
  await page.getByRole("menuitem", { name: /ocultar/i }).click();
  await expect(card).toContainText("Oculto");
  await openActions();
  await page.getByRole("menuitem", { name: /mostrar/i }).click();
  await expect(card).toContainText("Publicado");
  const oldExpiry = await card.locator(".manage-metrics").innerText();
  await openActions();
  await page.getByRole("menuitem", { name: /renovar/i }).click();
  await expect(card.locator(".manage-metrics")).not.toHaveText(oldExpiry);
  await openActions();
  await page.getByRole("menuitem", { name: /eliminar/i }).click();
  await page.getByRole("button", { name: /^eliminar$/i }).click();
  await expect(page.getByText(id, { exact: false })).toHaveCount(0);
});

test("27 admin status filter, approve/hide/reject, user blocking and CSV are stateful", async ({
  page,
}) => {
  await login(page, "admin");
  await page.goto("/#/admin");
  await page.getByRole("button", { name: /anuncios/i }).click();
  const firstRow = page.locator("tbody tr").first();
  const actionButton = () =>
    firstRow.getByRole("button", { name: /acciones para/i });
  await actionButton().click();
  await page.getByRole("menuitem", { name: /ocultar/i }).click();
  await expect(firstRow).toContainText("Oculto");
  await actionButton().click();
  await page.getByRole("menuitem", { name: /rechazar/i }).click();
  await expect(firstRow).toContainText("Rechazado");
  await actionButton().click();
  await page.getByRole("menuitem", { name: /aprobar/i }).click();
  await expect(firstRow).toContainText("Publicado");
  await page.getByLabel("Estado").selectOption("Publicado");
  await expect(page.locator("tbody tr")).not.toHaveCount(0);
  await page.getByRole("button", { name: /usuarios/i }).click();
  await page
    .locator("tbody tr")
    .first()
    .getByRole("button", { name: /bloquear/i })
    .click();
  await page.getByRole("button", { name: /^bloquear$/i }).click();
  await expect(page.locator("tbody tr").first()).toContainText("Bloqueada");
  await page.getByRole("button", { name: /anuncios/i }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: /exportar CSV/i }).click();
  expect((await download).suggestedFilename()).toBe("112233-anuncios.csv");
});

test("28–29 mobile navigation and keyboard-only critical path", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("about:blank");
  await page.goto("/#/");
  await page.evaluate(() =>
    (document.activeElement as HTMLElement | null)?.blur(),
  );
  await page.bringToFront();
  const skipLink = page.locator(".skip-link");
  await expect(skipLink).toBeVisible();
  await skipLink.focus();
  await expect(skipLink).toBeFocused();
  await page.keyboard.press("Enter");
  const location = page.getByRole("button", { name: /abrir selección de ubicación/i }).first();
  await location.focus();
  await page.keyboard.press("Enter");
  const search = page.getByPlaceholder("Municipio, barrio, zona o dirección");
  await search.fill("Los Cristianos");
  await page.getByRole("button", { name: /Los Cristianos/i }).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: /^buscar$/i }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/buscar/);
  await expect(page.locator(".bottom-nav")).toBeVisible();
  await page.getByRole("button", { name: /todos los filtros/i }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog", { name: /filtros/i })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: /todos los filtros/i }),
  ).toBeFocused();
});
