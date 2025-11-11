// GEM Contract Management - Contracts Page JavaScript

// Initialize data from server
let allContracts = [];
let originalPerPage = 5;
let perPage = originalPerPage;
let currentPage = 1;
let totalRecords = 0;
let totalPages = 0;
let filteredContracts = [];

// DOM elements
let searchInput, clearSearchBtn, stateSearchSelect, clearStateSearchBtn;
let dateFromInput, dateToInput, clearAllFiltersBtn, tableBody, paginationContainer;
let fromDatePicker, toDatePicker;

// Initialize contracts data (called from template)
function initializeContractsData(contractsData, itemsPerPage) {
    allContracts = contractsData;
    originalPerPage = itemsPerPage;
    perPage = originalPerPage;
    totalRecords = allContracts.length;
    totalPages = Math.ceil(totalRecords / perPage);
    filteredContracts = [...allContracts];

    // Initialize DOM elements
    searchInput = document.getElementById('searchInput');
    clearSearchBtn = document.getElementById('clearSearchBtn');
    stateSearchSelect = document.getElementById('stateSearchSelect');
    clearStateSearchBtn = document.getElementById('clearStateSearchBtn');
    dateFromInput = document.getElementById('dateFrom');
    dateToInput = document.getElementById('dateTo');
    clearAllFiltersBtn = document.getElementById('clearAllFiltersBtn');
    tableBody = document.querySelector('tbody');
    paginationContainer = document.getElementById('pagination-container');

    // Set up event listeners
    setupEventListeners();

    // Initialize plugins
    initializePlugins();

    // Initial display
    displayFilteredContractsPaginated();
}

