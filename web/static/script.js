/**
 * Discord 私人頻道內容提取器 - 前端 JavaScript
 */

// 全局變量
let currentOffset = 0;
let currentMessages = [];
let searchTimeout = null;

// 頁面載入時初始化
document.addEventListener('DOMContentLoaded', function() {
    loadStatistics();
    loadChannels();
    loadMessages();
    setupAutoRefresh();
});

/**
 * 載入統計資訊
 */
function loadStatistics() {
    fetch('/api/statistics')
        .then(response => response.json())
        .then(data => {
            document.getElementById('total-messages').textContent = formatNumber(data.total_messages || 0);
            document.getElementById('total-channels').textContent = formatNumber(data.total_channels || 0);
            document.getElementById('total-attachments').textContent = formatNumber(data.total_attachments || 0);

            if (data.date_range) {
                const latest = new Date(data.date_range.latest);
                document.getElementById('date-range').textContent = formatDate(latest);
            } else {
                document.getElementById('date-range').textContent = '-';
            }
        })
        .catch(error => {
            console.error('載入統計失敗:', error);
            document.getElementById('total-messages').textContent = '0';
            document.getElementById('total-channels').textContent = '0';
            document.getElementById('total-attachments').textContent = '0';
        });
}

/**
 * 載入頻道列表
 */
function loadChannels() {
    fetch('/api/channels')
        .then(response => response.json())
        .then(channels => {
            const container = document.getElementById('channels-grid');
            const select = document.getElementById('channel-filter');

            // 清空現有內容（保留第一個選項）
            while (select.options.length > 1) {
                select.remove(1);
            }
            container.innerHTML = '';

            if (channels.length === 0) {
                container.innerHTML = '<div class="empty-state"><p class="empty-state-text">暫無頻道數據</p></div>';
                return;
            }

            channels.forEach(channel => {
                // 添加到選擇器
                const option = document.createElement('option');
                option.value = channel.id;
                option.textContent = channel.name || `頻道 ${channel.id}`;
                select.appendChild(option);

                // 添加到卡片列表
                const card = document.createElement('div');
                card.className = 'channel-card';
                card.onclick = () => window.location.href = `/channel/${channel.id}`;
                card.innerHTML = `
                    <h3><span class="channel-icon">📁</span> ${channel.name || `頻道 ${channel.id}`}</h3>
                    <p>${formatNumber(channel.message_count)} 條訊息</p>
                `;
                container.appendChild(card);
            });
        })
        .catch(error => {
            console.error('載入頻道失敗:', error);
            document.getElementById('channels-grid').innerHTML = '<div class="error"><p>載入頻道失敗</p></div>';
        });
}

/**
 * 載入訊息列表
 */
function loadMessages() {
    showLoading();
    fetchMessages();
}

/**
 * 獲取訊息數據
 */
