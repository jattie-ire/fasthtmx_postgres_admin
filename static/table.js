// Track newly added lookup values in memory (not yet in DB)
const newLookupValues = {};
const lookupCache = {};
let currentImportFile = null;

function openLookupModal(sourceTable, columnName, dataCol) {
    window.currentLookupContext = {
        sourceTable: sourceTable,
        columnName: columnName,
        dataCol: dataCol
    };
    
    document.getElementById('lookup-source-table').value = sourceTable;
    document.getElementById('lookup-column').value = columnName;
    document.getElementById('lookup-value').value = '';
    document.getElementById('lookup-value').focus();
    document.getElementById('lookup-modal').style.display = 'block';
}

function closeLookupModal() {
    document.getElementById('lookup-modal').style.display = 'none';
    window.currentLookupContext = null;
}

function submitAddLookup(event) {
    event.preventDefault();
    
    const sourceTable = document.getElementById('lookup-source-table').value;
    const columnName = document.getElementById('lookup-column').value;
    const value = document.getElementById('lookup-value').value;
    
    const key = `${sourceTable}.${columnName}`;
    if (!newLookupValues[key]) {
        newLookupValues[key] = [];
    }
    if (!newLookupValues[key].includes(value)) {
        newLookupValues[key].push(value);
    }
    
    document.querySelectorAll(`select[name="${columnName}"]`).forEach(select => {
        const exists = Array.from(select.options).some(opt => opt.value === value);
        if (!exists) {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = value;
            select.appendChild(option);
        }
    });
    
    if (window.currentClickedButton) {
        const selectInForm = window.currentClickedButton.closest('div').querySelector(`select[name="${columnName}"]`);
        if (selectInForm) {
            selectInForm.value = value;
            selectInForm.classList.add('modified');
        }
    }
    
    document.getElementById('form-inputs').style.display = 'none';
    document.getElementById('modal-add-btn').style.display = 'none';
    document.getElementById('modal-cancel-btn').textContent = 'OK';
    document.getElementById('success-value').textContent = value;
    document.getElementById('modal-success-msg').style.display = 'block';
    
    document.getElementById('modal-cancel-btn').style.pointerEvents = 'auto';
    document.getElementById('modal-cancel-btn').style.cursor = 'pointer';
    
    document.getElementById('modal-cancel-btn').onclick = function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        document.getElementById('form-inputs').style.display = 'block';
        document.getElementById('modal-add-btn').style.display = 'block';
        document.getElementById('modal-add-btn').textContent = 'Add';
        document.getElementById('modal-cancel-btn').textContent = 'Cancel';
        document.getElementById('modal-cancel-btn').onclick = null;
        document.getElementById('modal-success-msg').style.display = 'none';
        
        closeLookupModal();
    };
}

document.addEventListener('DOMContentLoaded', function() {
    const cancelBtn = document.getElementById('modal-cancel-btn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            closeLookupModal();
        });
    }
    
    document.querySelectorAll('.btn-add-lookup').forEach(btn => {
        btn.addEventListener('click', function(event) {
            event.preventDefault();
            event.stopPropagation();
            const sourceTable = this.dataset.source.split('.')[0];
            const columnName = this.dataset.col;
            window.currentClickedButton = this;
            openLookupModal(sourceTable, columnName, columnName);
        });
    });
});

document.addEventListener('change', function(e) {
    if (e.target.matches('input:not([type="hidden"]), select, textarea')) {
        e.target.classList.add('modified');
    }
}, true);

document.addEventListener('input', function(e) {
    if (e.target.matches('input:not([type="hidden"]), select, textarea')) {
        e.target.classList.add('modified');
    }
}, true);

document.addEventListener('submit', function(event) {
    if (event.target.id === 'add-lookup-form') {
        return true;
    }
    
    const modalOpen = document.getElementById('lookup-modal').style.display === 'block';
    
    if (modalOpen) {
        event.preventDefault();
        event.stopPropagation();
        return false;
    }
}, true);

// Import/Export Functions (defined before DOMContentLoaded)
function openImportModal() {
    document.getElementById('import-modal').style.display = 'block';
}

function closeImportModal() {
    document.getElementById('import-modal').style.display = 'none';
    document.getElementById('import-form').style.borderColor = 'var(--border-color)';
    document.getElementById('import-form').style.background = 'transparent';
    resetImportUI();
}

