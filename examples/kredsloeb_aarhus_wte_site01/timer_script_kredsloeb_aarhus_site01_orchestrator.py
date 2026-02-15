# Kredsløb Aarhus demo simulator (memory tags) - single orchestrator
# Intended for ONE Gateway Timer Script (e.g., 1000ms).
#
# Providers:
# - kredsloeb_process  -> [kredsloeb_process]Kredsloeb/Denmark/Midtjylland/Aarhus/Site01/...
# - kredsloeb_dh       -> [kredsloeb_dh]Kredsloeb/Denmark/Midtjylland/Aarhus/Site01/...
# - kredsloeb_env      -> [kredsloeb_env]Kredsloeb/Denmark/Midtjylland/Aarhus/Site01/...
#
# Notes:
# - Written as top-level code (no defs) for compatibility with Ignition timer contexts.
# - One enable switch controls all domains: .../Config/SimEnabled (in process provider).
# - Uses a simple cadence:
#   - process: every tick
#   - district heating: every 2 ticks
#   - emissions/compliance: every 5 ticks

import random
import math

root_proc = "[kredsloeb_process]Kredsloeb/Denmark/Midtjylland/Aarhus/Site01"
root_dh = "[kredsloeb_dh]Kredsloeb/Denmark/Midtjylland/Aarhus/Site01"
root_env = "[kredsloeb_env]Kredsloeb/Denmark/Midtjylland/Aarhus/Site01"

cfg = root_proc + "/Config"
diag = root_proc + "/Diagnostics"

plant = root_proc + "/Plant01/WasteToEnergy"
furn = plant + "/Furnace"
boil = plant + "/Boiler"
turb = plant + "/Turbine"
kpi = root_proc + "/Plant01/KPIs"

dh = root_dh + "/DistrictHeating/Network"
env_cems = root_env + "/Environment/CEMS"
env_lim = root_env + "/Environment/PermitLimits"
env_comp = root_env + "/Environment/Compliance"

sim_enabled = system.tag.readBlocking([cfg + "/SimEnabled"])[0].value
if not sim_enabled:
    system.tag.writeBlocking([diag + "/LastStatus"], ["Sim disabled"])
