function openRegisterModal() {
    const modal = document.getElementById('register-modal');
    if (!modal) return;
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
    setTimeout(() => {
        modal.querySelector('input[name="display_name"]')?.focus();
    }, 20);
}

function closeRegisterModal() {
    const modal = document.getElementById('register-modal');
    if (!modal) return;
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
}

function updateAccountShell(data) {
    const sidebarName = document.querySelector('[data-sidebar-name]');
    const sidebarPro = document.querySelector('[data-sidebar-pro]');
    const sidebarAvatar = document.querySelector('[data-sidebar-avatar]');
    const planLabel = document.querySelector('[data-plan-label]');
    const identityTitle = document.querySelector('.account-identity h1');
    const identitySubtitle = document.querySelector('.account-identity p:not(.eyebrow)');
    const proBadge = document.querySelector('[data-pro-badge]');

    if (sidebarName) sidebarName.textContent = data.display_name;
    if (sidebarPro) sidebarPro.classList.toggle('is-hidden', !data.is_pro);
    if (planLabel) planLabel.textContent = data.plan_label;
    if (identityTitle) identityTitle.textContent = data.display_name;
    if (identitySubtitle) identitySubtitle.textContent = data.username;
    if (proBadge) proBadge.classList.toggle('is-hidden', !data.is_pro);

    if (sidebarAvatar) {
        sidebarAvatar.replaceChildren();
        if (data.avatar_url) {
            const img = document.createElement('img');
            img.src = data.avatar_url;
            img.alt = '';
            sidebarAvatar.appendChild(img);
        } else {
            const fallback = document.createElement('span');
            fallback.className = 'profile-avatar-initial';
            fallback.textContent = data.avatar_initial || 'U';
            sidebarAvatar.appendChild(fallback);
        }
    }

    lucide.createIcons();
}

document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('[data-register-form]');
    if (!form) return;

    const state = form.querySelector('[data-register-state]');
    const submit = form.querySelector('button[type="submit"]');

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (state) {
            state.textContent = 'Создаём...';
            state.dataset.mode = 'saving';
        }
        if (submit) submit.disabled = true;

        try {
            const response = await fetch('/register/mock/', {
                method: 'POST',
                body: new FormData(form),
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCookie('csrftoken')
                }
            });

            if (!response.ok) throw new Error('Registration failed');
            const data = await response.json();
            updateAccountShell(data);
            if (state) {
                state.textContent = 'Готово';
                state.dataset.mode = 'saved';
            }
            closeRegisterModal();
            window.location.reload();
        } catch (error) {
            console.error(error);
            if (state) {
                state.textContent = 'Не удалось создать';
                state.dataset.mode = 'error';
            }
            if (submit) submit.disabled = false;
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closeRegisterModal();
    });
});
