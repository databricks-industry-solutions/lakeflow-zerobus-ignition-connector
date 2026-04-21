import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AssetHierarchy from "../../pages/AssetHierarchy";

vi.mock("../../services/api", () => ({
  api: {
    assetFramework: {
      getHierarchy: vi.fn().mockResolvedValue({
        data: [
          {
            asset_id: "windpark_north_bess01",
            parent_asset_id: null,
            asset_name: "Windpark North BESS01",
            asset_type: "battery_bess",
            template_id: "tpl_bess",
            site_name: "Windpark North",
            description: "BESS Unit 01",
            tag_count: 23,
            depth: 0,
            child_count: 0,
          },
        ],
      }),
      getTemplates: vi.fn().mockResolvedValue({ data: [] }),
      getTagSummary: vi.fn().mockResolvedValue({
        data: [
          {
            asset_id: "windpark_north_bess01",
            mapped_tag_count: 20,
            live_tag_count: 24,
            mapped_live_tag_count: 20,
            unmapped_tag_count: 4,
          },
        ],
      }),
      getAsset: vi.fn().mockResolvedValue({
        data: {
          asset_id: "windpark_north_bess01",
          parent_asset_id: null,
          asset_name: "Windpark North BESS01",
          asset_type: "battery_bess",
          template_id: "tpl_bess",
          site_name: "Windpark North",
          description: "BESS Unit 01",
          tag_count: 23,
          depth: 0,
          child_count: 0,
          template_name: "BESS",
        },
      }),
      getAssetTags: vi.fn().mockResolvedValue({
        data: [
          {
            asset_id: "windpark_north_bess01",
            tag_name: "telemetry/soc_pct",
            tag_path:
              "[bess]Demo/Region-A/Windpark-North/Site01/BESS01/Telemetry/SoC_pct",
            unit: "%",
            source_domain: "bess",
            is_mapped: true,
            live_value: 72.5,
            live_value_str: null,
            quality: 192,
            live_at: "2026-02-29T10:00:00Z",
            sdt_compressed: true,
            compression_ratio: 2.1,
          },
        ],
      }),
      getAssetAttributes: vi.fn().mockResolvedValue({ data: [] }),
      getLiveAttributes: vi.fn().mockResolvedValue({ data: [] }),
    },
  },
}));

describe("AssetHierarchy page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders tag explorer and inspector when selecting an asset", async () => {
    render(
      <MemoryRouter>
        <AssetHierarchy />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Windpark North BESS01")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Windpark North BESS01"));

    await waitFor(() => {
      expect(screen.getByText("Tag explorer")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText("soc_pct")).toBeInTheDocument();
      expect(screen.getAllByText("Tag inspector").length).toBeGreaterThan(0);
    });
  });
});