else:
    # Tick
    tick = int(system.tag.readBlocking([diag + "/TickCount"])[0].value or 0) + 1

    # ---- Read config / capacities ----
    max_waste_tph = float(system.tag.readBlocking([cfg + "/MaxWasteFeed_tph"])[0].value or 28.0)
    lhv_mjkg = float(system.tag.readBlocking([cfg + "/WasteLHV_MJ_per_kg"])[0].value or 9.0)
    turb_cap_mwe = float(system.tag.readBlocking([cfg + "/TurbineCapacity_MWe"])[0].value or 55.0)

    # ---- District heating demand model (every 2 ticks) ----
    # Demand rises as ambient drops; clamp to a plausible range.
    if tick % 2 == 0:
        amb = float(system.tag.readBlocking([dh + "/AmbientTemp_C"])[0].value or 5.0)
        # slow ambient drift (seasonal-ish)
        amb = amb + random.uniform(-0.05, 0.05)
        amb = max(-10.0, min(18.0, amb))

        # Simple demand curve: colder => more demand
        demand = 60.0 + (10.0 - amb) * 6.0  # MWth
        demand = max(40.0, min(170.0, demand))

        # Network setpoints (typical district heating behavior)
        supply_sp = 82.0 + (10.0 - amb) * 0.9
        supply_sp = max(70.0, min(102.0, supply_sp))

        ret_sp = 48.0 + (supply_sp - 75.0) * 0.2
        ret_sp = max(38.0, min(60.0, ret_sp))

        system.tag.writeBlocking(
            [dh + "/AmbientTemp_C", dh + "/HeatDemand_MWth", dh + "/SupplyTemp_C", dh + "/ReturnTemp_C"],
            [amb, demand, supply_sp, ret_sp],
        )

    # Re-read demand (used for process setpoints)
    demand_mwth = float(system.tag.readBlocking([dh + "/HeatDemand_MWth"])[0].value or 110.0)

    # ---- Process simulation (every tick) ----
    waste_tph = float(system.tag.readBlocking([furn + "/WasteFeedRate_tph"])[0].value or 18.0)
    o2 = float(system.tag.readBlocking([furn + "/O2_pct"])[0].value or 7.0)
    ftemp = float(system.tag.readBlocking([furn + "/FurnaceTemp_C"])[0].value or 940.0)

    load = float(system.tag.readBlocking([boil + "/BoilerLoad_pct"])[0].value or 60.0)
    spress = float(system.tag.readBlocking([boil + "/SteamPressure_bar"])[0].value or 90.0)
    stemp = float(system.tag.readBlocking([boil + "/SteamTemp_C"])[0].value or 505.0)
    sflow = float(system.tag.readBlocking([boil + "/SteamFlow_tph"])[0].value or 105.0)

    gen_mwe = float(system.tag.readBlocking([turb + "/GeneratorPower_MWe"])[0].value or 25.0)
    vac_kpa = float(system.tag.readBlocking([turb + "/CondenserVacuum_kPa"])[0].value or 10.0)
    valve = float(system.tag.readBlocking([turb + "/TurbineValve_pct"])[0].value or 55.0)

    # Target heat output roughly tracks demand; plant provides a large portion of it
    heat_target = demand_mwth * random.uniform(0.75, 0.95)
    heat_target = max(35.0, min(160.0, heat_target))

    # Waste feed moves slowly toward what is needed for heat + power
    # Rough energy balance: input thermal MW ~ waste_tph * LHV * 0.2778 (MJ/kg -> kW), then to MW
    # MW_in ≈ waste_tph * 1000 kg/t * LHV MJ/kg * 0.2778 kWh/MJ / 1000 kW/MW / h
    mw_in = waste_tph * lhv_mjkg * 0.2778

    # Assume overall efficiency 78-88% depending on load stability
    eff = 0.82 + random.uniform(-0.02, 0.02)
    useful_mw = mw_in * eff  # MW thermal equivalent delivered (heat + electric)

    # Split useful energy between heat and electricity; electricity capped by turbine
    # Keep electricity around 18-35% of useful energy depending on heat demand.
    elec_frac = 0.22 if heat_target > 120.0 else 0.30
    elec_frac = max(0.18, min(0.35, elec_frac + random.uniform(-0.02, 0.02)))
    gen_target = min(turb_cap_mwe, useful_mw * elec_frac)

    heat_out = max(0.0, useful_mw - gen_target)
    # Nudge heat_out toward heat_target by adjusting waste feed
    heat_error = heat_target - heat_out
    waste_tph = waste_tph + (heat_error * 0.03) + random.uniform(-0.15, 0.15)
    waste_tph = max(8.0, min(max_waste_tph, waste_tph))

    # Recompute with updated feed
    mw_in = waste_tph * lhv_mjkg * 0.2778
    eff = 0.83 + random.uniform(-0.015, 0.015)
    useful_mw = mw_in * eff
    gen_target = min(turb_cap_mwe, useful_mw * elec_frac)
    heat_out = max(0.0, useful_mw - gen_target)

    # Boiler/load dynamics
    load = load + ( (heat_out / 160.0) * 100.0 - load) * 0.15 + random.uniform(-0.5, 0.5)
    load = max(25.0, min(100.0, load))
    spress = 70.0 + load * 0.35 + random.uniform(-0.6, 0.6)   # bar
    stemp = 480.0 + load * 0.35 + random.uniform(-1.0, 1.0)  # C
    sflow = 70.0 + load * 0.6 + random.uniform(-1.5, 1.5)    # tph

    # Furnace chemistry-ish
    o2 = o2 + random.uniform(-0.15, 0.15) - (load - 65.0) * 0.002
    o2 = max(4.5, min(9.5, o2))
    ftemp = 860.0 + load * 1.6 + random.uniform(-6.0, 6.0)
    airflow = 22.0 + load * 0.22 + random.uniform(-0.8, 0.8)

    # Turbine
    gen_mwe = gen_mwe + (gen_target - gen_mwe) * 0.25 + random.uniform(-0.4, 0.4)
    gen_mwe = max(0.0, min(turb_cap_mwe, gen_mwe))
    valve = 25.0 + (gen_mwe / turb_cap_mwe) * 70.0 + random.uniform(-1.0, 1.0)
    valve = max(10.0, min(100.0, valve))
    vac_kpa = 9.5 + (gen_mwe / turb_cap_mwe) * 1.2 + random.uniform(-0.1, 0.1)
    vac_kpa = max(8.8, min(12.0, vac_kpa))

    # ---- District heating hydraulics (every 2 ticks) ----
    if tick % 2 == 0:
        supply = float(system.tag.readBlocking([dh + "/SupplyTemp_C"])[0].value or 90.0)
        ret = float(system.tag.readBlocking([dh + "/ReturnTemp_C"])[0].value or 52.0)
        flow = float(system.tag.readBlocking([dh + "/Flow_m3h"])[0].value or 2200.0)
        dp = float(system.tag.readBlocking([dh + "/PressureDiff_bar"])[0].value or 3.2)
        pump_speed = float(system.tag.readBlocking([dh + "/PumpSpeed_pct"])[0].value or 62.0)

        # Move flow with heat_out (very rough)
        flow_target = 1400.0 + heat_out * 9.0 + random.uniform(-30.0, 30.0)
        flow = flow + (flow_target - flow) * 0.2
        flow = max(900.0, min(3200.0, flow))

        # dp and pump speed drift with flow
        dp_target = 2.2 + (flow - 900.0) / 1200.0
        dp = dp + (dp_target - dp) * 0.2 + random.uniform(-0.05, 0.05)
        dp = max(1.5, min(4.5, dp))

        pump_speed = 45.0 + (flow - 900.0) / 40.0 + random.uniform(-1.0, 1.0)
        pump_speed = max(35.0, min(95.0, pump_speed))
        pump_running = True

        system.tag.writeBlocking(
            [dh + "/HeatOutput_MWth", dh + "/Flow_m3h", dh + "/PressureDiff_bar", dh + "/PumpSpeed_pct", dh + "/PumpRunning"],
            [heat_out, flow, dp, pump_speed, pump_running],
        )

    # ---- Emissions / compliance (every 5 ticks) ----
    if tick % 5 == 0:
        fg_temp = float(system.tag.readBlocking([env_cems + "/FlueGasTemp_C"])[0].value or 165.0)
        stack_o2 = float(system.tag.readBlocking([env_cems + "/StackO2_pct"])[0].value or 7.0)
        nox = float(system.tag.readBlocking([env_cems + "/NOx_mgNm3"])[0].value or 75.0)
        co = float(system.tag.readBlocking([env_cems + "/CO_mgNm3"])[0].value or 20.0)
        dust = float(system.tag.readBlocking([env_cems + "/Dust_mgNm3"])[0].value or 1.6)
        hcl = float(system.tag.readBlocking([env_cems + "/HCl_mgNm3"])[0].value or 2.5)

        nox_lim = float(system.tag.readBlocking([env_lim + "/NOx_mgNm3_Limit"])[0].value or 150.0)
        co_lim = float(system.tag.readBlocking([env_lim + "/CO_mgNm3_Limit"])[0].value or 50.0)
        dust_lim = float(system.tag.readBlocking([env_lim + "/Dust_mgNm3_Limit"])[0].value or 5.0)
        hcl_lim = float(system.tag.readBlocking([env_lim + "/HCl_mgNm3_Limit"])[0].value or 10.0)

        # Base emissions correlate with load and O2; add noise
        fg_temp = 140.0 + load * 0.45 + random.uniform(-2.0, 2.0)
        stack_o2 = max(5.0, min(9.5, o2 + random.uniform(-0.3, 0.3)))

        # NOx tends to rise with higher furnace temp and lower O2 (roughly)
        nox = 55.0 + (ftemp - 900.0) * 0.20 + (7.0 - stack_o2) * 6.0 + random.uniform(-6.0, 6.0)
        # CO rises with poor combustion (too low O2 / too much feed)
        co = 14.0 + (6.2 - stack_o2) * 10.0 + (waste_tph - 18.0) * 1.2 + random.uniform(-3.0, 3.0)
        # Dust and HCl mostly stable with occasional spikes
        dust = max(0.4, 1.2 + random.uniform(-0.3, 0.4))
        hcl = max(0.6, 2.2 + random.uniform(-0.6, 0.8))

        # Rare excursions (demo): spikes that may exceed limits
        last_exc = system.tag.readBlocking([env_comp + "/LastExcursion"])[0].value or ""
        if random.random() < 0.02:
            spike = random.choice(["NOx", "CO", "Dust", "HCl"])
            if spike == "NOx":
                nox = nox_lim * random.uniform(1.05, 1.25)
                last_exc = "NOx excursion"
            elif spike == "CO":
                co = co_lim * random.uniform(1.05, 1.35)
                last_exc = "CO excursion"
            elif spike == "Dust":
                dust = dust_lim * random.uniform(1.05, 1.4)
                last_exc = "Dust excursion"
            else:
                hcl = hcl_lim * random.uniform(1.05, 1.4)
                last_exc = "HCl excursion"

        nox_exc = nox > nox_lim
        co_exc = co > co_lim
        dust_exc = dust > dust_lim
        hcl_exc = hcl > hcl_lim
        any_exc = nox_exc or co_exc or dust_exc or hcl_exc

        system.tag.writeBlocking(
            [
                env_cems + "/FlueGasTemp_C",
                env_cems + "/StackO2_pct",
                env_cems + "/NOx_mgNm3",
                env_cems + "/CO_mgNm3",
                env_cems + "/Dust_mgNm3",
                env_cems + "/HCl_mgNm3",
                env_comp + "/NOx_Excursion",
                env_comp + "/CO_Excursion",
                env_comp + "/Dust_Excursion",
                env_comp + "/HCl_Excursion",
                env_comp + "/AnyPermitExcursion",
                env_comp + "/LastExcursion",
            ],
            [fg_temp, stack_o2, nox, co, dust, hcl, nox_exc, co_exc, dust_exc, hcl_exc, any_exc, last_exc],
        )

    # ---- Derived KPIs (every tick) ----
    overall_eff_pct = max(60.0, min(92.0, (useful_mw / max(mw_in, 1e-6)) * 100.0))
    availability = True  # extend later with forced outages if needed

    # Writes (process + KPIs)
    system.tag.writeBlocking(
        [
            diag + "/TickCount",
            diag + "/LastRun",
            diag + "/LastStatus",
            diag + "/LastError",

            furn + "/WasteFeedRate_tph",
            furn + "/PrimaryAirFlow_kg_s",
            furn + "/O2_pct",
            furn + "/FurnaceTemp_C",

            boil + "/BoilerLoad_pct",
            boil + "/SteamPressure_bar",
            boil + "/SteamTemp_C",
            boil + "/SteamFlow_tph",

            turb + "/GeneratorPower_MWe",
            turb + "/CondenserVacuum_kPa",
            turb + "/TurbineValve_pct",

            kpi + "/HeatOutput_MWth",
            kpi + "/ElectricOutput_MWe",
            kpi + "/OverallEfficiency_pct",
            kpi + "/Availability",
        ],
        [
            tick,
            system.date.now().toString(),
            "tick ok",
            "",

            waste_tph,
            airflow,
            o2,
            ftemp,

            load,
            spress,
            stemp,
            sflow,

            gen_mwe,
            vac_kpa,
            valve,

            heat_out,
            gen_mwe,
            overall_eff_pct,
            availability,
        ],
    )