function resetImportUI() {
    document.getElementById('import-file').value = '';
    document.getElementById('import-upload-section').style.display = 'block';
    document.getElementById('import-preview-section').style.display = 'none';
    document.getElementById('import-options-section').style.display = 'none';
    document.getElementById('import-btn').style.display = 'none';
    currentImportFile = null;
}

async function handleImportFile(event) {
    const files = event.target.files || (event.dataTransfer && event.dataTransfer.files);
    if (!files || files.length === 0) {
        console.log('No files selected');
        return;
    }
    
    const file = files[0];
    const fileType = file.name.split('.').pop().toLowerCase();
    console.log('File selected:', file.name, 'Type:', fileType);
    
    if (!['csv', 'xlsx'].includes(fileType)) {
        alert('Please select a CSV or Excel (.xlsx) file');
        return;
    }
    
    currentImportFile = file;
    
    // Get table name from current page
    const tableName = window.location.pathname.split('/').pop();
    console.log('Table name:', tableName);
    
    // Show preview
    showImportPreview(file, tableName);
}

async function showImportPreview(file, tableName) {
    try {
        console.log('Starting import preview for table:', tableName);
        document.getElementById('import-upload-section').style.display = 'none';
        
        // Create form data
        const formData = new FormData();
        formData.append('file', file);
        
        // Call preview API
        const url = `/api/import-preview/${tableName}`;
        console.log('Calling API:', url);
        
        const response = await fetch(url, {
            method: 'POST',
            body: formData
        });
        
        console.log('API response status:', response.status);
        const data = await response.json();
        console.log('API response data:', data);
        
        if (data.status === 'error') {
            alert('Error: ' + data.error);
            resetImportUI();
            return;
        }
        
        // Display preview
        displayImportPreview(data);
        
        // Show options and import button
        document.getElementById('import-preview-section').style.display = 'block';
        document.getElementById('import-options-section').style.display = 'block';
        document.getElementById('import-btn').style.display = 'block';
        console.log('Import preview UI displayed');
        
    } catch (error) {
        console.error('Error in showImportPreview:', error);
        alert('Error loading preview: ' + error.message);
        resetImportUI();
    }
}

function displayImportPreview(data) {
    const headerRow = document.getElementById('import-preview-header');
    const bodyElement = document.getElementById('import-preview-body');
    const errorsDiv = document.getElementById('import-errors');
    const warningsDiv = document.getElementById('import-warnings');
    
    // Clear previous content
    headerRow.innerHTML = '';
    bodyElement.innerHTML = '';
    errorsDiv.innerHTML = '';
    warningsDiv.innerHTML = '';
    
    // Display columns
    const columns = data.columns || [];
    columns.forEach(col => {
        const th = document.createElement('th');
        th.textContent = col;
        th.style.padding = '6px';
        th.style.borderBottom = '1px solid var(--border-color)';
        headerRow.appendChild(th);
    });
    
    // Display preview rows
    const previewRows = data.preview_rows || [];
    previewRows.forEach((row, rowIdx) => {
        const tr = document.createElement('tr');
        if (!row.valid) {
            tr.style.background = '#fadbd8';
        }
        
        columns.forEach(col => {
            const td = document.createElement('td');
            td.textContent = row.data[col] || '';
            td.style.padding = '4px';
            td.style.borderBottom = '1px solid var(--border-color)';
            td.style.fontSize = '11px';
            tr.appendChild(td);
        });
        
        bodyElement.appendChild(tr);
    });
    
    // Display errors
    if (data.validation_errors && data.validation_errors.length > 0) {
        errorsDiv.innerHTML = '<strong>Errors:</strong><br>' + data.validation_errors.slice(0, 5).join('<br>');
        if (data.validation_errors.length > 5) {
            errorsDiv.innerHTML += `<br>... and ${data.validation_errors.length - 5} more`;
        }
    }
    
    // Display warnings
    if (data.validation_warnings && data.validation_warnings.length > 0) {
        warningsDiv.innerHTML = '<strong>Warnings:</strong><br>' + data.validation_warnings.slice(0, 5).join('<br>');
        if (data.validation_warnings.length > 5) {
            warningsDiv.innerHTML += `<br>... and ${data.validation_warnings.length - 5} more`;
        }
    }
}

