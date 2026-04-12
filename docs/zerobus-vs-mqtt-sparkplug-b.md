# Zerobus vs MQTT / Sparkplug B: Positioning Guide

## Context

Customers running Inductive Automation's Ignition platform commonly use MQTT with Sparkplug B (via Cirrus Link modules) as their standard OT data transport. This document explains how the Zerobus Ignition module complements — rather than replaces — that architecture when the goal is getting OT data into Databricks.

## What is Sparkplug B?

Sparkplug B is an open-source specification (governed by the Eclipse Foundation) that sits **on top of MQTT** to standardise industrial IoT messaging. Plain MQTT provides pub/sub transport but defines nothing about topic structure, payload format, or device lifecycle — every implementation is bespoke. Sparkplug B fills those gaps.

### Topic namespace

Sparkplug B enforces a strict hierarchical topic structure:

```
spBv1.0/<group_id>/<message_type>/<edge_node_id>/[device_id]
```

Message types include `NBIRTH` / `NDEATH` (node birth/death), `DBIRTH` / `DDEATH` (device birth/death), `NDATA` / `DDATA` (data), and `NCMD` / `DCMD` (commands). This eliminates the "every site invents its own topic tree" problem.

### Protobuf payload

Sparkplug B uses Google Protocol Buffers (not JSON) for payloads. Each message contains:

```
{
  "timestamp": 1486144502122,       // message-level timestamp
  "seq": 2,                         // sequence number (gap = lost message)
  "metrics": [{
    "name": "Inputs/Temperature",   // metric path
    "alias": 1,                     // numeric shorthand (saves bandwidth after BIRTH)
    "timestamp": 1479123452194,     // metric-level sample time
    "dataType": "Float",            // typed: Boolean, Int32, Int64, Float, String, etc.
    "value": 25.6,
    "is_historical": false,         // true = backfilled point
    "is_transient": false,          // true = don't persist
    "metadata": { ... },            // engineering units, description, etc.
    "properties": { ... }           // custom key-value pairs
  }]
}
```

Key features:
- **Metric aliasing** — after the initial BIRTH message sends full metric names, subsequent DATA messages use numeric aliases. In large deployments (10,000+ tags), this reduces payload size by 30-70%.
- **Report by exception** — only changed values are published, reducing network traffic.
- **Sequence numbers** — receivers detect gaps and can request re-delivery.

### Birth and death certificates

- **NBIRTH / DBIRTH** — sent when a node or device comes online, announcing all available metrics with their metadata. This is the "schema advertisement."
- **NDEATH / DDEATH** — published by the MQTT broker (via Last Will and Testament) when a device disconnects unexpectedly. Operators always know if data is stale.

Plain MQTT has none of this — device state tracking requires custom application logic.

### Cirrus Link modules in Ignition

Cirrus Link provides the Sparkplug B implementation for Ignition:

| Module | Role |
|---|---|
| **MQTT Transmission** | Publishes Ignition tags as Sparkplug B messages to an MQTT broker. Acts as the "edge node" — attaches listeners to tags, generates BIRTH/DEATH/DATA messages on change. |
| **MQTT Engine** | Subscribes to Sparkplug B messages from the broker, auto-discovers tags on connection, and creates them in the Ignition tag tree. The "host application." |
| **MQTT Distributor** | Embedded MQTT broker (based on HiveMQ) that runs inside Ignition. Optional — many customers use external brokers (HiveMQ, Mosquitto, EMQX). |

A typical two-gateway architecture: Edge Ignition runs MQTT Transmission → publishes to broker → Central Ignition runs MQTT Engine → tags appear automatically.

## The current MQTT / Sparkplug B path to Databricks

```
Ignition Gateway
  → MQTT Transmission (Sparkplug B protobuf)
    → MQTT Broker (HiveMQ / Mosquitto / EMQX)
      → Kafka Connect / Spark Structured Streaming / custom consumer
        → Databricks Delta Lake
```

Sparkplug B solves the **OT interoperability** problem — how devices, gateways, and SCADA systems talk to each other in a vendor-neutral way with typed, self-describing payloads.

However, Sparkplug B does not solve the **OT-to-lakehouse** problem. Getting MQTT data into Databricks still requires a broker, a bridge (Kafka Connect, a Spark Structured Streaming job, or bespoke glue), and infrastructure to manage all of it.

The bridge must also **deserialise Sparkplug B protobuf**, extract metrics from the nested payload, and flatten them into a tabular schema suitable for Delta — non-trivial custom work.

## The Zerobus path

