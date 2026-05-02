/* sw.js — final dashboard redesign shell. Keeps data.json network-first. */

const CACHE = 'garage-v20260502-final-ui';
const SHELL = ['./', './index.html', './manifest.json', './img/truck-top.png', './img/hero-truck.png'];

const FINAL_STYLE = `
<meta name="theme-color" content="#02070c">
<style id="final-ui-redesign">
:root{--bg:#02070c;--card:#050b10;--tile:rgba(16,29,40,.98);--tile-2:rgba(255,255,255,.045);--line:rgba(190,207,222,.27);--line-2:rgba(221,234,245,.40);--cream:#eef5fb;--cream-2:#f7fbff;--white:#fff;--dim:#a7b1ba;--dim-2:#737e88;--amber:#ff981f;--amber-2:#ff981f;--green:#55df72;--warn:#e34a35}html,body{background:radial-gradient(circle at 50% 0%,rgba(46,64,78,.35),transparent 34%),#02070c!important}body{padding:max(env(safe-area-inset-top),12px) 10px max(env(safe-area-inset-bottom),16px)!important;color:#f7fbff!important}.card{max-width:430px!important;border-radius:24px!important;padding:0 16px 16px!important;background:linear-gradient(180deg,#060c12 0%,#03080d 100%)!important;border:1px solid rgba(210,225,240,.17)!important;box-shadow:0 28px 90px rgba(0,0,0,.78),inset 0 1px 0 rgba(255,255,255,.05)!important}.card:after{display:none!important}.hero{height:274px!important;margin:0 -16px -12px!important;background:radial-gradient(circle at 72% 39%,rgba(255,255,255,.12),transparent 33%),radial-gradient(circle at 58% 54%,rgba(95,105,112,.28),transparent 36%),linear-gradient(180deg,#090f15 0%,#05090d 100%)!important;border-top-left-radius:24px!important;border-top-right-radius:24px!important}.hero-flag{opacity:.20!important;filter:grayscale(.2) brightness(.45) contrast(1.12)!important}.hero-vignette{background:linear-gradient(180deg,rgba(0,0,0,0) 0%,rgba(0,0,0,.08) 64%,rgba(2,7,12,.96) 100%)!important}.hero-truck{right:-18px!important;top:77px!important;width:300px!important;max-width:74%!important;filter:brightness(1.48) saturate(.16) contrast(1.18) drop-shadow(0 18px 25px rgba(0,0,0,.8))!important}.hero-text{left:20px!important;top:34px!important;max-width:64%!important}.title{font-size:clamp(35px,10.8vw,48px)!important;line-height:.95!important;letter-spacing:-.055em!important;font-weight:900!important;text-shadow:0 3px 16px rgba(0,0,0,.74)!important}.sync{margin-top:20px!important;color:#c7ced5!important;font-size:16px!important;font-weight:600!important;letter-spacing:.21em!important}.sync:before{content:'';display:inline-block;width:12px;height:12px;margin-right:12px;border-radius:50%;background:#55df72;box-shadow:0 0 16px rgba(85,223,114,.55);vertical-align:-1px}.sync.stale:before{background:#e34a35;box-shadow:0 0 16px rgba(227,74,53,.45)}.final-hero-actions{position:absolute;right:16px;top:21px;display:flex;gap:14px;z-index:8}.final-icon-btn{width:52px;height:52px;border-radius:10px;border:1px solid rgba(205,220,232,.35);background:rgba(12,18,25,.58);color:#fff;display:grid;place-items:center;box-shadow:inset 0 1px 0 rgba(255,255,255,.07),0 8px 20px rgba(0,0,0,.35);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}.final-icon-btn svg{width:29px;height:29px}.grid{gap:12px!important}.tile{min-height:118px!important;border-radius:16px!important;padding:20px 16px!important;background:radial-gradient(circle at 25% 0%,rgba(255,255,255,.07),transparent 40%),linear-gradient(145deg,rgba(14,25,35,.98),rgba(4,11,17,.99))!important;border:1px solid rgba(221,234,245,.40)!important;box-shadow:inset 0 1px 0 rgba(255,255,255,.08),inset 0 -1px 0 rgba(0,0,0,.65),0 14px 30px rgba(0,0,0,.42)!important}.tile:after{display:none!important}.tile-label{color:#b5bdc5!important;font-size:14px!important;font-weight:600!important;letter-spacing:.26em!important}.tile-value{color:#fff!important;font-size:clamp(44px,12vw,64px)!important;letter-spacing:-.055em!important;font-weight:900!important}.tile-value.amber{color:#ff981f!important}.tile-sub{color:#a7afb7!important;font-size:18px!important}.tile-sub.healthy{color:#55df72!important}.tile-icon.amber{color:#ff981f!important}.tile-icon.green{color:#55df72!important}.fuel-arc{width:112px!important;height:82px!important}.fuel-arc-pct{font-size:32px!important;bottom:25px!important}.fuel-arc-label{font-size:20px!important;color:#a7afb7!important}.reset{margin-top:14px!important;border:1px solid rgba(255,152,31,.70)!important;color:#ff981f!important;background:rgba(255,152,31,.035)!important;padding:10px 24px!important;font-size:14px!important}.tires-corners{grid-template-columns:1fr 112px 1fr!important;gap:24px 25px!important}.truck-photo{width:112px!important;filter:drop-shadow(0 10px 20px rgba(0,0,0,.65))!important}.tire-pos{color:#aab2ba!important;font-size:18px!important;letter-spacing:.08em!important}.tire-num{font-size:42px!important;color:#fff!important;text-shadow:0 4px 12px rgba(0,0,0,.45)!important}.loc-place{color:#fff!important;font-size:30px!important;line-height:1!important;letter-spacing:-.04em!important}.loc-map{height:164px!important;border-radius:12px!important;border:1px solid rgba(205,220,232,.25)!important;background:#07131c!important}.loc-map iframe{filter:invert(92%) hue-rotate(170deg) saturate(.75) brightness(.45) contrast(1.25)!important}.loc-map:after{display:none!important}.loc-link,.loc-coords{background:rgba(0,0,0,.72)!important;color:#fff!important;border-color:rgba(205,220,232,.25)!important}.actions{gap:12px!important;border-top:none!important;padding-top:12px!important}.btn{min-height:86px!important;border-radius:12px!important;border:1px solid rgba(205,220,232,.38)!important;background:linear-gradient(180deg,rgba(255,255,255,.035),rgba(255,255,255,.005))!important;color:#fff!important;font-size:24px!important;letter-spacing:.22em!important;box-shadow:inset 0 1px 0 rgba(255,255,255,.08),0 10px 22px rgba(0,0,0,.33)!important}.btn[data-cmd='unlock']{color:#ff981f!important;border-color:rgba(255,152,31,.90)!important;box-shadow:inset 0 0 28px rgba(255,152,31,.11),0 0 24px rgba(255,152,31,.20)!important}.panel{background:#0b151e!important;border:1px solid rgba(190,207,222,.27)!important;border-radius:16px!important}.foot{color:#8e98a2!important;font-size:14px!important;border-top:1px solid rgba(205,220,232,.15)!important}.foot button{color:#a5aeb7!important;font-size:14px!important;text-decoration:none!important;text-transform:uppercase!important}@media(max-width:390px){body{padding-left:7px!important;padding-right:7px!important}.hero{height:260px!important}.hero-truck{width:264px!important;right:-22px!important;top:79px!important}.sync{font-size:14px!important}.tile{padding:16px 14px!important;min-height:110px!important}.tile-value{font-size:45px!important}.tile-sub{font-size:18px!important}.fuel-arc{width:108px!important}.btn{font-size:20px!important;min-height:76px!important}.foot,.foot button{font-size:12px!important}}
</style>`;

