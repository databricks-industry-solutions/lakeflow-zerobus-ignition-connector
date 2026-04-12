"""Synthetic data generators for AGL BESS demo.

Each generator class maintains internal state and produces tag events matching
the Ignition tag structure defined in examples/agl_tomago_bess_site01/*.json.

The generators replicate the simulation logic from the Ignition timer scripts
(timer_script_agl_*_tomago_site01.py) but run externally via HTTP ingest.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field


@dataclass
class TagEvent:
    """A single tag value event to send to the Gateway ingest endpoint."""

    tag_path: str
    value: object
    quality_code: int = 192  # OPC Good
    data_type: str = "Float4"
    timestamp_ms: int = field(default_factory=lambda: int(time.time() * 1000))


class BessGenerator:
    """BESS telemetry generator - battery SoC, power, thermal, alarms.

    Mirrors timer_script_agl_bess_tomago_site01.py logic.
    Provider: agl_bess

    Optional fault injection: when inject_fault_every_ticks is set, every N ticks
    the generator injects a thermal spike (rack_temp = 42°C) so that z-score
    anomaly detection in the pipeline can flag the asset as "at risk" for the demo.
    """

    def __init__(
        self,
        provider: str = "agl_bess",
        state: str = "NSW",
        location: str = "Tomago",
        unit_id: int = 1,
        *,
        inject_fault_every_ticks: int | None = 1500,
        fault_duration_ticks: int = 300,
    ):
        self.provider = provider
        self.state = state
        self.location = location
        self.unit_id = unit_id
        self.root = f"[{provider}]AGL/Australia/{state}/{location}/Site01"
        self.tick_count = 0
        self.inject_fault_every_ticks = inject_fault_every_ticks  # None = no fault injection
        self.fault_duration_ticks = fault_duration_ticks  # How many ticks each fault lasts
        self._fault_remaining = 0  # Countdown ticks remaining in current fault

        # State
        self.soc = 52.0
        self.soh = 99.2
        self.power_mw = 0.0
        self.ambient_temp = 22.0
        self.rack_temp = 31.0
        self.coolant_supply = 24.0
        self.coolant_return = 28.0
        self.alarm_count = 0
        self.critical_alarm = False
        self.last_alarm = ""
        self.derate_active = False
        self.derate_reason = ""

        # Constants
        self.capacity_mwh = 2000.0
        self.max_charge_mw = 500.0
        self.max_discharge_mw = 500.0

    def tick(self) -> list[TagEvent]:
        """Generate one tick of BESS telemetry events."""
        self.tick_count += 1
        now_ms = int(time.time() * 1000)

        # Optional fault injection: sustained thermal anomaly so pipeline z-score flags "at risk"
        hvac_running = True
        if (
            self.inject_fault_every_ticks is not None
            and self.inject_fault_every_ticks > 0
            and self.tick_count % self.inject_fault_every_ticks == 0
        ):
            self._fault_remaining = self.fault_duration_ticks

        if self._fault_remaining > 0:
            # Hold elevated temperature during fault window
            self.rack_temp = 42.0 + random.uniform(-0.5, 0.5)
            self._fault_remaining -= 1
        else:
            # Normal: ambient drift + HVAC
            self.ambient_temp += random.uniform(-0.2, 0.2)
            self.rack_temp += 0.03 * (self.ambient_temp - self.rack_temp) + random.uniform(-0.15, 0.15)

        # Coolant temps track ambient
        self.coolant_supply += 0.02 * (self.ambient_temp - self.coolant_supply) + random.uniform(-0.1, 0.1)
        self.coolant_return = self.coolant_supply + 3.0 + random.uniform(-0.3, 0.3)

        # Thermal derate model
        self.derate_active = False
        self.derate_reason = ""
        derate_factor = 1.0
        if self.rack_temp > 38.0:
            self.derate_active = True
            self.derate_reason = "THERMAL"
            derate_factor = max(0.4, 1.0 - (self.rack_temp - 38.0) * 0.06)

        eff_max_ch = self.max_charge_mw * derate_factor
        eff_max_dis = self.max_discharge_mw * derate_factor

        # Power drift
        self.power_mw += random.uniform(-8.0, 8.0)
        self.power_mw = max(-eff_max_ch, min(eff_max_dis, self.power_mw))

        # SoC update (positive power = discharge = SoC decreases)
        soc_delta = (-self.power_mw / self.capacity_mwh) * (100.0 / 3600.0)
        self.soc = max(5.0, min(98.0, self.soc + soc_delta))

        # SoH degrades very slowly
        self.soh = max(80.0, self.soh - random.uniform(0, 0.0001))

        # Derived
        energy_available = self.capacity_mwh * (self.soc / 100.0)

        # DC voltage correlates with SoC
        dc_voltage = 1100.0 + (self.soc / 100.0) * 300.0 + random.uniform(-5, 5)
        dc_current = (self.power_mw * 1000.0) / max(dc_voltage, 1.0) if abs(self.power_mw) > 0.1 else 0.0
        ac_voltage = 33.0 + random.uniform(-0.2, 0.2)
        frequency = 50.0 + random.uniform(-0.03, 0.03)
        reactive_power = self.power_mw * random.uniform(-0.05, 0.05)

        # Alarms
        if random.random() < 0.003:
            self.alarm_count += 1
            self.last_alarm = "Rack temp sensor noisy"
        if self.rack_temp > 45.0:
            self.critical_alarm = True
            self.last_alarm = "THERMAL TRIP RISK"
        else:
            self.critical_alarm = False

        # Mode
        if self.power_mw > 5.0:
            mode = "DISCHARGE"
        elif self.power_mw < -5.0:
            mode = "CHARGE"
        else:
            mode = "STANDBY"

        available = not self.critical_alarm

        bess = f"{self.root}/BESS{self.unit_id:02d}"
        events = [
            TagEvent(f"{bess}/Telemetry/SoC_pct", round(self.soc, 2), timestamp_ms=now_ms),
            TagEvent(f"{bess}/Telemetry/SoH_pct", round(self.soh, 2), timestamp_ms=now_ms),
            TagEvent(f"{bess}/Telemetry/EnergyAvailable_MWh", round(energy_available, 1), timestamp_ms=now_ms),
            TagEvent(f"{bess}/Telemetry/ActivePower_MW", round(self.power_mw, 2), timestamp_ms=now_ms),
            TagEvent(f"{bess}/Telemetry/ReactivePower_MVAr", round(reactive_power, 2), timestamp_ms=now_ms),
            TagEvent(f"{bess}/Telemetry/DCVoltage_V", round(dc_voltage, 1), timestamp_ms=now_ms),
            TagEvent(f"{bess}/Telemetry/DCCurrent_A", round(dc_current, 1), timestamp_ms=now_ms),
            TagEvent(f"{bess}/Telemetry/ACVoltage_kV", round(ac_voltage, 2), timestamp_ms=now_ms),
            TagEvent(f"{bess}/Telemetry/Frequency_Hz", round(frequency, 3), timestamp_ms=now_ms),
            TagEvent(f"{bess}/Telemetry/Mode", mode, data_type="String", timestamp_ms=now_ms),
            TagEvent(f"{bess}/Telemetry/Available", available, data_type="Boolean", timestamp_ms=now_ms),
            TagEvent(f"{bess}/Telemetry/DerateActive", self.derate_active, data_type="Boolean", timestamp_ms=now_ms),
            TagEvent(f"{bess}/Telemetry/DerateReason", self.derate_reason, data_type="String", timestamp_ms=now_ms),
            TagEvent(f"{bess}/Limits/MaxCharge_MW", round(eff_max_ch, 1), timestamp_ms=now_ms),
            TagEvent(f"{bess}/Limits/MaxDischarge_MW", round(eff_max_dis, 1), timestamp_ms=now_ms),
            TagEvent(f"{bess}/Thermal/AmbientTemp_C", round(self.ambient_temp, 2), timestamp_ms=now_ms),
            TagEvent(f"{bess}/Thermal/HVAC_Running", hvac_running, data_type="Boolean", timestamp_ms=now_ms),
            TagEvent(f"{bess}/Thermal/CoolantSupplyTemp_C", round(self.coolant_supply, 2), timestamp_ms=now_ms),
            TagEvent(f"{bess}/Thermal/CoolantReturnTemp_C", round(self.coolant_return, 2), timestamp_ms=now_ms),
            TagEvent(f"{bess}/Thermal/MaxRackTemp_C", round(self.rack_temp, 2), timestamp_ms=now_ms),
            TagEvent(f"{bess}/Alarms/AlarmCount", self.alarm_count, data_type="Int4", timestamp_ms=now_ms),
            TagEvent(
                f"{bess}/Alarms/CriticalAlarmActive", self.critical_alarm, data_type="Boolean", timestamp_ms=now_ms
            ),
            TagEvent(f"{bess}/Alarms/LastAlarm", self.last_alarm, data_type="String", timestamp_ms=now_ms),
        ]
        return events


class GridGenerator:
    """Grid/dispatch generator - POI, dispatch targets, grid events.

    Mirrors timer_script_agl_grid_tomago_site01.py logic.
    Provider: agl_grid
    """

    def __init__(
        self,
        provider: str = "agl_grid",
        state: str = "NSW",
        location: str = "Tomago",
    ):
        self.provider = provider
        self.state = state
        self.location = location
        self.root = f"[{provider}]AGL/Australia/{state}/{location}/Site01"
        self.tick_count = 0

        # State
        self.target_power = 0.0
        self.constraint_active = False
        self.constraint_reason = ""
        self.curtailment_pct = 0.0
        self.fcas_enabled = False
        self.freq_event = False
        self.voltage_sag = False
        self.last_event = ""

    def tick(self) -> list[TagEvent]:
        self.tick_count += 1
        now_ms = int(time.time() * 1000)

        # Constraint toggle
        if random.random() < 0.01:
            self.constraint_active = not self.constraint_active
            self.constraint_reason = "NETWORK_LIMIT" if self.constraint_active else ""

        # Dispatch target swing
        self.target_power += random.uniform(-35.0, 35.0)
        self.target_power = max(-450.0, min(450.0, self.target_power))

        # Curtailment
        if self.constraint_active:
            self.curtailment_pct = min(40.0, max(5.0, self.curtailment_pct + random.uniform(-1.5, 3.0)))
        else:
            self.curtailment_pct = max(0.0, self.curtailment_pct - 2.0)

        eff_target = self.target_power * (1.0 - self.curtailment_pct / 100.0)

        # POI
        net = eff_target + random.uniform(-8.0, 8.0)
        export_mw = max(0.0, net)
        import_mw = max(0.0, -net)
        voltage_kv = 330.0 + random.uniform(-1.2, 1.2)
        frequency_hz = 50.0 + random.uniform(-0.05, 0.05)
        reactive_mvar = net * random.uniform(-0.03, 0.03)
        power_factor = 0.99 + random.uniform(-0.01, 0.005)
        breaker_closed = True

        # Grid events
        self.freq_event = False
        self.voltage_sag = False
        if random.random() < 0.002:
            self.freq_event = True
            self.last_event = "FREQUENCY_EVENT"
        elif random.random() < 0.002:
            self.voltage_sag = True
            self.last_event = "VOLTAGE_SAG"

        # FCAS toggle
        if random.random() < 0.005:
            self.fcas_enabled = not self.fcas_enabled

        poi = f"{self.root}/Substation01/POI"
        disp = f"{self.root}/Dispatch"
        events_path = f"{self.root}/Events"

        events = [
            TagEvent(f"{poi}/ExportPower_MW", round(export_mw, 2), timestamp_ms=now_ms),
            TagEvent(f"{poi}/ImportPower_MW", round(import_mw, 2), timestamp_ms=now_ms),
            TagEvent(f"{poi}/NetPower_MW", round(net, 2), timestamp_ms=now_ms),
            TagEvent(f"{poi}/ReactivePower_MVAr", round(reactive_mvar, 2), timestamp_ms=now_ms),
            TagEvent(f"{poi}/PowerFactor", round(power_factor, 4), timestamp_ms=now_ms),
            TagEvent(f"{poi}/Voltage_kV", round(voltage_kv, 2), timestamp_ms=now_ms),
            TagEvent(f"{poi}/Frequency_Hz", round(frequency_hz, 3), timestamp_ms=now_ms),
            TagEvent(f"{poi}/BreakerClosed", breaker_closed, data_type="Boolean", timestamp_ms=now_ms),
            TagEvent(f"{disp}/TargetNetPower_MW", round(self.target_power, 2), timestamp_ms=now_ms),
            TagEvent(f"{disp}/ConstraintActive", self.constraint_active, data_type="Boolean", timestamp_ms=now_ms),
            TagEvent(f"{disp}/ConstraintReason", self.constraint_reason, data_type="String", timestamp_ms=now_ms),
            TagEvent(f"{disp}/Curtailment_pct", round(self.curtailment_pct, 2), timestamp_ms=now_ms),
            TagEvent(f"{disp}/FCAS_Enabled", self.fcas_enabled, data_type="Boolean", timestamp_ms=now_ms),
            TagEvent(
                f"{events_path}/FrequencyEventActive", self.freq_event, data_type="Boolean", timestamp_ms=now_ms
            ),
            TagEvent(f"{events_path}/VoltageSagActive", self.voltage_sag, data_type="Boolean", timestamp_ms=now_ms),
            TagEvent(f"{events_path}/LastEvent", self.last_event, data_type="String", timestamp_ms=now_ms),
        ]
        return events


class MarketGenerator:
    """NEM market price generator - RRP, FCAS prices.

    Mirrors timer_script_agl_market_tomago_site01.py logic.
    Provider: agl_market
    """

    def __init__(
        self,
        provider: str = "agl_market",
        state: str = "NSW",
        location: str = "Tomago",
    ):
        self.provider = provider
        self.state = state
        self.location = location
        self.root = f"[{provider}]AGL/Australia/{state}/{location}/Site01"
        self.tick_count = 0

        self.rrp = 110.0
        self.spike_active = False
        self.fcas_contingency = 18.0
        self.fcas_reg = 12.0

    def tick(self) -> list[TagEvent]:
        self.tick_count += 1
        now_ms = int(time.time() * 1000)

        # Mean-reverting price with occasional spikes
        self.rrp += (110.0 - self.rrp) * 0.05 + random.uniform(-8.0, 8.0)
        if random.random() < 0.02:
            self.spike_active = True
            self.rrp += random.uniform(150.0, 400.0)
        else:
            self.spike_active = False

        self.fcas_contingency = max(0.0, self.fcas_contingency + random.uniform(-2.0, 3.0))
        self.fcas_reg = max(0.0, self.fcas_reg + random.uniform(-1.5, 2.5))

        mkt = f"{self.root}/Market"
        events = [
            TagEvent(f"{mkt}/RRP_AUD_per_MWh", round(self.rrp, 2), timestamp_ms=now_ms),
            TagEvent(f"{mkt}/PriceSpikeActive", self.spike_active, data_type="Boolean", timestamp_ms=now_ms),
            TagEvent(
                f"{mkt}/FCAS_ContingencyPrice_AUD_per_MWh", round(self.fcas_contingency, 2), timestamp_ms=now_ms
            ),
            TagEvent(f"{mkt}/FCAS_RegPrice_AUD_per_MWh", round(self.fcas_reg, 2), timestamp_ms=now_ms),
        ]
        return events


class CmmsGenerator:
    """CMMS (maintenance) generator - work orders, outages.

    Mirrors timer_script_agl_cmms_tomago_site01.py logic.
    Provider: agl_cmms
    """

    def __init__(
        self,
        provider: str = "agl_cmms",
        state: str = "NSW",
        location: str = "Tomago",
    ):
        self.provider = provider
        self.state = state
        self.location = location
        self.root = f"[{provider}]AGL/Australia/{state}/{location}/Site01"
        self.tick_count = 0

        self.open_work_orders = 7
        self.high_priority_wo = 1
        self.planned_outage = False
        self.forced_outage = False
        self.last_work_order = ""

    def tick(self) -> list[TagEvent]:
        self.tick_count += 1
        now_ms = int(time.time() * 1000)

        # Work order drift
        self.open_work_orders = max(0, self.open_work_orders + random.choice([-1, 0, 0, 1]))
        self.high_priority_wo = max(0, min(self.open_work_orders, self.high_priority_wo + random.choice([-1, 0, 0, 1])))

        # Outage toggles
        if random.random() < 0.01:
            self.planned_outage = not self.planned_outage
            self.last_work_order = "PM-HVAC-Filter-Replace" if self.planned_outage else ""
        if random.random() < 0.005:
            self.forced_outage = not self.forced_outage
            if self.forced_outage:
                self.last_work_order = "CM-PCS-Inverter-Fault"

        cmms = f"{self.root}/CMMS"
        events = [
            TagEvent(f"{cmms}/OpenWorkOrders", self.open_work_orders, data_type="Int4", timestamp_ms=now_ms),
            TagEvent(f"{cmms}/HighPriorityWorkOrders", self.high_priority_wo, data_type="Int4", timestamp_ms=now_ms),
            TagEvent(f"{cmms}/PlannedOutageActive", self.planned_outage, data_type="Boolean", timestamp_ms=now_ms),
            TagEvent(f"{cmms}/ForcedOutageActive", self.forced_outage, data_type="Boolean", timestamp_ms=now_ms),
            TagEvent(f"{cmms}/LastWorkOrder", self.last_work_order, data_type="String", timestamp_ms=now_ms),
        ]
        return events
