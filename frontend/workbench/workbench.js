/**
 * Your Company - Review Workbench (Phase 3, v3.7.0)
 * PDF.js viewer + SVG overlay for AI detection audit.
 *
 * Voice rules: zero em-dashes. Hyphens or periods only.
 */

/* global pdfjsLib */

// -- State -------------------------------------------------------------------
let _pdfDoc = null;
let _currentPage = 1;
let _totalPages = 0;
let _scale = 1.5;
let _members = [];         // takeoff member data with bboxes
let _selectedIdx = -1;     // currently selected member index
let _projectId = '';
let _projectName = '';
let _pdfPath = '';

// AISC shape set for client-side validation (populated from bridge)
let _validShapes = new Set();

// -- Helpers -----------------------------------------------------------------
function api() {
  return (window.pywebview && window.pywebview.api) ? window.pywebview.api : null;
}

function showToast(msg, type) {
  // Simple toast. Reuse parent window's showToast if available.
  if (window.opener && window.opener.showToast) {
    window.opener.showToast(msg, type);
    return;
  }
  const el = document.createElement('div');
  el.textContent = msg;
  el.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);' +
    'padding:8px 16px;border-radius:6px;font-family:var(--mono);font-size:11px;z-index:9999;' +
    'background:' + (type === 'success' ? '#34d399' : type === 'error' ? '#ff3b3b' : '#ff5f00') + ';' +
    'color:#fff;opacity:0;transition:opacity .3s;';
  document.body.appendChild(el);
  requestAnimationFrame(function() { el.style.opacity = '1'; });
  setTimeout(function() { el.style.opacity = '0'; setTimeout(function() { el.remove(); }, 300); }, 3000);
}

// -- PDF rendering -----------------------------------------------------------
async function loadPDF(url) {
  // PDF.js setup
  if (typeof pdfjsLib === 'undefined') {
    // Fallback: try loading as ES module
    try {
      const mod = await import('https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.4.168/pdf.min.mjs');
      window.pdfjsLib = mod;
      mod.GlobalWorkerOptions.workerSrc =
        'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.4.168/pdf.worker.min.mjs';
    } catch (e) {
      showToast('PDF.js failed to load. Check internet connection.', 'error');
      return;
    }
  }

  try {
    _pdfDoc = await pdfjsLib.getDocument(url).promise;
    _totalPages = _pdfDoc.numPages;
    _currentPage = 1;
    document.getElementById('wb-empty-state').style.display = 'none';
    updatePageControls();
    await renderPage(_currentPage);
  } catch (e) {
    showToast('Failed to load PDF: ' + e.message, 'error');
  }
}

async function renderPage(num) {
  if (!_pdfDoc) return;
  const page = await _pdfDoc.getPage(num);
  const viewport = page.getViewport({ scale: _scale });

  const canvas = document.getElementById('pdf-canvas');
  const ctx = canvas.getContext('2d');
  canvas.width = viewport.width;
  canvas.height = viewport.height;

  // Size the SVG overlay to match
  const svg = document.getElementById('detection-overlay');
  svg.setAttribute('width', viewport.width);
  svg.setAttribute('height', viewport.height);
  svg.setAttribute('viewBox', '0 0 ' + viewport.width + ' ' + viewport.height);

  await page.render({ canvasContext: ctx, viewport: viewport }).promise;

  // Render detection overlays for this page
  renderDetections();
  updatePageControls();
}

function updatePageControls() {
  document.getElementById('page-info').textContent = _currentPage + ' / ' + _totalPages;
  document.getElementById('btn-prev').disabled = _currentPage <= 1;
  document.getElementById('btn-next').disabled = _currentPage >= _totalPages;
  document.getElementById('zoom-level').textContent = Math.round(_scale * 100) + '%';
}

async function prevPage() { if (_currentPage > 1) { _currentPage--; await renderPage(_currentPage); } }
async function nextPage() { if (_currentPage < _totalPages) { _currentPage++; await renderPage(_currentPage); } }
async function zoomIn() { _scale = Math.min(4.0, _scale + 0.25); await renderPage(_currentPage); }
async function zoomOut() { _scale = Math.max(0.5, _scale - 0.25); await renderPage(_currentPage); }

