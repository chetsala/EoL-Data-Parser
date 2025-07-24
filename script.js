let tableToday;
let tableAll;
let fullData = [];
let headers = [];
let headerMap = {}; // normalized header names -> index

function fetchCSV() {
  fetch('EoL_test.csv?' + new Date().getTime())
    .then(response => response.text())
    .then(text => {
      const rows = text.trim().split('\n');

      // --- Normalize headers (trim + lowercase for map) ---
      const rawHeaders = rows[0].split(',').map(h => h.trim());
      headers = rawHeaders;
      headerMap = {};
      headers.forEach((h, i) => {
        headerMap[h.toLowerCase()] = i;
      });

      // --- Exclude unwanted columns (case insensitive) ---
      const excluded = ["message", "test rig id", "notes (optional)", "filename"];
      const includedIndexes = headers
        .map((header, i) => excluded.includes(header.toLowerCase()) ? null : i)
        .filter(i => i !== null);

      headers = includedIndexes.map(i => rawHeaders[i]);

      // --- Parse data rows using included indexes ---
      fullData = rows.slice(1).map(row => {
        const cells = row.split(',').map(c => c.trim());
        return includedIndexes.map(i => cells[i] || "");
      });

      // --- Debug logs to verify parsing ---
      console.log("Raw CSV Header Line:", rows[0]);
      console.log("Detected headers after exclusion:", headers);
      console.log("First parsed row (if available):", fullData[0]);
      console.log("Total rows parsed:", fullData.length);

      renderTables();
      renderCharts();
    })
    .catch(err => console.error("Error loading CSV:", err));
}

// ------------------- TABLES -------------------

function renderTables() {
  // Detect Date column index
  const dateIdx = headers.findIndex(h => h.toLowerCase().includes("date"));
  const todayStr = new Date().toISOString().split('T')[0]; // YYYY-MM-DD

  // Filter today's data (only if Date column exists)
  let todayData = fullData;
  if (dateIdx !== -1) {
    todayData = fullData.filter(row => {
      const rowDate = row[dateIdx];
      return rowDate && rowDate.startsWith(todayStr);
    });
    console.log("Today filter active. Rows matching today:", todayData.length);
  } else {
    console.warn("Date column not found. Today tab will show all data.");
  }

  // --- Full History Table ---
  if (tableAll) {
    tableAll.clear().rows.add(fullData).draw();
  } else {
    tableAll = $('#tableAll').DataTable({
      data: fullData,
      columns: headers.map(h => ({ title: h })),
      pageLength: 25,
      autoWidth: false
    });
    populateFilters("All", headers, fullData);
    applyFilterHandlers("All", headers);
  }

  // --- Today's Data Table ---
  if (tableToday) {
    tableToday.clear().rows.add(todayData).draw();
  } else {
    tableToday = $('#tableToday').DataTable({
      data: todayData,
      columns: headers.map(h => ({ title: h })),
      pageLength: 25,
      autoWidth: false
    });
    populateFilters("Today", headers, todayData);
    applyFilterHandlers("Today", headers);
  }
}

// ------------------- FILTERS -------------------

function populateFilters(scope, headers, data) {
  const getUniqueValues = (index) =>
    index === -1 ? [] : [...new Set(data.map(row => row[index]).filter(Boolean))].sort();

  const resultIdx = headers.findIndex(h => h.toLowerCase() === "result");
  const modeIdx = headers.findIndex(h => h.toLowerCase() === "mode");
  const versionIdx = headers.findIndex(h => h.toLowerCase() === "version");
  const failureIdx = headers.findIndex(h => h.toLowerCase() === "failure reason");

  populateSelect(`filterResult${scope}`, getUniqueValues(resultIdx));
  populateSelect(`filterMode${scope}`, getUniqueValues(modeIdx));
  populateSelect(`filterVersion${scope}`, getUniqueValues(versionIdx));
  populateSelect(`filterFailure${scope}`, getUniqueValues(failureIdx));
}

function populateSelect(id, values) {
  const select = document.getElementById(id);
  if (!select) {
    console.warn(`Filter element with id "${id}" not found in HTML.`);
    return;
  }
  select.innerHTML = '<option value="">All</option>';
  values.forEach(v => {
    const option = document.createElement("option");
    option.value = v;
    option.text = v;
    select.appendChild(option);
  });
}

