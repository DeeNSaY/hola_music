// ===== Обработка Flash сообщений =====
document.addEventListener('DOMContentLoaded', function() {
    // Автоматическое скрытие flash сообщений через 5 секунд
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(message => {
        setTimeout(() => {
            message.style.opacity = '0';
            setTimeout(() => message.remove(), 300);
        }, 5000);

        // Кнопка закрытия
        const closeBtn = message.querySelector('.close-flash');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                message.style.opacity = '0';
                setTimeout(() => message.remove(), 300);
            });
        }
    });

    // Мобильное меню
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', function() {
            const navLinks = document.querySelector('.nav-links');
            navLinks.classList.toggle('show');
        });
    }

    // Плавная прокрутка для якорных ссылок
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });
});

// ===== Форматирование времени =====
function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// ===== Debounce для оптимизации =====
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ===== Сохранение состояния темы =====
const theme = localStorage.getItem('theme');
if (theme === 'light') {
    document.body.classList.add('light-theme');
}

// ===== Обработка ошибок на клиенте =====
window.addEventListener('error', function(e) {
    console.error('Client Error:', e.error);
});

// ===== Прогресс загрузки =====
function showLoading() {
    const loader = document.createElement('div');
    loader.className = 'loading-overlay';
    loader.innerHTML = '<div class="spinner"></div>';
    document.body.appendChild(loader);
}

function hideLoading() {
    const loader = document.querySelector('.loading-overlay');
    if (loader) loader.remove();
}

// ===== Уведомления =====
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <span class="notification-icon">${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</span>
        <span class="notification-message">${message}</span>
    `;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// ===== Копирование в буфер обмена =====
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showNotification('Скопировано в буфер обмена!', 'success');
    } catch (err) {
        showNotification('Не удалось скопировать', 'error');
    }
}

// ===== Поиск по плейлистам =====
function filterPlaylists(searchTerm) {
    const playlists = document.querySelectorAll('.chart-card');
    const term = searchTerm.toLowerCase();

    playlists.forEach(playlist => {
        const title = playlist.querySelector('h3')?.textContent.toLowerCase() || '';
        const country = playlist.querySelector('.chart-country')?.textContent.toLowerCase() || '';

        if (title.includes(term) || country.includes(term)) {
            playlist.style.display = '';
        } else {
            playlist.style.display = 'none';
        }
    });
}

// ===== Добавление в избранное =====
function addToFavorites(playlistId, playlistTitle) {
    let favorites = JSON.parse(localStorage.getItem('favorites') || '[]');

    if (!favorites.find(f => f.id === playlistId)) {
        favorites.push({ id: playlistId, title: playlistTitle });
        localStorage.setItem('favorites', JSON.stringify(favorites));
        showNotification('Добавлено в избранное!', 'success');
    } else {
        showNotification('Уже в избранном', 'info');
    }
}

// ===== Загрузка избранного =====
function loadFavorites() {
    const favorites = JSON.parse(localStorage.getItem('favorites') || '[]');
    const container = document.getElementById('favoritesContainer');

    if (container && favorites.length > 0) {
        container.innerHTML = favorites.map(fav => `
            <div class="favorite-item">
                <a href="/playlist/${fav.id}">${fav.title}</a>
                <button onclick="removeFromFavorites('${fav.id}')">✖</button>
            </div>
        `).join('');
    }
}

// ===== Экспорт чата =====
function exportChat() {
    const messages = document.querySelectorAll('.message');
    let chatText = 'Hola Music Chat Export\n\n';

    messages.forEach(msg => {
        const role = msg.classList.contains('user-message') ? 'User' : 'Hola AI';
        const content = msg.querySelector('.message-content')?.textContent || '';
        chatText += `[${role}]: ${content}\n\n`;
    });

    const blob = new Blob([chatText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `hola_chat_${new Date().toISOString()}.txt`;
    a.click();
    URL.revokeObjectURL(url);

    showNotification('Чат экспортирован!', 'success');
}

// ===== Инициализация при загрузке страницы =====
document.addEventListener('DOMContentLoaded', function() {
    loadFavorites();

    // Добавляем обработчик для поиска если есть поле поиска
    const searchInput = document.getElementById('searchPlaylists');
    if (searchInput) {
        searchInput.addEventListener('input', debounce((e) => {
            filterPlaylists(e.target.value);
        }, 300));
    }

    // Анимация появления элементов при скролле
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    document.querySelectorAll('.feature-card, .step, .chart-card').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        el.style.transition = 'all 0.6s ease';
        observer.observe(el);
    });
});

// ===== Обработка клавиатуры =====
document.addEventListener('keydown', function(e) {
    // Escape для закрытия модальных окон
    if (e.key === 'Escape') {
        const modals = document.querySelectorAll('.modal');
        modals.forEach(modal => {
            if (modal.style.display === 'block') {
                modal.style.display = 'none';
            }
        });
    }

    // Ctrl + K для поиска
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.getElementById('searchPlaylists');
        if (searchInput) {
            searchInput.focus();
        }
    }
});