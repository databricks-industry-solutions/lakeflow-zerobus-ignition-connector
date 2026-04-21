import { existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const envPath = resolve(__dirname, '..', '.env');

if (!existsSync(envPath)) {
  console.error('\x1b[31mError: .env file not found.\x1b[0m');
  console.error('Copy .env.example to .env and fill in your credentials:');
  console.error('  cp .env.example .env');
  process.exit(1);
}

console.log('\x1b[32m.env file found. Starting demo...\x1b[0m');
