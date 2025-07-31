document.addEventListener('DOMContentLoaded', function() {
    const socket = io();
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

    socket.on('connect', function() {
        console.log('Connected to server');
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
        if (totalCostEl) totalCostEl.textContent = `$${data.total_cost.toFixed(2)}`;
    }

    function updateProgress(data) {
        const progressBar = document.getElementById('progress-bar');
        const progressText = document.getElementById('progress-text');
        const progressContainer = document.getElementById('progress-container');
        
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
                    stopTimer();
                } else {
                    if (progressBar) {
                        progressBar.classList.add('progress-bar-animated');
                        progressBar.classList.remove('bg-success');
                    }
                }
            } else {
                progressContainer.style.display = 'none';
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
            row.onclick = () => showCompanyDetails(company);
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

    function showCompanyDetails(company) {
        const modalContent = document.getElementById('modalContent');
        if (!modalContent) return;

        let content = '<div class="container">';
        
        for (const [key, value] of Object.entries(company)) {
            content += `
                <div class="row mb-3">
                    <div class="col-4 fw-bold">${key}</div>
                    <div class="col-8">${value}</div>
                </div>
                <hr class="my-3">
            `;
        }
        
        content += '</div>';
        modalContent.innerHTML = content;
        const modalLabel = document.getElementById('dataModalLabel');
        if(modalLabel) modalLabel.textContent = company['Company Name'];
        if (dataModal) dataModal.show();
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

    window.startAgent = function() {
        const fileInput = document.getElementById('fileInput');
        if (!fileInput) return;
        const file = fileInput.files[0];

        if (!file) {
            alert('Please select a file to upload.');
            return;
        }

        const resultsSection = document.getElementById('results-section');
        if (resultsSection) resultsSection.style.display = 'block';

        if (startButton) {
            startButton.disabled = true;
            startButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
        }
        if (agentControls) agentControls.style.display = 'block';
        if (stopButton) stopButton.disabled = false;
        if (clearButton) clearButton.disabled = true;

        if (agentMonitoringContainer) agentMonitoringContainer.innerHTML = '';
        if (companiesBody) companiesBody.innerHTML = '';
        const totalCostEl = document.getElementById('total-cost');
        if (totalCostEl) totalCostEl.textContent = '$0.00';
        updateProgress({ processed: 0, total: 0 });

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
            if (data.error) {
                console.error('Error:', data.error);
                alert('An error occurred: ' + data.error);
                stopTimer();
            } else {
                console.log(data.message);
                if (startButton) startButton.disabled = true;
                if (agentControls) agentControls.style.display = 'block';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            stopTimer();
        });
    }

    window.downloadEnrichedData = function() {
        fetch('/download_file')
            .then(response => {
                if (response.status === 202) {
                    return response.json().then(data => {
                        alert(data.error);
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
            })
            .catch(error => {
                console.error('Error downloading file:', error);
                alert('Error downloading file. Please try again.');
            });
    }

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

    window.clearData = function() {
        fetch('/clear-data', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            console.log(data.message);
            if (agentMonitoringContainer) agentMonitoringContainer.innerHTML = '';
            if (companiesBody) companiesBody.innerHTML = '';
            const totalCostEl = document.getElementById('total-cost');
            if (totalCostEl) totalCostEl.textContent = '$0.00';
            updateProgress({ processed: 0, total: 0 });
            const resultsSection = document.getElementById('results-section');
            if (resultsSection) resultsSection.style.display = 'none';
            
            if (startButton) {
                startButton.disabled = false;
                startButton.innerHTML = '<i class="fas fa-play-circle me-2"></i>Launch Agent';
            }
            if (agentControls) agentControls.style.display = 'none';
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while clearing data.');
        });
    };
});