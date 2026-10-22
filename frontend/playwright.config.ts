import {defineConfig} from '@playwright/test';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..');
export default defineConfig({
 testDir:'./e2e',workers:1,timeout:60000,reporter:'list',
 outputDir:'../output/playwright/test-results',
 use:{baseURL:'http://127.0.0.1:8876',headless:true,channel:process.env.MAIZI_BROWSER_CHANNEL||(process.platform==='darwin'?'chrome':undefined),viewport:{width:1280,height:900},trace:'retain-on-failure'},
 webServer:{command:(process.platform==='win32'?'.venv\\Scripts\\python.exe':'.venv/bin/python')+' -m maizi.launcher --strict-port --port 8876 --no-browser --data-dir .runtime/browser-'+Date.now(),cwd:root,url:'http://127.0.0.1:8876/api/health',reuseExistingServer:false,env:{LLM_API_KEY:'',LLM_MODEL:'',LLM_BASE_URL:''},timeout:30000}
});
