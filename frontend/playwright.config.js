import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests',use:{baseURL:'http://127.0.0.1:8000',headless:true,launchOptions:{executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox','--enable-unsafe-swiftshader']}},workers:1});
