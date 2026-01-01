/* =====================================================================
   SmartTrader – Shared Navigation Component
   ===================================================================== */

function renderNavigation() {
    const token = localStorage.getItem('token');
    const isAuthenticated = !!token;

    const navHTML = `
        <nav class="st-nav" id="mainNav">
            <div class="st-nav-container">
                <div class="st-nav-brand">
                    <a href="/" class="st-nav-logo">SmartTrader</a>
                </div>
                <div class="st-nav-menu" id="navMenu">
                    ${isAuthenticated ? `
                        <a href="/app" class="st-nav-link">داشبورد</a>
                        <a href="/insights" class="st-nav-link">تحلیل‌ها</a>
                        <a href="/pricing" class="st-nav-link">تعرفه‌ها</a>
                        <span class="st-nav-divider"></span>
                        <a href="/" class="st-nav-link" onclick="localStorage.removeItem('token'); return true;">خروج</a>
                    ` : `
                        <a href="/" class="st-nav-link">صفحه اصلی</a>
                        <a href="/pricing" class="st-nav-link">تعرفه‌ها</a>
                        <a href="/insights" class="st-nav-link">تحلیل‌ها</a>
                        <a href="/login" class="st-nav-link st-nav-link-primary">ورود</a>
                        <a href="/register" class="st-nav-link st-nav-link-cta">ثبت‌نام</a>
                    `}
                </div>
                <button class="st-nav-toggle" id="navToggle" aria-label="Toggle menu">
                    <span></span>
                    <span></span>
                    <span></span>
                </button>
            </div>
        </nav>
    `;

    // Inject at the beginning of body
    const body = document.body;
    if (body) {
        const navElement = document.createElement('div');
        navElement.innerHTML = navHTML;
        body.insertBefore(navElement.firstElementChild, body.firstChild);

        // Mobile menu toggle
        const toggle = document.getElementById('navToggle');
        const menu = document.getElementById('navMenu');
        if (toggle && menu) {
            toggle.addEventListener('click', () => {
                menu.classList.toggle('st-nav-menu-open');
                toggle.classList.toggle('st-nav-toggle-active');
            });
        }
    }
}

// Auto-inject on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', renderNavigation);
} else {
    renderNavigation();
}

