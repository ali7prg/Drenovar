const {chromium} = require('playwright');
(async () => {
  const files = process.argv[2];
  const out = process.argv[3];
  const browser = await chromium.launch({args: ['--use-gl=angle', '--use-angle=swiftshader', '--ignore-gpu-blocklist']});
  const page = await browser.newPage({viewport: {width: 1600, height: 460}});
  const errors = [];
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') errors.push(m.text()); });
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto('http://127.0.0.1:8765/index.html?files=' + files);
  await page.waitForFunction(() => document.title === 'DONE', null, {timeout: 600000});
  const report = await page.evaluate(() => window.__report);
  await page.screenshot({path: out + '.png'});
  require('fs').writeFileSync(out + '.json', JSON.stringify({three: 'r171', errors, report}, null, 1));
  console.log(JSON.stringify(report.map(r => ({file: r.file, ok: r.ok, clips: r.clips, bones: r.bones, unbound: r.unbound, independent: r.independent, error: r.error}))));
  console.log('console errors/warnings:', errors.length, errors.slice(0, 5));
  await browser.close();
})();