```
Ignition Gateway
  → Zerobus Module (gRPC + protobuf)
    → Databricks Delta Lake (direct write)
```

The Zerobus module replaces the entire MQTT-to-Databricks pipeline with a single hop. Tag change events stream directly from the Ignition JVM into a Delta table — no broker, no Kafka, no glue code.

The module subscribes to Ignition tags directly (not to MQTT topics), so it is **protocol-agnostic** — whether the underlying tag source is OPC-UA, Sparkplug B via MQTT Engine, Modbus, or a database driver, the same tag change event flows through the same pipeline. As noted in the Ignition blog draft: *"A tag path like `[MyOpcUa]Devices/Turbine1/Speed` or `[MQTT Engine]Sparkplug B/Group/Edge Node/Device/pressure` flows through identical event handling."*

## Protocol and payload comparison

| Aspect | Sparkplug B (over MQTT) | Zerobus module (gRPC) |
|---|---|---|
| **Transport** | MQTT 3.1.1 / 5.0 (TCP, pub/sub) | gRPC over HTTP/2 (streaming, point-to-point) |
| **Payload encoding** | Protobuf (Sparkplug B schema) | Protobuf (Zerobus OTEvent schema) |
| **Payload structure** | Device-centric — nested metrics array with aliases, birth/death lifecycle | Analytics-centric — flat tag event (path, value, timestamp, quality) maps directly to Delta columns |
| **Topic / routing** | Hierarchical topic namespace (`spBv1.0/group/DDATA/node/device`) | Single gRPC stream per target table |
| **State management** | Birth/death certificates, sequence numbers, Last Will & Testament | Store-and-forward buffer with backpressure, disk spool for durability |
| **Bandwidth optimisation** | Metric aliasing (30-70% reduction), report by exception | SDT compression (up to 10:1 — typically 4-8:1 for analog signals) |
| **Schema discovery** | BIRTH messages advertise all metrics + metadata | Target Delta table schema is the contract — Zerobus validates on ingest |
| **Delivery guarantee** | MQTT QoS 0/1/2 (at-most/at-least/exactly once) | At-least-once (durable ack from Zerobus service) |
| **Authentication** | Broker credentials + TLS certificates | Databricks OAuth via service principal (M2M) |
| **Infrastructure required** | MQTT broker (HA cluster) + bridge to Databricks | None — Databricks-hosted serverless endpoint |

## Side-by-side comparison (operational)

| Concern | MQTT + Sparkplug B | Zerobus module |
|---|---|---|
| **Broker infrastructure** | Customer-managed (provisioning, monitoring, patching, HA) | Eliminated — Databricks-hosted endpoint |
| **Reliability** | MQTT QoS + broker persistence | Built-in store-and-forward buffer (memory or disk-backed with backpressure) |
| **Data reduction** | Report by exception + metric aliasing (payload size) | Swinging Door Trending (SDT) compression — filters redundant points before they leave the gateway |
| **Schema** | Sparkplug B protobuf (device-centric, nested) | Zerobus protobuf (analytics-centric, lands as typed Delta columns) |
| **Latency to query** | Broker → consumer → staging → Delta (minutes) | gRPC stream → Delta table (seconds, P50 ~5s) |
| **Fan-out to other systems** | MQTT broker feeds multiple subscribers (SCADA, MES, historians) | Purpose-built for the Databricks path only |
| **Private connectivity** | Customer manages broker network placement | Service-Direct Front-End Private Link (Public Preview) — on-prem → ExpressRoute → Azure VNet → Private Endpoint → Zerobus |

## Complementary, not competitive

Zerobus replaces MQTT **only for the Ignition-to-Databricks analytics path**. If the customer uses Sparkplug B to feed other downstream systems — SCADA HMIs, MES, other historians, device-to-device communication — those MQTT subscriptions remain as-is.

```
Ignition Gateway (on-prem)
  ├── MQTT Transmission (Sparkplug B) → Broker → SCADA, MES, other OT consumers
  └── Zerobus Module (gRPC)           → Private Link → Delta Lake → ML, dashboards, analytics
```

The two paths serve fundamentally different consumers:

| | MQTT / Sparkplug B path | Zerobus path |
|---|---|---|
| **Purpose** | Operational (real-time control, HMI) | Analytical (historical insight, ML, dashboards) |
| **Consumers** | SCADA operators, MES, devices | Data engineers, data scientists, BI dashboards |
| **Retention** | Ephemeral / short-lived | Durable / queryable for months or years |
| **Latency requirement** | Sub-second (control loops) | Seconds (acceptable for analytics) |
| **Network** | OT network (isolated, air-gapped) | IT/cloud network (via Private Link) |