// Generate pagination HTML
function generatePaginationHTML(currentPage, totalPages, perPage, totalRecords, availableSizes = [5, 10, 50, 100]) {
    const startRecord = (currentPage - 1) * perPage + 1;
    const endRecord = Math.min(currentPage * perPage, totalRecords);

    // Inline styles for consistency
    const mainContainerStyle = 'style="display: flex; flex-direction: column; gap: 0.5rem; padding: 0.75rem 1rem; background: rgba(255, 255, 255, 0.98); border-radius: 12px; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);"';
    const rowStyle = 'style="display: flex; justify-content: space-between; align-items: center; gap: 1.5rem; padding: 0.3rem 0;"';
    const summaryStyle = 'style="color: #1e40af; font-weight: 600; font-size: 0.95rem; display: flex; align-items: center; gap: 0.5rem; white-space: nowrap;"';
    const pagesStyle = 'style="color: #1e40af; font-weight: 700; font-size: 0.95rem; padding: 0.3rem 0.8rem; white-space: nowrap;"';
    const controlsContainerStyle = 'style="display: flex; gap: 0.5rem; align-items: center; justify-content: center; flex-wrap: wrap; flex: 1;"';
    const btnStyle = 'style="display: inline-flex; align-items: center; justify-content: center; padding: 0.6rem 1rem; border: 1px solid #e2e8f0; background: white; color: #1e40af; text-decoration: none; border-radius: 6px; font-size: 0.875rem; font-weight: 600; transition: all 0.2s ease; min-width: 2.5rem; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);"';
    const btnActiveStyle = 'style="display: inline-flex; align-items: center; justify-content: center; padding: 0.6rem 1rem; border: 1px solid #1e40af; background: #1e40af; color: white; text-decoration: none; border-radius: 6px; font-size: 0.875rem; font-weight: 600; min-width: 2.5rem; box-shadow: 0 4px 8px rgba(30, 64, 175, 0.25);"';
    const btnDisabledStyle = 'style="display: inline-flex; align-items: center; justify-content: center; padding: 0.6rem 1rem; border: 1px solid #e2e8f0; background: #f1f5f9; color: #94a3b8; border-radius: 6px; font-size: 0.875rem; font-weight: 600; min-width: 2.5rem; opacity: 0.4; cursor: not-allowed;"';
    const ellipsisStyle = 'style="padding: 0.6rem 0.5rem; color: #64748b; font-weight: 600; font-size: 0.875rem;"';
    const selectorStyle = 'style="display: flex; align-items: center; gap: 0.75rem; font-size: 0.875rem; color: #1e293b; font-weight: 600; white-space: nowrap;"';

    let html = '<div ' + mainContainerStyle + '>';

    // Row 1: Showing info (left) + Pagination buttons (center) + Page X of Y (right)
    html += '<div ' + rowStyle + '>' +
            '<span ' + summaryStyle + '>' +
                '<i class="fas fa-info-circle"></i>' +
                'Showing ' + startRecord + ' to ' + endRecord + ' of ' + totalRecords + ' records' +
            '</span>';

    // Pagination controls in center
    html += '<div ' + controlsContainerStyle + '>';

    // First button
    if (currentPage > 1) {
        html += '<a href="#" onclick="changePage(1); return false;" class="pagination-btn" ' + btnStyle + ' title="First Page"><i class="fas fa-angle-double-left"></i></a>';
    } else {
        html += '<span class="pagination-btn disabled" ' + btnDisabledStyle + ' title="First Page"><i class="fas fa-angle-double-left"></i></span>';
    }

    // Previous button
    if (currentPage > 1) {
        html += '<a href="#" onclick="changePage(' + (currentPage - 1) + '); return false;" class="pagination-btn" ' + btnStyle + ' title="Previous Page"><i class="fas fa-chevron-left"></i></a>';
    } else {
        html += '<span class="pagination-btn disabled" ' + btnDisabledStyle + ' title="Previous Page"><i class="fas fa-chevron-left"></i></span>';
    }

    // Page numbers
    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(totalPages, currentPage + 2);

    if (startPage > 1) {
        html += '<a href="#" onclick="changePage(1); return false;" class="pagination-btn" ' + btnStyle + '>1</a>';
        if (startPage > 2) html += '<span class="pagination-ellipsis" ' + ellipsisStyle + '>...</span>';
    }

    for (let pageNum = startPage; pageNum <= endPage; pageNum++) {
        if (pageNum === currentPage) {
            html += '<span class="pagination-btn active" ' + btnActiveStyle + '>' + pageNum + '</span>';
        } else {
            html += '<a href="#" onclick="changePage(' + pageNum + '); return false;" class="pagination-btn" ' + btnStyle + '>' + pageNum + '</a>';
        }
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) html += '<span class="pagination-ellipsis" ' + ellipsisStyle + '>...</span>';
        html += '<a href="#" onclick="changePage(' + totalPages + '); return false;" class="pagination-btn" ' + btnStyle + '>' + totalPages + '</a>';
    }

    // Next button
    if (currentPage < totalPages) {
        html += '<a href="#" onclick="changePage(' + (currentPage + 1) + '); return false;" class="pagination-btn" ' + btnStyle + ' title="Next Page"><i class="fas fa-chevron-right"></i></a>';
    } else {
        html += '<span class="pagination-btn disabled" ' + btnDisabledStyle + ' title="Next Page"><i class="fas fa-chevron-right"></i></span>';
    }

    // Last button
    if (currentPage < totalPages) {
        html += '<a href="#" onclick="changePage(' + totalPages + '); return false;" class="pagination-btn" ' + btnStyle + ' title="Last Page"><i class="fas fa-angle-double-right"></i></a>';
    } else {
        html += '<span class="pagination-btn disabled" ' + btnDisabledStyle + ' title="Last Page"><i class="fas fa-angle-double-right"></i></span>';
    }

    html += '</div>';

    // Page X of Y on the right
    html += '<span ' + pagesStyle + '>' +
                '<i class="fas fa-bookmark"></i> Page ' + currentPage + ' of ' + totalPages +
            '</span>';

    html += '</div>';

    // Row 2: Page size selector
    html += '<div style="display: flex; justify-content: center; align-items: center; padding: 0.3rem 0;">' +
            '<div ' + selectorStyle + '>' +
                '<label for="pageSize">Show:</label>' +
                '<select id="pageSize" onchange="changePageSize(this.value)" style="padding: 0.4rem 1rem; border: 1px solid #e2e8f0; border-radius: 6px; background: white; color: #1e293b; font-size: 0.875rem; cursor: pointer; font-weight: 600; min-width: 80px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);">';

    availableSizes.forEach(size => {
        const selected = size === perPage ? 'selected' : '';
        html += '<option value="' + size + '" ' + selected + '>' + size + '</option>';
    });

    html += '</select>' +
            '<span>per page</span>' +
        '</div>' +
    '</div>';

    html += '</div>';

    return html;
}

