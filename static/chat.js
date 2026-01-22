let currentUser = null;
const username = document.body.dataset.username.trim().toLowerCase();

// DOM Elements
const userListEl = document.getElementById('userList');
const messagesEl = document.getElementById('messagesContainer');
const messageInputEl = document.getElementById('messageInput');
const sendBtnEl = document.getElementById('sendBtn');
const currentChatEl = document.getElementById('currentChat');

let typingTimeout;

// ----------------- Online Users -----------------
async function updateOnlineUsers() {
    try {
        const response = await fetch('/api/users');
        if (!response.ok) return;
        const data = await response.json();
        const users = data.users || [];

        userListEl.innerHTML = '';
        if (!users.length) {
            userListEl.innerHTML = '<div class="empty-state">No users online</div>';
            return;
        }

        users.forEach(user => {
            const li = document.createElement('li');
            li.className = 'user-item';
            if (currentUser && currentUser.username === user.username) li.classList.add('active');
            li.innerHTML = `<div class="user-name">${user.username}</div>`;
            li.onclick = (e) => selectUser(user, e);
            userListEl.appendChild(li);
        });
    } catch (err) {
        console.error('Error loading users:', err);
    }
}

// ----------------- Select Chat -----------------
function selectUser(user, event) {
    currentUser = user;
    document.querySelectorAll('.user-item').forEach(i => i.classList.remove('active'));
    event.currentTarget.classList.add('active');

    currentChatEl.textContent = `Chat with ${user.username}`;
    messageInputEl.disabled = sendBtnEl.disabled = false;
    messageInputEl.focus();

    loadMessages(user.username);
}

// ----------------- Messages -----------------
async function loadMessages(recipient) {
    try {
        const response = await fetch(`/api/messages?with=${encodeURIComponent(recipient)}`);
        if (!response.ok) return;
        const data = await response.json();
        const messages = data.messages || [];
        displayMessages(messages);
        markMessagesAsRead(messages);
    } catch (err) {
        console.error('Error loading messages:', err);
    }
}

function displayMessages(messages) {
    messagesEl.innerHTML = '';
    if (!messages.length) {
        messagesEl.innerHTML = '<div class="empty-state">No messages yet</div>';
        return;
    }

    messages.forEach(msg => {
        const div = document.createElement('div');
        const isSent = msg.sender.trim().toLowerCase() === username;
        div.className = `message ${isSent ? 'sent' : 'received'}`;

        const time = new Date(msg.timestamp).toLocaleTimeString();
        let statusHTML = '';

        if (isSent) {
            // Show "sent", "delivered", "read"
            if (msg.status === 'read') statusHTML = '<span class="status read">Read</span>';
            else if (msg.status === 'delivered') statusHTML = '<span class="status delivered">Delivered</span>';
            else statusHTML = '<span class="status sent">Sent</span>';
        }

        div.innerHTML = `
            <div class="message-bubble">${msg.message}</div>
            <div class="message-time">${time} • ${msg.sender} ${statusHTML}</div>
        `;
        messagesEl.appendChild(div);
    });

    messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ----------------- Send Message -----------------
async function sendMessage() {
    const message = messageInputEl.value.trim();
    if (!message || !currentUser) return;
    sendBtnEl.disabled = true;

    try {
        const response = await fetch('/api/messages', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ recipient: currentUser.username, message })
        });

        if (response.ok) {
            messageInputEl.value = '';
            loadMessages(currentUser.username);
        } else {
            const error = await response.json();
            alert(`Failed: ${error.error || 'Unknown error'}`);
        }
    } catch (err) {
        console.error('Error sending message:', err);
        alert('Network error');
    } finally {
        sendBtnEl.disabled = false;
        messageInputEl.focus();
    }
}

// ----------------- Typing -----------------
messageInputEl.addEventListener('input', () => {
    if (!currentUser) return;
    notifyTyping('start');
    clearTimeout(typingTimeout);
    typingTimeout = setTimeout(() => notifyTyping('stop'), 1000);
});

async function notifyTyping(action) {
    try {
        await fetch('/api/typing', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ recipient: currentUser.username, action })
        });
    } catch (err) {
        console.error('Typing notification failed', err);
    }
}

async function fetchTyping() {
    if (!currentUser) return;
    try {
        const res = await fetch('/api/get_typing');
        const data = await res.json();
        const typingUsers = data.typing || [];

        let indicator = document.getElementById('typingIndicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'typingIndicator';
            indicator.style.padding = '0 20px 10px';
            indicator.style.fontSize = '12px';
            indicator.style.color = '#555';
            messagesEl.parentNode.insertBefore(indicator, messagesEl.nextSibling);
        }

        indicator.textContent = typingUsers.includes(currentUser.username)
            ? `${currentUser.username} is typing...`
            : '';
    } catch (err) {
        console.error('Failed to fetch typing users', err);
    }
}

// ----------------- Read Receipts -----------------
async function markMessagesAsRead(messages) {
    for (const msg of messages) {
        if (msg.recipient.toLowerCase() === username && msg.status !== 'read') {
            try {
                await fetch('/api/update_status', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message_id: msg.id, status: 'read' })
                });
            } catch (err) {
                console.error('Failed to update read status', err);
            }
        }
    }
}

// ----------------- Event Listeners -----------------
sendBtnEl.addEventListener('click', sendMessage);
messageInputEl.addEventListener('keypress', e => { if (e.key === 'Enter') sendMessage(); });

// ----------------- Polling -----------------
setInterval(updateOnlineUsers, 3000);
setInterval(() => {
    if (currentUser) {
        loadMessages(currentUser.username);
        fetchTyping();
    }
}, 2000);

// ----------------- Initial Load -----------------
updateOnlineUsers();