## Data duplication

Running both paths means the same tag change events are published to two destinations. This is **purpose-driven routing**, not wasteful duplication:

- The MQTT path delivers raw, uncompressed events to operational consumers that need every point.
- The Zerobus path applies SDT compression at the edge, meaning fewer points are transmitted — typically 4:1 to 10:1 compression (75-90% reduction) depending on signal characteristics and deviation settings.

The alternative — tapping the MQTT stream and bridging it into Databricks — requires all the broker and bridge infrastructure that Zerobus eliminates. It also requires custom code to deserialise Sparkplug B protobuf, extract the nested metrics, and flatten them into Delta-compatible rows.

## Private connectivity (on-prem gateways)

For customers with on-prem Ignition gateways who cannot use the public internet:

**Service-Direct Front-End Private Link** (Public Preview) provides inbound private connectivity to Zerobus Ingest:

```
On-prem Ignition Gateway
  → ExpressRoute / VPN
    → Azure VNet
      → Private Endpoint (service_direct sub-resource)
        → Zerobus Ingest endpoint
          → Delta Lake
```

Setup:
1. Create a private endpoint in the customer's Azure VNet (or one peered via ExpressRoute to on-prem)
2. Register the private endpoint in the Databricks account console
3. Configure DNS to resolve `<region>.service-direct.privatelink.azuredatabricks.net` to the private IP

All traffic stays on the Azure backbone — never touches the public internet.

Reference: [Configure inbound Private Link for performance-intensive services](https://learn.microsoft.com/en-us/azure/databricks/security/network/front-end/service-direct-privatelink)

## Regional availability

Zerobus Ingest is available in a subset of Azure regions. Notable for APJ customers:

| Region | Zerobus | Databricks Apps | Serverless compute |
|---|---|---|---|
| `australiaeast` (Sydney) | Yes | Yes | Yes |
| `australiasoutheast` (Melbourne) | **No** | No | Yes |
| `southeastasia` (Singapore) | Yes | Yes | Yes |

Both `australiaeast` and `australiasoutheast` are in Australia — same legal jurisdiction, same data sovereignty compliance. For on-prem gateways, the extra ~10-15ms latency to Sydney vs Melbourne is invisible on a pipeline with P50 time-to-table of ~5 seconds.

Full region list: [Zerobus Ingest connector limitations](https://learn.microsoft.com/en-us/azure/databricks/ingestion/zerobus-limits)

## Internal contacts

| Person | Role | Contact |
|---|---|---|
| **Victoria Bukta** | PM, Zerobus Ingest | victoria.bukta@databricks.com |
| **Aleksandar Tomic** | Tech Lead, Zerobus | via `#lakeflow-connect-zerobus` |

Slack: `#lakeflow-connect-zerobus` — for region requests, customer asks, and technical questions.

## One-sentence pitch

> Why maintain a broker and a bridge to get OT data into your lakehouse when you can stream directly from Ignition — with edge compression and private connectivity included?

## Sources

- [Eclipse Sparkplug specification](https://www.eclipse.org/tahu/spec/Sparkplug%20Topic%20Namespace%20and%20State%20ManagementV2.2-with%20appendix%20B%20format%20-%20Eclipse.pdf)
- [MQTT Sparkplug vs. Plain MQTT (Ubidots)](https://ubidots.com/blog/mqtt-sparkplug-vs-plain-mqtt/)
- [Sparkplug B payload structures (HiveMQ)](https://www.hivemq.com/blog/mqtt-payload-structures-iiot/)
- [Sparkplug B vs Plain MQTT: Performance Lessons](https://iiotblog.com/2025/12/01/sparkplug-b-vs-plain-mqtt-performance-lessons/)
- [Cirrus Link MQTT modules](https://cirrus-link.com/mqtt-modules/)
- [Zerobus Ingest connector overview (Azure docs)](https://learn.microsoft.com/en-us/azure/databricks/ingestion/zerobus-overview)
- [Zerobus Ingest connector limitations (Azure docs)](https://learn.microsoft.com/en-us/azure/databricks/ingestion/zerobus-limits)
- [Service-Direct Private Link for performance-intensive services (Azure docs)](https://learn.microsoft.com/en-us/azure/databricks/security/network/front-end/service-direct-privatelink)
- [Zerobus community blog: Kafka-Free Real-Time Streaming](https://community.databricks.com/t5/technical-blog/partner-blog-zerobus-ingest-on-databricks/ba-p/142433)
