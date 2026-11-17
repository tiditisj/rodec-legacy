import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://legacy.rodec.com',
  trailingSlash: 'ignore',
  build: { format: 'directory' },
});