// -- Detection overlay -------------------------------------------------------
function renderDetections() {
  const svg = document.getElementById('detection-overlay');
  // Clear existing
  while (svg.firstChild) svg.removeChild(svg.firstChild);

  _members.forEach(function(m, idx) {
    if (!m.bbox || m.bbox.length < 4) return;

    // Scale bbox from PDF points to current viewport
    var x0 = m.bbox[0] * _scale;
    var y0 = m.bbox[1] * _scale;
    var x1 = m.bbox[2] * _scale;
    var y1 = m.bbox[3] * _scale;

    // Determine status class
    var status = m.workbench_status || 'review';
    var cls = 'det-box ';
    if (status === 'approved') cls += 'approved';
    else if (status === 'high_confidence') cls += 'high';
    else if (status === 'invalid') cls += 'invalid';
    else cls += 'review';
    if (idx === _selectedIdx) cls += ' selected';

    // Rectangle
    var rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect.setAttribute('x', x0);
    rect.setAttribute('y', y0);
    rect.setAttribute('width', x1 - x0);
    rect.setAttribute('height', y1 - y0);
    rect.setAttribute('class', cls);
    rect.setAttribute('data-idx', idx);
    rect.addEventListener('click', function() { selectMember(idx); });
    rect.addEventListener('contextmenu', function(e) { e.preventDefault(); editMember(idx); });
    svg.appendChild(rect);

    // Label
    var label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', x0 + 3);
    label.setAttribute('y', y0 - 4);
    label.setAttribute('class', 'det-label');
    label.textContent = (m.mark || '') + ' ' + (m.shape || m.normalized || '');
    svg.appendChild(label);
  });
}

// -- Member selection and editing --------------------------------------------
function selectMember(idx) {
  _selectedIdx = idx;
  renderDetections();
  renderMemberList();

  if (idx >= 0 && idx < _members.length) {
    editMember(idx);
  }
}

function editMember(idx) {
  if (idx < 0 || idx >= _members.length) return;
  _selectedIdx = idx;
  var m = _members[idx];

  document.getElementById('edit-mark').value = m.mark || '';
  document.getElementById('edit-shape').value = m.shape || m.normalized || '';
  document.getElementById('edit-qty').value = m.qty || 1;
  document.getElementById('edit-length').value = m.length_ft || '';
  document.getElementById('edit-camber').value = m.camber || '';
  document.getElementById('edit-grade').value = m.grade || 'A992';
  document.getElementById('edit-validation').textContent = '';
  document.getElementById('edit-validation').className = 'wb-validation';
  document.getElementById('wb-edit-panel').style.display = 'block';

  // Live AISC validation on shape input
  var shapeInput = document.getElementById('edit-shape');
  shapeInput.oninput = function() { validateShapeInput(shapeInput.value); };
  validateShapeInput(shapeInput.value);
}

function validateShapeInput(shape) {
  var el = document.getElementById('edit-validation');
  if (!shape) { el.textContent = ''; return; }

  var normalized = shape.replace(/\s/g, '').toUpperCase().replace(/\u00d7/g, 'X');

  if (_validShapes.size === 0) {
    // No shapes loaded yet. Try bridge validation.
    el.textContent = 'AISC validation: loading...';
    el.className = 'wb-validation';
    return;
  }

  if (_validShapes.has(normalized)) {
    el.textContent = 'AISC v16.0: VALID';
    el.className = 'wb-validation valid';
  } else {
    el.textContent = 'AISC v16.0: NOT FOUND. Check designation.';
    el.className = 'wb-validation invalid';
  }
}

