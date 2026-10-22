import { test, expect, type Page } from "@playwright/test";
async function login(page: Page, id = "240103049") {
  await page.goto("/");
  await page.getByLabel("SDU ID").fill(id);
  await page.getByPlaceholder("At least 8 characters").fill("Campus123!");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Where to?" })).toBeVisible();
}
async function search(page: Page, name: string) {
  const back = page.getByRole("button", { name: "Back to places" });
  if (await back.isVisible()) await back.click();
  await page.getByRole("textbox", { name: "Search campus" }).fill(name);
  await page
    .locator(".location-list")
    .getByRole("button", { name: new RegExp(name) })
    .first()
    .click();
  await expect(page.locator(".location-details h3")).toHaveText(name);
}
test("login shows identity and avatar, survives reload and logs out", async ({
  page,
}) => {
  await login(page);
  await expect(page.locator(".identity-link")).toContainText("Yerassyl");
  await expect(page.locator(".identity-link .avatar")).toHaveText("Y");
  await page.reload();
  await expect(page.locator(".identity-link")).toContainText("Student");
  await page.getByRole("link", { name: "Profile", exact: true }).click();
  await page.getByRole("button", { name: "Log out", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Good to see you." }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Good to see you." }),
  ).toBeVisible();
});
test("guest can explore and route but cannot save", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Continue as guest" }).click();
  await search(page, "D201");
  await expect(
    page.getByRole("button", { name: "Log in to save" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Save place" })).toHaveCount(0);
  await page.getByRole("button", { name: "Find route", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Route directions" }),
  ).toContainText("floor 1 to floor 2");
});
test("D201 switches floor and route from entrance draws both floors", async ({
  page,
}) => {
  await login(page, "240103050");
  await search(page, "D201");
  await expect(
    page.locator(".floor-switch button").filter({ hasText: "Floor 2" }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Find route", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Route directions" }),
  ).toContainText("Your route");
  await expect(page.locator(".route-floor-tabs button")).toHaveCount(2);
  await page
    .locator(".route-floor-tabs")
    .getByRole("button", { name: "Floor 2" })
    .click();
  await expect(
    page.locator('svg[aria-label="Schematic floor 2"] line'),
  ).not.toHaveCount(0);
});
test("saved accessibility preference changes cross-floor routing to a lift", async ({
  page,
}) => {
  await login(page, "240103051");
  await page.getByRole("link", { name: "Profile", exact: true }).click();
  await page.getByRole("switch").check();
  await expect(
    page.getByText("Preference saved to your account"),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByRole("switch")).toBeChecked();
  await page.getByRole("link", { name: "Campus map", exact: true }).click();
  await search(page, "D201");
  await page.getByRole("button", { name: "Find route", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Route directions" }),
  ).toContainText("lift from floor 1 to floor 2");
  await expect(
    page.getByRole("region", { name: "Route directions" }),
  ).toContainText("Stairs excluded");
});
test("five saved places persist and removal permits replacement", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Create an account" }).click();
  await page.getByLabel("Full name").fill("Browser Test Student");
  await page.getByLabel("SDU ID").fill("299888777");
  await page.getByPlaceholder("At least 8 characters").fill("Campus123!");
  await page.getByLabel("Confirm password").fill("Campus123!");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  for (const room of ["D101", "D102", "D103", "D104", "D201"]) {
    await search(page, room);
    await page.getByRole("button", { name: /Save place/ }).click();
    await expect(
      page.getByRole("button", { name: /Remove saved/ }),
    ).toBeVisible();
  }
  await search(page, "D202");
  await expect(page.getByRole("button", { name: /Save place/ })).toBeDisabled();
  await page.getByRole("link", { name: /Saved places/ }).click();
  await expect(page.locator(".place-card")).toHaveCount(5);
  await page
    .locator(".place-card")
    .first()
    .getByRole("button", { name: "Remove", exact: true })
    .click();
  await expect(page.locator(".place-card")).toHaveCount(4);
  await page.reload();
  await expect(page.locator(".place-card")).toHaveCount(4);
  await page.getByRole("link", { name: "Campus map", exact: true }).click();
  await search(page, "D202");
  await page.getByRole("button", { name: /Save place/ }).click();
  await expect(
    page.getByRole("button", { name: /Remove saved/ }),
  ).toBeVisible();
});
test("administrator edits persist and public details reflect the database", async ({
  page,
}) => {
  await login(page, "240000002");
  await page.getByRole("link", { name: "Administration", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Filter admin locations" })
    .fill("Library");
  await page
    .getByRole("row")
    .filter({ has: page.getByText("Library", { exact: true }) })
    .getByRole("button", { name: /Edit/ })
    .click();
  await page.getByLabel("Opening hours").fill("Sample: 09:00–17:00");
  await page.getByRole("button", { name: "Save location" }).click();
  await expect(page.getByText("Changes saved to the database.")).toBeVisible();
  await page.reload();
  await page
    .getByRole("textbox", { name: "Filter admin locations" })
    .fill("Library");
  await expect(
    page.getByRole("cell", { name: "Sample: 09:00–17:00" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Campus map", exact: true }).click();
  await search(page, "Library");
  await expect(page.locator(".detail-facts")).toContainText(
    "Sample: 09:00–17:00",
  );
});
test("mobile map keeps floor/zoom controls usable and identity visible", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "Continue as guest" }).click();
  await expect(page.locator(".compact-identity")).toContainText("Guest");
  await expect(
    page.getByRole("button", { name: "Zoom in", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Explore", exact: true }).click();
  await search(page, "D201");
  await page.getByRole("button", { name: "Find route", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Route directions" }),
  ).toContainText("Your route");
  await page.getByRole("button", { name: "Close explore panel" }).click();
  await expect(
    page.getByRole("button", { name: "Fit map", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

test("assistant recommends a service and resolves an actual ambiguous lift choice", async ({
  page,
}) => {
  await login(page, "240103053");
  await page.getByRole("link", { name: "Assistant", exact: true }).click();
  await page.getByRole("button", { name: "I feel sick" }).click();
  await expect(page.locator(".assistant-message").last()).toContainText(
    "Medical Point",
  );
  await page
    .getByRole("textbox", { name: "Ask the campus assistant" })
    .fill("directions to a lift");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.locator(".choice-list button").first()).toBeVisible();
  const choice = page.locator(".choice-list button").first();
  await choice.click();
  await expect(page.locator(".assistant-message").last()).toContainText(
    "Selected",
  );
  await page.locator(".assistant-message").last().getByRole("button").click();
  await expect(page.locator(".location-details h3")).toContainText("lift");
});

test("editable sample timetable persists dates and exposes map action", async ({
  page,
}) => {
  await login(page, "240103052");
  await page.getByRole("link", { name: "Timetable", exact: true }).click();
  await page.getByRole("button", { name: "Add sample lesson" }).click();
  await page.getByLabel("Course", { exact: true }).fill("Browser sample class");
  await page.getByLabel("Date and time · Asia/Almaty").fill("2030-01-15T10:30");
  await page.getByLabel("Room label").fill("D201");
  await page
    .getByLabel("Link to campus location")
    .selectOption({ label: "D201 · Floor 2" });
  await page.getByRole("button", { name: "Save lesson" }).click();
  const row = page
    .locator(".schedule-list article")
    .filter({ hasText: "Browser sample class" });
  await expect(row).toContainText("15 Jan, 10:30");
  await row.getByRole("button", { name: "Edit", exact: true }).click();
  await expect(page.getByLabel("Date and time · Asia/Almaty")).toHaveValue(
    "2030-01-15T10:30",
  );
  await page
    .getByLabel("Course", { exact: true })
    .fill("Edited browser sample");
  await page.getByRole("button", { name: "Save lesson" }).click();
  await page.reload();
  const edited = page
    .locator(".schedule-list article")
    .filter({ hasText: "Edited browser sample" });
  await expect(edited).toContainText("15 Jan, 10:30");
  await edited.getByRole("button", { name: "Map", exact: true }).click();
  await expect(page.locator(".location-details h3")).toHaveText("D201");
});

test("AI conversation ID is carried into follow-ups and new chat resets it", async ({
  page,
}) => {
  await login(page);
  await page.route("**/api/assistant/status", (route) =>
    route.fulfill({
      json: {
        configured: true,
        engine: "openrouter",
        model: "deepseek/deepseek-v4-flash-0731",
      },
    }),
  );
  const received: Record<string, unknown>[] = [];
  await page.route("**/api/assistant/query", async (route) => {
    received.push(route.request().postDataJSON());
    await route.fulfill({
      json: {
        answer: "Library hours are not confirmed.",
        location: null,
        choices: [],
        needs_clarification: false,
        engine: "openrouter",
        model: "deepseek/deepseek-v4-flash-0731",
        conversation_id: "browser-conversation",
      },
    });
  });
  await page.getByRole("link", { name: "Assistant", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Ask the campus assistant" })
    .fill("Find somewhere quiet");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.locator(".assistant-message")).toHaveCount(1);
  await expect(page.locator(".answer-source")).toContainText("DeepSeek");
  await page
    .getByRole("textbox", { name: "Ask the campus assistant" })
    .fill("When does it close?");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.locator(".assistant-message")).toHaveCount(2);
  expect(received[1].conversation_id).toBe("browser-conversation");
  await page.getByRole("button", { name: "New chat", exact: true }).click();
  await expect(page.locator(".assistant-message")).toHaveCount(0);
  await page
    .getByRole("textbox", { name: "Ask the campus assistant" })
    .fill("Library");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.locator(".assistant-message")).toHaveCount(1);
  expect(received[2].conversation_id).toBeUndefined();
});

test("assistant route handoff opens real server-generated segments on map", async ({
  page,
  request,
}) => {
  await login(page);
  const places = await (await request.get("/api/locations")).json();
  const target = places.find((p: { name: string }) => p.name === "D201");
  const actualRoute = await (
    await request.get(`/api/routes?start=1&destination=${target.id}`)
  ).json();
  expect(actualRoute.status).toBe("schematic_draft");
  await page.route("**/api/assistant/query", (route) =>
    route.fulfill({
      json: {
        answer: "This schematic route starts at Main Entrance.",
        location: target,
        route: actualRoute,
        choices: [],
        needs_clarification: false,
        engine: "openrouter",
        conversation_id: "route-conversation",
      },
    }),
  );
  await page.getByRole("link", { name: "Assistant", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Ask the campus assistant" })
    .fill("Route from entrance to D201");
  await page.getByRole("button", { name: "Send question" }).click();
  await page.getByRole("button", { name: "Open route on map" }).click();
  await expect(
    page.getByRole("region", { name: "Route directions" }),
  ).toContainText("floor 1 to floor 2");
  await expect(
    page.locator('svg[aria-label="Schematic floor 1"] line'),
  ).not.toHaveCount(0);
});
