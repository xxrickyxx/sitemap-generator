// DOM Elements
const inputUrl = document.getElementById('input-url');
const inputLimit = document.getElementById('input-limit');
const inputConcurrency = document.getElementById('input-concurrency');
const inputDelay = document.getElementById('input-delay');
const inputIgnoreQuery = document.getElementById('input-ignore-query');
const inputOutputDir = document.getElementById('input-output-dir');

const valLimit = document.getElementById('val-limit');
const valConcurrency = document.getElementById('val-concurrency');
const valDelay = document.getElementById('val-delay');

const btnStart = document.getElementById('btn-start');
const btnStop = document.getElementById('btn-stop');
const btnOpenFolder = document.getElementById('btn-open-folder');
const btnClearConsole = document.getElementById('btn-clear-console');

const serverStatusDot = document.getElementById('server-status-dot');
const serverStatusText = document.getElementById('server-status-text');

const progressState = document.getElementById('progress-state');
const progressPercent = document.getElementById('progress-percent');
const progressBar = document.getElementById('progress-bar');
const elapsedTime = document.getElementById('elapsed-time');

const statDiscovered = document.getElementById('stat-discovered');
const statQueue = document.getElementById('stat-queue');
const statTotal = document.getElementById('stat-total');
const statErrors = document.getElementById('stat-errors');

const outputPanel = document.getElementById('output-panel');
const fileList = document.getElementById('file-list');
const outputPathLabel = document.getElementById('output-path-label');

const consoleOutput = document.getElementById('console-output');
const autoscrollCheck = document.getElementById('autoscroll-check');

// State Variables
let isCrawling = false;
let pollIntervalId = null;
let lastLogLength = 0;
let currentOutputDir = '';

// Initialize sliders events
inputLimit.addEventListener('input', () => {
    valLimit.textContent = inputLimit.value;
});
inputConcurrency.addEventListener('input', () => {
    valConcurrency.textContent = inputConcurrency.value;
});
inputDelay.addEventListener('input', () => {
    valDelay.textContent = `${inputDelay.value}s`;
});

// Helper: Format Time (Seconds -> MM:SS)
function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

// Helper: Append log line to console
function appendLogLine(line) {
    const div = document.createElement('div');
    div.className = 'log-line';
    
    // Classify line content for styling
    if (line.includes('Starting crawl') || line.includes('Crawl completed') || line.includes('Server started')) {
        div.classList.add('log-system');
    } else if (line.includes('Failed') || line.includes('Error') || line.includes('Parser error')) {
        div.classList.add('log-error');
    } else if (line.includes('Generating Sitemaps') || line.includes('Writing sitemaps')) {
        div.classList.add('log-warning');
    } else if (line.includes('Crawling:')) {
        // Successful or standard crawl message
        if (line.includes('200 OK') || line.includes('successfully generated')) {
            div.classList.add('log-success');
        } else {
            div.classList.add('log-info');
        }
    } else {
        div.classList.add('log-info');
    }
    
    div.textContent = line;
    consoleOutput.appendChild(div);
}

// Refresh console logs
function updateLogs(logs) {
    if (logs.length === 0) {
        consoleOutput.innerHTML = '';
        lastLogLength = 0;
        return;
    }
    
    // If logs were cleared or reset
    if (logs.length < lastLogLength) {
        consoleOutput.innerHTML = '';
        lastLogLength = 0;
    }
    
    // Append new lines
    for (let i = lastLogLength; i < logs.length; i++) {
        appendLogLine(logs[i]);
    }
    
    lastLogLength = logs.length;
    
    // Scroll to bottom
    if (autoscrollCheck.checked) {
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
    }
}