async function saveEdit() {
  if (_selectedIdx < 0 || _selectedIdx >= _members.length) return;
  var m = _members[_selectedIdx];

  var newShape = document.getElementById('edit-shape').value.replace(/\s/g, '').toUpperCase();
  var oldShape = (m.shape || m.normalized || '').toUpperCase();
  var changed = false;
  var changes = {};

  // Detect what changed
  var newMark = document.getElementById('edit-mark').value;
  if (newMark !== (m.mark || '')) { changes.mark = { old: m.mark || '', new: newMark }; m.mark = newMark; changed = true; }

  if (newShape !== oldShape) { changes.shape = { old: oldShape, new: newShape }; m.shape = newShape; m.normalized = newShape; changed = true; }

  var newQty = parseInt(document.getElementById('edit-qty').value, 10) || 1;
  if (newQty !== (m.qty || 1)) { changes.qty = { old: m.qty || 1, new: newQty }; m.qty = newQty; changed = true; }

  var newLength = parseFloat(document.getElementById('edit-length').value) || 0;
  if (newLength !== (m.length_ft || 0)) { changes.length_ft = { old: m.length_ft || 0, new: newLength }; m.length_ft = newLength; changed = true; }

  var newCamber = document.getElementById('edit-camber').value;
  if (newCamber !== (m.camber || '')) { changes.camber = { old: m.camber || '', new: newCamber }; m.camber = newCamber; changed = true; }

  var newGrade = document.getElementById('edit-grade').value;
  if (newGrade !== (m.grade || 'A992')) { changes.grade = { old: m.grade || 'A992', new: newGrade }; m.grade = newGrade; changed = true; }

  if (!changed) {
    showToast('No changes detected.', 'info');
    return;
  }

  // Mark as user-approved
  m.workbench_status = 'approved';

  // Save corrections to the bridge
  var bridge = api();
  if (bridge && bridge.save_workbench_correction) {
    for (var field in changes) {
      try {
        await bridge.save_workbench_correction(
          _projectId,
          m.id || m.mark || ('m' + _selectedIdx),
          field,
          String(changes[field].old),
          String(changes[field].new),
          '', // source_drawing
          _currentPage - 1,
          m.confidence || 0,
          'joseph'
        );
      } catch (e) { /* bridge not available in standalone mode */ }
    }
  }

  renderDetections();
  renderMemberList();
  showToast('Saved: ' + Object.keys(changes).join(', '), 'success');
}

function approveDetection() {
  if (_selectedIdx < 0 || _selectedIdx >= _members.length) return;
  _members[_selectedIdx].workbench_status = 'approved';
  renderDetections();
  renderMemberList();
  showToast('Detection approved.', 'success');
  cancelEdit();
}

function cancelEdit() {
  _selectedIdx = -1;
  document.getElementById('wb-edit-panel').style.display = 'none';
  renderDetections();
  renderMemberList();
}

// -- Member list sidebar -----------------------------------------------------
function renderMemberList() {
  var body = document.getElementById('member-list-body');
  body.innerHTML = '';
  document.getElementById('member-count').textContent = _members.length;

  _members.forEach(function(m, idx) {
    var status = m.workbench_status || 'review';
    var dotColor = status === 'approved' ? '#34d399' :
                   status === 'high_confidence' ? '#4FC3F7' :
                   status === 'invalid' ? '#ff3b3b' : '#ff5f00';

    var row = document.createElement('div');
    row.className = 'wb-member-row' + (idx === _selectedIdx ? ' selected' : '');
    row.innerHTML =
      '<span class="wb-dot" style="background:' + dotColor + '"></span>' +
      '<span class="wb-member-shape">' + (m.shape || m.normalized || '?') + '</span>' +
      '<span class="wb-member-mark">' + (m.mark || '-') + '</span>';
    row.addEventListener('click', function() { selectMember(idx); });
    body.appendChild(row);
  });

  // Stats
  var stats = document.getElementById('wb-stats');
  var approved = _members.filter(function(m) { return m.workbench_status === 'approved'; }).length;
  var review = _members.filter(function(m) { return m.workbench_status === 'review' || m.workbench_status === 'needs_review'; }).length;
  stats.textContent = approved + '/' + _members.length + ' approved . ' + review + ' need review';
  document.getElementById('btn-export').disabled = _members.length === 0;
}