async function confirmImport() {
    if (!currentImportFile) {
        alert('No file selected');
        return;
    }
    
    const tableName = window.location.pathname.split('/').pop();
    const replaceAll = document.getElementById('replace-all-data').checked;
    const skipDuplicates = document.getElementById('skip-duplicates').checked;
    const dryRun = document.getElementById('dry-run').checked;
    
    try {
        const formData = new FormData();
        formData.append('file', currentImportFile);
        formData.append('replace_all', replaceAll ? 'true' : 'false');
        formData.append('skip_duplicates', skipDuplicates ? 'true' : 'false');
        formData.append('dry_run', dryRun ? 'true' : 'false');
        
        // Disable button during import
        document.getElementById('import-btn').disabled = true;
        
        const response = await fetch(`/api/import-execute/${tableName}`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.status === 'error') {
            alert('Import error: ' + data.error);
        } else {
            let message = data.message;
            if (data.errors && data.errors.length > 0) {
                message += '\n\nErrors:\n' + data.errors.slice(0, 3).join('\n');
                if (data.errors.length > 3) {
                    message += `\n... and ${data.errors.length - 3} more`;
                }
            }
            alert(message);
            
            // Close modal and refresh table if not dry-run
            if (!dryRun) {
                closeImportModal();
                location.reload();
            }
        }
        
        document.getElementById('import-btn').disabled = false;
        
    } catch (error) {
        alert('Import failed: ' + error.message);
        document.getElementById('import-btn').disabled = false;
    }
}

// Cookie management for user preferences
function setCookie(name, value, days = 365) {
    const date = new Date();
    date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
    const expires = "expires=" + date.toUTCString();
    document.cookie = name + "=" + encodeURIComponent(value) + ";" + expires + ";path=/";
}

function getCookie(name) {
    const nameEQ = name + "=";
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
        let cookie = cookies[i].trim();
        if (cookie.indexOf(nameEQ) === 0) {
            return decodeURIComponent(cookie.substring(nameEQ.length));
        }
    }
    return null;
}

// Handle page size change
document.addEventListener('DOMContentLoaded', function() {
    // Import button click handler
    const importBtnToggle = document.getElementById('import-btn-toggle');
    if (importBtnToggle) {
        importBtnToggle.addEventListener('click', openImportModal);
    }
    
    const pageSizeSelect = document.getElementById('page-size-select');
    if (pageSizeSelect) {
        // Load saved page size preference from cookie
        const tableName = document.querySelector('input[name="table_name"]')?.value || 
                        new URLSearchParams(window.location.search).get('table') ||
                        window.location.pathname.split('/').pop();
        const savedPageSize = getCookie(`pageSize_${tableName}`);
        if (savedPageSize) {
            pageSizeSelect.value = savedPageSize;
        }
        
        // Save page size to cookie when changed
        pageSizeSelect.addEventListener('change', function() {
            const newPageSize = this.value;
            setCookie(`pageSize_${tableName}`, newPageSize);
            window.location.href = `/table/${tableName}?page=1&limit=${newPageSize}`;
        });
    }
    
    // Setup import modal interactions
    const importForm = document.getElementById('import-form');
    if (importForm) {
        // Make form clickable to open file dialog
        importForm.addEventListener('click', function(e) {
            if (e.target.id !== 'import-file') {
                document.getElementById('import-file').click();
            }
        });
        
        // Setup drag & drop
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            importForm.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        ['dragenter', 'dragover'].forEach(eventName => {
            importForm.addEventListener(eventName, highlight, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            importForm.addEventListener(eventName, unhighlight, false);
        });
        
        function highlight(e) {
            importForm.style.borderColor = 'var(--accent-primary)';
            importForm.style.background = 'var(--bg-form-focus)';
        }
        
        function unhighlight(e) {
            importForm.style.borderColor = 'var(--border-color)';
            importForm.style.background = 'transparent';
        }
        
        // Handle drop
        importForm.addEventListener('drop', handleDrop, false);
        
        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files.length > 0) {
                document.getElementById('import-file').files = files;
                handleImportFile({ target: { files: files } });
            }
        }
    }
});

