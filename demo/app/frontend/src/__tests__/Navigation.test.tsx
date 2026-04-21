import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Sidebar from "../components/Sidebar";

describe("Navigation", () => {
  it("contains all required navigation links", () => {
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>,
    );

    const expectedLinks = [
      "Talk Track",
      "Dashboard",
      "Compression",
      "Assets",
      "Architecture",
      "Asset Hierarchy",
      "Templates",
    ];

    for (const linkText of expectedLinks) {
      expect(screen.getByRole("link", { name: linkText })).toBeInTheDocument();
    }
  });
});
