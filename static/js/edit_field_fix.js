// Temporary fix for editField function
DiscordModule.editField = (fieldName) => {
    const fieldValueEl = document.getElementById(`field-${fieldName.replace('_', '-')}`);
    const currentValue = fieldValueEl.innerText;
    const actualValue = currentValue === 'Not set' ? '' : currentValue;

    // Create modal
    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.style.display = 'flex';
    modal.innerHTML = `
        <div class="discord-modal" style="max-width: 400px;">
            <h2 style="margin-bottom: 16px;">Изменить ${fieldName === 'custom_status' ? 'Custom Status' : fieldName}</h2>
            <input id="edit-field-input" type="text" value="${actualValue}" placeholder="${fieldName === 'custom_status' ? '🎮 Playing games' : ''}" style="width: 100%; padding: 10px; background: rgba(255,255,255,0.1); border: 1px solid var(--primary); border-radius: 4px; color: white; font-size: 14px; margin-bottom: 16px;">
            <div style="display: flex; gap: 10px; justify-content: flex-end;">
                <button onclick="this.closest('.modal-backdrop').remove()" style="padding: 8px 16px; background: #4f545c; border: none; border-radius: 4px; color: white; cursor: pointer;">Отмена</button>
                <button onclick="DiscordModule.saveEditField('${fieldName}')" style="padding: 8px 16px; background: var(--primary); border: none; border-radius: 4px; color: white; cursor: pointer;">Сохранить</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    setTimeout(() => document.getElementById('edit-field-input').focus(), 100);
};

DiscordModule.saveEditField = (fieldName) => {
    const value = document.getElementById('edit-field-input').value.trim();
    document.querySelector('.modal-backdrop').remove();
    DiscordModule.updateUserField(fieldName, value);
};
