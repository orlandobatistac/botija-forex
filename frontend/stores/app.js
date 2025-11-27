/**
 * Application Store for Botija Forex AI Trading Bot
 */
document.addEventListener('alpine:init', () => {
    Alpine.store('app', {
        theme: localStorage.getItem('theme') || 'dark',
        botRunning: false,
        lastUpdate: new Date(),
        tradingMode: 'DEMO',

        toggleTheme() {
            this.theme = this.theme === 'dark' ? 'light' : 'dark';
            localStorage.setItem('theme', this.theme);
            document.documentElement.classList.toggle('dark');
        },

        setBotRunning(running) {
            this.botRunning = running;
        },

        setTradingMode(mode) {
            this.tradingMode = mode;
        },

        updateTimestamp() {
            this.lastUpdate = new Date();
        }
    });
});
