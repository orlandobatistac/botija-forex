/**
 * API Utility functions for Botija Forex AI Trading Bot
 */
class API {
    constructor(baseUrl = '/api') {
        this.baseUrl = baseUrl;
    }

    getAuthToken() {
        return Alpine.store('auth').token;
    }

    getHeaders(includeAuth = true, customHeaders = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...customHeaders
        };

        if (includeAuth && this.getAuthToken()) {
            headers['Authorization'] = `Bearer ${this.getAuthToken()}`;
        }

        return headers;
    }

    async handleResponse(response) {
        if (!response.ok) {
            const error = await response.json().catch(() => ({ message: response.statusText }));
            throw new Error(error.message || `HTTP ${response.status}`);
        }

        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            return response.json();
        }

        return response.text();
    }

    async get(endpoint, params = {}, options = {}) {
        const url = new URL(`${this.baseUrl}${endpoint}`, window.location.origin);
        Object.entries(params).forEach(([key, value]) => {
            if (value !== null && value !== undefined) {
                url.searchParams.append(key, value);
            }
        });

        const response = await fetch(url, {
            method: 'GET',
            headers: this.getHeaders(options.auth !== false, options.headers),
            ...options
        });

        return this.handleResponse(response);
    }

    async post(endpoint, data = {}, options = {}) {
        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            method: 'POST',
            headers: this.getHeaders(options.auth !== false, options.headers),
            body: JSON.stringify(data),
            ...options
        });

        return this.handleResponse(response);
    }

    async put(endpoint, data = {}, options = {}) {
        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            method: 'PUT',
            headers: this.getHeaders(options.auth !== false, options.headers),
            body: JSON.stringify(data),
            ...options
        });

        return this.handleResponse(response);
    }

    async delete(endpoint, options = {}) {
        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            method: 'DELETE',
            headers: this.getHeaders(options.auth !== false, options.headers),
            ...options
        });

        return this.handleResponse(response);
    }
}

window.api = new API();
