 // Auto-hide alerts after 5 seconds
        setTimeout(() => {
            document.querySelectorAll('.alert').forEach(alert => {
                alert.style.opacity = '0';
                alert.style.transition = 'opacity 0.5s';
                setTimeout(() => alert.style.display = 'none', 500);
            });
        }, 5000);
        
        // Focus on username field
        document.getElementById('username').focus();