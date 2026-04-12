import { Link } from 'react-router-dom';
import { useState } from 'react';
import deltaLogo from '../default/delta.png';
import livingIntelligence from '../default/living_intelligence.png';

const ignitionLogo =
  'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="112" height="32"><rect width="112" height="32" rx="6" fill="%23259BD7"/><text x="56" y="21" font-size="13" text-anchor="middle" fill="white" font-family="Arial">Ignition</text></svg>';
const databricksLogo =
  'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="128" height="32"><rect width="128" height="32" rx="6" fill="%23FF3621"/><text x="64" y="21" font-size="13" text-anchor="middle" fill="white" font-family="Arial">Databricks</text></svg>';

/* ------------------------------------------------------------------ */
/*  Data: Session sections with questions and answers                  */
/* ------------------------------------------------------------------ */

interface Question {
  id: string;
  question: string;
  answer: string;
}

interface SessionSection {
  number: number;
  title: string;
  subtitle: string;
  time: string;
  color: string;
  demoLink?: { to: string; label: string };
  questions: Question[];
}

const sections: SessionSection[] = [
  {
    number: 1,
    title: 'Ingestion & Pipelines',
    subtitle: 'How data gets into Databricks and moves through the platform',
    time: '8 min',
    color: 'blue',
    demoLink: { to: '/dashboard', label: 'See live ingest dashboard' },
    questions: [
      {
        id: 'Q13',
        question: 'What are the common methods for ingesting data into Databricks?',
        answer:
          'Lakeflow Connect provides fully managed, serverless connectors for SaaS apps (Salesforce, ServiceNow, HubSpot, Zendesk, NetSuite) and databases (SQL Server, PostgreSQL, MySQL) with automatic CDC and schema evolution. Auto Loader incrementally processes new files from cloud storage (S3, ADLS, GCS) with schema inference. Structured Streaming natively supports Kafka, Kinesis, and Pub/Sub, while Zerobus provides direct gRPC streaming for OT/IIoT workloads without requiring Kafka infrastructure.',
      },
      {
        id: 'Q14',
        question: 'How does Databricks handle streaming vs. batch ingestion?',
        answer:
          'Databricks unifies batch and streaming through Structured Streaming — the same Spark API handles both, processing data incrementally with exactly-once guarantees and checkpoint-based fault tolerance. Lakeflow Declarative Pipelines builds on this by letting you declare streaming tables (continuously updated) and materialized views (batch-recomputed) in the same pipeline with built-in quality expectations, autoscaling, and monitoring.',
      },
      {
        id: 'Q15',
        question: 'What is Auto Loader and how does it work?',
        answer:
          'Auto Loader is a Structured Streaming source (cloudFiles) that incrementally processes new files arriving in cloud storage across JSON, CSV, XML, Parquet, Avro, ORC, text, and binary formats. It offers two file detection modes: directory listing (periodic scans) and file notification (cloud-native event services like SNS/SQS or Event Grid for lower cost at scale). Schema inference, evolution, and a rescued data column ensure no data is lost to drift, while a RocksDB checkpoint guarantees exactly-once processing across billions of files.',
      },
      {
        id: 'Q16',
        question: 'How do we ingest from cloud storage, databases, and APIs?',
        answer:
          'Cloud storage: Auto Loader incrementally ingests files from S3, ADLS, or GCS with automatic schema inference. Databases: Lakeflow Connect provides managed CDC pipelines for SQL Server, PostgreSQL, and MySQL (including on-premises via Direct Connect) with automatic schema evolution. SaaS APIs: Lakeflow Connect offers managed connectors for Salesforce, ServiceNow, HubSpot, and more. Lakehouse Federation pushes queries to external databases (Oracle, Snowflake, BigQuery, Redshift) via JDBC without migrating data.',
      },
    ],
  },
  {
    number: 2,
    title: 'Data Quality & Schema Management',
    subtitle: 'Validate, monitor, and evolve your data as sources change',
    time: '8 min',
    color: 'green',
    demoLink: { to: '/dashboard', label: 'See Lakeflow expectations in the pipeline' },
    questions: [
      {
        id: 'Q1',
        question: 'What out-of-the-box data quality features does Databricks offer?',
        answer:
          'Lakeflow Declarative Pipelines provide built-in expectations (EXPECT, EXPECT OR DROP, EXPECT OR FAIL) that validate every row and track pass/fail metrics over time in the pipeline event log. Lakehouse Monitoring creates automatic data quality monitors at the table level — tracking null rates, distinct counts, distribution drift, and freshness — with results stored in metric tables you can alert on. Delta Lake enforces CHECK constraints, NOT NULL constraints, and primary/foreign key declarations at the storage layer.',
      },
      {
        id: 'Q2',
        question: 'How do we validate and monitor data quality over time?',
        answer:
          'Lakehouse Monitoring attaches to any managed table and automatically profiles each column on a configurable schedule, storing time-series metrics (nulls, drift, volume, freshness) in a companion Delta table you can query or alert on. Lakeflow pipeline expectations generate a continuous pass/fail record in the event log with per-expectation row counts, visible in the pipeline UI. For custom rules, combine these with SQL-based data quality dashboards in Databricks AI/BI or set up alerts via SQL alert destinations.',
      },
      {
        id: 'Q3',
        question: 'How do we handle source data changes and schema drift?',
        answer:
          'Auto Loader\'s schemaEvolutionMode (addNewColumns, rescue, failOnNewColumns, none) automatically detects new fields or type changes in incoming files, optionally adding columns to the target or routing unexpected data to a _rescued_data column for inspection. Delta Lake\'s mergeSchema option allows writes to add new columns on the fly, while column mapping (delta.columnMapping.mode) enables renaming or dropping columns as metadata-only operations without rewriting data.',
      },
      {
        id: 'Q12',
        question: 'What about schema evolution and data contracts?',
        answer:
          'Delta Lake supports additive schema evolution via mergeSchema and overwriteSchema, column mapping for safe renames and drops, and type widening (e.g., INT to BIGINT, FLOAT to DOUBLE) without data rewrites. CHECK constraints and NOT NULL enforce invariants at write time — any violating write is rejected atomically. Lakeflow expectations enforce pipeline-level contracts with row-level granularity (warn, drop, or fail). Primary and foreign key declarations provide logical contracts for downstream query optimisation and lineage.',
      },
    ],
  },
  {
    number: 3,
    title: 'Lakehouse Zoning & Dev/Test/Prod',
    subtitle: 'Bronze/Silver/Gold layers, environment isolation, and deployment',
    time: '6 min',
    color: 'blue',
    demoLink: { to: '/architecture', label: 'See architecture comparison' },
    questions: [
      {
        id: 'Q11',
        question: 'What is Bronze/Silver/Gold?',
        answer:
          'The medallion architecture organises a lakehouse into three layers of increasing quality: Bronze stores raw data as-is from source systems preserving full fidelity (raw_tags, bom_raw_observations), Silver performs cleaning, validation, and deduplication for an enterprise-consistent view (validated observations, parsed throughput), and Gold delivers highly aggregated, business-aligned tables optimised for dashboards and ML (health_scores, revenue_risk, market_snapshot).',
      },
      {
        id: 'Q5',
        question: 'How do we isolate dev, test, and production environments?',
        answer:
          'Unity Catalog workspace-catalog binding restricts which catalogs are accessible from which workspaces — setting a catalog\'s isolation mode to ISOLATED ensures production data is only accessible from production workspaces, even if a user has table-level permissions. Read-only bindings let developers query production data from dev workspaces without write access. Combined with separate catalogs per environment (dev_catalog, prod_catalog) and UC grants, this provides full data-layer isolation.',
      },
      {
        id: 'Q6',
        question: 'How do we deploy and promote between environments?',
        answer:
          'Databricks Asset Bundles (DABs) define targets (dev, staging, production) in databricks.yml, each with its own workspace and resource overrides. Development mode auto-prefixes resource names and pauses schedules for safe iteration, while production mode enforces Git branch validation, service principal run-as identity, and prevents cluster overrides. Promotion is done via databricks bundle deploy -t <target> triggered from CI/CD pipelines (GitHub Actions, Azure DevOps), ensuring reproducible, source-controlled deployments.',
      },
    ],
  },
  {
    number: 4,
    title: 'Storage, Retention & Backup',
    subtitle: 'Time travel, data lifecycle, and disaster recovery',
    time: '6 min',
    color: 'green',
    questions: [
      {
        id: 'Q8',
        question: 'How does historical data access work?',
        answer:
          'Delta Lake provides built-in time travel: query any previous table state with SELECT * FROM table VERSION AS OF <version> or TIMESTAMP AS OF \'<timestamp>\'. Every write creates a new version recorded in the transaction log (viewable with DESCRIBE HISTORY), retained for 30 days by default. Data files are retained for 7 days by default (delta.deletedFileRetentionDuration). RESTORE TABLE reverts a table to a prior version as a logged, reversible transaction.',
      },
      {
        id: 'Q7',
        question: 'What about retention policies and storage tiering?',
        answer:
          'Delta Lake has two configurable retention properties: delta.deletedFileRetentionDuration (default 7 days) controls how long deleted data files are kept before VACUUM can remove them, and delta.logRetentionDuration (default 30 days) controls transaction log history. Storage tiering (hot/cool/archive) is managed at the cloud provider level (Azure Blob lifecycle, S3 Intelligent-Tiering). Predictive Optimisation automatically runs VACUUM to remove stale files, managing storage costs without manual intervention.',
      },
      {
        id: 'Q9',
        question: 'Does data automatically move to cheaper storage?',
        answer:
          'Databricks does not automatically tier data to cheaper storage classes within Delta Lake itself. However, Predictive Optimisation (available on Unity Catalog managed tables) automatically runs OPTIMIZE, VACUUM, and ANALYZE on serverless compute — compacting small files, removing unreferenced data beyond retention, and updating statistics. For cloud-level tiering (e.g., moving old Parquet files to S3 Glacier or Azure Cool), configure storage lifecycle policies at the cloud provider level.',
      },
      {
        id: 'Q17',
        question: 'What are the backup and recovery options?',
        answer:
          'Time travel + RESTORE TABLE lets you query or roll back to any version within the retention window. Deep Clone (CREATE TABLE target CLONE source) creates a full independent copy of data and metadata — recommended as the primary backup mechanism for cross-region disaster recovery. Shallow Clone creates a metadata-only copy for cheap dev/test environments. For enterprise DR, Databricks recommends active-passive workspace deployment with deep clones replicated to a secondary region.',
      },
    ],
  },
  {
    number: 5,
    title: 'Security, Power BI & Integration',
    subtitle: 'Access control, BI connectivity, and connecting external systems',
    time: '6 min',
    color: 'blue',
    demoLink: { to: '/analytics', label: 'See the Databricks App dashboard' },
    questions: [
      {
        id: 'Q10',
        question: 'How does access control work?',
        answer:
          'Unity Catalog provides a hierarchical privilege model where permissions inherit downward from Catalog \u2192 Schema \u2192 Table, managed via SQL GRANT/REVOKE statements. For fine-grained security, row filters restrict which rows a user can see, and column masks transform sensitive values at query time — both implemented as SQL UDFs and enforced seamlessly across notebooks, SQL warehouses, and dashboards. Full audit logging and automatic column-level lineage are built in.',
      },
      {
        id: 'Q4',
        question: 'How does Databricks improve Power BI performance?',
        answer:
          'Power BI connects via a native connector targeting serverless SQL warehouses that provide instant startup, intelligent auto-scaling, and fully managed infrastructure with no capacity tuning required. Serverless warehouses are powered by the Photon vectorised query engine (written in C++), significantly accelerating SQL and BI workloads compared to traditional Spark execution. Unity Catalog metric views via BI compatibility mode, service principal OAuth authentication, and Partner Connect for one-click setup further streamline the enterprise BI workflow.',
      },
      {
        id: 'Q19',
        question: 'What is Delta Sharing and how do Delta tables work?',
        answer:
          'Delta tables are built on Delta Lake, which extends Parquet files with a file-based transaction log providing ACID transactions, time travel, schema enforcement and evolution, and unified batch-plus-streaming processing on a single copy of data. Delta Sharing is an open protocol for secure cross-organisation data sharing — providers share live, read-only access to tables without copying data, and recipients consume it using any platform (Spark, pandas, Power BI, Snowflake) regardless of their computing environment, with row/column-level filtering and audit logging via Unity Catalog.',
      },
      {
        id: 'Q22',
        question: 'How do we connect to web apps, SQL databases, and analytics tools?',
        answer:
          'Databricks Apps lets you deploy custom web applications (Streamlit, Dash, Gradio, React, Express) directly within a workspace on serverless infrastructure, with built-in OAuth authentication and governed access to Unity Catalog data. Lakehouse Federation enables live queries against external databases (SQL Server, PostgreSQL, Oracle, Snowflake, BigQuery) through Unity Catalog foreign catalogs without migrating data. For BI tools, native ODBC/JDBC drivers connect Power BI, Tableau, and Excel to serverless SQL warehouses, while Lakebase offers managed PostgreSQL-compatible transactional databases for low-latency operational workloads.',
      },
    ],
  },
  {
    number: 6,
    title: 'ML, Data Science & AI',
    subtitle: 'Feature engineering, experiment tracking, and AI agents',
    time: '7 min',
    color: 'green',
    demoLink: { to: '/analytics', label: 'See health scores and revenue risk' },
    questions: [
      {
        id: 'Q18',
        question: 'How does feature engineering work?',
        answer:
          'Databricks Feature Engineering in Unity Catalog lets you create, store, and serve feature tables as governed Delta tables with primary keys. Features are defined using Python or SQL transformations, automatically tracked with lineage, and can be served online via Feature Serving endpoints for millisecond-latency real-time inference. Point-in-time lookups prevent data leakage during training, and on-demand features compute at inference time without pre-materialisation.',
      },
      {
        id: 'Q20',
        question: 'How do we track experiments and version models?',
        answer:
          'MLflow, natively integrated into Databricks, tracks experiments by automatically logging parameters, metrics, and artifacts for each run with side-by-side comparison. Models are versioned and governed through the Unity Catalog Model Registry, which provides model lineage, stage transitions (Staging \u2192 Production), access controls, and deployment metadata across workspaces. One-click deploy to serverless model serving endpoints with auto-scaling and built-in monitoring via inference tables.',
      },
      {
        id: 'Q21',
        question: 'How do we compute derived signals like rolling averages and trends?',
        answer:
          'Spark SQL window functions (AVG OVER with ROWS BETWEEN or RANGE BETWEEN) compute rolling averages, trends, and ranked signals within Lakeflow Declarative Pipelines, running incrementally on streaming or batch Delta tables. Structured Streaming stateful aggregations handle real-time windowed computations. Pandas UDFs (applyInPandas) enable complex per-group transforms at scale, while Feature Store sliding windows ensure point-in-time correct features for ML training.',
      },
      {
        id: 'Q23',
        question: 'How do we run time-series ML at scale across many assets?',
        answer:
          'The Many Models pattern uses pandas UDFs (applyInPandas) to group by asset_id and train independent models per asset in parallel across a Spark cluster — wrapping libraries like Prophet, statsmodels, or custom PyTorch models with MLflow tracking per asset. Databricks AutoML also supports time-series forecasting with one-click Prophet, ARIMA, and DeepAR across multiple series. Feature Store time-series keys ensure correct point-in-time lookups across years of history.',
      },
      {
        id: 'Q24',
        question: 'What AI agent capabilities are available?',
        answer:
          'Mosaic AI Agent Framework provides tools for building, evaluating, and deploying compound AI agents that can use retrieval (Vector Search), function calling (Unity Catalog tools/functions), and chain-of-thought reasoning, deployed as Model Serving endpoints with built-in monitoring via inference tables. Genie provides natural-language-to-SQL agents for business users to query curated table sets conversationally. Databricks Apps lets you deploy custom web UIs (Streamlit, Dash, React) with full workspace access on serverless infrastructure.',
      },
    ],
  },
];

