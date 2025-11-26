/**
 * Authentication Store for Kraken AI Trading Bot
 */
document.addEventListener('alpine:init', () => {
    Alpine.store('auth', {
        user: null,
        token: localStorage.getItem('auth_token'),
        loading: false,

        async login(credentials) {
            this.loading = true;

            try {
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(credentials)
                });

                if (!response.ok) {
                    throw new Error('Login failed');
                }

                const data = await response.json();
                this.user = data.user;
                this.token = data.token;
                localStorage.setItem('auth_token', data.token);

                return true;
            } catch (error) {
                console.error('Login error:', error);
                throw error;
            } finally {
                this.loading = false;
            }
        },

        async logout() {
            try {
                if (this.token) {
                    await fetch('/api/auth/logout', {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${this.token}`,
                            'Content-Type': 'application/json'
                        }
                    });
                }
            } catch (error) {
                console.error('Logout error:', error);
            } finally {
                this.user = null;
                this.token = null;
                localStorage.removeItem('auth_token');
            }
        },

        get isAuthenticated() {
            return !!this.token && !!this.user;
        }
    });
});
