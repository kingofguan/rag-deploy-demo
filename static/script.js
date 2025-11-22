// API base URL (will be the same origin in production)
const API_BASE = '';

// DOM elements
const messagesContainer = document.getElementById('messages');
const questionInput = document.getElementById('questionInput');
const sendButton = document.getElementById('sendButton');
const buttonText = document.getElementById('buttonText');
const buttonSpinner = document.getElementById('buttonSpinner');
const systemInfo = document.getElementById('systemInfo');
const statusIndicator = document.getElementById('statusText');

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    loadSystemInfo();
});

// Check system health
async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE}/health`);
        const data = await response.json();
        
        if (data.status === 'healthy' && data.qa_chain_initialized) {
            statusIndicator.textContent = 'System Online';
        } else {
            statusIndicator.textContent = 'System Initializing...';
        }
    } catch (error) {
        statusIndicator.textContent = 'System Offline';
        console.error('Health check failed:', error);
    }
}

// Load system information
async function loadSystemInfo() {
    try {
        const response = await fetch(`${API_BASE}/api/info`);
        const data = await response.json();
        
        systemInfo.innerHTML = `
            <p><strong>App Name:</strong> ${data.app_name}</p>
            <p><strong>Description:</strong> ${data.description}</p>
            <p><strong>Technologies:</strong></p>
            <ul style="margin-left: 20px; margin-top: 5px;">
                ${data.technologies.map(tech => `<li>${tech}</li>`).join('')}
            </ul>
            <p style="margin-top: 10px;"><strong>Status:</strong> <span style="color: #10b981;">✓ ${data.status}</span></p>
        `;
    } catch (error) {
        systemInfo.innerHTML = '<p style="color: #ef4444;">Failed to load system information</p>';
        console.error('Failed to load system info:', error);
    }
}

// Send question to backend
async function sendQuestion() {
    const question = questionInput.value.trim();
    
    if (!question) {
        return;
    }
    
    // Disable input while processing
    setLoading(true);
    
    // Add user message to chat
    addMessage('user', question);
    
    // Clear input
    questionInput.value = '';
    
    try {
        const response = await fetch(`${API_BASE}/api/ask`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ question }),
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Add assistant response to chat
        addMessage('assistant', data.answer, data.sources);
        
    } catch (error) {
        console.error('Error sending question:', error);
        addMessage('assistant', 'Sorry, I encountered an error processing your question. Please try again.', null, true);
    } finally {
        setLoading(false);
    }
}

// Add message to chat
function addMessage(role, content, sources = null, isError = false) {
    // Remove welcome message if it exists
    const welcomeMessage = document.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.remove();
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const label = role === 'user' ? 'You' : 'Assistant';
    
    let messageHTML = `
        <div class="message-label">${label}</div>
        <div class="message-content ${isError ? 'error-message' : ''}">
            ${content}
        </div>
    `;
    
    if (sources && sources.length > 0) {
        messageHTML += `
            <div class="sources">
                <h4>📚 Sources:</h4>
                ${sources.map((source, idx) => `
                    <div class="source-item">
                        <strong>Source ${idx + 1}:</strong> ${source}
                    </div>
                `).join('')}
            </div>
        `;
    }
    
    messageDiv.innerHTML = messageHTML;
    messagesContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Set loading state
function setLoading(loading) {
    sendButton.disabled = loading;
    questionInput.disabled = loading;
    
    if (loading) {
        buttonText.style.display = 'none';
        buttonSpinner.style.display = 'inline-block';
    } else {
        buttonText.style.display = 'inline';
        buttonSpinner.style.display = 'none';
    }
}

