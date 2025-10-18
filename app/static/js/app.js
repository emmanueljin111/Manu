document.addEventListener('DOMContentLoaded', () => {
    const addSongBtn = document.getElementById('add-song');
    const songTable = document.getElementById('song-table');
    if (addSongBtn && songTable) {
        addSongBtn.addEventListener('click', () => {
            addSongRow();
        });
        if (songTable.querySelector('tbody').children.length === 0) {
            addSongRow();
        }
    }
    setupMultiInput();
});

function addSongRow() {
    const template = document.getElementById('song-row-template');
    const tbody = document.querySelector('#song-table tbody');
    if (!template || !tbody) return;
    const fragment = template.content.cloneNode(true);
    const row = fragment.querySelector('tr');
    const removeBtn = row.querySelector('.remove-song');
    if (removeBtn) {
        removeBtn.addEventListener('click', () => {
            row.remove();
            renumberSongs();
        });
    }
    tbody.appendChild(fragment);
    renumberSongs();
}

function renumberSongs() {
    document.querySelectorAll('#song-table tbody tr').forEach((row, index) => {
        const orderCell = row.querySelector('.order-cell');
        if (orderCell) {
            orderCell.textContent = index + 1;
        }
    });
    if (document.querySelectorAll('#song-table tbody tr').length === 0) {
        addSongRow();
    }
}

function setupMultiInput() {
    document.querySelectorAll('.add-person').forEach(button => {
        button.addEventListener('click', () => {
            const role = button.dataset.role;
            const container = button.previousElementSibling;
            addPersonInput(role, container);
        });
    });

    document.querySelectorAll('.multi-input').forEach(container => {
        if (container.children.length === 0) {
            const role = container.dataset.role;
            addPersonInput(role, container);
        } else {
            container.querySelectorAll('.remove-person').forEach(attachRemoveListener);
        }
    });
}

function addPersonInput(role, container) {
    if (!container) return;
    const template = document.getElementById('person-input-template');
    if (!template) return;
    const fragment = template.content.cloneNode(true);
    fragment.querySelector('input').setAttribute('name', `${role}_participants`);
    const element = fragment.firstElementChild;
    container.appendChild(element);
    attachRemoveListener(element.querySelector('.remove-person'));
}

function attachRemoveListener(button) {
    if (!button) return;
    button.addEventListener('click', () => {
        const wrapper = button.closest('.input-group');
        if (wrapper) {
            const container = wrapper.parentElement;
            wrapper.remove();
            if (container && container.children.length === 0) {
                const role = container.dataset.role;
                addPersonInput(role, container);
            }
        }
    });
}
