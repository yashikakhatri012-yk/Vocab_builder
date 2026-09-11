const menuButton = document.getElementById('menuButton');
const sidebar = document.getElementById('sidebar');
const overlay = document.getElementById('mobileOverlay');

function closeMenu() {
  sidebar?.classList.remove('open');
  overlay?.classList.remove('show');
  menuButton?.setAttribute('aria-expanded', 'false');
}

menuButton?.addEventListener('click', () => {
  const open = !sidebar?.classList.contains('open');
  sidebar?.classList.toggle('open', open);
  overlay?.classList.toggle('show', open);
  menuButton?.setAttribute('aria-expanded', String(open));
});
overlay?.addEventListener('click', closeMenu);

document.querySelectorAll('.sidebar .nav-link, .brand').forEach((link) => {
  link.addEventListener('click', () => {
    if (window.innerWidth <= 900) closeMenu();
  });
});

// Auto-dismiss feedback messages after a short delay.
document.querySelectorAll('.flash').forEach((flash) => {
  setTimeout(() => {
    flash.style.opacity = '0';
    flash.style.transform = 'translateY(-4px)';
    setTimeout(() => flash.remove(), 250);
  }, 4500);
});

// Keep the minimal mobile navigation usable without adding another CSS asset.
const mobileNavStyle = document.createElement('style');
mobileNavStyle.textContent = `
.skip-link{position:fixed;left:12px;top:12px;z-index:100;padding:9px 12px;background:#fff;color:#171922;border:1px solid #e7e8ed;border-radius:10px;transform:translateY(-150%);transition:transform .15s;font-size:12px;font-weight:800}
.skip-link:focus{transform:translateY(0)}
.mobile-nav{display:none}
@media(max-width:560px){
  .app-main{padding-bottom:82px}
  .mobile-nav{display:flex;position:fixed;z-index:30;left:10px;right:10px;bottom:10px;height:60px;background:rgba(255,255,255,.95);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);border:1px solid #e7e8ed;border-radius:18px;box-shadow:0 12px 30px rgba(20,22,35,.12);justify-content:space-around;align-items:center}
  .mobile-nav-link{width:25%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;color:#838999;text-decoration:none;font-size:16px;border-radius:14px}
  .mobile-nav-link small{font-size:9px;font-weight:800}
  .mobile-nav-link.active{color:#5b55e8;background:#f0efff}
}
`;
document.head.appendChild(mobileNavStyle);
