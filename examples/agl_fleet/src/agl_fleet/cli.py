"""CLI entry point for the AGL Fleet Simulator.

Generates synthetic BESS, grid, market, and CMMS tag events and posts them
to an Ignition 8.3 Gateway's Zerobus HTTP ingest endpoint.

Usage:
    uv run agl-sim --gateway http://localhost:7088
    uv run agl-sim --gateway http://localhost:7088 --sites 7 --interval 500
    uv run agl-sim --dry-run --sites 3 --ticks 10
    uv run agl-sim --units 4   # override all sites to 4 units each

    # Configure Gateway from Databricks profile + start sim
    # Profile must have client_id/client_secret (OAuth M2M) in ~/.databrickscfg
    # Endpoint format: <workspace-id>.zerobus.<region>.azuredatabricks.net (Azure)
    #                  <workspace-id>.zerobus.<region>.cloud.databricks.com (AWS)
    uv run --extra setup agl-sim --setup --profile agl-demo \
        --zerobus-endpoint 7405607216190670.zerobus.eastus2.azuredatabricks.net

    # Configure only (no simulation)
    uv run --extra setup agl-sim --setup-only --profile agl-demo \
        --zerobus-endpoint 7405607216190670.zerobus.eastus2.azuredatabricks.net
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
import time

from .client import AsyncGatewayClient
from .generators import BessGenerator, CmmsGenerator, GridGenerator, MarketGenerator

# Site topology - (state, location, default_units) ordered by fleet significance.
# Unit counts approximate real AGL BESS fleet capacity (1 unit ~ 1 battery container).
SITE_TOPOLOGY: list[tuple[str, str, int]] = [
    ("SA", "TorrensIsland", 20),  # 250 MW flagship BESS
    ("NSW", "Liddell", 5),        # 50 MW
    ("NSW", "BrokenHill", 5),     # 50 MW
    ("SA", "Dalrymple", 3),       # 30 MW
    ("QLD", "Wandoan", 8),        # 100 MW
    ("NSW", "Tomago", 4),         # 40 MW
    ("QLD", "Callide", 6),        # grid + storage
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AGL Fleet Simulator - direct synthetic data for Ignition Gateway")
    parser.add_argument(
        "--gateway",
        default=os.environ.get("IGNITION_GATEWAY_URL", "http://localhost:7088"),
        help="Ignition Gateway URL (default: http://localhost:7088)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("ZEROBUS_API_KEY"),
        help="Optional API key for Zerobus ingest endpoint",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.environ.get("SIM_INTERVAL_MS", "1000")),
        help="Tick interval in milliseconds (default: 1000)",
    )
    parser.add_argument(
        "--ticks",
        type=int,
        default=int(os.environ.get("SIM_TICKS", "0")),
        help="Number of ticks to run (0 = infinite, default: 0)",
    )
    parser.add_argument(
        "--market-interval",
        type=int,
        default=2000,
        help="Market generator tick interval in ms (default: 2000)",
    )
    parser.add_argument(
        "--cmms-interval",
        type=int,
        default=10000,
        help="CMMS generator tick interval in ms (default: 10000)",
    )
    parser.add_argument(
        "--sites",
        type=int,
        default=int(os.environ.get("SIM_SITES", str(len(SITE_TOPOLOGY)))),
        metavar="N",
        help=f"Number of sites (1-{len(SITE_TOPOLOGY)}, default: all {len(SITE_TOPOLOGY)})",
    )
    parser.add_argument(
        "--units",
        type=int,
        default=int(os.environ.get("SIM_UNITS", "0")),
        metavar="N",
        help="BESS units per site override (0 = use realistic per-site defaults, default: 0)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Generate events but don't send them")
    parser.add_argument(
        "--fault-every-ticks",
        type=int,
        default=int(os.environ.get("SIM_FAULT_EVERY_TICKS", "1500")),
        metavar="N",
        help="Inject thermal spike every N BESS ticks so pipeline flags 'at risk' (default: 1500; 0 = off)",
    )
    parser.add_argument(
        "--fault-duration-ticks",
        type=int,
        default=int(os.environ.get("SIM_FAULT_DURATION_TICKS", "300")),
        metavar="N",
        help="Duration of each thermal fault in ticks (default: 300 = 5 min at 1s/tick)",
    )

    # Gateway setup flags (requires `--extra setup` for databricks-sdk)
    setup_group = parser.add_argument_group("gateway setup", "Configure Gateway Zerobus from a Databricks CLI profile")
    setup_group.add_argument(
        "--setup",
        action="store_true",
        help="Configure Gateway Zerobus connection from Databricks CLI profile before running",
    )
    setup_group.add_argument(
        "--setup-only",
        action="store_true",
        help="Configure Gateway Zerobus connection and exit (no simulation)",
    )
    setup_group.add_argument(
        "--profile",
        default=os.environ.get("DATABRICKS_CONFIG_PROFILE", "DEFAULT"),
        help="Databricks CLI profile name (default: DEFAULT)",
    )

    def _zerobus_endpoint_default() -> str | None:
        e = os.environ.get("ZEROBUS_ENDPOINT")
        if e:
            return e
        wid, reg = os.environ.get("WORKSPACE_ID"), os.environ.get("DATABRICKS_REGION")
        if wid and reg:
            return f"{wid}.zerobus.{reg}.azuredatabricks.net"
        return None

    setup_group.add_argument(
        "--zerobus-endpoint",
        default=_zerobus_endpoint_default(),
        help="Zerobus gRPC endpoint (or set ZEROBUS_ENDPOINT / WORKSPACE_ID+DATABRICKS_REGION in env)",
    )
    setup_group.add_argument(
        "--target-table",
        default=os.environ.get(
            "ZEROBUS_TARGET_TABLE",
            f"{os.environ.get('CATALOG', 'agl_demo')}.{os.environ.get('SCHEMA', 'ot')}.raw_tags",
        ),
        help="Target Delta table (default: ${CATALOG}.${SCHEMA}.raw_tags or agl_demo.ot.raw_tags)",
    )

    return parser.parse_args()


def build_generators(
    sites: int,
    units_override: int = 0,
    fault_every_ticks: int = 1500,
    fault_duration_ticks: int = 300,
) -> tuple[list[BessGenerator], list[GridGenerator], list[MarketGenerator], list[CmmsGenerator]]:
    """Create generator instances for every site+unit combination.

    Args:
        sites: Number of sites to simulate (capped at len(SITE_TOPOLOGY)).
        units_override: If > 0, override all sites to this many units.
            If 0, use per-site defaults from SITE_TOPOLOGY.
    """
    bess_gens: list[BessGenerator] = []
    grid_gens: list[GridGenerator] = []
    market_gens: list[MarketGenerator] = []
    cmms_gens: list[CmmsGenerator] = []

    inject_fault = fault_every_ticks if fault_every_ticks > 0 else None
    for site_idx in range(min(sites, len(SITE_TOPOLOGY))):
        state, location, default_units = SITE_TOPOLOGY[site_idx]
        site_units = units_override if units_override > 0 else default_units
        grid_gens.append(GridGenerator(state=state, location=location))
        market_gens.append(MarketGenerator(state=state, location=location))
        cmms_gens.append(CmmsGenerator(state=state, location=location))
        for unit_id in range(1, site_units + 1):
            bess_gens.append(
                BessGenerator(
                    state=state,
                    location=location,
                    unit_id=unit_id,
                    inject_fault_every_ticks=inject_fault,
                    fault_duration_ticks=fault_duration_ticks,
                )
            )

    return bess_gens, grid_gens, market_gens, cmms_gens


async def run(args: argparse.Namespace) -> int:
    num_sites = min(args.sites, len(SITE_TOPOLOGY))
    sites = SITE_TOPOLOGY[:num_sites]

    # Calculate per-site and total unit counts
    site_units = []
    for _st, _loc, default_units in sites:
        site_units.append(args.units if args.units > 0 else default_units)
    total_bess = sum(site_units)
    total_assets = total_bess + num_sites * 3
    events_per_tick = total_bess * 23 + num_sites * 16

    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  AGL Fleet Simulator - Lakeflow Ignition Connector")
    print("  Generating synthetic BESS, grid, market, and CMMS tag events")
    print("  Events stream via Ignition gateway into Databricks Delta Lake")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    print(f"  Gateway:        {args.gateway}")
    print(f"  Sites:          {num_sites}")
    for i, (st, loc, _) in enumerate(sites):
        print(f"    {loc} ({st}): {site_units[i]} BESS units")
    print(f"  Total BESS:     {total_bess} units")
    print(f"  Total assets:   {total_assets}")
    print(f"  Interval:       {args.interval}ms")
    print(f"  Market interval:{args.market_interval}ms")
    print(f"  CMMS interval:  {args.cmms_interval}ms")
    print(f"  Events/tick:    ~{events_per_tick} (BESS+Grid, excl. market/cmms)")
    print(f"  Est. events/s:  ~{round(events_per_tick * 1000 / args.interval)}")
    print(f"  Max ticks:      {'infinite' if args.ticks == 0 else args.ticks}")
    print(f"  Dry run:        {args.dry_run}")
    print(
        f"  Fault inject:   every {args.fault_every_ticks} ticks, sustained for {args.fault_duration_ticks} ticks"
        if args.fault_every_ticks > 0
        else "  Fault inject:   off"
    )
    print()

    bess_gens, grid_gens, market_gens, cmms_gens = build_generators(
        num_sites,
        units_override=args.units,
        fault_every_ticks=args.fault_every_ticks,
        fault_duration_ticks=args.fault_duration_ticks,
    )

    # Initialize client
    client = None
    if not args.dry_run:
        client = AsyncGatewayClient(args.gateway, api_key=args.api_key)

        # Health check
        try:
            health = await client.health_check()
            print(f"  Gateway status: {health.get('status', 'unknown')}")
            if not health.get("enabled", False):
                print("  WARNING: Zerobus module is not enabled - events may be dropped")
        except Exception as e:
            print(f"  WARNING: Health check failed: {e}")

        # Auto-configure Gateway for expected throughput (only raises limits, never lowers)
        target_eps = round(events_per_tick * 1000 / args.interval * 1.5)  # 50% headroom
        target_queue = max(10_000, target_eps * 5)
        try:
            result = await client.configure(target_eps, target_queue)
            if result is None:
                print(f"  Gateway config: already sufficient (>={target_eps} eps, >={target_queue} queue)")
            else:
                print(f"  Gateway config: raised to maxEventsPerSecond={target_eps}, maxQueueSize={target_queue}")
        except Exception as e:
            print(f"  WARNING: Could not auto-configure Gateway: {e}")

        print()

    # Graceful shutdown
    running = True
    loop = asyncio.get_running_loop()

    def handle_signal():
        nonlocal running
        print("\n[sim] Shutting down...")
        running = False

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    # Stats
    total_sent = 0
    total_accepted = 0
    total_dropped = 0
    tick_count = 0
    unique_tags: set[str] = set()
    stats_interval_ms = 10_000
    last_stats_time = time.time() * 1000
    last_market_tick = 0.0
    last_cmms_tick = 0.0

    print("[sim] Starting simulation... (Ctrl+C to stop)")
    print()

    while running:
        tick_start = time.time() * 1000

        if args.ticks > 0 and tick_count >= args.ticks:
            break

        try:
            # Always tick all BESS and Grid generators
            events = []
            for gen in bess_gens:
                events.extend(gen.tick())
            for gen in grid_gens:
                events.extend(gen.tick())

            # Market ticks at slower rate
            if tick_start - last_market_tick >= args.market_interval:
                for gen in market_gens:
                    events.extend(gen.tick())
                last_market_tick = tick_start

            # CMMS ticks at slowest rate
            if tick_start - last_cmms_tick >= args.cmms_interval:
                for gen in cmms_gens:
                    events.extend(gen.tick())
                last_cmms_tick = tick_start

            tick_count += 1
            total_sent += len(events)

            # Track unique tag paths
            if tick_count <= 3:
                for e in events:
                    unique_tags.add(e.tag_path)

            if args.dry_run:
                total_accepted += len(events)
                if tick_count <= 3 or tick_count % 10 == 0:
                    print(f"[tick {tick_count}] Generated {len(events)} events (dry run)")
                    if tick_count == 1:
                        for e in events[:5]:
                            print(f"  {e.tag_path} = {e.value} ({e.data_type})")
                        if len(events) > 5:
                            print(f"  ... and {len(events) - 5} more")
            else:
                result = await client.send_batch(events)
                accepted = result.get("accepted", 0)
                dropped = result.get("dropped", 0)
                total_accepted += accepted
                total_dropped += dropped

                if tick_count <= 3 or tick_count % 10 == 0:
                    print(f"[tick {tick_count}] sent={len(events)} accepted={accepted} dropped={dropped}")

        except Exception as e:
            print(f"[sim] Error: {e}")

        # Periodic stats
        now = time.time() * 1000
        if now - last_stats_time >= stats_interval_ms:
            elapsed_s = (now - last_stats_time) / 1000
            events_per_s = (
                round(total_sent / ((now - (last_stats_time - stats_interval_ms)) / 1000)) if elapsed_s > 0 else 0
            )
            print(
                f"[stats] ticks={tick_count} events/s~{round(len(events) * 1000 / args.interval)} "
                f"total_sent={total_sent} accepted={total_accepted} dropped={total_dropped} "
                f"unique_tags={len(unique_tags)}"
            )
            last_stats_time = now

        # Sleep for remainder of interval
        elapsed = time.time() * 1000 - tick_start
        sleep_ms = max(0, args.interval - elapsed)
        if sleep_ms > 0 and running:
            await asyncio.sleep(sleep_ms / 1000)

    # Summary
    print()
    print("=== Summary ===")
    print(f"  Sites:      {num_sites}")
    print(f"  BESS units: {total_bess}")
    print(f"  Ticks:      {tick_count}")
    print(f"  Sent:       {total_sent}")
    print(f"  Accepted:   {total_accepted}")
    print(f"  Dropped:    {total_dropped}")
    print(f"  Unique tags:{len(unique_tags)}")

    if client:
        await client.close()

    print("[sim] Done.")
    return 0 if total_dropped == 0 else 1


def _run_setup(args: argparse.Namespace) -> None:
    """Configure Gateway Zerobus connection from a Databricks CLI profile."""
    # Lazy import - only available with `--extra setup`
    try:
        from databricks.sdk.core import Config
    except ImportError:
        print("ERROR: databricks-sdk is required for --setup/--setup-only.")
        print("  Install with: uv run --extra setup agl-sim --setup ...")
        sys.exit(1)

    if not args.zerobus_endpoint:
        print("ERROR: --zerobus-endpoint (or ZEROBUS_ENDPOINT env var) is required for --setup.")
        sys.exit(1)

    # Load Databricks CLI profile
    profile = args.profile
    print(f"[setup] Loading Databricks CLI profile: {profile}")
    try:
        cfg = Config(profile=profile)
    except Exception as e:
        print(f"ERROR: Failed to load Databricks profile '{profile}': {e}")
        sys.exit(1)

    host = cfg.host
    client_id = cfg.client_id
    client_secret = cfg.client_secret

    if not client_id or not client_secret:
        print(f"ERROR: Profile '{profile}' does not contain OAuth M2M credentials (client_id/client_secret).")
        print("  Ensure your ~/.databrickscfg profile has client_id and client_secret set.")
        sys.exit(1)

    print(f"[setup] Workspace:        {host}")
    print(f"[setup] Zerobus endpoint: {args.zerobus_endpoint}")
    print(f"[setup] OAuth client ID:  {client_id}")
    print(f"[setup] Target table:     {args.target_table}")
    print(f"[setup] Gateway:          {args.gateway}")

    from .client import OPTIMIZED_DEFAULTS, setup_gateway

    print("[setup] Optimized defaults:")
    for k, v in OPTIMIZED_DEFAULTS.items():
        print(f"[setup]   {k}: {v}")

    try:
        result = setup_gateway(
            gateway_url=args.gateway,
            workspace_url=host,
            zerobus_endpoint=args.zerobus_endpoint,
            oauth_client_id=client_id,
            oauth_client_secret=client_secret,
            target_table=args.target_table,
        )
        print(f"[setup] Gateway configured successfully: {result}")
    except Exception as e:
        print(f"ERROR: Failed to configure Gateway: {e}")
        sys.exit(1)


def main():
    args = parse_args()

    if args.setup or args.setup_only:
        _run_setup(args)
        if args.setup_only:
            return 0

    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
