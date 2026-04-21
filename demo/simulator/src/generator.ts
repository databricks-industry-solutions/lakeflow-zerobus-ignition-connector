/**
 * Tag value generator - produces realistic time-series values
 * using configurable patterns: sinusoidal, step, random_walk, alarm.
 */

export interface TagEvent {
  eventTimestamp: Date;
  assetId: string;
  tagName: string;
  tagValue: number;
  quality: number;
}

export interface TagProfileConfig {
  name: string;
  unit: string;
  min: number;
  max: number;
  typical: number;
  noise_factor: number;
  update_frequency_ms: number;
  pattern: string;
  comp_dev: number;
  comp_dev_percent: number;
  comp_max_seconds: number;
  comp_min_seconds: number;
}

/** Legacy helper - kept for Phase 1 backward compat */
export function generateTagValue(
  min: number,
  max: number,
  noise: number,
): number {
  const mid = (min + max) / 2;
  const range = max - min;
  return mid + (Math.random() - 0.5) * range * noise;
}

/**
 * Generate a sinusoidal value within [min, max] with noise.
 * The period is ~100 ticks to simulate slow-varying analog signals.
 */
export function generateSinusoidal(
  min: number,
  max: number,
  noiseFactor: number,
  tick: number,
  period: number = 100,
): number {
  const mid = (min + max) / 2;
  const amplitude = (max - min) / 2;
  const base = mid + amplitude * Math.sin((2 * Math.PI * tick) / period);
  const noise = (Math.random() - 0.5) * (max - min) * noiseFactor;
  return Math.max(min, Math.min(max, base + noise));
}

/**
 * Generate a step function value. Returns the new value and the internal state.
 * Transitions happen randomly (~1% chance per tick), with optional drift.
 */
export function generateStep(
  min: number,
  max: number,
  currentState: number,
  _tick: number,
): { value: number; state: number } {
  const range = max - min;
  // ~1% chance of a step transition per tick
  if (Math.random() < 0.01) {
    // Jump to a new discrete level
    const levels = Math.max(2, Math.ceil(range / (range * 0.2)));
    const step = range / levels;
    const newLevel = min + Math.round(Math.random() * levels) * step;
    const clamped = Math.max(min, Math.min(max, newLevel));
    return { value: clamped, state: clamped };
  }
  // Small drift around current state
  const drift = (Math.random() - 0.5) * range * 0.001;
  const value = Math.max(min, Math.min(max, currentState + drift));
  return { value, state: value };
}

/**
 * Generate a random walk value within [min, max].
 * Steps are proportional to noiseFactor * range.
 */
export function generateRandomWalk(
  min: number,
  max: number,
  noiseFactor: number,
  previousValue: number,
): number {
  const range = max - min;
  const step = (Math.random() - 0.5) * range * noiseFactor;
  return Math.max(min, Math.min(max, previousValue + step));
}

/**
 * Generate an alarm value. Usually 0 (no alarm), occasionally spikes.
 */
export function generateAlarm(
  min: number,
  max: number,
): number {
  // 0.5% chance of alarm per tick
  if (Math.random() < 0.005) {
    return Math.floor(Math.random() * (max - min)) + min + 1;
  }
  return min; // No alarm
}

/**
 * TagValueGenerator - stateful generator that produces TagEvent values
 * for a single tag using its configured pattern.
 */
export class TagValueGenerator {
  private config: TagProfileConfig;
  private tick = 0;
  private state: number;

  constructor(config: TagProfileConfig) {
    this.config = config;
    this.state = config.typical;
  }

  /** Generate the next tag value event */
  next(assetId: string = 'default', timestamp?: Date): TagEvent {
    const value = this.generateValue();
    this.tick++;
    return {
      eventTimestamp: timestamp ?? new Date(),
      assetId,
      tagName: this.config.name,
      tagValue: value,
      quality: 192, // OPC Good
    };
  }

  private generateValue(): number {
    const { min, max, noise_factor, pattern } = this.config;

    switch (pattern) {
      case 'sinusoidal': {
        return generateSinusoidal(min, max, noise_factor, this.tick);
      }
      case 'step': {
        const result = generateStep(min, max, this.state, this.tick);
        this.state = result.state;
        return result.value;
      }
      case 'random_walk': {
        const value = generateRandomWalk(min, max, noise_factor, this.state);
        this.state = value;
        return value;
      }
      case 'alarm': {
        return generateAlarm(min, max);
      }
      default: {
        return generateSinusoidal(min, max, noise_factor, this.tick);
      }
    }
  }
}
