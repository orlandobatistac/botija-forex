/**
 * Toast Notification Component for Botija Forex AI Trading Bot
 */
function toast(message = '', type = 'info') {
    const container = document.getElementById('toast-container') || (() => {
        const div = document.createElement('div');
        div.id = 'toast-container';
        div.className = 'fixed top-4 right-4 z-50 space-y-2';
        document.body.appendChild(div);
        return div;
    })();

    const toastEl = document.createElement('div');
    toastEl.className = `px-4 py-3 rounded-lg text-white font-medium toast ${
        type === 'success' ? 'bg-green-500' :
        type === 'error' ? 'bg-red-500' :
        type === 'warning' ? 'bg-yellow-500' :
        'bg-blue-500'
    }`;
    toastEl.textContent = message;

    container.appendChild(toastEl);

    setTimeout(() => {
        toastEl.remove();
    }, 3000);
}

window.toast = toast;
