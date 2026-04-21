import { describe, it, expect } from 'vitest';
import { readFileSync } from 'fs';
import { resolve } from 'path';

describe('Root package.json', () => {
  const rootPkg = JSON.parse(
    readFileSync(resolve(import.meta.dirname, '../../../package.json'), 'utf-8'),
  );

  it('contains dev script', () => {
    expect(rootPkg.scripts).toHaveProperty('dev');
  });

  it('contains build script', () => {
    expect(rootPkg.scripts).toHaveProperty('build');
  });
});