const demoStops = [
  {
    to: '/dashboard',
    number: '01',
    title: 'Live ingest dashboard',
    talk: 'See ~2,700 events/sec streaming from 5 sites into Delta tables. SDT compression, latency, active assets \u2014 directly from Ignition via Zerobus gRPC.',
  },
  {
    to: '/analytics',
    number: '02',
    title: 'Fleet health & revenue risk',
    talk: 'Which assets are at risk, and how much revenue is exposed in the next high-price market window. Z-score anomaly detection + revenue modelling.',
  },
  {
    to: '/market-weather',
    number: '03',
    title: 'NEM market & BOM weather',
    talk: 'Live AEMO and Bureau of Meteorology data flowing through the same Lakeflow pipeline. No pre-staged CSVs.',
  },
  {
    to: '/assets',
    number: '04',
    title: 'Fleet visibility',
    talk: '20 BESS units across 5 sites. Click into any asset for tag-level trends: SoC%, active power, rack temperatures.',
  },
  {
    to: '/compression',
    number: '05',
    title: 'Compression deep dive',
    talk: 'SDT at the connector, then Delta columnar on top. Adjust deviation thresholds and see the impact on data volume.',
  },
  {
    to: '/performance',
    number: '06',
    title: 'Performance & scaling',
    talk: 'Scaling calculator: what happens at 20, 50, 100 sites. Zerobus scales horizontally with multi-stream.',
  },
  {
    to: '/architecture',
    number: '07',
    title: 'Architecture comparison',
    talk: '8+ traditional components collapse into 5 Lakehouse components. Hours to onboard, not weeks.',
  },
];

