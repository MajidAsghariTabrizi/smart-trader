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
                        <a href="/app" class="st-nav-link">Command Center</a>
                        <a href="/insights" class="st-nav-link">Market Intelligence</a>
                        <a href="/pricing" class="st-nav-link">Pricing</a>
                        <span class="st-nav-divider"></span>
                        <a href="/" class="st-nav-link" onclick="localStorage.removeItem('token'); return true;">Logout</a>
                    ` : `
                        <a href="/" class="st-nav-link">Home</a>
                        <a href="/pricing" class="st-nav-link">Pricing</a>
                        <a href="/insights" class="st-nav-link">Insights</a>
                        <a href="/login" class="st-nav-link st-nav-link-primary">Login</a>
                        <a href="/register" class="st-nav-link st-nav-link-cta">Get Started</a>
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
            toggle.addEventListener('click', (e) => {
                e.stopPropagation();
                menu.classList.toggle('st-nav-menu-open');
                toggle.classList.toggle('st-nav-toggle-active');
                // Prevent body scroll when menu is open
                if (menu.classList.contains('st-nav-menu-open')) {
                    document.body.style.overflow = 'hidden';
                } else {
                    document.body.style.overflow = '';
                }
            });

            // Close menu when clicking outside
            document.addEventListener('click', (e) => {
                if (window.innerWidth <= 767) {
                    if (!menu.contains(e.target) && !toggle.contains(e.target)) {
                        menu.classList.remove('st-nav-menu-open');
                        toggle.classList.remove('st-nav-toggle-active');
                        document.body.style.overflow = '';
                    }
                }
            });

            // Close menu when clicking a link
            const navLinks = menu.querySelectorAll('.st-nav-link');
            navLinks.forEach(link => {
                link.addEventListener('click', () => {
                    if (window.innerWidth <= 767) {
                        menu.classList.remove('st-nav-menu-open');
                        toggle.classList.remove('st-nav-toggle-active');
                        document.body.style.overflow = '';
                    }
                });
            });

            // Handle window resize
            window.addEventListener('resize', () => {
                if (window.innerWidth > 767) {
                    menu.classList.remove('st-nav-menu-open');
                    toggle.classList.remove('st-nav-toggle-active');
                    document.body.style.overflow = '';
                }
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

