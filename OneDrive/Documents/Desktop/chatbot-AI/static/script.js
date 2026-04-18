document.addEventListener('DOMContentLoaded', () => {
    console.log('✅ DOM loaded');

    // State
    let currentConversationId = null;
    let conversations = [];
    let availableModels = ['llama3'];

    // DOM Elements
    const chatMessages = document.getElementById('chatMessages');
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const clearInputBtn = document.getElementById('clearInputBtn');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const charCounter = document.getElementById('charCounter');
    const menuToggle = document.getElementById('menuToggle');
    const sidebar = document.getElementById('sidebar');
    const newChatBtn = document.getElementById('newChatBtn');
    const chatHistory = document.getElementById('chatHistory');
    const modelSelect = document.getElementById('modelSelect');
    const streamToggle = document.getElementById('streamToggle');
    const exportBtn = document.getElementById('exportBtn');
    const logoutBtn = document.getElementById('logoutBtn');
    const usernameDisplay = document.getElementById('usernameDisplay');

    // ==================== AUTH CHECK ====================
    async function checkAuth() {
        try {
            const res = await fetch('/api/auth/status');
            const data = await res.json();
            if (!data.authenticated) {
                window.location.href = '/login';
                return false;
            }
            if (usernameDisplay) {
                usernameDisplay.textContent = data.username || 'User';
            }
            return true;
        } catch (err) {
            console.error('Auth check failed:', err);
            window.location.href = '/login';
            return false;
        }
    }

    // Logout
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            await fetch('/api/auth/logout', { method: 'POST' });
            window.location.href = '/login';
        });
    }

    // ==================== MARKED CONFIG ====================
    marked.setOptions({
        highlight: function(code, lang) {
            if (lang && hljs.getLanguage(lang)) {
                try { return hljs.highlight(code, { language: lang }).value; } catch {}
            }
            return code;
        },
        breaks: true,
        gfm: true
    });

    function safeMarked(content) {
        if (!content || typeof content !== 'string') {
            return '<p><em>No response</em></p>';
        }
        try {
            return marked.parse(content);
        } catch (e) {
            return `<p>Error rendering: ${escapeHtml(content)}</p>`;
        }
    }

    // ==================== HELPERS ====================
    function updateCharCount() {
        if (charCounter) charCounter.textContent = `${messageInput.value.length}/5000`;
    }
    messageInput.addEventListener('input', updateCharCount);
    updateCharCount();

    messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 200) + 'px';
    });

    clearInputBtn.addEventListener('click', () => {
        messageInput.value = '';
        updateCharCount();
        messageInput.style.height = 'auto';
        messageInput.focus();
    });

    function scrollToBottom() {
        const container = document.querySelector('.chat-container');
        if (container) container.scrollTop = container.scrollHeight;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function setLoading(isLoading) {
        if (loadingIndicator) loadingIndicator.classList.toggle('hidden', !isLoading);
        sendBtn.disabled = isLoading;
        messageInput.disabled = isLoading;
        clearInputBtn.disabled = isLoading;
        if (!isLoading) messageInput.focus();
    }

    // ==================== LOAD MODELS ====================
    async function loadModels() {
        try {
            const res = await fetch('/api/models');
            const models = await res.json();
            if (models && models.length > 0) {
                availableModels = models;
                if (modelSelect) {
                    modelSelect.innerHTML = models.map(m => `<option value="${m}">${m}</option>`).join('');
                }
            }
        } catch (err) {
            console.warn('Could not load models:', err);
        }
    }

    // ==================== SIDEBAR RENDERING ====================
    function getDateGroup(dateStr) {
        const date = new Date(dateStr);
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1);
        const oneWeekAgo = new Date(today); oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
        const oneMonthAgo = new Date(today); oneMonthAgo.setMonth(oneMonthAgo.getMonth() - 1);

        if (date >= today) return 'Today';
        if (date >= yesterday) return 'Yesterday';
        if (date >= oneWeekAgo) return 'Previous 7 Days';
        if (date >= oneMonthAgo) return 'Previous 30 Days';
        return 'Older';
    }

    function renderSidebar() {
        if (!chatHistory) return;
        const groups = {};
        conversations.forEach(conv => {
            const group = getDateGroup(conv.updated_at);
            if (!groups[group]) groups[group] = [];
            groups[group].push(conv);
        });

        const groupOrder = ['Today', 'Yesterday', 'Previous 7 Days', 'Previous 30 Days', 'Older'];
        let html = '';
        groupOrder.forEach(group => {
            if (groups[group] && groups[group].length > 0) {
                html += `<div class="history-group"><div class="history-group-title">${group}</div>`;
                groups[group].forEach(conv => {
                    const activeClass = conv.id === currentConversationId ? 'active' : '';
                    html += `
                        <div class="history-item ${activeClass}" data-id="${conv.id}">
                            <i class="fas fa-message"></i>
                            <span class="history-title">${escapeHtml(conv.title || 'New Chat')}</span>
                            <button class="delete-conv-btn" data-id="${conv.id}" title="Delete">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    `;
                });
                html += `</div>`;
            }
        });
        chatHistory.innerHTML = html || '<div class="empty-history">No conversations yet</div>';

        document.querySelectorAll('.history-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (e.target.closest('.delete-conv-btn')) return;
                switchConversation(parseInt(item.dataset.id));
            });
        });
        document.querySelectorAll('.delete-conv-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const id = parseInt(btn.dataset.id);
                await fetch(`/api/conversations/${id}`, { method: 'DELETE' });
                await loadConversations();
                if (currentConversationId === id) newConversation();
            });
        });
    }

    // ==================== API CALLS ====================
    async function loadConversations() {
        try {
            const res = await fetch('/api/conversations');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            conversations = await res.json();
            renderSidebar();
        } catch (err) {
            console.error('Failed to load conversations:', err);
        }
    }

    async function switchConversation(convId) {
        try {
            const res = await fetch(`/api/conversations/${convId}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            currentConversationId = convId;
            renderSidebar();
            renderMessages(data.messages || []);
        } catch (err) {
            console.error('Failed to switch conversation:', err);
        }
    }

    async function newConversation() {
        try {
            const res = await fetch('/api/conversations', { method: 'POST' });
            const data = await res.json();
            currentConversationId = data.id;
            await loadConversations();
            renderMessages([]);
        } catch (err) {
            console.error('Failed to create conversation:', err);
        }
    }

    // ==================== EXPORT ====================
    if (exportBtn) {
        exportBtn.addEventListener('click', () => {
            if (currentConversationId) {
                window.open(`/api/conversations/${currentConversationId}/export`, '_blank');
            } else {
                alert('No conversation selected.');
            }
        });
    }

    // ==================== RENDER MESSAGES ====================
    function renderMessages(messages) {
        chatMessages.innerHTML = '';
        if (!messages || messages.length === 0) {
            const welcomeDiv = document.createElement('div');
            welcomeDiv.className = 'message bot-message welcome-message';
            welcomeDiv.innerHTML = `
                <div class="message-avatar"><i class="fas fa-robot"></i></div>
                <div class="message-content">
                    <div class="message-bubble">
                        <h2>Welcome to Nexus AI</h2>
                        <p>I'm your private, offline AI assistant powered by Ollama.</p>
                        <div class="quick-actions">
                            <button class="quick-action" data-prompt="Explain quantum computing in simple terms">🔬 Explain quantum computing</button>
                            <button class="quick-action" data-prompt="Write a Python function to reverse a string">🐍 Write Python code</button>
                            <button class="quick-action" data-prompt="Give me a productivity tip">💡 Productivity tip</button>
                        </div>
                    </div>
                </div>
            `;
            chatMessages.appendChild(welcomeDiv);
            document.querySelectorAll('.quick-action').forEach(btn => {
                btn.addEventListener('click', () => {
                    messageInput.value = btn.dataset.prompt;
                    updateCharCount();
                    messageInput.style.height = 'auto';
                    messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + 'px';
                    handleSend();
                });
            });
            return;
        }

        messages.forEach(msg => {
            const isUser = msg.role === 'user';
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
            msgDiv.innerHTML = `
                <div class="message-avatar">
                    <i class="fas fa-${isUser ? 'user' : 'robot'}"></i>
                </div>
                <div class="message-content">
                    <div class="message-bubble">
                        ${isUser ? `<p>${escapeHtml(msg.content)}</p>` : safeMarked(msg.content)}
                    </div>
                </div>
            `;
            chatMessages.appendChild(msgDiv);
        });
        document.querySelectorAll('.bot-message pre code').forEach(hljs.highlightElement);
        scrollToBottom();
    }

    function addUserMessageToUI(text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message user-message';
        msgDiv.innerHTML = `
            <div class="message-avatar"><i class="fas fa-user"></i></div>
            <div class="message-content"><div class="message-bubble"><p>${escapeHtml(text)}</p></div></div>
        `;
        chatMessages.appendChild(msgDiv);
        scrollToBottom();
    }

    function addBotMessageToUI(content) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message bot-message';
        msgDiv.innerHTML = `
            <div class="message-avatar"><i class="fas fa-robot"></i></div>
            <div class="message-content"><div class="message-bubble">${safeMarked(content)}</div></div>
        `;
        chatMessages.appendChild(msgDiv);
        msgDiv.querySelectorAll('pre code').forEach(hljs.highlightElement);
        scrollToBottom();
        return msgDiv;
    }

    function updateBotMessageContent(botMsgDiv, content) {
        const bubble = botMsgDiv.querySelector('.message-bubble');
        bubble.innerHTML = safeMarked(content);
        bubble.querySelectorAll('pre code').forEach(hljs.highlightElement);
        scrollToBottom();
    }

    // ==================== SEND MESSAGE ====================
    async function handleSend() {
        const message = messageInput.value.trim();
        if (!message) return;
        if (message.length > 5000) {
            alert('Message too long (max 5000 characters)');
            return;
        }

        const useStream = streamToggle ? streamToggle.checked : true;
        const model = modelSelect ? modelSelect.value : (availableModels[0] || 'llama3');

        if (!currentConversationId) {
            try {
                const res = await fetch('/api/conversations', { method: 'POST' });
                const data = await res.json();
                currentConversationId = data.id;
            } catch (err) {
                console.error('Failed to create conversation:', err);
                addBotMessageToUI('❌ Error creating conversation.');
                return;
            }
        }

        addUserMessageToUI(message);
        messageInput.value = '';
        updateCharCount();
        messageInput.style.height = 'auto';

        setLoading(true);

        try {
            if (useStream) {
                const response = await fetch('/chat/stream', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message, conversation_id: currentConversationId, model })
                });

                if (!response.ok) {
                    const errData = await response.json().catch(() => ({}));
                    throw new Error(errData.error || 'Stream request failed');
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let botMsgDiv = null;
                let fullContent = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value, { stream: true });
                    const lines = chunk.split('\n');

                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            const jsonStr = line.slice(6);
                            try {
                                const data = JSON.parse(jsonStr);
                                if (data.token) {
                                    fullContent += data.token;
                                    if (!botMsgDiv) {
                                        botMsgDiv = addBotMessageToUI(fullContent);
                                    } else {
                                        updateBotMessageContent(botMsgDiv, fullContent);
                                    }
                                } else if (data.done) {
                                    if (data.conversation_id) {
                                        currentConversationId = data.conversation_id;
                                    }
                                } else if (data.error) {
                                    addBotMessageToUI(`❌ Error: ${data.error}`);
                                }
                            } catch (e) {
                                console.warn('Failed to parse SSE:', jsonStr);
                            }
                        }
                    }
                }
            } else {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message, conversation_id: currentConversationId, model })
                });

                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'Server error');

                const aiResponse = data.response || 'No response received.';
                addBotMessageToUI(aiResponse);
                if (data.conversation_id) {
                    currentConversationId = data.conversation_id;
                }
            }

            await loadConversations();
            renderSidebar();
        } catch (err) {
            console.error('Send error:', err);
            addBotMessageToUI(`❌ **Error:** ${err.message}`);
        } finally {
            setLoading(false);
        }
    }

    // ==================== EVENT LISTENERS ====================
    sendBtn.addEventListener('click', handleSend);
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });
    newChatBtn.addEventListener('click', newConversation);
    if (menuToggle) {
        menuToggle.addEventListener('click', () => {
            sidebar?.classList.toggle('collapsed');
        });
    }

    // ==================== INIT ====================
    checkAuth().then(isAuth => {
        if (!isAuth) return;
        loadModels();
        loadConversations().then(() => {
            if (conversations.length > 0) {
                switchConversation(conversations[0].id);
            } else {
                renderMessages([]);
            }
        });
    });
});