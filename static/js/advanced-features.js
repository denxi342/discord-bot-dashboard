/**
 * Advanced Messenger Features Module
 * Handles: Upload Progress, File Previews, Image Compression, Albums, Unread Divider, Link Previews
 */

const AdvancedFeatures = {
    // Current upload progress tracking
    activeUploads: new Map(), // Map<upload_id, { progress, xhr, filename }>

    /**
     * Feature 1: Upload Progress with XMLHttpRequest
     */
    uploadFileWithProgress: async (file, onProgress) => {
        return new Promise((resolve, reject) => {
            const formData = new FormData();
            formData.append('file', file);

            const xhr = new XMLHttpRequest();
            const uploadId = Date.now() + Math.random();

            // Track upload
            AdvancedFeatures.activeUploads.set(uploadId, {
                progress: 0,
                xhr: xhr,
                filename: file.name
            });

            // Progress event
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const percentComplete = Math.round((e.loaded / e.total) * 100);
                    AdvancedFeatures.activeUploads.get(uploadId).progress = percentComplete;
                    if (onProgress) onProgress(percentComplete, file.name);
                }
            });

            // Load event
            xhr.addEventListener('load', () => {
                if (xhr.status === 200) {
                    const response = JSON.parse(xhr.responseText);
                    AdvancedFeatures.activeUploads.delete(uploadId);
                    resolve(response);
                } else {
                    AdvancedFeatures.activeUploads.delete(uploadId);
                    reject(new Error('Upload failed'));
                }
            });

            // Error event
            xhr.addEventListener('error', () => {
                AdvancedFeatures.activeUploads.delete(uploadId);
                reject(new Error('Network error'));
            });

            xhr.open('POST', '/api/upload-file', true);
            xhr.send(formData);
        });
    },

    /**
     * Feature 2: Image Compression
     */
    compressImage: async (file, quality = 0.7) => {
        return new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                const img = new Image();
                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    let width = img.width;
                    let height = img.height;

                    // Maximum dimensions
                    const MAX_WIDTH = 1920;
                    const MAX_HEIGHT = 1080;

                    if (width > height) {
                        if (width > MAX_WIDTH) {
                            height *= MAX_WIDTH / width;
                            width = MAX_WIDTH;
                        }
                    } else {
                        if (height > MAX_HEIGHT) {
                            width *= MAX_HEIGHT / height;
                            height = MAX_HEIGHT;
                        }
                    }

                    canvas.width = width;
                    canvas.height = height;

                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, width, height);

                    canvas.toBlob((blob) => {
                        const compressedFile = new File([blob], file.name, {
                            type: 'image/jpeg',
                            lastModified: Date.now()
                        });
                        resolve(compressedFile);
                    }, 'image/jpeg', quality);
                };
                img.src = e.target.result;
            };
            reader.readAsDataURL(file);
        });
    },

    /**
     * Feature 3: Create Photo Album
     */
    createAlbum: async (files) => {
        const formData = new FormData();
        files.forEach(file => {
            formData.append('files[]', file);
        });

        const res = await fetch('/api/albums/create', {
            method: 'POST',
            body: formData
        });

        return await res.json();
    },

    /**
     * Feature 4: Link Preview
     */
    fetchLinkPreview: async (url) => {
        try {
            const res = await fetch('/api/preview-link-enhanced', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url })
            });
            const data = await res.json();
            return data.success ? data.preview : null;
        } catch (e) {
            console.error('Link preview error:', e);
            return null;
        }
    },

    /**
     * Feature 5: Mark messages as read
     */
    markAsRead: async (dmId, messageId) => {
        try {
            await fetch(`/api/dms/${dmId}/mark-read`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message_id: messageId })
            });
        } catch (e) {
            console.error('Mark read error:', e);
        }
    },

    /**
     * Feature 6: Get unread position
     */
    getUnreadPosition: async (dmId) => {
        try {
            const res = await fetch(`/api/dms/${dmId}/unread-position`);
            const data = await res.json();
            return data.success ? data : null;
        } catch (e) {
            console.error('Unread position error:', e);
            return null;
        }
    },

    /**
     * Feature 7: Render link preview card
     */
    renderLinkPreview: (preview) => {
        if (!preview) return '';

        const imageHtml = preview.image ?
            `<img src="${preview.image}" alt="${preview.title}" class="link-preview-image">` : '';

        return `
            <div class="link-preview-card" onclick="window.open('${preview.url}', '_blank')">
                ${imageHtml}
                <div class="link-preview-content">
                    <div class="link-preview-title">${Utils.escapeHtml(preview.title)}</div>
                    ${preview.description ? `<div class="link-preview-desc">${Utils.escapeHtml(preview.description)}</div>` : ''}
                    <div class="link-preview-url">${preview.site_name || new URL(preview.url).hostname}</div>
                </div>
            </div>
        `;
    },

    /**
     * Feature 8: Render PDF preview
     */
    renderPDFPreview: async (pdfUrl, containerId) => {
        if (typeof pdfjsLib === 'undefined') {
            console.error('PDF.js not loaded');
            return;
        }

        try {
            const loadingTask = pdfjsLib.getDocument(pdfUrl);
            const pdf = await loadingTask.promise;
            const page = await pdf.getPage(1);

            const scale = 1.5;
            const viewport = page.getViewport({ scale: scale });

            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');
            canvas.height = viewport.height;
            canvas.width = viewport.width;

            const renderContext = {
                canvasContext: context,
                viewport: viewport
            };

            await page.render(renderContext).promise;

            const container = document.getElementById(containerId);
            if (container) {
                container.innerHTML = '';
                container.appendChild(canvas);
            }
        } catch (e) {
            console.error('PDF preview error:', e);
        }
    },

    /**
     * Feature 9: Render file preview with lightbox
     */
    openLightbox: (imageUrl) => {
        // Create lightbox modal
        const lightbox = document.createElement('div');
        lightbox.className = 'lightbox-modal';
        lightbox.innerHTML = `
            <div class="lightbox-backdrop" onclick="this.parentElement.remove()"></div>
            <div class="lightbox-content">
                <button class="lightbox-close" onclick="this.closest('.lightbox-modal').remove()">×</button>
                <img src="${imageUrl}" alt="Preview">
            </div>
        `;
        document.body.appendChild(lightbox);

        // Close on Esc
        const closeHandler = (e) => {
            if (e.key === 'Escape') {
                lightbox.remove();
                document.removeEventListener('keydown', closeHandler);
            }
        };
        document.addEventListener('keydown', closeHandler);
    },

    /**
     * Feature 10: Detect URLs in text
     */
    detectURLs: (text) => {
        const urlRegex = /(https?:\/\/[^\s]+)/g;
        return text.match(urlRegex) || [];
    },

    /**
     * Feature 11: Insert unread divider
     */
    insertUnreadDivider: (container, firstUnreadId) => {
        const messages = container.querySelectorAll('.dm-bubble');
        messages.forEach(msg => {
            const msgId = parseInt(msg.dataset.messageId);
            if (msgId === firstUnreadId) {
                const divider = document.createElement('div');
                divider.className = 'unread-divider';
                divider.innerHTML = `
                    <div class="unread-line"></div>
                    <div class="unread-label">Новые сообщения</div>
                    <div class="unread-line"></div>
                `;
                msg.parentElement.insertBefore(divider, msg);
            }
        });
    },

    /**
     * Feature 12: Show upload progress UI
     */
    showUploadProgress: (filename, progress) => {
        let progressEl = document.getElementById('upload-progress-ui');

        if (!progressEl) {
            progressEl = document.createElement('div');
            progressEl.id = 'upload-progress-ui';
            progressEl.className = 'upload-progress-container';
            document.body.appendChild(progressEl);
        }

        progressEl.innerHTML = `
            <div class="upload-progress-card">
                <div class="upload-progress-header">
                    <i class="fa-solid fa-cloud-arrow-up"></i>
                    <span>Загрузка: ${filename}</span>
                </div>
                <div class="upload-progress-bar-container">
                    <div class="upload-progress-bar" style="width: ${progress}%"></div>
                </div>
                <div class="upload-progress-percent">${progress}%</div>
            </div>
        `;

        if (progress >= 100) {
            setTimeout(() => {
                progressEl.remove();
            }, 1000);
        }
    }
};

// Export to global scope
window.AdvancedFeatures = AdvancedFeatures;