// Get Crawler Status
async function pollStatus() {
    try {
        const response = await fetch('/api/status');
        if (!response.ok) throw new Error('Network error');
        const data = await response.json();
        
        // Update stats
        statDiscovered.textContent = data.discovered_urls;
        statQueue.textContent = data.queue_size;
        statTotal.textContent = data.pages_fetched;
        statErrors.textContent = data.errors_count;
        elapsedTime.textContent = formatTime(data.elapsed_seconds);
        
        currentOutputDir = data.output_dir;
        outputPathLabel.textContent = data.output_dir;
        
        // Calculate progress percentage
        // progress = Visited / (Visited + Queue)
        const totalEstimated = data.pages_fetched + data.queue_size;
        let percent = 0;
        if (data.current_action === "Completed") {
            percent = 100;
        } else if (totalEstimated > 0) {
            percent = Math.round((data.pages_fetched / totalEstimated) * 100);
        }
        
        progressBar.style.width = `${percent}%`;
        progressPercent.textContent = `${percent}%`;
        
        // Update Action State
        isCrawling = data.running;
        
        if (isCrawling) {
            btnStart.disabled = true;
            btnStop.disabled = false;
            progressState.textContent = `Stato: ${data.current_action}`;
            
            serverStatusDot.className = 'status-dot pulse-running';
            serverStatusText.textContent = `Scansione in corso...`;
            
            // Auto hide output panel if running again
            outputPanel.classList.add('hidden');
        } else {
            btnStart.disabled = false;
            btnStop.disabled = true;
            progressState.textContent = `Stato: ${data.current_action}`;
            
            if (data.current_action === "Completed") {
                serverStatusDot.className = 'status-dot pulse-idle';
                serverStatusText.textContent = `Scansione Completata`;
                
                // Show output files
                renderOutputFiles(data.generated_files);
                outputPanel.classList.remove('hidden');
            } else if (data.current_action === "Stopped") {
                serverStatusDot.className = 'status-dot pulse-stopped';
                serverStatusText.textContent = `Scansione Interrotta`;
            } else {
                serverStatusDot.className = 'status-dot pulse-idle';
                serverStatusText.textContent = `Pronto`;
            }
        }
        
        // Update logs
        updateLogs(data.logs || []);
        
    } catch (err) {
        console.error('Error polling status:', err);
        serverStatusDot.className = 'status-dot pulse-stopped';
        serverStatusText.textContent = `Errore di Connessione`;
    }
}

// Render generated sitemaps file list
function renderOutputFiles(files) {
    fileList.innerHTML = '';
    if (!files || files.length === 0) {
        const li = document.createElement('li');
        li.textContent = "Nessun file generato.";
        fileList.appendChild(li);
        return;
    }
    
    files.forEach(file => {
        const li = document.createElement('li');
        
        const nameSpan = document.createElement('span');
        nameSpan.className = 'file-name';
        nameSpan.innerHTML = `<i class="fa-solid fa-file-code"></i> ${file}`;
        li.appendChild(nameSpan);
        
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'file-actions';
        
        // Add copy button
        const copyBtn = document.createElement('button');
        copyBtn.className = 'btn-link';
        copyBtn.innerHTML = `<i class="fa-regular fa-copy"></i> Copia Nome`;
        copyBtn.title = "Copia il nome del file negli appunti";
        copyBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(file);
            copyBtn.innerHTML = `<i class="fa-solid fa-check"></i> Copiato!`;
            setTimeout(() => {
                copyBtn.innerHTML = `<i class="fa-regular fa-copy"></i> Copia Nome`;
            }, 2000);
        });
        
        actionsDiv.appendChild(copyBtn);
        li.appendChild(actionsDiv);
        
        fileList.appendChild(li);
    });
}

// Start Crawling Action
async function startCrawl() {
    const url = inputUrl.value.trim();
    if (!url) return;
    
    const limit = parseInt(inputLimit.value);
    const concurrency = parseInt(inputConcurrency.value);
    const delay = parseFloat(inputDelay.value);
    const ignoreQuery = inputIgnoreQuery.checked;
    const outputDir = inputOutputDir.value.trim();
    
    btnStart.disabled = true;
    btnStop.disabled = false;
    outputPanel.classList.add('hidden');
    
    try {
        const response = await fetch('/api/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url,
                limit,
                concurrency,
                delay,
                ignore_query: ignoreQuery,
                output_dir: outputDir
            })
        });
        
        if (!response.ok) throw new Error('Impossibile avviare il crawler');
        
        // Immediate status check
        await pollStatus();
    } catch (err) {
        alert('Errore: ' + err.message);
        btnStart.disabled = false;
        btnStop.disabled = true;
    }
}

// Stop Crawling Action
async function stopCrawl() {
    btnStop.disabled = true;
    try {
        const response = await fetch('/api/stop', { method: 'POST' });
        if (!response.ok) throw new Error('Impossibile fermare il crawler');
        await pollStatus();
    } catch (err) {
        alert('Errore fermando scansione: ' + err.message);
    }
}

// Open output folder in local file system explorer
async function openFolder() {
    if (!currentOutputDir) return;
    try {
        const response = await fetch('/api/open-folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder: currentOutputDir })
        });
        const result = await response.json();
        if (!result.success) {
            alert('Impossibile aprire la cartella: ' + (result.error || 'Percorso non trovato'));
        }
    } catch (err) {
        alert('Errore durante l\'apertura della cartella: ' + err.message);
    }
}

// Bind Button Clicks
btnStart.addEventListener('click', startCrawl);
btnStop.addEventListener('click', stopCrawl);
btnOpenFolder.addEventListener('click', openFolder);
btnClearConsole.addEventListener('click', () => {
    consoleOutput.innerHTML = '';
    // Optional: we don't clear the server's logs, just client display
});

// Setup continuous polling
pollStatus(); // Initial load
pollIntervalId = setInterval(pollStatus, 1000);