function applyFilterHandlers(scope, headers) {
  const resultIdx = headers.findIndex(h => h.toLowerCase() === "result");
  const modeIdx = headers.findIndex(h => h.toLowerCase() === "mode");
  const versionIdx = headers.findIndex(h => h.toLowerCase() === "version");
  const failureIdx = headers.findIndex(h => h.toLowerCase() === "failure reason");

  $(`#filterResult${scope}, #filterMode${scope}, #filterVersion${scope}, #filterFailure${scope}`).on('change', function () {
    (scope === "All" ? tableAll : tableToday).draw();
  });

  $.fn.dataTable.ext.search.push((settings, rowData) => {
    if ((scope === "All" && settings.nTable.id !== 'tableAll') ||
        (scope === "Today" && settings.nTable.id !== 'tableToday')) {
      return true; // Only filter appropriate table
    }

    const rFilter = $(`#filterResult${scope}`).val();
    const mFilter = $(`#filterMode${scope}`).val();
    const vFilter = $(`#filterVersion${scope}`).val();
    const fFilter = $(`#filterFailure${scope}`).val();

    return (!rFilter || rowData[resultIdx] === rFilter) &&
           (!mFilter || rowData[modeIdx] === mFilter) &&
           (!vFilter || rowData[versionIdx] === vFilter) &&
           (!fFilter || rowData[failureIdx] === fFilter);
  });
}

// ------------------- CHARTS -------------------

let passFailChart, failureReasonChart, dailyTrendChart;

function renderCharts() {
  if (!fullData.length) return;

  const resultIdx = headers.findIndex(h => h.toLowerCase() === "result");
  const failureIdx = headers.findIndex(h => h.toLowerCase() === "failure reason");
  const dateIdx = headers.findIndex(h => h.toLowerCase().includes("date"));

  // --- Pass vs Fail Pie Chart ---
  const passCount = resultIdx !== -1 ? fullData.filter(row => row[resultIdx] === "Pass").length : 0;
  const failCount = resultIdx !== -1 ? fullData.filter(row => row[resultIdx] === "Fail").length : 0;

  const passFailData = {
    labels: ["Pass", "Fail"],
    datasets: [{
      data: [passCount, failCount],
      backgroundColor: ["#4caf50", "#f44336"]
    }]
  };

  if (passFailChart) passFailChart.destroy();
  passFailChart = new Chart(document.getElementById("passFailChart"), {
    type: 'pie',
    data: passFailData
  });

  // --- Failure Reasons Bar Chart ---
  const failReasons = {};
  if (resultIdx !== -1 && failureIdx !== -1) {
    fullData.forEach(row => {
      if (row[resultIdx] === "Fail") {
        const reason = row[failureIdx] || "Unknown";
        failReasons[reason] = (failReasons[reason] || 0) + 1;
      }
    });
  }

  if (failureReasonChart) failureReasonChart.destroy();
  failureReasonChart = new Chart(document.getElementById("failureReasonChart"), {
    type: 'bar',
    data: {
      labels: Object.keys(failReasons),
      datasets: [{
        label: "Failure Count",
        data: Object.values(failReasons),
        backgroundColor: "#2196f3"
      }]
    },
    options: {
      indexAxis: 'y',
      plugins: { legend: { display: false } }
    }
  });

  // --- Daily Trend Line Chart ---
  const dailyCounts = {};
  if (dateIdx !== -1) {
    fullData.forEach(row => {
      const day = row[dateIdx].split('T')[0]; // Extract YYYY-MM-DD
      dailyCounts[day] = (dailyCounts[day] || 0) + 1;
    });
  } else {
    console.warn("Date column not found — Daily Trend chart may be empty.");
  }

  if (dailyTrendChart) dailyTrendChart.destroy();
  dailyTrendChart = new Chart(document.getElementById("dailyTrendChart"), {
    type: 'line',
    data: {
      labels: Object.keys(dailyCounts).sort(),
      datasets: [{
        label: "Tests per Day",
        data: Object.values(dailyCounts),
        borderColor: "#673ab7",
        fill: false,
        tension: 0.1
      }]
    }
  });
}

// ------------------- INIT -------------------

fetchCSV();
setInterval(fetchCSV, 30000);
