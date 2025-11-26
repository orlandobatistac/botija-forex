/**
 * Navigation Bar Component for Kraken AI Trading Bot
 */
function navbar() {
    return {
        mobileMenuOpen: false,
        userMenuOpen: false,

        toggleMobileMenu() {
            this.mobileMenuOpen = !this.mobileMenuOpen;
        },

        toggleUserMenu() {
            this.userMenuOpen = !this.userMenuOpen;
        },

        closeMobileMenu() {
            this.mobileMenuOpen = false;
        },

        closeUserMenu() {
            this.userMenuOpen = false;
        },

        async logout() {
            try {
                await this.$store.auth.logout();
                window.location.href = '/login';
            } catch (error) {
                console.error('Logout error:', error);
            }
        },

        get user() {
            return this.$store.auth.user;
        },

        get isAuthenticated() {
            return this.$store.auth.isAuthenticated;
        },

        init() {
            document.addEventListener('click', (event) => {
                if (!this.$el.contains(event.target)) {
                    this.mobileMenuOpen = false;
                    this.userMenuOpen = false;
                }
            });
        }
    }
}

window.navbar = navbar;
