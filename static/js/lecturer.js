
document.addEventListener("DOMContentLoaded", function () {

    /*1. SECTION NAVIGATION  */

    var navLinks = document.querySelectorAll(".sidebar .nav-link");
    var sections = document.querySelectorAll(".lecturer-section");

    navLinks.forEach(function (link) {
        link.addEventListener("click", function (e) {
            var targetId = this.getAttribute("data-target");

            // No data-target → let the browser handle normal navigation
            if (!targetId) return;

            e.preventDefault();

            // Mark clicked link as active, deactivate others
            navLinks.forEach(function (l) { l.classList.remove("active"); });
            this.classList.add("active");

            // Hide all sections, show the target section
            sections.forEach(function (s) {
                s.style.display = "none";
                s.classList.remove("active");
            });

            var target = document.getElementById(targetId);
            if (target) {
                target.style.display = "block";
                target.classList.add("active");
            }

            // If leaving the Mark Attendance section, stop the webcam
            if (targetId !== "mark-attendance-section") {
                var stopBtn = document.getElementById("stopCameraBtn");
                if (stopBtn && stopBtn.style.display !== "none") {
                    stopBtn.click();
                }
            }
        });
    });


    /*  2. LIVE DATE & TIME DISPLAY 
       Shows the current date in #lecturerDateDisplay and updates the
       session time ticker every minute.                              */

    var dateDisplay = document.getElementById("lecturerDateDisplay");
    if (dateDisplay) {
        dateDisplay.textContent = new Date().toLocaleDateString("en-US", {
            weekday: "long", year: "numeric", month: "long", day: "numeric"
        });
        updateSessionTime();
        setInterval(updateSessionTime, 60000); // refresh every minute
    }

    function updateSessionTime() {
        var now  = new Date();
        var h    = now.getHours();
        var m    = now.getMinutes();
        var ampm = h >= 12 ? "PM" : "AM";
        h        = h % 12 || 12;
        var timeStr = h + ":" + (m < 10 ? "0" + m : m) + " " + ampm;

        var liveTimeEl = document.getElementById("lecturerLiveTime");
        if (liveTimeEl) liveTimeEl.textContent = timeStr;
    }


    /*3. SESSION INFO BOX 
       When a row is clicked in the timetable on the Mark Attendance
       page, this fills the session details box with that row's data. */

    var timetableBody = document.querySelector("#timetableTable tbody");
    if (timetableBody) {
        timetableBody.addEventListener("click", function (e) {
            var row = e.target.closest(".data-row");
            if (!row) return;

            var cells = row.cells;
            if (cells.length < 12) return;

     
            var subject  = cells[5]  ? cells[5].textContent.trim()  : "-";
            var year     = cells[2]  ? cells[2].textContent.trim()  : "-";
            var semester = cells[3]  ? cells[3].textContent.trim()  : "-";
            var mode     = cells[4]  ? cells[4].textContent.trim()  : "-";
            var date     = cells[8]  ? cells[8].textContent.trim()  : "-";
            var start    = cells[9]  ? cells[9].textContent.trim()  : "-";
            var end      = cells[10] ? cells[10].textContent.trim() : "-";

            var sessionSubjectEl  = document.getElementById("sessionSubject");
            var sessionYearEl     = document.getElementById("sessionYear");
            var sessionSemesterEl = document.getElementById("sessionSemester");
            var sessionModeEl     = document.getElementById("sessionMode");
            var sessionDateEl     = document.getElementById("sessionDate");
            var sessionTimeEl     = document.getElementById("sessionTime");
            var sessionHintEl     = document.getElementById("sessionHint");

            if (sessionSubjectEl)  sessionSubjectEl.textContent  = subject;
            if (sessionYearEl)     sessionYearEl.textContent     = year;
            if (sessionSemesterEl) sessionSemesterEl.textContent = semester;
            if (sessionModeEl)     sessionModeEl.textContent     = mode;
            if (sessionDateEl)     sessionDateEl.textContent     = date;
            if (sessionTimeEl)     sessionTimeEl.textContent     = start + " - " + end;
            if (sessionHintEl)     sessionHintEl.style.display   = "none";
        });
    }


    /*4. LECTURER TIMETABLE DATE FILTER*/
    var dateInput = document.getElementById("filterDate");
    if (dateInput) {
        dateInput.addEventListener("change", function () {
            var selectedDate = dateInput.value;
            window.location.href = "/lecturer/timetable?date=" + selectedDate;
        });
    }

});