function fetchMessages() {
    const channelId = document.getElementById('channel-filter').value;
    const search = document.getElementById('search-input').value;
    const author = document.getElementById('author-filter').value;
    const limit = document.getElementById('limit-select').value;

    let url = `/api/messages?limit=${limit}&offset=${currentOffset}`;
    if (channelId) url += `&channel_id=${channelId}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (author) url += `&author=${encodeURIComponent(author)}`;

    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (currentOffset === 0) {
                currentMessages = [];
            }
            currentMessages = [...currentMessages, ...data.messages];
            renderMessages(currentMessages);
            updateMessageCount(data.total);

            // 顯示/隱藏載入更多按鈕
            const loadMoreContainer = document.getElementById('load-more-container');
            if (data.messages.length < data.total - currentOffset) {
                loadMoreContainer.style.display = 'flex';
            } else {
                loadMoreContainer.style.display = 'none';
            }
        })
        .catch(error => {
            showError('載入失敗: ' + error.message);
        });
}

/**
 * 渲染訊息列表
 */
function renderMessages(messages) {
    const container = document.getElementById('messages-list');

    if (messages.length === 0) {
        container.innerHTML = '<div class="empty-state"><p class="empty-state-text">暫無訊息</p></div>';
        return;
    }

    container.innerHTML = messages.map((msg, index) => createMessageCard(msg, index)).join('');

    // 添加點擊事件
    document.querySelectorAll('.message-card').forEach((card, index) => {
        card.addEventListener('click', () => openMessageModal(currentMessages[index]));
    });
}

/**
 * 創建訊息卡片 HTML
 */
function createMessageCard(msg, index) {
    const avatarInitial = msg.author ? msg.author.charAt(0).toUpperCase() : '?';
    const time = formatDateTime(new Date(msg.timestamp));
    const content = escapeHtml(msg.content || '');
    const channelName = msg.channel_name || `頻道 ${msg.channel_id}`;

    let attachmentsHtml = '';
    if (msg.attachments && msg.attachments.length > 0) {
        const attachmentIcons = {
            'image': '🖼️',
            'video': '🎬',
            'audio': '🎵',
            'application': '📎'
        };
        attachmentsHtml = '<div class="message-attachments">';
        msg.attachments.forEach(att => {
            const icon = attachmentIcons[att.content_type?.split('/')[0]] || '📎';
            attachmentsHtml += `
                <div class="attachment-item">
                    <span class="icon">${icon}</span>
                    <span>${escapeHtml(att.filename)}</span>
                </div>
            `;
        });
        attachmentsHtml += '</div>';
    }

    let editedHtml = msg.edited_timestamp ? '<span class="edited-tag">(已編輯)</span>' : '';

    return `
        <div class="message-card" data-index="${index}">
            <div class="message-header">
                <div class="message-avatar">${avatarInitial}</div>
                <div class="message-author-info">
                    <span class="message-author">${escapeHtml(msg.author || '未知用戶')}</span>
                    <span class="message-time">${time}</span>
                </div>
                <span class="message-channel">${escapeHtml(channelName)}</span>
            </div>
            <div class="message-content">${formatContent(content)}</div>
            ${editedHtml}
            ${attachmentsHtml}
        </div>
    `;
}

/**
 * 打開訊息詳情 Modal
 */
function openMessageModal(msg) {
    const modal = document.getElementById('message-modal');
    const modalBody = document.getElementById('modal-body');

    const avatarInitial = msg.author ? msg.author.charAt(0).toUpperCase() : '?';
    const time = formatDateTime(new Date(msg.timestamp));
    const content = escapeHtml(msg.content || '');
    const jumpUrl = msg.jump_url;

    let attachmentsHtml = '';
    if (msg.attachments && msg.attachments.length > 0) {
        attachmentsHtml = `
            <div class="modal-attachments">
                <h4>附件 (${msg.attachments.length})</h4>
                <div class="modal-attachment-list">
        `;
        msg.attachments.forEach(att => {
            const size = formatFileSize(att.size || 0);
            attachmentsHtml += `
                <div class="modal-attachment-item">
                    <div class="modal-attachment-info">
                        <span>📎</span>
                        <span class="modal-attachment-name">${escapeHtml(att.filename)}</span>
                        <span class="modal-attachment-size">${size}</span>
                    </div>
                    <a href="${att.url}" target="_blank" class="btn btn-small btn-secondary">下載</a>
                </div>
            `;
        });
        attachmentsHtml += '</div></div>';
    }

    let mentionsHtml = '';
    if (msg.mentions && msg.mentions.length > 0) {
        mentionsHtml = `<p style="color: var(--text-muted); font-size: 0.9rem;">提及: ${msg.mentions.map(m => `<span class="mention">@${escapeHtml(m)}</span>`).join(' ')}</p>`;
    }

    modalBody.innerHTML = `
        <div class="modal-message-header">
            <div class="modal-message-avatar">${avatarInitial}</div>
            <div>
                <div class="modal-message-author">${escapeHtml(msg.author || '未知用戶')}</div>
                <div class="modal-message-meta">
                    ${time}
                    ${msg.edited_timestamp ? '<span class="edited-tag">(已編輯)</span>' : ''}
                </div>
            </div>
        </div>
        <div class="modal-message-content">${formatContent(content)}</div>
        ${mentionsHtml}
        ${attachmentsHtml}
        <p style="margin-top: 1rem;">
            <a href="${jumpUrl}" target="_blank" class="btn btn-primary">在 Discord 中查看</a>
        </p>
    `;

    modal.classList.add('show');
    document.body.style.overflow = 'hidden';
}

/**
 * 關閉 Modal
 */
function closeModal() {
    const modal = document.getElementById('message-modal');
    modal.classList.remove('show');
    document.body.style.overflow = '';
}

// 點擊 Modal 外部關閉
document.addEventListener('click', function(e) {
    const modal = document.getElementById('message-modal');
    if (e.target === modal) {
        closeModal();
    }
});

// ESC 鍵關閉 Modal
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeModal();
    }
});

/**
 * 應用篩選條件
 */
function applyFilters() {
    currentOffset = 0;
    currentMessages = [];
    fetchMessages();
}

/**
 * 載入更多訊息
 */
function loadMore() {
    currentOffset += parseInt(document.getElementById('limit-select').value);
    fetchMessages();
}

/**
 * 防抖搜尋
 */
function debounceSearch(event) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        applyFilters();
    }, 300);
}

/**
 * 顯示載入狀態
 */
function showLoading() {
    document.getElementById('messages-list').innerHTML = '<p class="loading">載入中...</p>';
}

/**
 * 顯示錯誤
 */
function showError(message) {
    document.getElementById('messages-list').innerHTML = `
        <div class="error">
            <p class="error-icon">⚠️</p>
            <p>${escapeHtml(message)}</p>
        </div>
    `;
}

/**
 * 隱藏載入更多
 */
function hideLoadMore() {
    document.getElementById('load-more-container').style.display = 'none';
}

/**
 * 更新訊息數量顯示
 */
function updateMessageCount(total) {
    document.getElementById('message-count').textContent = `${formatNumber(total)} 條訊息`;
}

/**
 * 匯出 CSV
 */
function exportCSV() {
    window.location.href = '/api/export';
}

/**
 * 匯出 JSON
 */
function exportJSON() {
    window.location.href = '/api/export/json';
}

/**
 * 設置自動重新整理
 */
function setupAutoRefresh() {
    setInterval(() => {
        loadStatistics();
        if (!document.getElementById('search-input').value &&
            !document.getElementById('author-filter').value) {
            // 如果沒有搜尋條件，才重新整理
            loadMessages();
        }
    }, 30000); // 每 30 秒重新整理
}

// ==================== 工具函數 ====================

/**
 * 格式化數字
 */
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

/**
 * 格式化日期
 */
function formatDate(date) {
    const now = new Date();
    const diff = now - date;
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) {
        return '今天';
    } else if (days === 1) {
        return '昨天';
    } else if (days < 7) {
        return `${days} 天前`;
    } else if (days < 30) {
        const weeks = Math.floor(days / 7);
        return `${weeks} 週前`;
    } else if (days < 365) {
        const months = Math.floor(days / 30);
        return `${months} 個月前`;
    } else {
        const years = Math.floor(days / 365);
        return `${years} 年前`;
    }
}

/**
 * 格式化日期時間
 */
function formatDateTime(date) {
    const now = new Date();
    const diff = now - date;
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    const timeStr = date.toLocaleTimeString('zh-TW', {
        hour: '2-digit',
        minute: '2-digit'
    });

    if (days === 0) {
        return `今天 ${timeStr}`;
    } else if (days === 1) {
        return `昨天 ${timeStr}`;
    } else {
        return date.toLocaleDateString('zh-TW', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
}

/**
 * 格式化檔案大小
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * 跳脫 HTML
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * 格式化訊息內容
 */
function formatContent(content) {
    if (!content) return '';

    // 跳脫 HTML
    content = escapeHtml(content);

    // 處理換行
    content = content.replace(/\n/g, '<br>');

    // 處理 @提及
    content = content.replace(/<@(\d+)>/g, '<span class="mention">@用戶</span>');
    content = content.replace(/@(\w+)/g, '<span class="mention">@$1</span>');

    // 處理頻道提及
    content = content.replace(/<#(\d+)>/g, '<span class="mention">#頻道</span>');

    // 處理粗體
    content = content.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // 處理斜體
    content = content.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // 處理刪除線
    content = content.replace(/~~(.+?)~~/g, '<del>$1</del>');

    // 處理程式碼（行內）
    content = content.replace(/`([^`]+)`/g, '<code style="background: var(--secondary-color); padding: 0.1rem 0.4rem; border-radius: 3px; font-family: monospace;">$1</code>');

    // 處理程式碼區塊
    content = content.replace(/```(\w*)\n([\s\S]+?)```/g, '<div class="code-block"><code>$2</code></div>');

    // 處理連結
    content = content.replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank">$1</a>');

    return content;
}

// 導出全局函數供模板使用
window.applyFilters = applyFilters;
window.loadMore = loadMore;
window.debounceSearch = debounceSearch;
window.exportCSV = exportCSV;
window.exportJSON = exportJSON;
window.closeModal = closeModal;
window.showLoading = showLoading;
window.showError = showError;
window.updateMessageCount = updateMessageCount;
window.hideLoadMore = hideLoadMore;