/* ------------------------------------------------------------------ */
/*  Styling helpers                                                    */
/* ------------------------------------------------------------------ */

const sectionColors: Record<string, { accent: string; bg: string; badge: string; border: string }> = {
  blue: {
    accent: 'text-databricks-primary',
    bg: 'bg-databricks-primary/5',
    badge: 'bg-databricks-primary text-white',
    border: 'border-databricks-primary/20',
  },
  green: {
    accent: 'text-brand-green',
    bg: 'bg-brand-green/5',
    badge: 'bg-brand-green text-white',
    border: 'border-brand-green/20',
  },
};

/* ------------------------------------------------------------------ */
/*  Components                                                         */
/* ------------------------------------------------------------------ */

function QuestionCard({ q }: { q: Question }) {
  const [open, setOpen] = useState(false);
  return (
    <button
      type="button"
      onClick={() => setOpen((v) => !v)}
      className="w-full text-left bg-surface-card border border-gray-200 rounded-card p-4 shadow-card hover:shadow-card-hover transition-all duration-200 cursor-pointer"
    >
      <div className="flex items-start gap-3">
        <span className="shrink-0 inline-flex items-center justify-center w-8 h-8 rounded-full bg-gray-100 text-xs font-bold text-gray-600">
          {q.id}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <h4 className="font-heading text-sm font-semibold text-gray-900 leading-snug">
              {q.question}
            </h4>
            <span className="shrink-0 text-gray-400 text-sm select-none mt-0.5">
              {open ? '\u25B2' : '\u25BC'}
            </span>
          </div>
          {open && (
            <p className="text-sm text-gray-600 leading-relaxed mt-2">{q.answer}</p>
          )}
        </div>
      </div>
    </button>
  );
}

