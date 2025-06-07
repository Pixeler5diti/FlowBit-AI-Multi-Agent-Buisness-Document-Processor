// Main JavaScript file for the Multi-Agent Document Classifier

document.addEventListener('DOMContentLoaded', function() {
    // Initialize form handling
    initializeUploadForm();
    
    // Initialize tooltips
    initializeTooltips();
    
    console.log('Multi-Agent Document Classifier initialized');
});

function initializeUploadForm() {
    const uploadForm = document.getElementById('uploadForm');
    const fileInput = document.getElementById('file');
    const loadingModal = new bootstrap.Modal(document.getElementById('loadingModal'));
    
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            // Validate file selection
            if (!fileInput.files.length) {
                e.preventDefault();
                showAlert('Please select a file to upload', 'error');
                return;
            }
            
            // Validate file size (16MB limit)
            const file = fileInput.files[0];
            const maxSize = 16 * 1024 * 1024; // 16MB
            
            if (file.size > maxSize) {
                e.preventDefault();
                showAlert('File size exceeds 16MB limit. Please select a smaller file.', 'error');
                return;
            }
            
            // Show loading modal
            loadingModal.show();
        });
    }
    
    // File input change handler
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                // Update UI to show selected file
                const fileName = file.name;
                const fileSize = formatFileSize(file.size);
                
                console.log(`File selected: ${fileName} (${fileSize})`);
                
                // You could add file preview here in future versions
            }
        });
    }
}

function initializeTooltips() {
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

function showAlert(message, type = 'info') {
    // Create and show a custom alert
    const alertContainer = document.createElement('div');
    alertContainer.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
    alertContainer.innerHTML = `
        <i class="fas fa-${type === 'error' ? 'exclamation-triangle' : 'info-circle'} me-2"></i>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Insert at top of main container
    const container = document.querySelector('.container');
    container.insertBefore(alertContainer, container.firstChild);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alertContainer && alertContainer.parentNode) {
            alertContainer.remove();
        }
    }, 5000);
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// API helper functions for future use
class DocumentClassifierAPI {
    constructor(baseURL = '') {
        this.baseURL = baseURL;
    }
    
    async classifyDocument(content, filename) {
        try {
            const response = await fetch('/api/classify', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    content: content,
                    filename: filename
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('Classification API error:', error);
            throw error;
        }
    }
    
    async getResults(resultId) {
        try {
            const response = await fetch(`/api/results/${resultId}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('Get results API error:', error);
            throw error;
        }
    }
}

// Global API instance for future use
window.classifierAPI = new DocumentClassifierAPI();

// Utility functions for results page
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showAlert('Copied to clipboard!', 'success');
    }, function(err) {
        console.error('Could not copy text: ', err);
        showAlert('Failed to copy to clipboard', 'error');
    });
}

// Export functionality for future LangFlow integration
function exportToLangFlow(resultData) {
    const langFlowFormat = {
        "nodes": [
            {
                "id": "classifier-1",
                "type": "classifier",
                "data": {
                    "component": "ClassifierAgent",
                    "inputs": {
                        "document_content": "{{input}}",
                        "filename": "{{filename}}"
                    },
                    "outputs": {
                        "document_format": resultData.document_format,
                        "business_intent": resultData.business_intent,
                        "confidence_score": resultData.confidence_score
                    }
                },
                "position": { "x": 100, "y": 100 }
            }
        ],
        "edges": [],
        "viewport": { "x": 0, "y": 0, "zoom": 1 }
    };
    
    // Create and download JSON file
    const blob = new Blob([JSON.stringify(langFlowFormat, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `classifier-flow-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showAlert('LangFlow export downloaded!', 'success');
}

console.log('Document Classifier JavaScript loaded successfully');
