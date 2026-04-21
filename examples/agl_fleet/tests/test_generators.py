"""Tests for AGL fleet synthetic data generators."""

from agl_fleet.generators import BessGenerator, CmmsGenerator, GridGenerator, MarketGenerator, TagEvent


# --- Backward-compatible defaults (NSW/Tomago, unit 1) ---


def test_bess_generator_produces_events():
    gen = BessGenerator()
    events = gen.tick()
    assert len(events) == 23  # 13 telemetry + 3 limits + 5 thermal + 2 alarms (count + critical + last)
    assert all(isinstance(e, TagEvent) for e in events)


def test_bess_tag_paths_use_correct_provider():
    gen = BessGenerator(provider="agl_bess")
    events = gen.tick()
    for e in events:
        assert e.tag_path.startswith("[agl_bess]AGL/Australia/NSW/Tomago/Site01/BESS01/")


def test_bess_soc_stays_in_bounds():
    gen = BessGenerator()
    for _ in range(100):
        gen.tick()
    assert 5.0 <= gen.soc <= 98.0


def test_grid_generator_produces_events():
    gen = GridGenerator()
    events = gen.tick()
    assert len(events) == 16
    assert all(isinstance(e, TagEvent) for e in events)


def test_grid_tag_paths_use_correct_provider():
    gen = GridGenerator(provider="agl_grid")
    events = gen.tick()
    for e in events:
        assert e.tag_path.startswith("[agl_grid]AGL/Australia/NSW/Tomago/Site01/")


def test_market_generator_produces_events():
    gen = MarketGenerator()
    events = gen.tick()
    assert len(events) == 4
    assert all(isinstance(e, TagEvent) for e in events)


def test_market_rrp_is_numeric():
    gen = MarketGenerator()
    events = gen.tick()
    rrp_event = next(e for e in events if "RRP_AUD_per_MWh" in e.tag_path)
    assert isinstance(rrp_event.value, float)


def test_cmms_generator_produces_events():
    gen = CmmsGenerator()
    events = gen.tick()
    assert len(events) == 5
    assert all(isinstance(e, TagEvent) for e in events)


def test_cmms_work_orders_stay_non_negative():
    gen = CmmsGenerator()
    for _ in range(200):
        gen.tick()
    assert gen.open_work_orders >= 0
    assert gen.high_priority_wo >= 0


def test_all_generators_combined_event_count():
    """First tick should produce BESS(23) + Grid(16) + Market(4) + CMMS(5) = 48 events."""
    bess = BessGenerator()
    grid = GridGenerator()
    market = MarketGenerator()
    cmms = CmmsGenerator()
    events = bess.tick() + grid.tick() + market.tick() + cmms.tick()
    assert len(events) == 48


def test_tag_event_payload_format():
    """Verify TagEvent fields match the Gateway's expected TagEventPayload format."""
    gen = BessGenerator()
    events = gen.tick()
    e = events[0]
    assert hasattr(e, "tag_path")
    assert hasattr(e, "value")
    assert hasattr(e, "quality_code")
    assert hasattr(e, "data_type")
    assert hasattr(e, "timestamp_ms")
    assert e.quality_code == 192
    assert isinstance(e.timestamp_ms, int)


# --- Parameterized generators (custom state/location/unit) ---


def test_bess_custom_state_location():
    gen = BessGenerator(state="QLD", location="Callide")
    events = gen.tick()
    for e in events:
        assert "[agl_bess]AGL/Australia/QLD/Callide/Site01/BESS01/" in e.tag_path


def test_bess_custom_unit_id():
    gen = BessGenerator(unit_id=5)
    events = gen.tick()
    for e in events:
        assert "/BESS05/" in e.tag_path


def test_grid_custom_state_location():
    gen = GridGenerator(state="QLD", location="Gladstone")
    events = gen.tick()
    for e in events:
        assert "[agl_grid]AGL/Australia/QLD/Gladstone/Site01/" in e.tag_path


def test_market_custom_state_location():
    gen = MarketGenerator(state="NSW", location="BrokenHill")
    events = gen.tick()
    for e in events:
        assert "[agl_market]AGL/Australia/NSW/BrokenHill/Site01/" in e.tag_path


def test_cmms_custom_state_location():
    gen = CmmsGenerator(state="NSW", location="Liddell")
    events = gen.tick()
    for e in events:
        assert "[agl_cmms]AGL/Australia/NSW/Liddell/Site01/" in e.tag_path


# --- Multi-unit tag path uniqueness ---


