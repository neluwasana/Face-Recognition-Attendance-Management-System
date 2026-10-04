

document.addEventListener("DOMContentLoaded", function () {

    /* Element References*/
    var dateEl          = document.getElementById("currentDateDisplay");
    var reportBody      = document.getElementById("reportBody");
    var filterBtn       = document.getElementById("filterBtn");
    var resetBtn        = document.getElementById("resetBtn");
    var exportBtn       = document.getElementById("exportBtn");
    var exportPdfBtn    = document.getElementById("exportPdfBtn");
    var filterDate      = document.getElementById("filterDate");
    var filterStudent   = document.getElementById("filterStudent");
    var filterLecture   = document.getElementById("filterLecture");
    var filterStudyMode = document.getElementById("filterStudyMode");
    var filterDept      = document.getElementById("filterDepartment");
    var filterYear      = document.getElementById("filterYear");
    var filterSemester  = document.getElementById("filterSemester");
    var summTotal       = document.getElementById("summTotal");
    var summPresent     = document.getElementById("summPresent");
    var summStudents    = document.getElementById("summStudents");
    var summLectures    = document.getElementById("summLectures");

    /* HTML templates defined in attendance_report.html */
    var rowTemplate = document.getElementById("reportRowTemplate");
    var emptyRowTpl = document.getElementById("emptyRowTemplate");

    /* Holds the current set of records (used by CSV / Print) */
    var allRecords = [];


    /* Show current date in header */
    if (dateEl) {
        dateEl.textContent = new Date().toLocaleDateString("en-US", {
            weekday: "long", year: "numeric", month: "long", day: "numeric"
        });
    }

    /* Load all records when the page first opens */
    loadReport();


    /*LOAD REPORT FROM SERVER
       Sends a GET request to /api/attendance-report
       with optional filter parameters.*/
    function loadReport(filters) {
        filters = filters || {};

        var url    = "/api/attendance-report";
        var params = new URLSearchParams();

        if (filters.date)       params.append("date",       filters.date);
        if (filters.student)    params.append("student",    filters.student);
        if (filters.lecture)    params.append("lecture",    filters.lecture);
        if (filters.study_mode) params.append("study_mode", filters.study_mode);
        if (filters.department) params.append("department", filters.department);
        if (filters.year)       params.append("year",       filters.year);
        if (filters.semester)   params.append("semester",   filters.semester);

        if (params.toString()) url += "?" + params.toString();

        fetch(url)
            .then(function (res) { return res.json(); })
            .then(function (data) {
                allRecords = data.records || [];
                renderTable(allRecords);
                updateSummary(data);
            })
            .catch(function (err) {
                showEmptyRow("Error loading data: " + err.message);
            });
    }


    /* 
       RENDER TABLE
       Clones the <template id="reportRowTemplate">
       once per record and fills it with text.
       */
    function renderTable(records) {
        if (!reportBody) return;

        /* Clear old rows */
        reportBody.textContent = "";

        if (!records || records.length === 0) {
            showEmptyRow("No attendance records found.");
            return;
        }

        records.forEach(function (r, i) {
            var clone = rowTemplate.content.cloneNode(true);

            clone.querySelector(".col-no-val").textContent      = i + 1;
            clone.querySelector(".col-sid-val").textContent     = r.student_id   || "-";
            clone.querySelector(".col-name-val").textContent    = r.student_name || "-";
            clone.querySelector(".col-year-val").textContent    = r.year         || "-";
            clone.querySelector(".col-sem-val").textContent     = r.semester     || "-";
            clone.querySelector(".col-lecture-val").textContent = r.lecture_name || "-";
            clone.querySelector(".col-date-val").textContent    = r.date         || "-";
            clone.querySelector(".col-time-val").textContent    = r.time         || "-";

            /* Apply correct badge class for study mode */
            var modeSpan      = clone.querySelector(".col-mode-val .badge");
            modeSpan.className   = "badge " + (r.part_time_full_time === "Full Time" ? "badge-dept" : "badge-mode-pt");
            modeSpan.textContent = r.part_time_full_time || "-";

            reportBody.appendChild(clone);
        });
    }


    /* 
       SHOW EMPTY / ERROR ROW
       Clones <template id="emptyRowTemplate">
       and inserts a single message row.
     */
    function showEmptyRow(message) {
        if (!reportBody) return;
        reportBody.textContent = "";
        var clone = emptyRowTpl.content.cloneNode(true);
        clone.querySelector(".empty-msg-text").textContent = message;
        reportBody.appendChild(clone);
    }


    /* UPDATE SUMMARY CARDS */
    function updateSummary(data) {
        if (summTotal)    summTotal.textContent    = data.total_records   || 0;
        if (summPresent)  summPresent.textContent  = data.total_records   || 0;
        if (summStudents) summStudents.textContent = data.unique_students || 0;
        if (summLectures) summLectures.textContent = data.unique_lectures || 0;
    }


    /* FILTER BUTTON*/
    if (filterBtn) {
        filterBtn.addEventListener("click", function () {
            loadReport({
                date:       filterDate      ? filterDate.value           : "",
                student:    filterStudent   ? filterStudent.value.trim() : "",
                lecture:    filterLecture   ? filterLecture.value.trim() : "",
                study_mode: filterStudyMode ? filterStudyMode.value      : "",
                department: filterDept      ? filterDept.value           : "",
                year:       filterYear      ? filterYear.value           : "",
                semester:   filterSemester  ? filterSemester.value       : ""
            });
        });
    }


    /* RESET BUTTON
       Clears all filters and reloads all records.*/
    if (resetBtn) {
        resetBtn.addEventListener("click", function () {
            if (filterDate)      filterDate.value      = "";
            if (filterStudent)   filterStudent.value   = "";
            if (filterLecture)   filterLecture.value   = "";
            if (filterStudyMode) filterStudyMode.value = "";
            if (filterDept)      filterDept.value      = "";
            if (filterYear)      filterYear.value      = "";
            if (filterSemester)  filterSemester.value  = "";
            loadReport();
        });
    }


    /* EXPORT CSV
       Builds a CSV string from allRecords and
       triggers a browser download. */
    if (exportBtn) {
        exportBtn.addEventListener("click", function () {

            if (allRecords.length === 0) {
                alert("No records to export!");
                return;
            }

            var csv = "No,Student ID,Name,Year,Semester,Study Mode,Lecture,Date,Time,Status\n";

            allRecords.forEach(function (r, i) {
                csv += (i + 1)                        + "," +
                       (r.student_id          || "")  + "," +
                       (r.student_name        || "")  + "," +
                       (r.year                || "")  + "," +
                       (r.semester            || "")  + "," +
                       (r.part_time_full_time || "")  + "," +
                       (r.lecture_name        || "")  + "," +
                       (r.date                || "")  + "," +
                       (r.time                || "")  + ",Present\n";
            });

            var blob     = new Blob([csv], { type: "text/csv" });
            var url      = URL.createObjectURL(blob);
            var link     = document.createElement("a");
            link.href     = url;
            link.download = "attendance_report_" + new Date().toISOString().slice(0, 10) + ".csv";
            link.click();
            URL.revokeObjectURL(url);
        });
    }


    /*SELECT ALL / DESELECT ALL CHECKBOX
       Controls the header checkbox and individual
       row checkboxes together. */
    var selectAllChk = document.getElementById("selectAllRows");
    if (selectAllChk) {
        selectAllChk.addEventListener("change", function () {
            var rowChks = reportBody.querySelectorAll(".row-select");
            rowChks.forEach(function (chk) { chk.checked = selectAllChk.checked; });
        });
    }

    /* Keep "select all" in sync when individual rows change */
    if (reportBody) {
        reportBody.addEventListener("change", function (e) {
            if (!e.target.classList.contains("row-select")) return;
            var all   = reportBody.querySelectorAll(".row-select");
            var chkd  = reportBody.querySelectorAll(".row-select:checked");
            if (selectAllChk) {
                selectAllChk.checked       = all.length > 0 && chkd.length === all.length;
                selectAllChk.indeterminate = chkd.length > 0 && chkd.length < all.length;
            }
        });
    }


    /*PRINT / PDF  (browser print dialog) */

    /* Helper: read a filter field, return its value or "All" */
    function filterVal(el) {
        if (!el) return "All";
        var v = (el.value || "").trim();
        return v || "All";
    }

    /* Helper: populate #pdfFilterInfo from current filter state */
    function populateFilterInfo() {
        document.getElementById("pdfSubject").textContent  = filterVal(filterLecture);
        document.getElementById("pdfYear").textContent     = filterVal(filterYear);
        document.getElementById("pdfSemester").textContent = filterVal(filterSemester);
        document.getElementById("pdfLecturer").textContent = filterVal(filterStudent);
        document.getElementById("pdfDate").textContent     = filterVal(filterDate);
    }

    /* Track which rows were temporarily hidden so we can restore them */
    var _hiddenRows = [];

    /* Blank the document title before print so it doesn't appear in PDF */
    var _origTitle = document.title;
    window.addEventListener("beforeprint", function () {
        document.title = "";
    });

    /* Restore everything after the print dialog closes */
    window.addEventListener("afterprint", function () {
        document.title = _origTitle;

        /* Restore any hidden rows */
        _hiddenRows.forEach(function (row) { row.style.display = ""; });
        _hiddenRows = [];

        /* Hide the filter info block */
        var pdfInfo = document.getElementById("pdfFilterInfo");
        if (pdfInfo) pdfInfo.style.display = "none";

        /* Uncheck select-all */
        if (selectAllChk) {
            selectAllChk.checked       = false;
            selectAllChk.indeterminate = false;
        }
    });

    /* Single PDF button */
    if (exportPdfBtn) {
        exportPdfBtn.addEventListener("click", function () {
            if (allRecords.length === 0) {
                alert("No records to print!");
                return;
            }

            var checkedRows = reportBody
                ? Array.from(reportBody.querySelectorAll(".row-select:checked"))
                : [];

            var pdfInfo = document.getElementById("pdfFilterInfo");

            if (checkedRows.length > 0) {
                /*Selected rows mode  */
                /* Hide every data row whose checkbox is NOT checked */
                var allRows = Array.from(reportBody.querySelectorAll("tr.data-row"));
                _hiddenRows = allRows.filter(function (row) {
                    return !row.querySelector(".row-select:checked");
                });
                _hiddenRows.forEach(function (row) { row.style.display = "none"; });

                /* Show filter info */
                populateFilterInfo();
                if (pdfInfo) pdfInfo.style.display = "block";

            } else {
                /*All records mode */
                /* Nothing to hide; filter info stays hidden */
                if (pdfInfo) pdfInfo.style.display = "none";
            }

            window.print();
        });
    }

}); 


