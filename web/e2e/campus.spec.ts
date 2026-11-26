import { test, expect, type Page } from "@playwright/test";
import { features } from "../src/features";
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
  await page.getByRole("button", { name: "Your account", exact: true }).click();
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
  const bar = page.getByRole("navigation", { name: "Route floors" });
  await expect(bar.getByRole("listitem")).toHaveCount(2);
  await bar.getByRole("button", { name: /^2 Floor 2/ }).click();
  await expect(
    page.locator('svg[aria-label="Schematic floor 2"] line'),
  ).not.toHaveCount(0);
});
test("route bar shows every floor and steps between them", async ({ page }) => {
  await login(page, "240103050");
  await search(page, "D201");
  await page.getByRole("button", { name: "Find route", exact: true }).click();
  const bar = page.getByRole("navigation", { name: "Route floors" });
  await expect(bar.getByRole("listitem")).toHaveCount(2);
  await expect(bar.locator('[aria-current="step"]')).toContainText(
    "Floor 1",
  );
  const floors = page.locator(".floor-switch button");
  await expect(floors.filter({ hasText: "Floor 2" })).toHaveAttribute(
    "data-route",
    "on",
  );
  await expect(floors.filter({ hasText: "Floor 3" })).toHaveAttribute(
    "data-route",
    "off",
  );
  await bar.getByRole("button", { name: "Next: floor 2" }).click();
  await expect(floors.filter({ hasText: "Floor 2" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page
    .getByRole("button", { name: "Arrive from floor 1. Show floor 1" })
    .click();
  await expect(floors.filter({ hasText: "Floor 1" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(
    page.getByRole("button", { name: /to floor 2\. Show floor 2/ }),
  ).toBeVisible();
});
test("saved accessibility preference changes cross-floor routing to a lift", async ({
  page,
}) => {
  await login(page, "240103051");
  await page.getByRole("button", { name: "Your account", exact: true }).click();
  const menu = page.getByRole("dialog", { name: "Your account" });
  await menu.getByRole("switch", { name: /Avoid stairs/ }).check();
  await expect(menu.getByRole("switch")).toBeEnabled();
  await page.reload();
  await page.getByRole("button", { name: "Your account", exact: true }).click();
  await expect(menu.getByRole("switch")).toBeChecked();
  await page.keyboard.press("Escape");
  await expect(menu).toHaveCount(0);
  await search(page, "D201");
  await page.getByRole("button", { name: "Find route", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Route directions" }),
  ).toContainText("lift from floor 1 to floor 2");
  await expect(
    page.getByRole("region", { name: "Route directions" }),
  ).toContainText("stairs excluded");
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
  await expect(page.getByLabel("X")).toHaveCount(0);
  await page.getByRole("button", { name: "Save details" }).click();
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
  // The panel closes on a phone so the route and its floors are in view.
  await expect(
    page.getByRole("navigation", { name: "Route floors" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Next: floor 2" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Fit map", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Place details" }).click();
  await expect(
    page.getByRole("region", { name: "Route directions" }),
  ).toContainText("Your route");
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
  test.skip(!features.timetable, "Timetable is switched off in features.ts");
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

test("all newly connected services draw routes in both directions", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Continue as guest" }).click();
  const response = await page.request.get("/api/campus-map");
  const map = await response.json();
  const names = [
    "Canteen",
    "Food / drinks point",
    "Red Canteen",
    "Mini Red Hall",
    "Table Tennis Zone",
    "Print & Stationery",
    "Entrance near Block G",
  ];
  for (const name of names) {
    await search(page, name);
    await page.getByRole("combobox", { name: "Route start" }).selectOption("1");
    await page.getByRole("button", { name: "Find route", exact: true }).click();
    await expect(
      page.getByRole("region", { name: "Route directions" }),
    ).toContainText("Your route");
    await expect(page.locator(".route-line")).not.toHaveCount(0);
    const target = map.places.find((p: { name: string }) => p.name === name);
    await search(page, map.places.find((p: { id: number }) => p.id === 1).name);
    await page
      .getByRole("combobox", { name: "Route start" })
      .selectOption(String(target.id));
    await page.getByRole("button", { name: "Find route", exact: true }).click();
    await expect(
      page.getByRole("region", { name: "Route directions" }),
    ).toContainText(`Start at ${name}`);
  }
});

test("unmapped places cannot start a route and changing destination clears it", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Continue as guest" }).click();
  await search(page, "D201");
  await page.getByRole("button", { name: "Find route", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Route directions" }),
  ).toBeVisible();
  await search(page, "Technopark");
  await expect(
    page.getByRole("region", { name: "Route directions" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Find route", exact: true }),
  ).toBeDisabled();
  await expect(
    page
      .getByRole("combobox", { name: "Route start" })
      .locator("option")
      .filter({ hasText: "Technopark" }),
  ).toHaveCount(0);
});

test("a shared room opens for a new mobile visitor and an invalid link offers search", async ({
  page,
  browser,
  context,
  baseURL,
}) => {
  await login(page);
  await search(page, "D201");
  await page.getByRole("button", { name: "Share destination" }).click();
  const url = await page.getByLabel("Destination link").inputValue();
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.getByRole("button", { name: "Copy link" }).click();
  await expect(page.getByRole("status")).toHaveText("Link copied");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(url);

  const visitor = await browser.newPage({
    viewport: { width: 390, height: 844 },
  });
  try {
    await visitor.goto(url);
    await expect(
      visitor.getByRole("button", { name: "Floor 2", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    await visitor.getByRole("button", { name: /D201.*View details/ }).click();
    await expect(visitor.locator(".location-details h3")).toHaveText("D201");

    await visitor.goto(new URL("/map?place=bad-id", baseURL).href);
    await expect(visitor.getByRole("alert")).toContainText(
      "This destination is unavailable",
    );
    await visitor
      .getByRole("button", { name: "Search campus", exact: true })
      .click();
    await expect(
      visitor.getByRole("textbox", { name: "Search campus" }),
    ).toBeFocused();
  } finally {
    await visitor.close();
  }
});

test("offline map survives a failed update and reopens a shared room without a network", async ({
  page,
  context,
  baseURL,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Continue as guest" }).click();
  await search(page, "D201");
  await page.getByRole("button", { name: "Share destination" }).click();
  const url = await page.getByLabel("Destination link").inputValue();
  await page.getByRole("button", { name: "Close", exact: true }).click();

  await page.getByRole("button", { name: "Offline map" }).click();
  const dialog = page.getByRole("dialog", { name: "Offline map" });
  await page.route("**/api/campus-map", () => {});
  const request = page.waitForRequest("**/api/campus-map");
  await dialog.getByRole("button", { name: "Download campus map" }).click();
  await request;
  await dialog.getByRole("button", { name: "Cancel download" }).click();
  await expect(
    dialog.getByRole("button", { name: "Download campus map" }),
  ).toBeEnabled();
  await expect(dialog.getByText("Ready offline", { exact: true })).toHaveCount(
    0,
  );
  await page.unroute("**/api/campus-map");
  await dialog.getByRole("button", { name: "Download campus map" }).click();
  await expect(dialog.getByRole("status")).toHaveText("Ready offline");
  await page.route("**/api/campus-map", (route) => route.abort());
  await dialog.getByRole("button", { name: "Update download" }).click();
  await expect(dialog.getByRole("alert")).toContainText("Cannot reach");
  await expect(
    dialog.getByText("Ready offline", { exact: true }),
  ).toBeVisible();
  await page.unroute("**/api/campus-map");

  await page.close();
  await context.setOffline(true);
  const offlinePage = await context.newPage();
  await offlinePage.goto(url);
  await expect(offlinePage.getByRole("status")).toContainText(
    "Offline · Using map saved",
  );
  await expect(offlinePage.locator(".location-details h3")).toHaveText("D201");
  await expect(
    offlinePage.getByRole("button", { name: "Floor 2", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    offlinePage.getByRole("button", { name: "Find route" }),
  ).toBeDisabled();
  await offlinePage
    .getByRole("link", { name: "Assistant", exact: true })
    .click();
  await expect(
    offlinePage
      .getByText("The assistant needs a connection.", { exact: true })
      .last(),
  ).toBeVisible();
  await context.setOffline(false);
  await expect(
    offlinePage.getByRole("button", { name: "Find route" }),
  ).toBeEnabled();
  await expect(offlinePage.locator(".location-details h3")).toHaveText("D201");
  await context.setOffline(true);
  await expect(
    offlinePage.getByRole("button", { name: "Find route" }),
  ).toBeDisabled();
  const searchBox = offlinePage.getByRole("textbox", { name: "Search campus" });
  for (const [query, expected] of [
    ["d 201", "D201"],
    ["printer", "Print & Stationery"],
    ["libary", "Library"],
  ]) {
    await searchBox.fill(query);
    await expect(
      offlinePage.locator(".location-list button").first(),
    ).toContainText(expected);
  }

  await offlinePage.goto(new URL("/map?place=999999999", baseURL).href);
  await expect(offlinePage.getByRole("alert")).toContainText(
    "isn’t in your saved map",
  );
  await offlinePage.getByRole("button", { name: "Offline map" }).click();
  const offlineDialog = offlinePage.getByRole("dialog", {
    name: "Offline map",
  });
  await offlineDialog.getByRole("button", { name: "Remove download" }).click();
  await offlineDialog.getByRole("button", { name: "Remove download" }).click();
  await expect(
    offlinePage.getByRole("heading", {
      name: "No offline map is saved on this device",
    }),
  ).toBeVisible();
  await offlinePage.reload();
  await expect(
    offlinePage.getByRole("heading", {
      name: "No offline map is saved on this device",
    }),
  ).toBeVisible();
});

async function logout(page: Page) {
  await page.getByRole("button", { name: "Your account", exact: true }).click();
  await page.getByRole("button", { name: "Log out", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Good to see you." }),
  ).toBeVisible();
}
test("guest saves a step-free preference and sees why no step-free route exists", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Continue as guest" }).click();
  await search(page, "D201");
  await page.getByRole("switch", { name: /Avoid stairs/ }).check();
  await page.getByRole("button", { name: "Find route", exact: true }).click();
  const directions = page.getByRole("region", { name: "Route directions" });
  await expect(directions).toContainText("lift from floor 1 to floor 2");
  await expect(directions).toContainText("Step-free access at D201 is not verified");
  await page.getByRole("button", { name: "Show step-free connections" }).click();
  await expect(page.locator(".map-legend")).toContainText("Step-free");
  await search(page, "Canteen — Floor 3");
  await page.getByRole("button", { name: "Find route", exact: true }).click();
  await expect(directions).toContainText("lift from floor 1 to floor 3");
  await search(page, "Main corridor staircase 8");
  await page.getByRole("button", { name: "Find route", exact: true }).click();
  await expect(directions).toContainText("A staircase cannot be a step-free endpoint");
  await page.getByRole("button", { name: "Your account", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "Your account" }).getByRole("switch"),
  ).toBeChecked();
});
test("blocked path report is tracked and resolved by an administrator", async ({
  page,
}) => {
  await login(page);
  await search(page, "D201");
  await page.getByRole("button", { name: "Find route", exact: true }).click();
  await page.getByRole("button", { name: "Report a problem" }).click();
  await expect(
    page.getByRole("radio", { name: /blocked/ }),
  ).toBeChecked();
  await page.getByLabel("Where exactly?").selectOption({ index: 3 });
  await page
    .getByLabel("What did you see?")
    .fill("Browser test: corridor closed for repairs");
  await page.getByRole("button", { name: "Submit report" }).click();
  await expect(page.getByRole("status").filter({ hasText: "received" })).toBeVisible();
  await page
    .getByRole("dialog")
    .getByRole("link", { name: "My reports" })
    .click();
  const mine = page
    .locator(".report-card")
    .filter({ hasText: "corridor closed for repairs" });
  await expect(mine).toContainText("Received");
  await logout(page);

  await login(page, "240000002");
  await page.getByRole("link", { name: "Administration", exact: true }).click();
  await page.getByRole("button", { name: "Reports", exact: true }).click();
  const row = page
    .locator(".admin-report")
    .filter({ hasText: "corridor closed for repairs" });
  await row.getByRole("button", { name: /Close this path/ }).click();
  await expect(page.getByText(/Path closed\. Routes now go around it/)).toBeVisible();
  await expect(row).toHaveCount(0);
  await expect(page.locator(".closed-path")).toHaveCount(1);
  await page.getByRole("button", { name: /^Resolved/ }).click();
  await expect(row).toBeVisible();
  await page.getByRole("button", { name: "Reopen now" }).click();
  await expect(page.locator(".closed-path")).toHaveCount(0);
  await logout(page);

  await login(page);
  await expect(
    page.getByRole("link", { name: /My reports/ }).locator(".nav-badge-new"),
  ).toHaveText("1");
  await page.getByRole("link", { name: /My reports/ }).click();
  await expect(mine).toContainText("Resolved");
  await expect(mine).toContainText("New update");
  await expect(mine).toContainText("This path is now closed, and routes go around it.");
  await expect(page.locator(".nav-badge-new")).toHaveCount(0);
});
test("administrator publishes, shows and deletes an announcement", async ({
  page,
}) => {
  test.skip(!features.announcements, "Announcements are switched off in features.ts");
  await login(page, "240000002");
  await page.getByRole("link", { name: "Administration", exact: true }).click();
  await page.getByRole("button", { name: "Announcements", exact: true }).click();
  await page.getByRole("button", { name: "New announcement" }).click();
  await page.getByLabel("Title").fill("Browser test: Library quiet floor");
  await page.getByLabel("Message").fill("Silent study only this week.");
  await page.getByLabel("Place it's about").selectOption({ label: "Library" });
  await page.getByRole("button", { name: "Publish announcement" }).click();
  const row = page
    .locator(".admin-list-row")
    .filter({ hasText: "Library quiet floor" });
  await expect(row).toContainText("Showing");
  await page.getByRole("link", { name: "Announcements", exact: true }).click();
  await expect(page.locator(".news-card").first()).toContainText(
    "Library quiet floor",
  );
  await page.getByRole("link", { name: "Campus map", exact: true }).click();
  await search(page, "Library");
  await expect(
    page.getByRole("region", { name: "Announcements for this place" }),
  ).toContainText("Silent study only this week.");
  await page.getByRole("link", { name: "Administration", exact: true }).click();
  await page.getByRole("button", { name: "Announcements", exact: true }).click();
  await row.getByRole("button", { name: "Delete", exact: true }).click();
  await row.getByRole("button", { name: "Delete permanently" }).click();
  await expect(row).toHaveCount(0);
  await page.goto("/updates");
  await expect(page).toHaveURL(/\/announcements$/);
  await expect(page.getByText("Library quiet floor")).toHaveCount(0);
});
test("guest reports a blocked corridor near a place without planning a route", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Continue as guest" }).click();
  await search(page, "Main Entrance");
  await page.getByRole("button", { name: "Report a problem" }).click();
  await page.getByText("A corridor, staircase or lift is blocked").click();
  const where = page.getByLabel("Where exactly?");
  await expect(where.locator("optgroup")).toHaveAttribute(
    "label",
    "Around Main Entrance",
  );
  await expect(page.locator('.path-preview line[stroke="#dc2626"]')).toHaveCount(0);
  await page.locator(".path-preview g").first().click();
  await expect(page.locator('.path-preview line[stroke="#dc2626"]')).toHaveCount(1);
  await expect(where).not.toHaveValue("");
  await where.selectOption({ label: "Floor 1 corridor between Main Entrance and Cloakroom" });
  await page.getByLabel("What did you see?").fill("Browser test: boxes block the corridor");
  await page.getByRole("button", { name: "Submit report" }).click();
  await expect(page.getByRole("status").filter({ hasText: "received" })).toBeVisible();
  await page
    .getByRole("dialog")
    .getByRole("link", { name: "My reports" })
    .click();
  await expect(
    page.locator(".report-card").filter({ hasText: "boxes block the corridor" }),
  ).toContainText("Floor 1 corridor between Main Entrance and Cloakroom");
});
test("old profile address opens My reports and the guest account menu offers sign-in", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Continue as guest" }).click();
  await page.goto("/profile");
  await expect(page).toHaveURL(/\/reports$/);
  await expect(
    page.getByRole("heading", { name: "Problems you reported." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Your account", exact: true }).click();
  const menu = page.getByRole("dialog", { name: "Your account" });
  await expect(menu).toContainText("Guest");
  await menu.getByRole("button", { name: "Log in or create an account" }).click();
  await expect(
    page.getByRole("heading", { name: "Good to see you." }),
  ).toBeVisible();
});
test("administrator fixes a reported location in one step; reporter can withdraw", async ({
  page,
}) => {
  await login(page, "240103050");
  await search(page, "Library");
  await page.getByRole("button", { name: "Report a problem" }).click();
  await page
    .getByLabel("What's wrong?")
    .fill("Browser test: open until 22:00 now");
  await page.getByRole("button", { name: "Submit report" }).click();
  await page.getByRole("button", { name: "Done" }).click();
  await page.getByRole("button", { name: "Report a problem" }).click();
  await page.getByLabel("What's wrong?").fill("Browser test: sent by mistake");
  await page.getByRole("button", { name: "Submit report" }).click();
  await page.getByRole("dialog").getByRole("link", { name: "My reports" }).click();
  const mistake = page
    .locator(".report-card")
    .filter({ hasText: "sent by mistake" });
  await mistake.getByRole("button", { name: "Withdraw", exact: true }).click();
  await mistake.getByRole("button", { name: "Withdraw report" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Report withdrawn" })).toBeVisible();
  // Withdrawn reports leave the default view and sit under their own filter.
  await expect(mistake).toHaveCount(0);
  await page
    .getByRole("group", { name: "Filter your reports" })
    .getByRole("button", { name: /^Withdrawn/ })
    .click();
  await expect(mistake).toContainText("Withdrawn");
  await logout(page);

  await login(page, "240000002");
  await page.getByRole("link", { name: "Administration", exact: true }).click();
  await page.getByRole("button", { name: "Reports", exact: true }).click();
  const row = page
    .locator(".admin-report")
    .filter({ hasText: "open until 22:00 now" });
  await row.getByRole("button", { name: /Fix the details/ }).click();
  await expect(page.getByRole("dialog")).toContainText("open until 22:00 now");
  await page.getByLabel("Opening hours").fill("Sample: 08:00–22:00");
  await page.getByRole("button", { name: "Save and resolve report" }).click();
  await expect(page.getByText(/Details saved\. The report is resolved/)).toBeVisible();
  await expect(row).toHaveCount(0);
  await page.getByRole("button", { name: /^Withdrawn/ }).click();
  await expect(
    page.locator(".admin-report").filter({ hasText: "sent by mistake" }),
  ).toContainText("The reporter withdrew this report.");
  await logout(page);

  await login(page, "240103050");
  await page.getByRole("link", { name: /My reports/ }).click();
  const fixed = page
    .locator(".report-card")
    .filter({ hasText: "open until 22:00 now" });
  await expect(fixed).toContainText("Resolved");
  await expect(fixed).toContainText("We updated the details for Library");
  await page.getByRole("link", { name: "Campus map", exact: true }).click();
  await search(page, "Library");
  await expect(page.locator(".detail-facts")).toContainText("Sample: 08:00–22:00");
});
test("switched-off sections are hidden everywhere", async ({ page }) => {
  test.skip(features.timetable || features.announcements, "Both sections are on");
  await login(page, "240000002");
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await expect(nav.getByRole("link", { name: "Timetable" })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Announcements" })).toHaveCount(0);
  for (const path of ["/schedule", "/announcements", "/updates"]) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/map$/);
  }
  await page.getByRole("link", { name: "Assistant", exact: true }).click();
  await expect(page.getByRole("button", { name: /next class/ })).toHaveCount(0);
  await page.getByRole("link", { name: "Administration", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Announcements", exact: true }),
  ).toHaveCount(0);
});
test("same-place reports get their own cards and are declined one by one", async ({
  page,
}) => {
  for (const who of ["240103051", "240103052"]) {
    await login(page, who);
    await search(page, "Medical Point");
    await page.getByRole("button", { name: "Report a problem" }).click();
    await page.getByLabel("What's wrong?").fill(`Browser test: moved upstairs (${who})`);
    await page.getByRole("button", { name: "Submit report" }).click();
    await expect(page.getByRole("status").filter({ hasText: "received" })).toBeVisible();
    await page.getByRole("button", { name: "Done" }).click();
    await logout(page);
  }
  await login(page, "240000002");
  await page.getByRole("link", { name: "Administration", exact: true }).click();
  await page.getByRole("button", { name: "Reports", exact: true }).click();
  const cards = page
    .locator(".admin-report")
    .filter({ hasText: "moved upstairs" });
  await expect(cards).toHaveCount(2);
  await expect(cards.first()).toContainText("also reported in #");
  for (const who of ["240103051", "240103052"]) {
    const card = cards.filter({ hasText: who }).first();
    await card.getByRole("button", { name: "Reply or decline…" }).click();
    await card
      .getByLabel("Message to the reporter")
      .fill("We checked: it is still on the first floor.");
    await card.getByRole("button", { name: "Decline with this message" }).click();
    await expect(page.getByText(/the reporter was told why/)).toBeVisible();
  }
  await expect(cards).toHaveCount(0);
  await logout(page);

  await login(page, "240103052");
  await page.getByRole("link", { name: /My reports/ }).click();
  const mine = page.locator(".report-card").filter({ hasText: "moved upstairs" });
  await expect(mine).toContainText("Not changed");
  await expect(mine).toContainText("still on the first floor");
});