// -- Load drawing from bridge ------------------------------------------------
async function loadDrawing() {
  var bridge = api();
  if (!bridge) {
    showToast('Bridge not available. Open from the main Virtual Office.', 'error');
    return;
  }

  // Get the current project's PDF path from the main window
  if (window.opener && window.opener._lastPdfPath) {
    _pdfPath = window.opener._lastPdfPath;
    _projectId = window.opener._lastBidNumber || '';
    _projectName = window.opener._lastProjectName || '';
  }

  if (_pdfPath) {
    // Load PDF via local file URL
    await loadPDF('file:///' + _pdfPath.replace(/\\/g, '/'));
  }

  // Load member data
  if (window.opener && window.opener._lastTakeoffMembers) {
    _members = window.opener._lastTakeoffMembers;
    renderMemberList();
    renderDetections();
    document.getElementById('wb-project-info').textContent = _projectName || _projectId || 'Project loaded';
  }
}

// -- Load shapes for client-side validation ----------------------------------
async function loadValidShapes() {
  var bridge = api();
  if (!bridge) return;

  try {
    // Try to get shapes from the bridge
    var result = await bridge.get_valid_shapes();
    if (result && result.shapes && Array.isArray(result.shapes)) {
      result.shapes.forEach(function(s) { _validShapes.add(s.toUpperCase()); });
    }
  } catch (e) {
    // Shapes not available. Validation will show "loading..."
  }
}

// -- Export to Tekla ---------------------------------------------------------
async function exportTekla() {
  if (!_members.length) { showToast('No members to export.', 'error'); return; }

  var bridge = api();
  if (!bridge || !bridge.export_tekla_xml) {
    showToast('Tekla export not available. Use main Virtual Office.', 'error');
    return;
  }

  showToast('Exporting Tekla XML...', 'info');
  try {
    // Convert members to Tekla format (reuse parent window's converter if available)
    var teklaMembers = _members;
    if (window.opener && window.opener.teklaMembersFromVerified) {
      teklaMembers = window.opener.teklaMembersFromVerified(_members);
    }

    var r = await bridge.export_tekla_xml(
      _projectId,
      _projectName,
      JSON.stringify(teklaMembers)
    );
    if (r && r.success) {
      showToast('Tekla XML exported: ' + r.items_exported + ' items.', 'success');
    } else {
      showToast('Export failed: ' + (r.error || 'unknown'), 'error');
    }
  } catch (e) {
    showToast('Export error: ' + e.message, 'error');
  }
}

// -- Drag and drop -----------------------------------------------------------
(function setupDragDrop() {
  var viewer = document.getElementById('wb-viewer');
  viewer.addEventListener('dragover', function(e) { e.preventDefault(); viewer.classList.add('drag-over'); });
  viewer.addEventListener('dragleave', function() { viewer.classList.remove('drag-over'); });
  viewer.addEventListener('drop', function(e) {
    e.preventDefault();
    viewer.classList.remove('drag-over');
    var files = e.dataTransfer.files;
    if (files.length > 0 && files[0].type === 'application/pdf') {
      var url = URL.createObjectURL(files[0]);
      loadPDF(url);
      document.getElementById('wb-project-info').textContent = files[0].name;
    }
  });
})();

// -- Initialize on load ------------------------------------------------------
window.addEventListener('DOMContentLoaded', function() {
  loadValidShapes();

  // If opened from main window with data, auto-load
  if (window.opener) {
    setTimeout(function() { loadDrawing(); }, 500);
  }
});

// Expose functions for HTML onclick handlers
window.prevPage = prevPage;
window.nextPage = nextPage;
window.zoomIn = zoomIn;
window.zoomOut = zoomOut;
window.loadDrawing = loadDrawing;
window.exportTekla = exportTekla;
window.saveEdit = saveEdit;
window.approveDetection = approveDetection;
window.cancelEdit = cancelEdit;
window.selectMember = selectMember;
