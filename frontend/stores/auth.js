/**
 * Authentication Store for Botija Forex AI Trading Bot
 */
document.addEventListener('alpine:init', () => {
    Alpine.store('auth', {
        user: null,
        token: localStorage.getItem('auth_token'),
        loading: false,

        async login(credentials) {
            this.loading = true;
            try {
                const response = await fetch('/api/v1/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(credentials)
                });

                if (!response.ok) {
                    throw new Error('Login failed');
                }

                const data = await response.json();
                this.token = data.token;
                this.user = data.user;
                localStorage.setItem('auth_token', data.token);
                return data;
            } catch (error) {
                console.error('Login error:', error);
                throw error;
            } finally {
                this.loading = false;
            }
        },

        async logout() {
            this.token = null;
            this.user = null;
            localStorage.removeItem('auth_token');
        },

        get isAuthenticated() {
            return !!this.token;
        }
    });
});
