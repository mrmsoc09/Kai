document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const loginError = document.getElementById('loginError');
    const loginContainer = document.getElementById('login-container');
    const mainContainer = document.querySelector('.container');

    // Hardcoded credentials for placeholder authentication
    const ADMIN_USERNAME = 'admin';
    const ADMIN_PASSWORD = 'password'; 

    function showLogin() {
        loginContainer.style.display = 'block';
        mainContainer.style.display = 'none';
    }

    function showAdminConsole() {
        loginContainer.style.display = 'none';
        mainContainer.style.display = 'block';
        initializeAdminFeatures(); // Call function to initialize admin console features
    }

    // Login Form Submission
    if (loginForm) {
        loginForm.addEventListener('submit', (event) => {
            event.preventDefault();
            const username = usernameInput.value;
            const password = passwordInput.value;

            if (username === ADMIN_USERNAME && password === ADMIN_PASSWORD) {
                localStorage.setItem('authenticated', 'true');
                showAdminConsole();
            } else {
                loginError.style.display = 'block';
            }
        });
    }

    // Check for existing session (e.g., localStorage) on page load
    if (localStorage.getItem('authenticated') === 'true') {
        showAdminConsole();
    } else {
        showLogin();
    }

    function initializeAdminFeatures() {
        const startScanForm = document.getElementById('startScanForm');
        const targetDomainInput = document.getElementById('targetDomain');
        const scanStatusDiv = document.getElementById('scanStatus');
        const navLinks = document.querySelectorAll('nav ul li a');
        const sections = document.querySelectorAll('main section');
    
        // Navigation functionality
        navLinks.forEach(link => {
            link.addEventListener('click', (event) => {
                event.preventDefault();
                const targetId = event.target.getAttribute('href').substring(1);
                
                sections.forEach(section => {
                    if (section.id === targetId) {
                        section.style.display = 'block';
                    } else {
                        section.style.display = 'none';
                    }
                });
            });
        });
    
        // Start Scan Form Submission
        if (startScanForm) {
            startScanForm.addEventListener('submit', async (event) => {
                event.preventDefault();
                const targetDomain = targetDomainInput.value.trim();
    
                if (!targetDomain) {
                    displayStatus('Please enter a target domain.', 'error');
                    return;
                }
    
                displayStatus('Initiating scan...', 'info');
    
                try {
                    // Note: The orchestrator service will be accessible via its service name and port within the Docker network.
                    // For frontend, if it's served by Nginx proxying to orchestrator, it would be a relative path.
                    // For direct access from browser (if exposed via ports), it would be localhost:8000.
                    // Assuming Nginx in admin_gui container will proxy /api to orchestrator:8000 for local dev setup.
                    const response = await fetch('http://localhost:8000/admin/start_scan', { // This will need to be proxied by Nginx in Docker
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ target_domain: targetDomain }),
                    });
    
                    const data = await response.json();
    
                    if (response.ok) {
                        displayStatus(`Scan initiated successfully for ${targetDomain}. Message: ${data.message}`, 'success');
                    } else {
                        displayStatus(`Failed to initiate scan: ${data.detail || response.statusText}`, 'error');
                    }
                } catch (error) {
                    console.error('Error initiating scan:', error);
                    displayStatus('An unexpected error occurred while trying to start the scan.', 'error');
                }
            });
        }
    
        function displayStatus(message, type) {
            scanStatusDiv.textContent = message;
            scanStatusDiv.style.display = 'block';
            scanStatusDiv.className = ''; // Clear existing classes
            scanStatusDiv.classList.add(type); // Add success, error, or info class
        }
    }
});
