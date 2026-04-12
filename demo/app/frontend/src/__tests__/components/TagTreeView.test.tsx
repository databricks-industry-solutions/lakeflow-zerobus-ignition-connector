import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import TagTreeView from "../../components/TagTreeView";
import type { AssetTagCatalogRow } from "../../services/api";

const TAGS: AssetTagCatalogRow[] = [
  {
    asset_id: "windpark_north_bess01",
    tag_name: "telemetry/soc_pct",
    tag_path:
      "[bess]Demo/Region-A/Windpark-North/Site01/BESS01/Telemetry/SoC_pct",
    unit: "%",
    source_domain: "bess",
    is_mapped: true,
    live_value: 73.1,
    live_value_str: null,
    quality: 192,
    live_at: "2026-02-29T10:00:00Z",
    sdt_compressed: true,
    compression_ratio: 2.2,
  },
  {
    asset_id: "windpark_north_bess01",
    tag_name: "thermal/maxracktemp_c",
    tag_path: null,
    unit: "C",
    source_domain: null,
    is_mapped: false,
    live_value: 34.2,
    live_value_str: null,
    quality: 192,
    live_at: "2026-02-29T10:00:00Z",
    sdt_compressed: true,
    compression_ratio: 1.8,
  },
];

describe("TagTreeView", () => {
  it("renders grouped tag paths and emits selected full tag name", () => {
    const onSelectTagName = vi.fn();
    render(
      <TagTreeView
        tags={TAGS}
        selectedTagName={null}
        onSelectTagName={onSelectTagName}
      />,
    );

    expect(screen.getByText("telemetry")).toBeInTheDocument();
    expect(screen.getByText("thermal")).toBeInTheDocument();
    expect(screen.getByText("soc_pct")).toBeInTheDocument();
    expect(screen.getByText("maxracktemp_c")).toBeInTheDocument();

    fireEvent.click(screen.getByText("soc_pct"));
    expect(onSelectTagName).toHaveBeenCalledWith("telemetry/soc_pct");
  });
});
