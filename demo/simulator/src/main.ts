#!/usr/bin/env tsx
/**
 * CLI entry point - generates simulated tag events and sends them to an
 * Ignition Gateway's Zerobus HTTP ingest endpoint (POST /system/zerobus/ingest/batch).
 *
 * Usage:
 *   npx tsx src/main.ts --gateway http://localhost:8088 --scenario battery --assets 3
 *   npx tsx src/main.ts --gateway http://localhost:8088 --scenario wind --assets 5 --interval 1000
 *   npx tsx src/main.ts --gateway http://localhost:8088 --scenario mixed --assets 4
 *
 * Environment variables (overridden by CLI flags):
 *   IGNITION_GATEWAY_URL  - Gateway base URL (default http://localhost:8088)
 *   SIM_SCENARIO          - wind | battery | mixed (default mixed)
 *   SIM_ASSETS            - number of simulated assets (default 3)
 *   SIM_INTERVAL_MS       - tick interval in ms (default 1000)
 */

import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { TagValueGenerator } from './generator.js';
import type { TagProfileConfig, TagEvent } from './generator.js';
import { ZerobusPublisher } from './publisher.js';
import type { ZerobusClient } from './publisher.js';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AssetProfile {
  asset_type: string;
  description: string;
  tags: TagProfileConfig[];
}

interface SimConfig {
  gatewayUrl: string;
  scenario: 'wind' | 'battery' | 'mixed';
  assetCount: number;
  intervalMs: number;
}

// ---------------------------------------------------------------------------
// CLI argument parsing (zero-dep)
// ---------------------------------------------------------------------------

function parseArgs(): SimConfig {
  const args = process.argv.slice(2);

  function flag(name: string, fallback: string): string {
    const idx = args.indexOf(`--${name}`);
    if (idx !== -1 && idx + 1 < args.length) return args[idx + 1];
    return fallback;
  }

  const gatewayUrl =
    flag('gateway', '') ||
    process.env.IGNITION_GATEWAY_URL ||
    'http://localhost:8088';

  const scenario = (
    flag('scenario', '') ||
    process.env.SIM_SCENARIO ||
    'mixed'
  ) as SimConfig['scenario'];

  const assetCount = parseInt(
    flag('assets', '') || process.env.SIM_ASSETS || '3',
    10,
  );

  const intervalMs = parseInt(
    flag('interval', '') || process.env.SIM_INTERVAL_MS || '1000',
    10,
  );

  return { gatewayUrl, scenario, assetCount, intervalMs };
}

// ---------------------------------------------------------------------------
// Profile loader
// ---------------------------------------------------------------------------

function loadProfile(name: string): AssetProfile {
  const __dirname = dirname(fileURLToPath(import.meta.url));
  const path = resolve(__dirname, 'profiles', `${name}.json`);
  return JSON.parse(readFileSync(path, 'utf-8')) as AssetProfile;
}

// ---------------------------------------------------------------------------
// HTTP ingest client (POSTs to Ignition Gateway /system/zerobus/ingest/batch)
// ---------------------------------------------------------------------------

function createHttpIngestClient(gatewayUrl: string): ZerobusClient {
  const url = `${gatewayUrl.replace(/\/$/, '')}/system/zerobus/ingest/batch`;

  return {
    async send(records: Record<string, unknown>[]): Promise<void> {
      // Convert records to the ingest endpoint's expected format
      const payload = records.map((r) => ({
        tagPath: `[sim]${r.asset_id}/${r.tag_name}`,
        value: r.tag_value,
        quality: r.quality,
        timestamp: new Date(r.event_timestamp as string).getTime(),
        dataType: 'Float8',
      }));

      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const body = await resp.text().catch(() => '');
        throw new Error(
          `Ingest failed: ${resp.status} ${resp.statusText} - ${body}`,
        );
      }
    },
  };
}

// ---------------------------------------------------------------------------
// Simulation engine
// ---------------------------------------------------------------------------

interface SimulatedAsset {
  assetId: string;
  assetType: string;
  generators: TagValueGenerator[];
}

