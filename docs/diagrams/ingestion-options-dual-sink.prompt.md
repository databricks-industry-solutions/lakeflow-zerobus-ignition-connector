Create a clean architecture diagram for an Ignition OT ingestion connector with TWO ingestion destinations.

Title: "Ignition OT ingestion: Zerobus and Lakebase SQL options"

Requirements:
- Use a white background.
- Keep text concise and legible.
- Use clear arrows and labels.
- Make both options visually equal (not implying one is deprecated).
- Include a short legend.
- Include Databricks branding style, but keep it neutral and product-focused.

Layout:
1) Left column:
   - "Ignition Gateway"
   - "Tag sources (OPC UA / MQTT / other providers)"
   - "Direct subscriptions OR HTTP ingest (/system/zerobus/ingest, /ingest/batch)"

2) Center column:
   - "OT Ingestion Connector"
   - internal flow boxes:
     - "TagEvent normalization"
     - "OTEvent mapping"
     - "Store-and-forward buffer"
     - "Batch flush loop"
   - "Sink mode switch"

3) Right side with two parallel branches:
   A) Top branch label: "Option A: Zerobus mode"
      - "Zerobus ingest (gRPC/protobuf)"
      - "Delta table (catalog.schema.raw_tags)"
      - note: "Best for Delta-native analytics / Lakeflow pipelines"

   B) Bottom branch label: "Option B: Lakebase mode"
      - "PostgreSQL sink (SQL batch inserts)"
      - "Lakebase table (raw_tags)"
      - note: "Best for low-latency operational SQL reads"

Callouts:
- "Modes are exclusive: sinkMode=zerobus OR sinkMode=lakebase"
- "Upstream ingestion path is shared for both modes"
- "Event Streams path: disable direct subscriptions and push JSON to HTTP endpoints"

Legend:
- Blue arrows = shared ingestion path
- Orange arrows = Zerobus/Delta path
- Green arrows = Lakebase SQL path

Output style:
- professional technical architecture figure suitable for README documentation.
