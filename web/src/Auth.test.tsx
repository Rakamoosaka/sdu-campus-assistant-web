import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, test, expect } from "vitest";
import { Auth } from "./Auth";
import { StateBox } from "./MapWorkspace";
vi.mock("./lib/api", async (original) => ({
  ...(await original<typeof import("./lib/api")>()),
  api: { post: vi.fn() },
}));
import { api } from "./lib/api";
test("credentials start empty and invalid ID/password produce actionable errors", async () => {
  render(<Auth onSuccess={vi.fn()} />);
  expect(screen.getByLabelText("SDU ID")).toHaveValue("");
  expect(screen.getByPlaceholderText("At least 8 characters")).toHaveValue("");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByText("Enter your 9-digit SDU ID.")).toBeVisible();
  expect(screen.getByText("Use at least 8 characters.")).toBeVisible();
  expect(api.post).not.toHaveBeenCalled();
});
test("password visibility is controllable and registration checks confirmation before sending", async () => {
  render(<Auth onSuccess={vi.fn()} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Create an account" }),
  );
  await userEvent.type(screen.getByLabelText("Full name"), "Test Student");
  await userEvent.type(screen.getByLabelText("SDU ID"), "299999999");
  await userEvent.type(
    screen.getByPlaceholderText("At least 8 characters"),
    "Campus123!",
  );
  await userEvent.type(screen.getByLabelText("Confirm password"), "Different!");
  await userEvent.click(screen.getByRole("button", { name: "Show password" }));
  expect(screen.getByPlaceholderText("At least 8 characters")).toHaveAttribute(
    "type",
    "text",
  );
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));
  expect(await screen.findByText("Passwords do not match.")).toBeVisible();
  expect(api.post).not.toHaveBeenCalled();
});
test("failed sign-in displays the backend message without claiming success", async () => {
  const success = vi.fn();
  vi.mocked(api.post).mockRejectedValueOnce(
    new Error("Connection unavailable"),
  );
  render(<Auth onSuccess={success} />);
  await userEvent.type(screen.getByLabelText("SDU ID"), "240103049");
  await userEvent.type(
    screen.getByPlaceholderText("At least 8 characters"),
    "Campus123!",
  );
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Connection unavailable",
  );
  expect(success).not.toHaveBeenCalled();
});
test("error state has a working retry action", async () => {
  const retry = vi.fn();
  render(<StateBox error={new Error("Server unavailable")} retry={retry} />);
  expect(screen.getByRole("alert")).toHaveTextContent("Server unavailable");
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(retry).toHaveBeenCalledOnce();
});