// Display filtered contracts with pagination
function displayFilteredContractsPaginated() {
    perPage = originalPerPage;
    totalPages = Math.ceil(filteredContracts.length / perPage);

    if (currentPage > totalPages) {
        currentPage = 1;
    }

    const start = (currentPage - 1) * perPage;
    const end = start + perPage;
    const pageContracts = filteredContracts.slice(start, end);

    if (pageContracts.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="6">
                    <div class="empty-state">
                        <i class="fas fa-search"></i>
                        <h3>No contracts found</h3>
                        <p>No contracts match your search criteria.</p>
                    </div>
                </td>
            </tr>
        `;
        paginationContainer.style.display = 'none';
        return;
    }

    let html = '';
    pageContracts.forEach((contract, index) => {
        const globalIndex = start + index + 1;
        html += `
            <tr>
                <td style="text-align: center; font-weight: bold;">
                    <div style="font-size: 1.1em; color: #495057;">${globalIndex}</div>
                </td>
                <td>
                    <div class="data-section">
                        <div class="section-title">
                            <i class="fas fa-building"></i> Organization
                        </div>
                        <div class="data-item"><strong>Type:</strong> ${contract.type || 'N/A'}</div>
                        <div class="data-item"><strong>Ministry:</strong> ${contract.ministry || 'N/A'}</div>
                        <div class="data-item"><strong>Department:</strong> ${contract.department || 'N/A'}</div>
                        <div class="data-item"><strong>Organization:</strong> ${contract.organisation_name || 'N/A'}</div>
                        <div class="data-item"><strong>Office Zone:</strong> ${contract.office_zone || 'N/A'}</div>
                    </div>
                </td>
                <td>
                    <div class="data-section">
                        <div class="section-title">
                            <i class="fas fa-store"></i> Seller
                        </div>
                        <div class="data-item"><strong>Company:</strong> ${contract.company_name || 'N/A'}</div>
                        <div class="data-item"><strong>Seller ID:</strong> ${contract.gem_seller_id || 'N/A'}</div>
                        <div class="data-item"><strong>Contact:</strong> ${contract.seller_contact_no || 'N/A'}</div>
                        <div class="data-item"><strong>Email:</strong> ${contract.seller_email_id || 'N/A'}</div>
                        <div class="data-item"><strong>Address:</strong> ${contract.seller_address || 'N/A'}</div>
                        <div class="data-item"><strong>MSME:</strong> ${contract.msme_registration_number || 'N/A'}</div>
                        <div class="data-item"><strong>GSTIN:</strong> ${contract.seller_gstin || 'N/A'}</div>
                    </div>
                </td>
                <td>
                    <div class="data-section">
                        <div class="section-title">
                            <i class="fas fa-user"></i> Buyer
                        </div>
                        <div class="data-item"><strong>Designation:</strong> ${contract.designation || 'N/A'}</div>
                        <div class="data-item"><strong>Contact:</strong> ${contract.buyer_contact_no || 'N/A'}</div>
                        <div class="data-item"><strong>Email:</strong> ${contract.email_id || 'N/A'}</div>
                        <div class="data-item"><strong>GSTIN:</strong> ${contract.buyer_gstin || 'N/A'}</div>
                        <div class="data-item"><strong>Address:</strong> ${contract.buyer_address || 'N/A'}</div>
                    </div>
                </td>
                <td>
                    <div class="action-buttons">
                        <a href="/products/${contract.contract_id}" class="btn btn-sm btn-info">
                            <i class="fas fa-box"></i> Products
                        </a>
                    </div>
                    <div class="data-section">
                        <div class="section-title">
                            <i class="fas fa-rupee-sign"></i> Value
                        </div>
                        <div class="data-item"><strong>Total Value:</strong> ₹${contract.total_order_value || 'N/A'}</div>
                    </div>
                </td>
                <td>
                    <div class="action-buttons">
                        <a href="/view/${contract.contract_id}" class="btn btn-sm btn-info" target="_blank">
                            <i class="fas fa-file-pdf"></i> View PDF
                        </a>
                    </div>
                </td>
            </tr>
        `;
    });

    tableBody.innerHTML = html;

    totalRecords = filteredContracts.length;
    totalPages = Math.ceil(totalRecords / perPage);
    paginationContainer.innerHTML = generatePaginationHTML(currentPage, totalPages, perPage, totalRecords);
    paginationContainer.style.display = 'block';
}

// Apply filters
function applyFilters(resetPage = true) {
    let tempFiltered = [...allContracts];

    // Search filter
    const searchTerm = searchInput.value.toLowerCase().trim();
    if (searchTerm) {
        tempFiltered = tempFiltered.filter(contract => {
            return (contract.contract_id && contract.contract_id.toLowerCase().includes(searchTerm)) ||
                   (contract.filename && contract.filename.toLowerCase().includes(searchTerm)) ||
                   (contract.organisation_name && contract.organisation_name.toLowerCase().includes(searchTerm)) ||
                   (contract.department && contract.department.toLowerCase().includes(searchTerm)) ||
                   (contract.type && contract.type.toLowerCase().includes(searchTerm)) ||
                   (contract.ministry && contract.ministry.toLowerCase().includes(searchTerm)) ||
                   (contract.office_zone && contract.office_zone.toLowerCase().includes(searchTerm)) ||
                   (contract.company_name && contract.company_name.toLowerCase().includes(searchTerm)) ||
                   (contract.gem_seller_id && contract.gem_seller_id.toLowerCase().includes(searchTerm)) ||
                   (contract.seller_contact_no && contract.seller_contact_no.toLowerCase().includes(searchTerm)) ||
                   (contract.seller_email_id && contract.seller_email_id.toLowerCase().includes(searchTerm)) ||
                   (contract.seller_address && contract.seller_address.toLowerCase().includes(searchTerm)) ||
                   (contract.msme_registration_number && contract.msme_registration_number.toLowerCase().includes(searchTerm)) ||
                   (contract.seller_gstin && contract.seller_gstin.toLowerCase().includes(searchTerm)) ||
                   (contract.designation && contract.designation.toLowerCase().includes(searchTerm)) ||
                   (contract.buyer_contact_no && contract.buyer_contact_no.toLowerCase().includes(searchTerm)) ||
                   (contract.email_id && contract.email_id.toLowerCase().includes(searchTerm)) ||
                   (contract.buyer_gstin && contract.buyer_gstin.toLowerCase().includes(searchTerm)) ||
                   (contract.buyer_address && contract.buyer_address.toLowerCase().includes(searchTerm)) ||
                   (contract.product_names && contract.product_names.toLowerCase().includes(searchTerm)) ||
                   (contract.category_names && contract.category_names.toLowerCase().includes(searchTerm)) ||
                   (contract.text_format && contract.text_format.toLowerCase().includes(searchTerm));
        });
    }

    // State filter
    const selectedState = stateSearchSelect.value.toLowerCase().trim();
    if (selectedState) {
        tempFiltered = tempFiltered.filter(contract =>
            contract.seller_address && contract.seller_address.toLowerCase().includes(selectedState)
        );
    }

    // Date filter
    function parseDDMMYYYY(dateStr) {
        if (!dateStr) return null;
        const parts = dateStr.split('/');
        if (parts.length === 3) {
            return new Date(parts[2], parts[1] - 1, parts[0]);
        }
        return null;
    }

    const fromDate = parseDDMMYYYY(dateFromInput.value);
    const toDate = parseDDMMYYYY(dateToInput.value);

    if (fromDate || toDate) {
        tempFiltered = tempFiltered.filter(contract => {
            if (!contract.date) return false;
            const contractDate = new Date(contract.date);
            if (fromDate && contractDate < fromDate) return false;
            if (toDate && contractDate > toDate) return false;
            return true;
        });
    }

    filteredContracts = tempFiltered;
    if (resetPage) {
        currentPage = 1;
    }

    displayFilteredContractsPaginated();
}

// Update Clear All button visibility
function updateClearAllButton() {
    const hasFilters = searchInput.value.trim() !== '' ||
                      stateSearchSelect.value !== '' ||
                      dateFromInput.value !== '' ||
                      dateToInput.value !== '';

    clearAllFiltersBtn.style.display = hasFilters ? 'flex' : 'none';
}

// Setup event listeners
function setupEventListeners() {
    // Search input with debounce
    let searchTimeout;
    searchInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            applyFilters();
            updateClearAllButton();
        }, 300);
    });

    // State select
    stateSearchSelect.addEventListener('change', () => {
        applyFilters();
        updateClearAllButton();
    });

    // Date inputs
    dateFromInput.addEventListener('change', () => {
        applyFilters();
        updateClearAllButton();
    });

    dateToInput.addEventListener('change', () => {
        applyFilters();
        updateClearAllButton();
    });

    // Clear all filters button
    clearAllFiltersBtn.addEventListener('click', () => {
        searchInput.value = '';
        $('#stateSearchSelect').val(null).trigger('change');
        dateFromInput.value = '';
        dateToInput.value = '';
        if (fromDatePicker) fromDatePicker.clear();
        if (toDatePicker) toDatePicker.clear();
        clearAllFiltersBtn.style.display = 'none';
        applyFilters();
    });

    // Export button
    document.getElementById('exportBtn').addEventListener('click', function() {
        const dataToExport = filteredContracts;

        if (dataToExport.length === 0) {
            alert('No data to export');
            return;
        }

        const contractIds = dataToExport.map(c => c.contract_id);

        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/contracts/export';

        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'contract_ids';
        input.value = JSON.stringify(contractIds);

        form.appendChild(input);
        document.body.appendChild(form);
        form.submit();
        document.body.removeChild(form);
    });
}

// Initialize plugins (Flatpickr, Select2)
function initializePlugins() {
    // Flatpickr initialization
    fromDatePicker = flatpickr("#dateFrom", {
        dateFormat: "d/m/Y",
        allowInput: true,
        onChange: function(selectedDates, dateStr, instance) {
            if (selectedDates.length > 0) {
                toDatePicker.set('minDate', selectedDates[0]);
            }
            updateClearAllButton();
            applyFilters();
        }
    });

    toDatePicker = flatpickr("#dateTo", {
        dateFormat: "d/m/Y",
        allowInput: true,
        onChange: function(selectedDates, dateStr, instance) {
            const fromDateValue = document.getElementById('dateFrom').value;
            if (fromDateValue && selectedDates.length > 0) {
                const fromParts = fromDateValue.split('/');
                const fromDate = new Date(fromParts[2], fromParts[1] - 1, fromParts[0]);
                const toDate = selectedDates[0];

                if (toDate < fromDate) {
                    alert('❌ Invalid To Date!\n\nTo Date cannot be before From Date.\n\nFrom Date: ' + fromDateValue + '\nTo Date: ' + dateStr);
                    instance.clear();
                    return;
                }
            }
            updateClearAllButton();
            applyFilters();
        }
    });

    // Select2 initialization
    $('#stateSearchSelect').select2({
        placeholder: "Select Seller State",
        allowClear: true,
        width: '100%',
        theme: 'default',
        dropdownAutoWidth: true,
        minimumResultsForSearch: 0
    });

    $('#stateSearchSelect').on('change', function() {
        updateClearAllButton();
        applyFilters();
    });
}

// Global functions for pagination
window.changePageSize = function(size) {
    originalPerPage = parseInt(size);
    perPage = originalPerPage;
    currentPage = 1;
    displayFilteredContractsPaginated();
};

window.changePage = function(page) {
    currentPage = page;
    displayFilteredContractsPaginated();
    window.scrollTo({ top: 0, behavior: 'smooth' });
};
