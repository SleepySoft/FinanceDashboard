<template>
  <div id="app">
    <nav class="nav">
      <div class="nav-left">
        <router-link to="/" class="logo">Stock Analyst</router-link>
      </div>
      <div class="nav-links">
        <router-link to="/" class="nav-link">Dashboard</router-link>
        <router-link to="/requests" class="nav-link">请求池</router-link>
      </div>
    </nav>
    <main>
      <router-view />
    </main>
  </div>
</template>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0b1120; color: #e2e8f0; min-height: 100vh; }
#app { max-width: 1200px; margin: 0 auto; padding: 16px; }

.nav { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; margin-bottom: 20px; border-bottom: 1px solid #334155; }
.logo { font-size: 18px; font-weight: 700; color: #60a5fa; text-decoration: none; }
.nav-links { display: flex; gap: 20px; }
.nav-link { color: #94a3b8; text-decoration: none; font-size: 14px; padding: 4px 0; }
.nav-link.router-link-active { color: #60a5fa; border-bottom: 2px solid #60a5fa; }

.card { background: #151e2e; border: 1px solid #334155; border-radius: 10px; padding: 20px; margin-bottom: 16px; }
h3 { font-size: 15px; font-weight: 600; margin-bottom: 12px; }
input, textarea, select { background: #0f172a; border: 1px solid #475569; color: #e2e8f0; padding: 8px 12px; border-radius: 6px; font-size: 14px; outline: none; }
input:focus, textarea:focus, select:focus { border-color: #3b82f6; }
button { cursor: pointer; border: none; border-radius: 6px; font-size: 13px; padding: 8px 16px; transition: opacity 0.15s; }
button:disabled { opacity: 0.5; cursor: not-allowed; }
button.primary { background: #3b82f6; color: white; }
button.ghost { background: transparent; color: #94a3b8; border: 1px solid #475569; }
button.danger { background: #dc2626; color: white; }

.tag { display: inline-block; padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: 500; }
.tag-green { background: #064e3b; color: #34d399; }
.tag-yellow { background: #713f12; color: #fbbf24; }
.tag-red { background: #7f1d1d; color: #f87171; }
.tag-none { background: #334155; color: #94a3b8; }

@media (max-width: 640px) {
  #app { padding: 10px; }
  .nav { flex-direction: column; gap: 10px; align-items: stretch; }
  .nav-links { justify-content: center; }
}
</style>
