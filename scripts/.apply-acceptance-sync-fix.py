from pathlib import Path

path = Path("tests/acceptance-flows.spec.ts")
text = path.read_text(encoding="utf-8")
start_marker = 'test("09 sorting by date and both prices plus real disjoint pagination", async ({'
end_marker = 'test("10–13 map marker/card sync, marker preview, bounds and polygon filtering", async ({'

if text.count(start_marker) != 1 or text.count(end_marker) != 1:
    raise SystemExit("acceptance test markers are not unique")

start = text.index(start_marker)
end = text.index(end_marker)
if start >= end:
    raise SystemExit("acceptance test markers are out of order")

replacement = '''test("09 sorting by date and both prices plus real disjoint pagination", async ({
  page,
}) => {
  await page.goto("/#/buscar?q=Tenerife&alquiler=long");
  const cards = page.locator(".results-list .property-card");
  const ids = () =>
    cards.evaluateAll((items) =>
      items.map((card) => card.getAttribute("data-listing-id")),
    );
  const selectedSort = () =>
    page.evaluate(
      () =>
        new URLSearchParams(window.location.hash.split("?", 2)[1] ?? "").get(
          "orden",
        ),
    );
  const priceOrder = async (direction: "asc" | "desc") => {
    const values = (
      await page.locator(".results-list .price-block strong").allTextContents()
    ).map((value) => Number.parseInt(value.replace(/\\D/g, "")));
    return {
      count: values.length,
      valid: values.every(Number.isFinite),
      ordered: values.every((value, index) =>
        index === 0 ||
        (direction === "asc"
          ? values[index - 1] <= value
          : values[index - 1] >= value),
      ),
    };
  };
  const dateOrder = async () =>
    page.evaluate((visibleIds) => {
      const stored = JSON.parse(
        localStorage.getItem("112233:listings:v3") || '{"data":[]}',
      ) as { data?: { id: string; publishedAt: string }[] };
      const listings = stored.data ?? [];
      const values = visibleIds.map((id) =>
        new Date(
          listings.find((item) => item.id === id)?.publishedAt ?? "",
        ).getTime(),
      );
      return {
        count: values.length,
        valid: values.every(Number.isFinite),
        ordered: values.every(
          (value, index) => index === 0 || values[index - 1] >= value,
        ),
      };
    }, await ids());

  await expect(cards).toHaveCount(9);
  await page.getByLabel("Ordenar resultados").selectOption("Más recientes");
  await expect.poll(selectedSort).toBe("Más recientes");
  await expect.poll(dateOrder).toEqual({ count: 9, valid: true, ordered: true });

  await page.getByLabel("Ordenar resultados").selectOption("Precio más alto");
  await expect.poll(selectedSort).toBe("Precio más alto");
  await expect.poll(() => priceOrder("desc")).toEqual({
    count: 9,
    valid: true,
    ordered: true,
  });

  await page.getByLabel("Ordenar resultados").selectOption("Precio más bajo");
  await expect.poll(selectedSort).toBe("Precio más bajo");
  await expect.poll(() => priceOrder("asc")).toEqual({
    count: 9,
    valid: true,
    ordered: true,
  });

  const firstPage = await ids();
  expect(firstPage).toHaveLength(9);
  expect(firstPage.every(Boolean)).toBe(true);
  await page.getByRole("button", { name: "2", exact: true }).click();
  await expect(page).toHaveURL(/pagina=2/);
  await expect(page.locator('.pagination [aria-current="page"]')).toHaveText(
    "2",
  );
  await expect
    .poll(async () => {
      const secondPage = await ids();
      return {
        count: secondPage.length,
        valid: secondPage.every(Boolean),
        disjoint: secondPage.every((id) => !firstPage.includes(id)),
      };
    })
    .toEqual({ count: 9, valid: true, disjoint: true });
  await expect(
    page.getByRole("button", { name: /página anterior/i }),
  ).toBeEnabled();
});

'''

updated = text[:start] + replacement + text[end:]
if updated == text:
    raise SystemExit("acceptance test replacement produced no change")
path.write_text(updated, encoding="utf-8")