function SectionBlock({ section }: { section: SessionSection }) {
  const c = sectionColors[section.color];
  return (
    <section className="mb-10">
      <div className={`rounded-card ${c.bg} border ${c.border} px-6 py-5 mb-4`}>
        <div className="flex items-center gap-3 mb-2">
          <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold ${c.badge}`}>
            {section.number}
          </span>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h2 className={`font-heading text-lg font-bold ${c.accent}`}>
                {section.title}
              </h2>
              <span className="text-xs text-gray-400 font-medium">{section.time}</span>
            </div>
            <p className="text-sm text-gray-600">{section.subtitle}</p>
          </div>
        </div>
        {section.demoLink && (
          <Link
            to={section.demoLink.to}
            className={`inline-block text-sm font-medium ${c.accent} mt-1 hover:underline`}
          >
            {section.demoLink.label} &rarr;
          </Link>
        )}
      </div>
      <div className="space-y-3 pl-2">
        {section.questions.map((q) => (
          <QuestionCard key={q.id} q={q} />
        ))}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Main page                                                          */
/* ------------------------------------------------------------------ */

export default function Landing() {
  return (
    <div className="max-w-4xl mx-auto">
      {/* ============================================================ */}
      {/*  Hero                                                         */}
      {/* ============================================================ */}
      <section className="mb-10 relative rounded-card overflow-hidden bg-gradient-to-br from-surface-canvas via-surface-canvas to-databricks-teal/5 px-6 py-8">
        <div className="flex items-center gap-4 mb-4">
          <img src={ignitionLogo} alt="Ignition" className="h-8 w-auto object-contain" />
          <img src={databricksLogo} alt="Databricks" className="h-8 w-auto object-contain" />
        </div>
        <p className="text-sm font-semibold text-databricks-primary tracking-wider uppercase mb-2">
          Databricks 101 &middot; Your questions, answered
        </p>
        <h1 className="font-heading text-4xl font-bold text-gray-900 leading-tight mb-4">
          Databricks for
          <br />
          <span className="text-databricks-primary">OT & Energy</span>
        </h1>
        <p className="text-lg text-gray-600 leading-relaxed max-w-2xl mb-4">
          This session walks through the 24 questions your team submitted,
          from ingestion and data quality to ML and AI agents, with a live
          demo running three real data sources through a Lakeflow pipeline.
        </p>
        <p className="text-sm text-gray-500">
          45 minutes &middot; 6 topic sections &middot; 24 questions &middot; live demo throughout
        </p>
      </section>

      {/* ============================================================ */}
      {/*  Living Intelligence Platform                                 */}
      {/* ============================================================ */}
      <section className="mb-10">
        <h2 className="font-heading text-sm font-semibold text-gray-500 tracking-wider uppercase mb-4">
          The big picture
        </h2>
        <div className="bg-surface-card border border-gray-200 rounded-card p-5 shadow-card space-y-4">
          <blockquote className="border-l-2 border-gray-300 pl-4 italic text-gray-500 text-sm">
            &ldquo;Intelligence that continuously senses, learns, and acts in the real
            world, not just reports on it.&rdquo;
            <span className="block text-xs not-italic mt-1 text-gray-400">
              <em>Living Intelligence</em>, Harvard Business Review 2025
            </span>
          </blockquote>

          {/* Insight → Decision → Action flow */}
          <div className="flex items-center justify-center gap-2 py-3">
            <span className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-sky-50 border border-sky-200">
              <span className="w-2 h-2 rounded-full bg-sky-500" />
              <span className="text-sm font-semibold text-sky-700">Insight</span>
            </span>
            <span className="text-gray-300 text-lg select-none">&rarr;</span>
            <span className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-amber-50 border border-amber-200">
              <span className="w-2 h-2 rounded-full bg-amber-500" />
              <span className="text-sm font-semibold text-amber-700">Decision</span>
            </span>
            <span className="text-gray-300 text-lg select-none">&rarr;</span>
            <span className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-green-50 border border-green-200">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              <span className="text-sm font-semibold text-green-700">Action</span>
            </span>
          </div>

          <img
            src={livingIntelligence}
            alt="Databricks Living Intelligence Platform — from open data lakehouse through governance, intelligence platform, intelligent apps, to real-world outcomes"
            className="w-full rounded-lg"
          />
          <p className="text-xs text-gray-400 text-center italic">
            Not an official Databricks architecture.
            Everything in today's demo maps to a layer in this stack.
          </p>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  Before / After comparison                                    */}
      {/* ============================================================ */}
      <section className="mb-10 space-y-4">
        <h2 className="font-heading text-sm font-semibold text-gray-500 tracking-wider uppercase mb-2">
          What changes
        </h2>

        {/* --- BEFORE: Traditional historian stack --- */}
        <div className="bg-gray-50 border border-gray-200 rounded-card p-5 shadow-card">
          <p className="text-xs font-semibold text-gray-400 tracking-wider uppercase mb-3">
            Before: Traditional OT historian
          </p>
          <div className="flex items-center gap-2 overflow-x-auto pb-1">
            {['SCADA / PLCs', 'OPC Server', 'Historian\nInterface', 'Data\nArchive', 'Asset\nFramework', 'Visualisation\nServer', 'Manual\nExports', 'Corporate\nData Warehouse'].map((label, i) => (
              <div key={label} className="flex items-center gap-2 shrink-0">
                {i > 0 && <span className="text-gray-300 select-none">&rarr;</span>}
                <div className="rounded bg-gray-200 border border-gray-300 px-3 py-2 text-center min-w-[72px]">
                  <p className="text-[10px] font-medium text-gray-500 whitespace-pre-line leading-tight">{label}</p>
                </div>
              </div>
            ))}
          </div>
          <p className="text-xs text-gray-400 mt-3">
            8 components &middot; separate licenses &middot; batch only &middot; vertical scaling &middot; data copied at every step &middot; no metadata catalog
          </p>
        </div>

        {/* --- AFTER: Databricks Lakehouse --- */}
        <div className="bg-surface-card border-2 border-databricks-primary/30 rounded-card p-5 shadow-card">
          <p className="text-xs font-semibold text-databricks-primary tracking-wider uppercase mb-3">
            After: Databricks Lakehouse
          </p>
          <div className="grid grid-cols-[1fr_auto_1fr_auto_1fr] items-center gap-3">
            {/* Sources */}
            <div className="space-y-2">
              <p className="text-[10px] font-semibold text-gray-400 tracking-wider uppercase text-center">Sources</p>
              <div className="rounded-lg bg-sky-600 text-white px-3 py-2.5 text-center">
                <p className="text-xs font-semibold">Ignition OT</p>
                <p className="text-[10px] opacity-75">streaming</p>
              </div>
              <div className="rounded-lg bg-teal-700 text-white px-3 py-2.5 text-center">
                <p className="text-xs font-semibold">BOM Weather</p>
                <p className="text-[10px] opacity-75">batch</p>
              </div>
              <div className="rounded-lg bg-indigo-600 text-white px-3 py-2.5 text-center">
                <p className="text-xs font-semibold">NEM Market</p>
                <p className="text-[10px] opacity-75">batch</p>
              </div>
            </div>

            <div className="text-2xl text-gray-300 select-none">&rarr;</div>

            {/* Delta Lake */}
            <div className="space-y-2 text-center">
              <div className="flex items-center justify-center gap-1.5">
                <img src={deltaLogo} alt="Delta Lake" className="h-5 w-5" />
                <p className="text-xs font-bold text-[#00ADD4]">Delta Lake</p>
              </div>
              <div className="rounded-lg bg-amber-600/10 border border-amber-600/30 px-3 py-2">
                <p className="text-[10px] font-semibold text-amber-700">Bronze</p>
                <p className="text-[9px] text-gray-500">raw_tags, bom_raw, nem_prices</p>
              </div>
              <div className="text-gray-300 text-xs select-none">&darr;</div>
              <div className="rounded-lg bg-gray-100 border border-gray-300 px-3 py-2">
                <p className="text-[10px] font-semibold text-gray-600">Silver</p>
                <p className="text-[9px] text-gray-500">validated, parsed, enriched</p>
              </div>
              <div className="text-gray-300 text-xs select-none">&darr;</div>
              <div className="rounded-lg bg-yellow-500/10 border border-yellow-500/30 px-3 py-2">
                <p className="text-[10px] font-semibold text-yellow-700">Gold</p>
                <p className="text-[9px] text-gray-500">health_scores, market_snapshot</p>
              </div>
            </div>

            <div className="text-2xl text-gray-300 select-none">&rarr;</div>

            {/* Consumers */}
            <div className="space-y-2">
              <p className="text-[10px] font-semibold text-gray-400 tracking-wider uppercase text-center">Consumers</p>
              <div className="rounded-lg bg-blue-600 text-white px-3 py-2.5 text-center">
                <p className="text-xs font-semibold">AI/BI Dashboards</p>
                <p className="text-[10px] opacity-75">built-in</p>
              </div>
              <div className="rounded-lg bg-violet-600 text-white px-3 py-2.5 text-center">
                <p className="text-xs font-semibold">Genie Spaces</p>
                <p className="text-[10px] opacity-75">natural language</p>
              </div>
              <div className="rounded-lg bg-emerald-600 text-white px-3 py-2.5 text-center">
                <p className="text-xs font-semibold">Apps</p>
                <p className="text-[10px] opacity-75">custom frontends</p>
              </div>
            </div>
          </div>

          {/* Key differentiators */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mt-4 pt-3 border-t border-gray-100">
            <div className="text-center">
              <p className="text-xs font-semibold text-gray-700">Data lake</p>
              <p className="text-[10px] text-gray-400">acts like a database</p>
            </div>
            <div className="text-center">
              <p className="text-xs font-semibold text-gray-700">Schema + PK/FK</p>
              <p className="text-[10px] text-gray-400">enforced on every write</p>
            </div>
            <div className="text-center">
              <p className="text-xs font-semibold text-gray-700">Unity Catalog</p>
              <p className="text-[10px] text-gray-400">tags, descriptions, quality</p>
            </div>
            <div className="text-center">
              <p className="text-xs font-semibold text-gray-700">One codebase</p>
              <p className="text-[10px] text-gray-400">batch &amp; streaming</p>
            </div>
            <div className="text-center">
              <p className="text-xs font-semibold text-gray-700">Lakeflow</p>
              <p className="text-[10px] text-gray-400">orchestrator + lineage</p>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  Question sections                                            */}
      {/* ============================================================ */}
      <div className="mb-6">
        <h2 className="font-heading text-sm font-semibold text-gray-500 tracking-wider uppercase mb-2">
          Your questions by topic
        </h2>
        <p className="text-sm text-gray-500">
          Click any question to see the short answer. We'll cover each in detail during the session.
        </p>
      </div>

      {sections.map((s) => (
        <SectionBlock key={s.number} section={s} />
      ))}

      {/* ============================================================ */}
      {/*  Demo walkthrough                                             */}
      {/* ============================================================ */}
      <section className="mb-10">
        <h2 className="font-heading text-sm font-semibold text-gray-500 tracking-wider uppercase mb-4">
          Demo stops
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {demoStops.map((stop) => (
            <Link
              key={stop.number}
              to={stop.to}
              className="block bg-surface-card border border-gray-200 rounded-card p-4 shadow-card hover:shadow-card-hover hover:border-databricks-primary transition-all duration-200"
            >
              <div className="flex items-start gap-3">
                <span className="text-xl font-heading font-bold text-databricks-primary/40 select-none tabular-nums">
                  {stop.number}
                </span>
                <div className="flex-1">
                  <h3 className="font-heading text-sm font-semibold text-gray-900 mb-1">
                    {stop.title}
                  </h3>
                  <p className="text-xs text-gray-500 leading-relaxed">{stop.talk}</p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* ============================================================ */}
      {/*  Closing CTA                                                  */}
      {/* ============================================================ */}
      <section className="mb-10">
        <div className="bg-surface-card border border-databricks-teal rounded-card p-8 text-center shadow-card">
          <h2 className="font-heading text-xl font-semibold text-gray-900 mb-2">
            Ready to walk through it?
          </h2>
          <p className="text-sm text-gray-600 mb-6">
            Start with the live dashboard, then follow the demo stops in order.
          </p>
          <Link
            to="/dashboard"
            className="inline-block px-8 py-3 bg-databricks-primary text-white text-base font-semibold rounded-card shadow-card hover:bg-databricks-primary/90 hover:shadow-card-hover transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-databricks-primary focus-visible:ring-offset-2"
          >
            Start the demo
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="pt-8 pb-4 border-t border-gray-200 flex items-center justify-center gap-2 text-sm text-gray-500">
        <img src={ignitionLogo} alt="" className="h-5 w-auto object-contain" aria-hidden />
        <span className="text-ignition-blue font-medium">Databricks 101</span>
        <span>&middot;</span>
        <span>Powered by</span>
        <img src={databricksLogo} alt="" className="h-4 w-auto object-contain" aria-hidden />
        <span className="text-databricks-primary font-medium">Lakeflow Declarative Pipelines</span>
      </footer>
    </div>
  );
}
