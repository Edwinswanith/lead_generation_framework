document.addEventListener('DOMContentLoaded', function() {
    // Socket connection setup
    const socket = io({
        auth: {
            session_id: sessionId
        }
    });

    const agentMonitoringContainer = document.getElementById('agent-monitoring-container');
    const companiesBody = document.getElementById('enriched-companies-body');
    const dataModalElement = document.getElementById('dataModal');
    let dataModal;
    if (dataModalElement) {
        dataModal = new bootstrap.Modal(dataModalElement);
    }
    
    const startButton = document.querySelector('button[onclick="startAgent()"]');
    const stopButton = document.querySelector('button[onclick="stopAgent()"]');
    const clearButton = document.querySelector('button[onclick="clearData()"]');
    const agentControls = document.getElementById('agent-controls');
    let timerInterval;
    let startTime;

    // Initialize email modal
    const emailModal = new bootstrap.Modal(document.getElementById('emailModal'));
    let emailStatusList = null;

    // Function to ensure email modal elements are ready
    function initializeEmailModal() {
        emailStatusList = document.getElementById('email-status-list');
        if (!emailStatusList) {
            console.warn('Email status list container not found');
        }
        return emailStatusList !== null;
    }

    // Function to update email status
    function updateEmailStatus(status) {
        if (!emailStatusList && !initializeEmailModal()) {
            console.error('Could not initialize email status container');
            return;
        }

        const statusHtml = `
            <div class="alert ${status.success ? 'alert-success' : 'alert-danger'}">
                <strong>${status.company_name}</strong><br>
                ${status.message}
            </div>
        `;
        emailStatusList.innerHTML = statusHtml + emailStatusList.innerHTML;
    }

    // Function to update email progress
    function updateEmailProgress(progress) {
        const progressBar = document.getElementById('email-progress-bar');
        const progressText = document.getElementById('email-progress-text');
        if (progressBar && progressText) {
            const percentage = (progress.sent / progress.total) * 100;
            progressBar.style.width = percentage + '%';
            progressBar.setAttribute('aria-valuenow', percentage);
            progressText.textContent = `${progress.sent}/${progress.total}`;
        }
    }

    function checkAgentStatus() {
        fetch('/status')
            .then(response => response.json())
            .then(data => {
                if (data.running) {
                    if (startButton) startButton.disabled = true;
                    if (agentControls) agentControls.style.display = 'block';
                    if (document.getElementById('results-section')) document.getElementById('results-section').style.display = 'block';
                } else {
                    if (startButton) startButton.disabled = false;
                    if (agentControls) agentControls.style.display = 'none';
                }
            });
    }

    if (startButton) {
        checkAgentStatus();
    }

    // Toast configuration for notifications
    const Toast = Swal.mixin({
        toast: true,
        position: 'top-end',
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true,
        didOpen: (toast) => {
            toast.addEventListener('mouseenter', Swal.stopTimer)
            toast.addEventListener('mouseleave', Swal.resumeTimer)
        }
    });

    // Function to show loading state
    function showLoading(message = 'Processing...') {
        Swal.fire({
            title: message,
            allowOutsideClick: false,
            allowEscapeKey: false,
            showConfirmButton: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });
    }

    // Function to show success message
    function showSuccess(title, message) {
        Toast.fire({
            icon: 'success',
            title: title,
            text: message
        });
    }

    // Function to show error message
    function showError(title, message) {
        Swal.fire({
            icon: 'error',
            title: title,
            text: message,
            confirmButtonText: 'OK'
        });
    }

    // Function to show warning message
    function showWarning(title, message) {
        Toast.fire({
            icon: 'warning',
            title: title,
            text: message
        });
    }

    socket.on('connect', function() {
        console.log('Connected to server');
        Toast.fire({
            icon: 'success',
            title: 'Connected to server'
        });
    });

    socket.on('disconnect', function() {
        console.log('Disconnected from server');
        Toast.fire({
            icon: 'error',
            title: 'Disconnected from server'
        });
    });

    socket.on('connect_error', function() {
        console.log('Connection error');
        Toast.fire({
            icon: 'error',
            title: 'Connection error'
        });
    });

    socket.on('logs_update', function(data) {
        updateLogs(data);
    });

    socket.on('companies_update', function(data) {
        updateCompanies(data);
    });

    socket.on('token_update', function(data) {
        updateTokens(data);
    });

    socket.on('progress_update', function(data) {
        updateProgress(data);
    });

    function updateTokens(data) {
        const totalCostEl = document.getElementById('total-cost');
        const totalCostContainer = document.getElementById('total-cost-container');
        if (totalCostEl) totalCostEl.textContent = `$${data.total_cost.toFixed(2)}`;
        if (totalCostContainer) totalCostContainer.style.display = 'block';
    }

    function updateProgress(data) {
        const progressBar = document.getElementById('progress-bar');
        const progressText = document.getElementById('progress-text');
        const progressContainer = document.getElementById('progress-container');
        const emailActionsGroup = document.getElementById('email-actions-group');
        
        if (progressContainer) {
            if (data.total > 0) {
                progressContainer.style.display = 'block';
                const percentage = (data.processed / data.total) * 100;
                if (progressBar) {
                    progressBar.style.width = percentage + '%';
                    progressBar.setAttribute('aria-valuenow', percentage);
                }
                if (progressText) progressText.textContent = `${data.processed} / ${data.total} companies processed`;

                if (data.processed === data.total) {
                    if (progressBar) {
                        progressBar.classList.remove('progress-bar-animated');
                        progressBar.classList.add('bg-success');
                    }
                    if (progressText) progressText.textContent += " - Complete!";
                    if (emailActionsGroup) emailActionsGroup.style.display = 'inline-flex';
                    stopTimer();
                } else {
                    if (progressBar) {
                        progressBar.classList.add('progress-bar-animated');
                        progressBar.classList.remove('bg-success');
                    }
                    if (emailActionsGroup) emailActionsGroup.style.display = 'none';
                }
            } else {
                progressContainer.style.display = 'none';
                if (emailActionsGroup) emailActionsGroup.style.display = 'none';
            }
        }
    }

    function updateLogs(data) {
        if (!agentMonitoringContainer) return;
        agentMonitoringContainer.innerHTML = '';
        agentMonitoringContainer.className = 'accordion';
        agentMonitoringContainer.id = 'agentLogsAccordion';

        let isFirst = true;
        let i = 0;
        for (const agent in data) {
            const accordionItemId = `collapse${i}`;
            const headerId = `heading${i}`;

            const agentContainer = document.createElement('div');
            agentContainer.className = 'accordion-item';

            const header = document.createElement('h2');
            header.className = 'accordion-header';
            header.id = headerId;
            
            const button = document.createElement('button');
            button.className = 'accordion-button';
            if (isFirst) {
                button.setAttribute('aria-expanded', 'true');
            } else {
                button.classList.add('collapsed');
                button.setAttribute('aria-expanded', 'false');
            }
            button.setAttribute('type', 'button');
            button.setAttribute('data-bs-toggle', 'collapse');
            button.setAttribute('data-bs-target', `#${accordionItemId}`);
            button.setAttribute('aria-controls', accordionItemId);
            button.innerHTML = `<i class="fas fa-robot me-2"></i>Agent: ${agent}`;
            header.appendChild(button);

            const collapseContainer = document.createElement('div');
            collapseContainer.id = accordionItemId;
            collapseContainer.className = 'accordion-collapse collapse';
            if (isFirst) {
                collapseContainer.classList.add('show');
            }
            collapseContainer.setAttribute('aria-labelledby', headerId);
            collapseContainer.setAttribute('data-bs-parent', '#agentLogsAccordion');

            const body = document.createElement('div');
            body.className = 'accordion-body agent-log-body';
            
            data[agent].forEach(log => {
                const logElement = document.createElement('div');
                const levelColor = log.level === 'INFO' ? '#3498db' : 
                                 log.level === 'WARNING' ? '#f1c40f' : 
                                 log.level === 'ERROR' ? '#e74c3c' : '#2ecc71';
                logElement.innerHTML = `
                    <div>
                        <span style="color: #bdc3c7">[${log.timestamp}]</span> 
                        <span style="color: ${levelColor}">[${log.level}]</span> 
                    </div>
                    <div style="padding-left: 20px;"><strong>Task:</strong> ${log.task}</div>
                `;
                body.appendChild(logElement);
            });

            collapseContainer.appendChild(body);
            agentContainer.appendChild(header);
            agentContainer.appendChild(collapseContainer);
            agentMonitoringContainer.appendChild(agentContainer);
            
            isFirst = false;
            i++;
        }
    }

    function updateCompanies(data) {
        if (!companiesBody) return;
        companiesBody.innerHTML = '';
        data.forEach(company => {
            const row = document.createElement('tr');
            row.onclick = () => showCompanyDetails(row);
            row.innerHTML = `
                <td class="fw-bold text-truncate">${company['Company Name']}</td>
                <td class="text-truncate"><a href="${company['Website']}" class="text-decoration-none" target="_blank">${company['Website']}</a></td>
                <td class="text-truncate">${company['CEO Name']}</td>
                <td class="text-truncate">${company['CEO Email']}</td>
                <td class="text-truncate">${company['Company Revenue']}</td>
                <td class="text-truncate">${company['Company Employee Count']}</td>
                <td class="text-truncate">${company['Company Founding Year']}</td>
                <td class="text-truncate">${company['Target Industries']}</td>
                <td class="text-truncate">${company['Target Company Size']}</td>
                <td class="text-truncate">${company['Target Geography']}</td>
                <td class="text-truncate">${company['Client Examples']}</td>
                <td class="text-truncate">${company['Service Focus']}</td>
                <td class="text-truncate">${company['Ranking']}</td>
                <td class="text-truncate">${company['Reasoning']}</td>
            `;
            companiesBody.appendChild(row);
        });
    }

    // Remove the old showModal function and replace with enhanced company details view
    function showCompanyDetails(row) {
        const cells = row.getElementsByTagName('td');
        const companyData = {
            'Company Name': cells[0].textContent,
            'Website': cells[1].textContent,
            'CEO Name': cells[2].textContent,
            'CEO Email': cells[3].textContent,
            'Company Revenue': cells[4].textContent,
            'Company Employee Count': cells[5].textContent,
            'Company Founding Year': cells[6].textContent,
            'Target Industries': cells[7].textContent,
            'Target Company Size': cells[8].textContent,
            'Target Geography': cells[9].textContent,
            'Client Examples': cells[10].textContent,
            'Service Focus': cells[11].textContent,
            'Ranking': cells[12].textContent,
            'Reasoning': cells[13].textContent
        };

        Swal.fire({
            title: `<strong>${companyData['Company Name']}</strong>`,
            html: `
                <div class="table-responsive">
                    <table class="table table-bordered table-striped">
                        <tbody>
                            ${Object.entries(companyData).map(([key, value]) => `
                                <tr>
                                    <th class="text-start bg-light" style="width: 30%;">${key}</th>
                                    <td class="text-start">${value || 'N/A'}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `,
            width: '800px',
            showCloseButton: true,
            showConfirmButton: false,
            showClass: {
                popup: 'animate__animated animate__fadeIn animate__faster'
            },
            hideClass: {
                popup: 'animate__animated animate__fadeOut animate__faster'
            },
            customClass: {
                container: 'company-details-modal',
                popup: 'rounded-4 shadow-lg',
                header: 'border-bottom pb-3',
                closeButton: 'btn btn-sm btn-light'
            }
        });
    }

    function stopTimer() {
        clearInterval(timerInterval);
        if (startTime) {
            const elapsedTime = Math.floor((Date.now() - startTime) / 1000);
            const minutes = Math.floor(elapsedTime / 60);
            const seconds = elapsedTime % 60;
            const timerEl = document.getElementById('timer');
            if (timerEl) timerEl.textContent = 
                `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        }
        if (startButton) {
            startButton.disabled = false;
            startButton.innerHTML = '<i class="fas fa-play-circle me-2"></i>Launch Agent';
        }
        if (stopButton) stopButton.disabled = true;
        if (clearButton) clearButton.disabled = false;
        if (agentControls) agentControls.style.display = 'block'; 
    }

    // Modify window.startAgent
    window.startAgent = function() {
        const fileInput = document.getElementById('fileInput');
        if (!fileInput) return;
        const file = fileInput.files[0];

        if (!file) {
            showWarning('No File Selected', 'Please select a file to upload.');
            return;
        }

        // Show file validation dialog
        Swal.fire({
            title: 'Start Processing?',
            html: `
                <div class="text-start">
                    <p><strong>File Details:</strong></p>
                    <ul>
                        <li>Name: ${file.name}</li>
                        <li>Size: ${(file.size / 1024).toFixed(2)} KB</li>
                        <li>Type: ${file.type || 'Unknown'}</li>
                    </ul>
                </div>
            `,
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Start Processing',
            cancelButtonText: 'Cancel',
            confirmButtonColor: '#3085d6',
            cancelButtonColor: '#d33'
        }).then((result) => {
            if (result.isConfirmed) {
                showLoading('Initializing agent...');

        const resultsSection = document.getElementById('results-section');
        if (resultsSection) resultsSection.style.display = 'block';

        if (startButton) {
            startButton.disabled = true;
            startButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
        }
        if (agentControls) agentControls.style.display = 'block';
        if (clearButton) clearButton.disabled = true;

                // Reset UI elements
        if (agentMonitoringContainer) agentMonitoringContainer.innerHTML = '';
        if (companiesBody) companiesBody.innerHTML = '';
        const totalCostEl = document.getElementById('total-cost');
        if (totalCostEl) totalCostEl.textContent = '$0.00';
        updateProgress({ processed: 0, total: 0 });

                // Start timer
        const timerContainer = document.getElementById('timer-container');
        const timerElement = document.getElementById('timer');
        if (timerContainer) timerContainer.style.display = 'block';
        if (timerElement) timerElement.textContent = '00:00';
        clearInterval(timerInterval);
        startTime = Date.now();
        timerInterval = setInterval(() => {
            const elapsedTime = Math.floor((Date.now() - startTime) / 1000);
            const minutes = Math.floor(elapsedTime / 60);
            const seconds = elapsedTime % 60;
            if (timerElement) timerElement.textContent = 
                `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        }, 1000);

        const formData = new FormData();
        formData.append('inputFile', file);

        fetch('/generate-leads', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
                    Swal.close();
            if (data.error) {
                        showError('Error', data.error);
                stopTimer();
            } else {
                        showSuccess('Success', 'Agent process started successfully');
                if (startButton) startButton.disabled = true;
                if (agentControls) agentControls.style.display = 'block';
            }
        })
        .catch(error => {
            console.error('Error:', error);
                    showError('Error', 'Failed to start the agent process');
            stopTimer();
        });
    }
        });
    };

    // Modify window.downloadEnrichedData
    window.downloadEnrichedData = function() {
        showLoading('Preparing download...');
        fetch('/download_file')
            .then(response => {
                Swal.close();
                if (response.status === 202) {
                    return response.json().then(data => {
                        showWarning('Please Wait', data.error);
                        return null;
                    });
                }
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.blob();
            })
            .then(blob => {
                if (!blob) return;
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'enriched_companies.csv';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                showSuccess('Success', 'Download started successfully');
            })
            .catch(error => {
                console.error('Error downloading file:', error);
                showError('Download Failed', 'Unable to download the file. Please try again.');
            });
    };

    window.stopAgent = function() {
        if (stopButton) stopButton.disabled = true;

        fetch('/stop-agent', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            console.log(data.message);
            alert('Agent stopping... The process will halt shortly.');
            stopTimer(); 
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while stopping the agent.');
            if (stopButton) stopButton.disabled = false;
        });
    };

    // Modify window.clearData
    window.clearData = function() {
        Swal.fire({
            title: 'Clear All Data?',
            text: 'This will remove all processed data and reset the system. This action cannot be undone.',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Yes, clear it!',
            cancelButtonText: 'No, keep it',
            confirmButtonColor: '#d33',
            cancelButtonColor: '#3085d6'
        }).then((result) => {
            if (result.isConfirmed) {
                showLoading('Clearing data...');
        fetch('/clear-data', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
                    Swal.close();
                    if (data.error) {
                        showError('Error', data.error);
                    } else {
                        showSuccess('Success', 'All data has been cleared');
            if (agentMonitoringContainer) agentMonitoringContainer.innerHTML = '';
            if (companiesBody) companiesBody.innerHTML = '';
            const totalCostEl = document.getElementById('total-cost');
            if (totalCostEl) totalCostEl.textContent = '$0.00';
            updateProgress({ processed: 0, total: 0 });
            const resultsSection = document.getElementById('results-section');
            if (resultsSection) resultsSection.style.display = 'none';
                        
                        const emailActionsGroup = document.getElementById('email-actions-group');
                        if (emailActionsGroup) emailActionsGroup.style.display = 'none';
            
            if (startButton) {
                startButton.disabled = false;
                startButton.innerHTML = '<i class="fas fa-play-circle me-2"></i>Launch Agent';
            }
            if (agentControls) agentControls.style.display = 'none';
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showError('Error', 'Failed to clear data');
                });
            }
        });
    };

    // Make sendBulkEmails globally accessible
    window.sendBulkEmails = function(mode) {
        Swal.fire({
            title: 'Send Emails',
            text: 'Do you want to send emails now?',
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Yes, send emails',
            cancelButtonText: 'No, cancel',
            confirmButtonColor: '#3085d6',
            cancelButtonColor: '#d33'
        }).then((result) => {
            if (result.isConfirmed) {
                // User confirmed, show the progress modal
                emailModal.show();
                
                // Initialize modal elements
                initializeEmailModal();
                
                // Clear previous status messages
                if (emailStatusList) {
                    emailStatusList.innerHTML = '';
                }
                
                // Reset progress bar
                const progressBar = document.getElementById('email-progress-bar');
                const progressText = document.getElementById('email-progress-text');
                if (progressBar && progressText) {
                    progressBar.style.width = '0%';
                    progressBar.setAttribute('aria-valuenow', 0);
                    progressText.textContent = '0/0';
                }

                // Start the email process
                fetch('/send-bulk-emails', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ mode: mode })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        Swal.fire({
                            title: 'Error',
                            text: data.error,
                            icon: 'error'
                        });
                        emailModal.hide();
                    }
        })
        .catch(error => {
            console.error('Error:', error);
                    Swal.fire({
                        title: 'Error',
                        text: 'Error starting email process',
                        icon: 'error'
                    });
                    emailModal.hide();
                });
            }
        });
    };

    // Socket event handlers
    socket.on('email_progress', function(data) {
        if (data.progress) {
            updateEmailProgress(data.progress);
        }
        
        if (data.status) {
            updateEmailStatus(data.status);
            
            // If it's the final status message
            if (data.status.company_name === 'System' && data.status.summary_file) {
                Swal.fire({
                    title: 'Process Complete',
                    text: data.status.message,
                    icon: 'success',
                    confirmButtonText: 'OK'
                });
            }
        }
    });

    // Update the click handler
    document.addEventListener('click', function(e) {
        const target = e.target.closest('tr');
        if (target && target.closest('#enriched-companies-body')) {
            showCompanyDetails(target);
        }
    });
});