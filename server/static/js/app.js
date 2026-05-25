// 前台通用交互逻辑
document.addEventListener('alpine:init', () => {
    console.log('Alpine.js initialized');
});

// 后台API请求封装（带Token）
async function adminFetch(url, options = {}) {
    const token = localStorage.getItem('admin_token');
    if (!token) { location.href = '/admin/login'; return; }
    options.headers = { ...options.headers, 'Authorization': `Bearer ${token}` };
    const resp = await fetch(url, options);
    if (resp.status === 401) { localStorage.removeItem('admin_token'); location.href = '/admin/login'; }
    return resp;
}
