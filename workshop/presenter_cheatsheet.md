# Medallion Architecture Workshop — Presenter Cheat Sheet

**Session:** 2 hours | **Time:** 1400 AEST | **Date:** 2026-04-13
**Audience:** AGL OT/data teams — data analysts, data scientists, data engineers, integration pipeline people
**Their tools:** PI + PI AF, GIS (ESRI), CMMS/SAP, AEMO market feeds, various laptop-based analysis

---

## Key Framing (repeat throughout)

> "We're not replacing PI, GIS, or SAP. Each is excellent at its own domain. We're replacing the CSV exports, laptop scripts, and Excel models that connect them."

> "The medallion architecture is the connective tissue between your existing tools."

---

## Build-Live Session Plan

### Pre-Session Prep
- [ ] Run Steps 1-3 of `setup_medallion.sql` (catalog + schemas + bronze with data)
- [ ] Have `demo_queries.sql` open in a SQL editor tab
- [ ] Have `setup_medallion.sql` open in another tab (for running Steps 4-9 live)
- [ ] Have Azure portal open to the medallion storage container
- [ ] **Fallback:** Run full `make workshop-setup` so all tables exist as backup

### Timing Guide

| Time | Section | Action | If behind |
|------|---------|--------|-----------|
| 0:00 | Slides 1-2 | Title + agenda | — |
| 0:05 | Slides 3-5 | OT data challenge, PI trapped, dispatch question | Compress to 2 slides |
| 0:12 | Slide 6 | Lakehouse stack (PI → Zerobus → ADLS) | — |
| 0:15 | Slides 7-12 | Delta Lake deep-dive (Parquet, log, time travel) | Skip slide 11 (log entry JSON) |
| 0:25 | Slides 13-15 | **DEMO: Azure portal** — browse files | — |
| 0:35 | Slides 16-20 | Medallion pattern overview | — |
| 0:45 | Slides 21-24 | Bronze principles + raw_tags schema | — |
| 0:50 | Slide 25 | **DEMO: Query bronze** — show raw data | — |
| 0:55 | **Run Step 4** | `CREATE parsed_tags` + `INSERT` live | If fails, query pre-populated table |
| 1:00 | **Run Step 5** | `CREATE aggregated_tags` + `INSERT` live | Combine with Step 4 |
| 1:05 | **Break** (10 min) | Prep Step 6 in editor | Shorten to 5 min if behind |
| 1:15 | **Run Step 6** | `CREATE enriched_tags` + `INSERT` live | — |
| 1:18 | Slide 33b | **PI AF replacement** — "this IS your new AF" | — |
| 1:22 | **Run PI AF queries** | `DESCRIBE TABLE EXTENDED`, signal mapping | — |
| 1:28 | **Run Step 7** | `CREATE health_scores` live | — |
| 1:32 | **Run Step 8** | `CREATE revenue_risk` live | Combine with Step 7 |
| 1:35 | Slide 41b | Data products — contracts, governance | — |
| 1:38 | **Run Step 9** | `COMMENT ON` statements live | — |
| 1:40 | Slide 41c | **Genie enablement** — show metadata queries | Skip Genie room if tight |
| 1:45 | Slides 42-46 | Recap, design principles, next steps | Compress to 43 + 45 |
| 1:50 | Slide 47 + Q&A | Questions | — |

---

## Talking Points by Slide

### Slide 4: "Your PI Data Is Trapped"
- "How many of you have a local script that parses tag_paths?" (hands will go up)
- "That's our silver layer — done once, governed, for everyone."
- "PI collects 2,700+ tags/sec brilliantly. But the data stays inside PI."

### Slide 5: "The Question PI Can't Answer"
- "Should we bid this battery into the next 5-minute dispatch interval?"
- "That needs OT health + spot price + weather + maintenance schedule."
- "4 tools, 4 exports, 1 person's laptop. That's your integration platform today."
- Don't say "spreadsheet" dismissively — these are smart people making it work with what they have.

### Slide 6: Lakehouse Stack
- "PI feeds in via Zerobus — no Kafka, no middleware."
- "GIS data can come via Auto Loader — drop Parquet/CSV/GeoJSON files."
- "SAP/CMMS via Lakeflow Connect or scheduled batch."
- "All land in YOUR Azure storage account. Open format. You own the files."