def test_multi_unit_bess_paths_are_unique():
    """Multiple BESS units at the same site must produce unique tag paths."""
    gens = [BessGenerator(state="NSW", location="Tomago", unit_id=i) for i in range(1, 5)]
    all_paths = []
    for gen in gens:
        events = gen.tick()
        all_paths.extend(e.tag_path for e in events)
    assert len(all_paths) == len(set(all_paths)), "Duplicate tag paths found across BESS units"


def test_multi_site_paths_are_unique():
    """Generators at different sites must produce unique tag paths."""
    sites = [("NSW", "Tomago"), ("QLD", "Callide"), ("NSW", "BrokenHill")]
    all_paths = []
    for state, location in sites:
        bess = BessGenerator(state=state, location=location)
        grid = GridGenerator(state=state, location=location)
        events = bess.tick() + grid.tick()
        all_paths.extend(e.tag_path for e in events)
    assert len(all_paths) == len(set(all_paths)), "Duplicate tag paths found across sites"


def test_multi_site_multi_unit_event_count():
    """3 sites x 2 units should produce (3*2*23 + 3*16 + 3*4 + 3*5) = 213 events."""
    from agl_fleet.cli import build_generators

    bess_gens, grid_gens, market_gens, cmms_gens = build_generators(sites=3, units=2)
    events = []
    for gen in bess_gens:
        events.extend(gen.tick())
    for gen in grid_gens:
        events.extend(gen.tick())
    for gen in market_gens:
        events.extend(gen.tick())
    for gen in cmms_gens:
        events.extend(gen.tick())
    # 6 BESS * 23 + 3 Grid * 16 + 3 Market * 4 + 3 CMMS * 5 = 138 + 48 + 12 + 15 = 213
    assert len(events) == 213


def test_build_generators_counts():
    """build_generators should create the right number of generator instances."""
    from agl_fleet.cli import build_generators

    bess, grid, market, cmms = build_generators(sites=5, units=4)
    assert len(bess) == 20  # 5 sites * 4 units
    assert len(grid) == 5
    assert len(market) == 5
    assert len(cmms) == 5


# --- Sustained fault injection ---


def test_fault_injection_sustains_elevated_rack_temp():
    """Fault injection should hold rack_temp elevated for fault_duration_ticks."""
    gen = BessGenerator(inject_fault_every_ticks=10, fault_duration_ticks=5)
    # Advance to tick 10 (triggers fault)
    for _ in range(10):
        gen.tick()
    # Fault should now be active for 5 ticks (ticks 11-15 internally, but
    # the trigger tick itself starts the countdown)
    # After tick 10, _fault_remaining was set to 5 and decremented to 4
    assert gen._fault_remaining == 4
    assert gen.rack_temp > 40.0  # Should be ~42 +/- 0.5

    # Next 4 ticks should still be elevated
    for i in range(4):
        gen.tick()
        assert gen.rack_temp > 40.0, f"rack_temp dropped too early at fault tick {i + 2}"

    # After 5 fault ticks total, fault should be over
    assert gen._fault_remaining == 0

    # Next tick should use normal drift (not elevated)
    gen.tick()
    # Can't assert exact temp since it drifts, but _fault_remaining should stay 0
    assert gen._fault_remaining == 0


def test_rack_temp_returns_to_normal_after_fault():
    """After fault window expires, rack_temp should drift back toward ambient."""
    gen = BessGenerator(inject_fault_every_ticks=5, fault_duration_ticks=3)
    # Trigger fault at tick 5
    for _ in range(5):
        gen.tick()
    assert gen.rack_temp > 40.0

    # Exhaust remaining fault ticks
    for _ in range(2):
        gen.tick()
    assert gen._fault_remaining == 0

    # Run many normal ticks - rack_temp should drift toward ambient (~22C)
    for _ in range(200):
        # Skip any re-triggering by setting inject_fault_every_ticks high
        gen.inject_fault_every_ticks = 999999
        gen.tick()
    assert gen.rack_temp < 35.0, "rack_temp should have drifted back toward ambient"


def test_fault_duration_zero_gives_single_tick():
    """fault_duration_ticks=0 should not sustain the fault (no elevated ticks)."""
    gen = BessGenerator(inject_fault_every_ticks=10, fault_duration_ticks=0)
    for _ in range(10):
        gen.tick()
    # With duration 0, _fault_remaining is set to 0 and the else branch runs
    assert gen._fault_remaining == 0
    # rack_temp should be near ambient, not elevated
    assert gen.rack_temp < 40.0
