/**
 * Reusable Modal Component for Botija Forex AI Trading Bot
 * Usage: x-data="modal({ title: 'My Modal', size: 'lg' })"
 */
function modal(config = {}) {
    return {
        open: false,
        title: config.title || 'Modal',
        size: config.size || 'md',
        closable: config.closable !== false,

        show() {
            this.open = true;
            document.body.style.overflow = 'hidden';
            this.$nextTick(() => {
                if (this.$refs.modal) {
                    this.$refs.modal.focus();
                }
            });
        },

        hide() {
            this.open = false;
            document.body.style.overflow = 'auto';
        },

        onEscape(event) {
            if (event.key === 'Escape' && this.closable) {
                this.hide();
            }
        },

        onBackdropClick(event) {
            if (event.target === event.currentTarget && this.closable) {
                this.hide();
            }
        },

        init() {
            this.$watch('open', value => {
                if (value) {
                    document.addEventListener('keydown', this.onEscape);
                } else {
                    document.removeEventListener('keydown', this.onEscape);
                }
            });
        },

        getSizeClasses() {
            const sizes = {
                'sm': 'max-w-sm',
                'md': 'max-w-md',
                'lg': 'max-w-lg',
                'xl': 'max-w-xl',
                '2xl': 'max-w-2xl',
                'full': 'max-w-full mx-4'
            };
            return sizes[this.size] || sizes.md;
        }
    }
}

window.modal = modal;