### When Running Steps 4-6 Live (Silver)
- Step 4 (parsed_tags): "Watch the tag_path become asset_id + signal. This is the parsing you all do in pandas — but done once, in the platform."
- Step 5 (aggregated_tags): "162K rows/min → 1,350 rows/min. 99% reduction. This is what makes fleet-wide queries fast."
- Step 6 (enriched_tags): "thermal/rack_temp_c becomes 'Rack Temperature' in °C. This is your PI AF metadata — but in SQL."

### Slide 33b: PI AF Replacement
- "PI AF is great for navigating one site's real-time data. Operators still need PI Vision."
- "What we're replacing is the gap between PI AF and everything else."
- "Silver enrichment gives you the same hierarchy — but across all sources, fleet-wide, queryable by SQL and Genie."
- Don't position as "PI AF is bad" — position as "PI AF is per-site, UC metadata is fleet-wide."

### When Someone Mentions GIS
- "Your GIS data is a perfect silver enrichment join."
- "Asset health (OT) + asset location (GIS) = spatial risk."
- "'Show me unhealthy assets within 50km of a forecast high-temp zone' — that's a gold-layer join neither PI nor ESRI can do alone."
- If they push on GIS: "H3 spatial indexing works natively on Delta tables. Happy to do a follow-up on the geospatial pattern."

### Slide 41b: Data Products
- Reference their enterprise pattern: "Source-aligned products per domain — PI data, GIS data, CMMS data. Consumer-aligned products in gold — health_scores for ops, revenue_risk for trading."
- "The contract is: schema, quality expectations, column descriptions. All already in the pipeline."
- "The difference from 'tables in a database' is governance: who owns it, what's the SLA, who can access it."

### Slide 41c: Genie
- Run COMMENT ON live — "30 seconds of SQL to add descriptions."
- Show the information_schema query — "Genie reads these to understand your data."
- If Genie room is set up: ask "which assets are at risk?" in natural language.
- If not: "An operator can now ask this question in English instead of navigating PI AF trees."

---

## Parking Lot Responses

Use these to acknowledge and defer without losing time:

| Topic | Response |
|-------|----------|
| PII handling | "There's a dedicated catalog isolation pattern for PII with row filtering and column masking. I have a deck on that — let's do a follow-up." |
| Data Vault / Kimball in silver | "Both valid. Your enhanced medallion supports dual-track silver — curation for ML, integration for DWH. Today is the curation path. Happy to whiteboard the integration track." |
| Synapse migration | "Lakebridge handles T-SQL conversion. Separate conversation focused on the corporate data side — today is OT." |
| Real-time latency | "The pipeline is streaming — sub-minute latency. PI still owns real-time ops monitoring. This is for analytical decisions that need cross-domain data." |
| Cost / pricing | "Happy to do a sizing exercise after — it depends on data volumes and compute patterns. Today let's focus on what the architecture looks like, then we can model cost." |
| Multi-cloud (Azure + AWS) | "Unity Catalog governs across both clouds. Delta Sharing moves data between them without copying. Separate deep-dive topic." |
| Code gen / AI-assisted development | "Databricks Assistant generates SQL and Python in notebooks. MLflow handles model lifecycle. Worth a separate session focused on the data science workflow." |
| Change management / standards | "UC provides the guardrails — schema enforcement, expectations, access controls, lineage. The medallion layers ARE the standard. Bronze = raw truth, silver = trusted, gold = published. That's your change management framework." |

---

## The ROI Question (if it comes up)

> "How many engineer-hours per week does your team spend extracting data from PI, joining it with other sources, and preparing it for analysis on laptops?"

If the answer is 5-10 hours per person across a 10-person team:
- That's 50-100 hours/week of manual integration
- ~$150-300K/year of engineering time on CSV gymnastics
- The medallion architecture automates this once, makes it governed, and frees those engineers to do actual analysis

---

## Fallback Plan

If a live SQL step fails (permissions, timeout, data issue):
1. Don't troubleshoot live. Say: "Let me show you the result from our earlier setup."
2. Switch to querying the pre-populated table (from `make workshop-setup` backup).
3. The query results are identical — only the live creation differs.
4. Move on. Fix the issue at the break.

---

## Files Reference

| File | Purpose |
|------|---------|
| `workshop/setup_medallion.sql` | Steps 1-9, run live in SQL editor |
| `workshop/demo_queries.sql` | Queries organized by slide section |
| `workshop/transformations/medallion_pipeline.py` | Lakeflow SDP pipeline code (show on screen) |
| `medallion_architecture_workshop.html` | Slide deck (50 slides) |
