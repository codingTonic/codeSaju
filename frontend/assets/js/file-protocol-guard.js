(function redirectFileAccessToLocalServer() {
    if (window.location.protocol !== 'file:') return;

    const currentPage = window.location.pathname.split('/').pop() || 'index.html';
    const hasTaskId = new URLSearchParams(window.location.search).has('task_id');
    const targetPage = currentPage === 'result.html' && !hasTaskId
        ? 'input.html'
        : currentPage;
    const target = new URL(`http://127.0.0.1:3005/pages/${targetPage}`);

    if (hasTaskId) {
        target.search = window.location.search;
    }
    target.hash = window.location.hash;
    window.location.replace(target.href);
}());
