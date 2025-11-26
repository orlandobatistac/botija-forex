/**
 * Application Store for Kraken AI Trading Bot
 */
document.addEventListener('alpine:init', () => {
    Alpine.store('app', {
        theme: localStorage.getItem('theme') || 'dark',
        botRunning: false,
        lastUpdate: new Date(),

        toggleTheme() {
            this.theme = this.theme === 'dark' ? 'light' : 'dark';
            localStorage.setItem('theme', this.theme);
            document.documentElement.classList.toggle('dark');
        },

        setBotRunning(running) {
            this.botRunning = running;
        },

        updateTimestamp() {
            this.lastUpdate = new Date();
        }
    });
});
