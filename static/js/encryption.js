/**
 * End-to-End Encryption Module
 * Uses Web Crypto API for client-side encryption
 * Protocol: ECDH key exchange + AES-GCM encryption
 */

const EncryptionModule = {
    // Crypto state
    publicKey: null,
    privateKey: null,
    isInitialized: false,

    // Shared secrets cache: {user_id: CryptoKey}
    sharedSecrets: {},

    // IndexedDB for key storage
    db: null,
    DB_NAME: 'MessengerEncryption',
    DB_VERSION: 1,

    /**
     * Initialize encryption system - open IndexedDB
     */
    async init() {
        console.log('[E2EE] Initializing encryption module...');

        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.DB_NAME, this.DB_VERSION);

            request.onerror = () => {
                console.error('[E2EE] Failed to open IndexedDB');
                reject(request.error);
            };

            request.onsuccess = () => {
                this.db = request.result;
                console.log('[E2EE] IndexedDB opened successfully');
                resolve();
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;

                // Store for encrypted private keys
                if (!db.objectStoreNames.contains('keys')) {
                    db.createObjectStore('keys', { keyPath: 'id' });
                }

                // Store for public keys cache
                if (!db.objectStoreNames.contains('publicKeys')) {
                    db.createObjectStore('publicKeys', { keyPath: 'userId' });
                }
            };
        });
    },

    /**
     * Generate a new ECDH key pair
     */
    async generateKeyPair() {
        console.log('[E2EE] Generating new key pair...');

        const keyPair = await window.crypto.subtle.generateKey(
            {
                name: 'ECDH',
                namedCurve: 'P-256'
            },
            true, // extractable
            ['deriveKey', 'deriveBits']
        );

        this.publicKey = keyPair.publicKey;
        this.privateKey = keyPair.privateKey;

        console.log('[E2EE] Key pair generated successfully');
        return keyPair;
    },

    /**
     * Export public key to JWK format for sharing
     */
    async exportPublicKey(publicKey = this.publicKey) {
        const jwk = await window.crypto.subtle.exportKey('jwk', publicKey);
        return JSON.stringify(jwk);
    },

    /**
     * Import public key from JWK string
     */
    async importPublicKey(jwkString) {
        const jwk = JSON.parse(jwkString);
        return await window.crypto.subtle.importKey(
            'jwk',
            jwk,
            {
                name: 'ECDH',
                namedCurve: 'P-256'
            },
            true,
            []
        );
    },

    /**
     * Derive encryption key from password using PBKDF2
     */
    async deriveKeyFromPassword(password, salt) {
        const encoder = new TextEncoder();
        const passwordKey = await window.crypto.subtle.importKey(
            'raw',
            encoder.encode(password),
            'PBKDF2',
            false,
            ['deriveKey']
        );

        return await window.crypto.subtle.deriveKey(
            {
                name: 'PBKDF2',
                salt: salt,
                iterations: 100000,
                hash: 'SHA-256'
            },
            passwordKey,
            { name: 'AES-GCM', length: 256 },
            false,
            ['encrypt', 'decrypt']
        );
    },

    /**
     * Store private key encrypted with password
     */
    async storePrivateKey(privateKey, password) {
        console.log('[E2EE] Storing private key...');

        // Generate random salt
        const salt = window.crypto.getRandomValues(new Uint8Array(16));

        // Derive key from password
        const encryptionKey = await this.deriveKeyFromPassword(password, salt);

        // Export private key
        const privateKeyJwk = await window.crypto.subtle.exportKey('jwk', privateKey);
        const privateKeyData = new TextEncoder().encode(JSON.stringify(privateKeyJwk));

        // Encrypt private key
        const iv = window.crypto.getRandomValues(new Uint8Array(12));
        const encryptedPrivateKey = await window.crypto.subtle.encrypt(
            { name: 'AES-GCM', iv: iv },
            encryptionKey,
            privateKeyData
        );

        // Store in IndexedDB
        const transaction = this.db.transaction(['keys'], 'readwrite');
        const store = transaction.objectStore('keys');

        await store.put({
            id: 'privateKey',
            encrypted: Array.from(new Uint8Array(encryptedPrivateKey)),
            salt: Array.from(salt),
            iv: Array.from(iv)
        });

        console.log('[E2EE] Private key stored successfully');
    },

    /**
     * Load and decrypt private key with password
     */
    async loadPrivateKey(password) {
        console.log('[E2EE] Loading private key...');

        return new Promise(async (resolve, reject) => {
            const transaction = this.db.transaction(['keys'], 'readonly');
            const store = transaction.objectStore('keys');
            const request = store.get('privateKey');

            request.onsuccess = async () => {
                const data = request.result;
                if (!data) {
                    reject(new Error('No private key found'));
                    return;
                }

                try {
                    // Derive decryption key
                    const salt = new Uint8Array(data.salt);
                    const decryptionKey = await this.deriveKeyFromPassword(password, salt);

                    // Decrypt private key
                    const iv = new Uint8Array(data.iv);
                    const encrypted = new Uint8Array(data.encrypted);
                    const decrypted = await window.crypto.subtle.decrypt(
                        { name: 'AES-GCM', iv: iv },
                        decryptionKey,
                        encrypted
                    );

                    // Import private key
                    const privateKeyJwk = JSON.parse(new TextDecoder().decode(decrypted));
                    this.privateKey = await window.crypto.subtle.importKey(
                        'jwk',
                        privateKeyJwk,
                        {
                            name: 'ECDH',
                            namedCurve: 'P-256'
                        },
                        true,
                        ['deriveKey', 'deriveBits']
                    );

                    console.log('[E2EE] Private key loaded successfully');
                    resolve(this.privateKey);
                } catch (error) {
                    console.error('[E2EE] Failed to decrypt private key:', error);
                    reject(new Error('Invalid password or corrupted key'));
                }
            };

            request.onerror = () => reject(request.error);
        });
    },

    /**
     * Check if private key exists in storage
     */
    async hasStoredKey() {
        return new Promise((resolve) => {
            const transaction = this.db.transaction(['keys'], 'readonly');
            const store = transaction.objectStore('keys');
            const request = store.get('privateKey');

            request.onsuccess = () => {
                resolve(!!request.result);
            };

            request.onerror = () => resolve(false);
        });
    },

    /**
     * Derive shared secret using ECDH
     */
    async deriveSharedSecret(theirPublicKey) {
        if (!this.privateKey) {
            throw new Error('Private key not loaded');
        }

        // Import their public key if it's a string
        if (typeof theirPublicKey === 'string') {
            theirPublicKey = await this.importPublicKey(theirPublicKey);
        }

        // Derive shared secret using ECDH
        const sharedSecret = await window.crypto.subtle.deriveKey(
            {
                name: 'ECDH',
                public: theirPublicKey
            },
            this.privateKey,
            {
                name: 'AES-GCM',
                length: 256
            },
            false, // not extractable
            ['encrypt', 'decrypt']
        );

        return sharedSecret;
    },

    /**
     * Get or derive shared secret for a user
     */
    async getSharedSecret(userId, theirPublicKey) {
        // Check cache
        if (this.sharedSecrets[userId]) {
            return this.sharedSecrets[userId];
        }

        // Derive new shared secret
        const sharedSecret = await this.deriveSharedSecret(theirPublicKey);
        this.sharedSecrets[userId] = sharedSecret;

        return sharedSecret;
    },

    /**
     * Encrypt a message using AES-GCM
     */
    async encryptMessage(plaintext, sharedSecret) {
        const encoder = new TextEncoder();
        const data = encoder.encode(plaintext);

        // Generate random IV
        const iv = window.crypto.getRandomValues(new Uint8Array(12));

        // Encrypt
        const ciphertext = await window.crypto.subtle.encrypt(
            { name: 'AES-GCM', iv: iv },
            sharedSecret,
            data
        );

        // Return encrypted data + IV
        return {
            ciphertext: Array.from(new Uint8Array(ciphertext)),
            iv: Array.from(iv)
        };
    },

    /**
     * Decrypt a message using AES-GCM
     */
    async decryptMessage(encryptedData, sharedSecret) {
        const ciphertext = new Uint8Array(encryptedData.ciphertext);
        const iv = new Uint8Array(encryptedData.iv);

        try {
            const decrypted = await window.crypto.subtle.decrypt(
                { name: 'AES-GCM', iv: iv },
                sharedSecret,
                ciphertext
            );

            const decoder = new TextDecoder();
            return decoder.decode(decrypted);
        } catch (error) {
            console.error('[E2EE] Decryption failed:', error);
            throw new Error('Failed to decrypt message');
        }
    },

    /**
     * Encrypt file data (Data URI or binary)
     */
    async encryptFile(fileDataUri, sharedSecret) {
        // Convert Data URI to binary
        const base64Data = fileDataUri.split(',')[1];
        const binaryData = Uint8Array.from(atob(base64Data), c => c.charCodeAt(0));

        // Generate random IV
        const iv = window.crypto.getRandomValues(new Uint8Array(12));

        // Encrypt
        const ciphertext = await window.crypto.subtle.encrypt(
            { name: 'AES-GCM', iv: iv },
            sharedSecret,
            binaryData
        );

        return {
            ciphertext: Array.from(new Uint8Array(ciphertext)),
            iv: Array.from(iv),
            mimeType: fileDataUri.split(';')[0].split(':')[1] // Extract mime type
        };
    },

    /**
     * Decrypt file data back to Data URI
     */
    async decryptFile(encryptedData, sharedSecret) {
        const ciphertext = new Uint8Array(encryptedData.ciphertext);
        const iv = new Uint8Array(encryptedData.iv);

        try {
            const decrypted = await window.crypto.subtle.decrypt(
                { name: 'AES-GCM', iv: iv },
                sharedSecret,
                ciphertext
            );

            // Convert back to Data URI
            const binaryArray = new Uint8Array(decrypted);
            const base64 = btoa(String.fromCharCode.apply(null, binaryArray));
            const mimeType = encryptedData.mimeType || 'application/octet-stream';

            return `data:${mimeType};base64,${base64}`;
        } catch (error) {
            console.error('[E2EE] File decryption failed:', error);
            throw new Error('Failed to decrypt file');
        }
    },

    /**
     * Export keys for backup
     */
    async exportKeys(password) {
        if (!this.privateKey || !this.publicKey) {
            throw new Error('No keys loaded');
        }

        const privateJwk = await window.crypto.subtle.exportKey('jwk', this.privateKey);
        const publicJwk = await window.crypto.subtle.exportKey('jwk', this.publicKey);

        const exportData = {
            private: privateJwk,
            public: publicJwk,
            timestamp: Date.now()
        };

        // Encrypt export with password
        const salt = window.crypto.getRandomValues(new Uint8Array(16));
        const encryptionKey = await this.deriveKeyFromPassword(password, salt);

        const data = new TextEncoder().encode(JSON.stringify(exportData));
        const iv = window.crypto.getRandomValues(new Uint8Array(12));

        const encrypted = await window.crypto.subtle.encrypt(
            { name: 'AES-GCM', iv: iv },
            encryptionKey,
            data
        );

        return {
            encrypted: Array.from(new Uint8Array(encrypted)),
            salt: Array.from(salt),
            iv: Array.from(iv)
        };
    },

    /**
     * Import keys from backup
     */
    async importKeys(backupData, password) {
        const salt = new Uint8Array(backupData.salt);
        const decryptionKey = await this.deriveKeyFromPassword(password, salt);

        const iv = new Uint8Array(backupData.iv);
        const encrypted = new Uint8Array(backupData.encrypted);

        try {
            const decrypted = await window.crypto.subtle.decrypt(
                { name: 'AES-GCM', iv: iv },
                decryptionKey,
                encrypted
            );

            const exportData = JSON.parse(new TextDecoder().decode(decrypted));

            // Import keys
            this.privateKey = await window.crypto.subtle.importKey(
                'jwk',
                exportData.private,
                { name: 'ECDH', namedCurve: 'P-256' },
                true,
                ['deriveKey', 'deriveBits']
            );

            this.publicKey = await window.crypto.subtle.importKey(
                'jwk',
                exportData.public,
                { name: 'ECDH', namedCurve: 'P-256' },
                true,
                []
            );

            console.log('[E2EE] Keys imported successfully');
            return true;
        } catch (error) {
            console.error('[E2EE] Import failed:', error);
            throw new Error('Invalid password or corrupted backup');
        }
    },

    /**
     * Get encryption fingerprint for verification
     */
    async getFingerprint(publicKey = this.publicKey) {
        const exported = await window.crypto.subtle.exportKey('raw', publicKey);
        const hashBuffer = await window.crypto.subtle.digest('SHA-256', exported);
        const hashArray = Array.from(new Uint8Array(hashBuffer));

        // Convert to hex and format as groups
        const hex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
        return hex.match(/.{1,4}/g).join(' ').toUpperCase();
    }
};

// Export to window for global access
window.EncryptionModule = EncryptionModule;

console.log('[E2EE] Encryption module loaded');
