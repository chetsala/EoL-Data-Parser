let table;

function fetchCSV() {
  fetch('EoL_test.csv?' + new Date().getTime())
    .then(response => response.text())
    .then(text => {
      const rows = text.trim().split('\n');
      const rawHeaders = rows[0].split(',').map(h => h.trim());

      // Define headers to exclude
      const excluded = ["Message", "Test Rig ID", "Notes (optional)", "Filename"];

      // Build new headers/index mapping
      const includedIndexes = rawHeaders
        .map((header, i) => excluded.includes(header) ? null : i)
        .filter(i => i !== null);
      const headers = includedIndexes.map(i => rawHeaders[i]);

      const data = rows.slice(1).map(row => {
        const cells = row.split(',').map(c => c.trim());
        return includedIndexes.map(i => cells[i] || "");
      });

      if (table) {
        table.clear().rows.add(data).draw();
      } else {
        table = $('#csvTable').DataTable({
          data: data,
          columns: headers.map(h => ({ title: h })),
          pageLength: 25,
          scrollX: false,
          autoWidth: false,
        });

        populateFilters(headers, data);
        applyFilterHandlers(headers);
      }
    })
    .catch(err => console.error("Error loading CSV:", err));
}


function populateFilters(headers, data) {
  const getUniqueValues = (index) => [...new Set(data.map(row => row[index]).filter(Boolean))].sort();

  const resultIdx = headers.indexOf("Result");
  const modeIdx = headers.indexOf("Mode");
  const versionIdx = headers.indexOf("Version");
  const failureIdx = headers.indexOf("Failure Reason");

  populateSelect("filterResult", getUniqueValues(resultIdx));
  populateSelect("filterMode", getUniqueValues(modeIdx));
  populateSelect("filterVersion", getUniqueValues(versionIdx));
  populateSelect("filterFailure", getUniqueValues(failureIdx));
}


function populateSelect(id, values) {
  const select = document.getElementById(id);

  // Clear previous options except "All"
  select.innerHTML = '<option value="">All</option>';

  values.forEach(v => {
    const option = document.createElement("option");
    option.value = v;
    option.text = v;
    select.appendChild(option);
  });
}

function applyFilterHandlers(headers) {
  const resultIdx = headers.indexOf("Result");
  const modeIdx = headers.indexOf("Mode");
  const versionIdx = headers.indexOf("Version");
  const failureIdx = headers.indexOf("Failure Reason");

  $('#filterResult, #filterMode, #filterVersion, #filterFailure').on('change', function () {
    table.draw();
  });

  $.fn.dataTable.ext.search.push((settings, rowData) => {
    const rFilter = $('#filterResult').val();
    const mFilter = $('#filterMode').val();
    const vFilter = $('#filterVersion').val();
    const fFilter = $('#filterFailure').val();

    return (!rFilter || rowData[resultIdx] === rFilter) &&
           (!mFilter || rowData[modeIdx] === mFilter) &&
           (!vFilter || rowData[versionIdx] === vFilter) &&
           (!fFilter || rowData[failureIdx] === fFilter);
  });
}

fetchCSV();
setInterval(fetchCSV, 30000);