function buildAssets(
  config: SimConfig,
): { assets: SimulatedAsset[]; tagCount: number } {
  const profiles: AssetProfile[] = [];

  if (config.scenario === 'wind' || config.scenario === 'mixed') {
    profiles.push(loadProfile('wind-turbine'));
  }
  if (config.scenario === 'battery' || config.scenario === 'mixed') {
    profiles.push(loadProfile('battery-bess'));
  }

  const assets: SimulatedAsset[] = [];
  let tagCount = 0;

  for (let i = 0; i < config.assetCount; i++) {
    const profile = profiles[i % profiles.length];
    const prefix = profile.asset_type === 'wind_turbine' ? 'wind' : 'bess';
    const assetId = `${prefix}_site01_u${String(i + 1).padStart(2, '0')}`;

    const generators = profile.tags.map((t) => new TagValueGenerator(t));
    tagCount += generators.length;

    assets.push({
      assetId,
      assetType: profile.asset_type,
      generators,
    });
  }

  return { assets, tagCount };
}

function generateTick(assets: SimulatedAsset[]): TagEvent[] {
  const now = new Date();
  const events: TagEvent[] = [];

  for (const asset of assets) {
    for (const gen of asset.generators) {
      events.push(gen.next(asset.assetId, now));
    }
  }

  return events;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  const config = parseArgs();

  console.log('');
  console.log('=== Zerobus Tag Simulator ===');
  console.log(`  Gateway:   ${config.gatewayUrl}`);
  console.log(`  Scenario:  ${config.scenario}`);
  console.log(`  Assets:    ${config.assetCount}`);
  console.log(`  Interval:  ${config.intervalMs}ms`);
  console.log('');

  const { assets, tagCount } = buildAssets(config);
  console.log(
    `  Tags:      ${tagCount} (${assets.map((a) => a.assetId).join(', ')})`,
  );
  console.log('');

  const client = createHttpIngestClient(config.gatewayUrl);
  const publisher = new ZerobusPublisher({
    client,
    sdtCompDev: 1.0,
    sdtCompMax: 600,
    sdtCompMin: 1,
  });

  // Stats logging interval (every 10 seconds)
  const STATS_INTERVAL_MS = 10_000;
  let lastStatsTime = Date.now();
  let tickCount = 0;
  let totalSent = 0;
  let totalRaw = 0;

  console.log('[sim] Starting simulation... (Ctrl+C to stop)');
  console.log('');

  // Graceful shutdown
  let running = true;
  process.on('SIGINT', () => {
    console.log('\n[sim] Shutting down...');
    running = false;
  });
  process.on('SIGTERM', () => {
    running = false;
  });

  while (running) {
    const tickStart = Date.now();

    try {
      // Generate events for all assets/tags
      const events = generateTick(assets);
      totalRaw += events.length;

      // Push through SDT compression
      let archived = 0;
      for (const event of events) {
        if (publisher.publish(event)) {
          archived++;
        }
      }
      totalSent += archived;

      // Flush compressed events to the gateway
      await publisher.flush();

      tickCount++;

      // Periodic stats
      const now = Date.now();
      if (now - lastStatsTime >= STATS_INTERVAL_MS) {
        const elapsed = (now - lastStatsTime) / 1000;
        const rawPerSec = Math.round(totalRaw / elapsed);
        const sentPerSec = Math.round(totalSent / elapsed);
        const ratio =
          totalSent > 0 ? (totalRaw / totalSent).toFixed(1) : 'N/A';
        console.log(
          `[stats] ticks=${tickCount} raw/s=${rawPerSec} sent/s=${sentPerSec} ` +
            `ratio=${ratio}:1 total_raw=${totalRaw} total_sent=${totalSent}`,
        );
        lastStatsTime = now;
        totalRaw = 0;
        totalSent = 0;
        tickCount = 0;
        publisher.resetCounters();
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(`[sim] Error: ${msg}`);
      // Continue running - the gateway might be temporarily unavailable
    }

    // Sleep for the remainder of the interval
    const elapsed = Date.now() - tickStart;
    const sleepMs = Math.max(0, config.intervalMs - elapsed);
    if (sleepMs > 0 && running) {
      await new Promise((resolve) => setTimeout(resolve, sleepMs));
    }
  }

  // Final flush
  try {
    await publisher.flush();
  } catch {
    // Ignore errors during shutdown
  }

  publisher.logThroughput();
  console.log('[sim] Done.');
}

main().catch((err) => {
  console.error('Fatal:', err);
  process.exit(1);
});
