/**
 * File Attachment Module for Discord Clone
 * Handles file uploads, previews, and rendering
 */

// Extend DiscordModule with file attachment functionality
DiscordModule.pendingFiles = [];

DiscordModule.handleFileSelect = function (input) {
    const files = Array.from(input.files);
    if (files.length === 0) return;

    // Add to pending files
    files.forEach(file => {
        // Check file size (10MB max)
        if (file.size > 10 * 1024 * 1024) {
            alert(`Файл "${file.name}" слишком большой (максимум 10МБ)`);
            return;
        }
        DiscordModule.pendingFiles.push(file);
    });

    // Show preview
    DiscordModule.showFilePreview();
    // Clear input
    input.value = '';
};

DiscordModule.showFilePreview = function () {
    const container = document.getElementById('file-preview-container');
    if (!container) return;

    if (DiscordModule.pendingFiles.length === 0) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'flex';
    container.innerHTML = '';
    container.style.flexWrap = 'wrap';
    container.style.gap = '8px';
    container.style.padding = '10px';
    container.style.background = 'var(--channel-bg)';
    container.style.borderRadius = '8px';
    container.style.marginBottom = '10px';

    DiscordModule.pendingFiles.forEach((file, index) => {
        const preview = document.createElement('div');
        preview.style.cssText = 'position:relative; padding:8px 12px; background:var(--sidebar-bg); border-radius:6px; display:flex; align-items:center; gap:8px;';

        const icon = file.type.startsWith('image/') ? 'fa-image' : 'fa-file';
        const sizeKB = (file.size / 1024).toFixed(1);

        preview.innerHTML = `
            <i class="fa-solid ${icon}" style="color:#5865f2;"></i>
            <span style="font-size:13px; color:var(--text-normal);">${file.name} (${sizeKB}КБ)</span>
            <i class="fa-solid fa-xmark" onclick="DiscordModule.removeFile(${index})" style="cursor:pointer; color:var(--text-muted); margin-left:8px;"></i>
        `;

        container.appendChild(preview);
    });
};

DiscordModule.removeFile = function (index) {
    DiscordModule.pendingFiles.splice(index, 1);
    DiscordModule.showFilePreview();
};

DiscordModule.uploadFiles = async function () {
    if (DiscordModule.pendingFiles.length === 0) return [];

    const uploadPromises = DiscordModule.pendingFiles.map(async (file) => {
        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch('/api/upload-file', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();

            if (data.success) {
                return data.file;
            } else {
                console.error(`Ошибка загрузки ${file.name}: ${data.error}`);
                alert(`Ошибка загрузки ${file.name}: ${data.error}`);
                return null;
            }
        } catch (e) {
            console.error('Upload error:', e);
            alert(`Ошибка загрузки ${file.name}`);
            return null;
        }
    });

    const results = await Promise.all(uploadPromises);
    const uploadedFiles = results.filter(f => f !== null);

    // Clear pending files
    DiscordModule.pendingFiles = [];
    DiscordModule.showFilePreview();

    return uploadedFiles;
};

DiscordModule.renderAttachments = function (attachments) {
    if (!attachments || attachments.length === 0) return '';

    let html = '<div class="message-attachments" style="margin-top:8px; display:flex; flex-direction:column; gap:8px;">';

    attachments.forEach(att => {
        if (att.type === 'image') {
            html += `
                <div class="attachment-image" style="max-width:400px; border-radius:8px; overflow:hidden; cursor:pointer;" onclick="DiscordModule.openImageLightbox('${att.path}')">
                    <img src="${att.path}" style="width:100%; height:auto; display:block;" alt="${att.filename}">
                </div>
            `;
        } else {
            const sizeKB = (att.size / 1024).toFixed(1);
            html += `
                <div class="attachment-file" style="padding:12px; background:var(--sidebar-bg); border-radius:8px; display:flex; align-items:center; gap:12px; max-width:400px;">
                    <i class="fa-solid fa-file" style="color:#5865f2; font-size:24px;"></i>
                    <div style="flex:1; overflow:hidden;">
                        <div style="font-weight:500; color:var(--text-link); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${att.filename}</div>
                        <div style="font-size:12px; color:var(--text-muted);">${sizeKB} КБ</div>
                    </div>
                    <a href="${att.path}" download="${att.filename}" style="color:var(--text-link); text-decoration:none;">
                        <i class="fa-solid fa-download"></i>
                    </a>
                </div>
            `;
        }
    });

    html += '</div>';
    return html;
};

DiscordModule.openImageLightbox = function (url) {
    // Create lightbox overlay
    const lightbox = document.createElement('div');
    lightbox.id = 'image-lightbox';
    lightbox.style.cssText = 'position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index:10000; display:flex; align-items:center; justify-content:center; cursor:zoom-out;';

    lightbox.innerHTML = `
        <img src="${url}" style="max-width:90%; max-height:90%; object-fit:contain;" alt="Image">
        <i class="fa-solid fa-xmark" style="position:absolute; top:20px; right:20px; font-size:32px; color:white; cursor:pointer;"></i>
    `;

    lightbox.onclick = () => lightbox.remove();
    document.body.appendChild(lightbox);
};

console.log('[Attachments] File attachment module loaded');