// Age-based row coloring function
function applyAgeBasedColoring() {
    if (!window.ageColoringConfig || !window.ageColoringConfig.enabled || !window.ageColoringConfig.column) {
        console.log('Age coloring disabled or not configured', window.ageColoringConfig);
        return;
    }
    
    const config = window.ageColoringConfig;
    console.log('Age coloring config:', config);
    
    const table = document.querySelector('.table-editor');
    if (!table) {
        console.log('Table not found');
        return;
    }
    
    const headerCells = table.querySelectorAll('thead th');
    let ageColumnIndex = -1;
    
    console.log('Header cells:', headerCells.length);
    
    // Find the column index
    for (let i = 0; i < headerCells.length; i++) {
        const headerText = headerCells[i].textContent.trim();
        console.log(`Header ${i}: "${headerText}"`);
        if (headerText === config.column) {
            ageColumnIndex = i;
            break;
        }
    }
    
    console.log(`Age column index: ${ageColumnIndex} (looking for "${config.column}")`);
    
    if (ageColumnIndex === -1) {
        console.log('Column not found');
        return;
    }
    
    const rows = table.querySelectorAll('tbody tr');
    console.log('Rows found:', rows.length);
    
    if (rows.length === 0) {
        console.log('No rows found');
        return;
    }
    
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    let ages = [];
    const rowAges = [];
    
    // Calculate ages for all rows
    rows.forEach((row, idx) => {
        const cells = row.querySelectorAll('td');
        if (cells[ageColumnIndex]) {
            const dateStr = cells[ageColumnIndex].textContent.trim();
            console.log(`Row ${idx} date: "${dateStr}"`);
            const date = parseDate(dateStr);
            
            if (date) {
                date.setHours(0, 0, 0, 0);
                const daysAgo = Math.floor((today - date) / (1000 * 60 * 60 * 24));
                console.log(`Row ${idx} age: ${daysAgo} days`);
                ages.push(daysAgo);
                rowAges.push(daysAgo);
            } else {
                console.log(`Row ${idx} date parse failed`);
                rowAges.push(0);
            }
        }
    });
    
    console.log('Ages:', ages);
    
    if (ages.length === 0) {
        console.log('No valid dates found');
        return;
    }
    
    const minAge = Math.min(...ages);
    const maxAge = Math.min(Math.max(...ages), config.maxAgeDays);
    
    // Apply colors to rows
    rows.forEach((row, idx) => {
        const age = rowAges[idx];
        
        if (age === undefined || age < 0) {
            row.style.backgroundColor = '';
            return;
        }
        
        // Calculate intensity
        let intensity = 0;
        if (minAge === maxAge) {
            // All rows are the same age
            if (minAge > 0) {
                // All old - use a light red
                intensity = 0.2;
            } else {
                // All today - use default
                intensity = 0;
            }
        } else {
            // Calculate intensity (0 = default theme, 1 = full red)
            if (age === minAge) {
                intensity = 0; // Newest = default theme color
            } else if (age >= config.maxAgeDays) {
                intensity = 1; // Older than max = full red
            } else {
                intensity = (age - minAge) / (maxAge - minAge);
            }
        }
        
        if (intensity === 0) {
            // Use default theme color (remove inline style)
            row.style.backgroundColor = '';
        } else {
            // Check if dark mode is active
            const isDarkMode = document.documentElement.classList.contains('dark-theme');
            
            let color;
            if (isDarkMode) {
                // Dark mode: use rgba with red tint for subtlety
                const alpha = intensity * 0.4; // max 40% opacity
                color = `rgba(220, 80, 80, ${alpha})`;
            } else {
                // Light mode: white to very light pink
                const r = Math.round(255);
                const g = Math.round(255 - (intensity * 80)); // 255 to 175
                const b = Math.round(255 - (intensity * 80)); // 255 to 175
                color = `rgb(${r}, ${g}, ${b})`;
            }
            
            row.style.backgroundColor = color;
            console.log(`Row ${idx} color: ${color}`);
        }
    });
    
    console.log('Age coloring applied successfully');
}

// Helper function to parse dates in various formats
function parseDate(dateStr) {
    if (!dateStr) return null;
    
    // Try ISO format (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
    let date = new Date(dateStr);
    if (!isNaN(date)) return date;
    
    // Try other formats
    const formats = [
        /(\d{4})-(\d{2})-(\d{2})/,  // YYYY-MM-DD
        /(\d{2})\/(\d{2})\/(\d{4})/, // MM/DD/YYYY
    ];
    
    for (const regex of formats) {
        const match = dateStr.match(regex);
        if (match) {
            if (regex === formats[0]) {
                return new Date(match[1], match[2] - 1, match[3]);
            } else if (regex === formats[1]) {
                return new Date(match[3], match[1] - 1, match[2]);
            }
        }
    }
    
    return null;
}

// Apply age coloring when page loads
function initAgeColoring() {
    console.log('✓ initAgeColoring called');
    console.log('window.ageColoringConfig:', window.ageColoringConfig);
    setTimeout(() => {
        console.log('✓ Calling applyAgeBasedColoring()');
        applyAgeBasedColoring();
    }, 100);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAgeColoring);
} else {
    // DOM already loaded
    console.log('✓ DOM already loaded, calling initAgeColoring immediately');
    initAgeColoring();
}

// End of file
