 let currentUser = null;
        const username = document.body.dataset.username.trim().toLowerCase();

        
        // DOM Elements
        const userListEl = document.getElementById('userList');
        const messagesEl = document.getElementById('messagesContainer');
        const messageInputEl = document.getElementById('messageInput');
        const sendBtnEl = document.getElementById('sendBtn');
        const currentChatEl = document.getElementById('currentChat');
        
        // Update online users
        async function updateOnlineUsers() {
            try {
                const response = await fetch('/api/users');
                if (response.ok) {
                    const data = await response.json();
                    const users = data.users || [];
                    
                    userListEl.innerHTML = '';
                    
                    if (users.length === 0) {
                        userListEl.innerHTML = '<div class="empty-state">No users online</div>';
                    } else {
                        users.forEach(user => {
                            const li = document.createElement('li');
                            li.className = 'user-item';
                            if (currentUser && currentUser.username === user.username) {
                                li.classList.add('active');
                            }
                            
                            li.innerHTML = `
                                <div class="user-name">${user.username}</div>
                                <div class="user-ip">${user.ip}</div>
                            `;
                            
                            li.onclick = (e) => selectUser(user, e);
                            userListEl.appendChild(li);
                        });
                    }
                }
            } catch (error) {
                console.error('Error loading users:', error);
            }
        }
        
        // Select user to chat with
        function selectUser(user, event) {
            currentUser = user;
            
            // Update UI
            document.querySelectorAll('.user-item').forEach(item => {
                item.classList.remove('active');
            });
            event.currentTarget.classList.add('active');
            
            currentChatEl.textContent = `Chat with ${user.username}`;
            
            // Enable input
            messageInputEl.disabled = false;
            sendBtnEl.disabled = false;
            messageInputEl.focus();
            
            // Load messages
            loadMessages(user.username);
        }
        
        // Load messages
        async function loadMessages(recipient) {
            try {
                const response = await fetch(`/api/messages?with=${encodeURIComponent(recipient)}`);
                if (response.ok) {
                    const data = await response.json();
                    displayMessages(data.messages || []);
                }
            } catch (error) {
                console.error('Error loading messages:', error);
            }
        }
        
        // Display messages
        function displayMessages(messages) {
            messagesEl.innerHTML = '';
            
            if (messages.length === 0) {
                messagesEl.innerHTML = '<div class="empty-state">No messages yet</div>';
                return;
            }
            
            messages.forEach(msg => {
                const div = document.createElement('div');
                const isSent = msg.sender.trim().toLowerCase() === username;
                div.className = `message ${isSent ? 'sent' : 'received'}`;
                
                const time = new Date(msg.timestamp).toLocaleTimeString();
                
                div.innerHTML = `
                    <div class="message-bubble">${msg.message}</div>
                    <div class="message-time">${time} • ${msg.sender}</div>
                `;
                
                messagesEl.appendChild(div);
            });
            
            // Scroll to bottom
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }
        
        // Send message
        async function sendMessage() {
            const message = messageInputEl.value.trim();
            if (!message || !currentUser) return;
            
            sendBtnEl.disabled = true;
            
            try {
                const response = await fetch('/api/messages', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        recipient: currentUser.username,
                        message: message
                    })
                });
                
                if (response.ok) {
                    messageInputEl.value = '';
                    loadMessages(currentUser.username);
                } else {
                    const error = await response.json();
                    alert(`Failed: ${error.error || 'Unknown error'}`);
                }
            } catch (error) {
                console.error('Error sending message:', error);
                alert('Network error');
            } finally {
                sendBtnEl.disabled = false;
                messageInputEl.focus();
            }
        }
        
        // Event listeners
        sendBtnEl.addEventListener('click', sendMessage);
        messageInputEl.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
        
        // Auto-refresh
        setInterval(updateOnlineUsers, 3000);
        setInterval(() => {
            if (currentUser) {
                loadMessages(currentUser.username);
            }
        }, 2000);
        
        // Initial load
        updateOnlineUsers();