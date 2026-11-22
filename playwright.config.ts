import { defineConfig } from '@playwright/test';
import { existsSync } from 'node:fs';

const chrome = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
export default defineConfig({
  testDir: './ui-tests', timeout: 45_000, workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:8000', viewport: { width: 1440, height: 1050 },
    launchOptions: existsSync(chrome) ? { executablePath: chrome } : {},
    screenshot: 'only-on-failure', trace: 'retain-on-failure' },
});
