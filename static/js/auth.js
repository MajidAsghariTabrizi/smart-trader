/* =====================================================================
   SmartTrader Auth Helper
   ===================================================================== */

function getAuthToken() {
    return localStorage.getItem('token');
}

function setAuthToken(token) {
    localStorage.setItem('token', token);
}

function removeAuthToken() {
    localStorage.removeItem('token');
}

function isAuthenticated() {
    return !!getAuthToken();
}

async function apiWithAuth(path, options = {}) {
    const token = getAuthToken();
    if (!token) {
        throw new Error('Not authenticated');
    }

    const headers = {
        'Authorization': `Bearer ${token}`,
        ...(options.headers || {}),
    };

    const res = await fetch(path, {
        ...options,
        headers,
    });

    if (res.status === 401) {
        removeAuthToken();
        window.location.href = '/login.html';
        return null;
    }

    return res;
}