const FINAL_SCRIPT = `<script id="final-ui-script">
(function(){function r(){return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M21 12a9 9 0 0 1-15.3 6.4"/><path d="M3 12A9 9 0 0 1 18.3 5.6"/><path d="M18 2v5h-5"/><path d="M6 22v-5h5"/></svg>'}function g(){return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 15.5A3.5 3.5 0 1 0 12 8a3.5 3.5 0 0 0 0 7.5Z"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .58V20a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1-.58 1.7 1.7 0 0 0-1.88.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.58-1H4a2 2 0 1 1 0-4h.09a1.7 1.7 0 0 0 .58-1 1.7 1.7 0 0 0-.34-1.88l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.58V4a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 .58 1.7 1.7 0 0 0 1.88-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9c.25.34.45.68.58 1H20a2 2 0 1 1 0 4h-.09c-.13.32-.33.66-.51 1Z"/></svg>'}function go(){var h=document.querySelector('.hero');if(!h||document.querySelector('.final-hero-actions'))return;var w=document.createElement('div');w.className='final-hero-actions';w.innerHTML='<button class="final-icon-btn" id="finalRefresh" aria-label="Refresh">'+r()+'</button><button class="final-icon-btn" id="finalSettings" aria-label="Settings">'+g()+'</button>';h.appendChild(w);document.getElementById('finalRefresh').onclick=function(){var b=document.getElementById('refresh');b?b.click():location.reload()};document.getElementById('finalSettings').onclick=function(){var b=document.getElementById('settingsBtn');if(b)b.click()};var u=document.querySelector(".btn[data-cmd='unlock']");if(u)u.classList.add('primary')}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',go);else go();})();
</script>`;

function transformIndex(html) {
  if (!html || html.includes('final-ui-redesign')) return html;
  return html.replace('<meta name="theme-color" content="#08121a">', '<meta name="theme-color" content="#02070c">')
             .replace('</style>', FINAL_STYLE + '\n</style>')
             .replace('</body>', FINAL_SCRIPT + '\n</body>');
}

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});

function isDashboardShell(url) {
  return url.pathname.endsWith('/dashboard/') || url.pathname.endsWith('/dashboard/index.html') || url.pathname.endsWith('/garage-uconnect/dashboard/') || url.pathname.endsWith('/garage-uconnect/dashboard/index.html');
}

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);

  if (e.request.mode === 'navigate' || isDashboardShell(url)) {
    e.respondWith(fetch('./index.html', { cache: 'no-store' }).then((res) => res.text()).then((html) => new Response(transformIndex(html), { headers: { 'Content-Type': 'text/html; charset=UTF-8', 'Cache-Control': 'no-store' } })).catch(() => caches.match('./index.html').then((res) => res ? res.text() : '<!doctype html><title>Ram Truck 2500</title><body>Offline</body>').then((html) => new Response(transformIndex(html), { headers: { 'Content-Type': 'text/html; charset=UTF-8' } }))));
    return;
  }

  if (url.pathname.endsWith('data.json')) {
    e.respondWith(fetch(e.request).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(e.request, copy));
      return res;
    }).catch(() => caches.match(e.request)));
    return;
  }

  e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request)));
});
