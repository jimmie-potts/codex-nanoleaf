const {chromium} = require('playwright');
const {spawn} = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const readline = require('node:readline');
const checks = require('../tests/browser_checks.cjs');
const root = path.resolve(__dirname, '..');

(async () => {
  const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  const child = spawn(python, ['-u', path.join(__dirname, 'demo.py'), '--port', '0'], {cwd: root, stdio: ['ignore', 'pipe', 'pipe']});
  let browser;
  try {
    const url = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(Error('Demo server startup timed out')), 15000);
      const finish = (error, value) => {clearTimeout(timer); error ? reject(error) : resolve(value)};
      child.once('error', error => finish(error));
      child.once('exit', code => finish(Error(`Demo exited with code ${code}`)));
      child.stderr.on('data', data => process.stderr.write(data));
      readline.createInterface({input: child.stdout}).once('line', line => {
        try {finish(null, JSON.parse(line).url)} catch (error) {finish(error)}
      });
    });
    const options = {headless: true};
    if (process.env.NANOLEAF_BROWSER_EXECUTABLE) options.executablePath = process.env.NANOLEAF_BROWSER_EXECUTABLE;
    browser = await chromium.launch(options);
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    fs.mkdirSync(path.join(root, 'test-results'), {recursive: true});
    try {
      await checks(page, new URL(url).port, root);
      const detail=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:2});
      await detail.goto(url);await detail.waitForSelector('#wall.prism-scene');
      await detail.waitForFunction(()=>window.wallAssembly?.snapshot()?.progress===1);
      for(const progress of [.05,.3,.65,1]){
        await detail.evaluate(value=>{prism.pause();prism.seek(value)},progress);
        await detail.screenshot({path:path.join(root,`test-results/prism-hidpi-${Math.round(progress*100)}.png`),fullPage:true});
      }
      await detail.close();
    }
    catch (error) {
      await page.screenshot({path:path.join(root,'test-results/prism-failure.png'),fullPage:true}).catch(()=>{});
      throw error;
    }
  } finally {
    if (browser) await browser.close();
    const stopped = new Promise(resolve => child.once('exit', resolve));
    if (child.exitCode === null && child.signalCode === null) {child.kill(); await stopped}
  }
})().catch(error => {console.error(error); process.exitCode = 1});
