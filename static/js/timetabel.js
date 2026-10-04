

//  TOAST HELPER 
function showFlashToast(message, type) {
    var existing = document.querySelectorAll(".floating-toast");
    existing.forEach(function (t) { t.remove(); });

    var toast = document.createElement("div");
    toast.className = "flash " + type + " floating-toast";
    var icon = type === "success" ? "✅" : "⚠️";
    toast.innerHTML = "<span>" + icon + "</span> <span>" + message + "</span>";
    document.body.appendChild(toast);

    setTimeout(function () {
        toast.style.animation = "slideOut 0.3s forwards";
        setTimeout(function () { toast.remove(); }, 300);
    }, 3500);
}


//  SCHEDULE TYPE TOGGLE 
function toggleScheduleFields() {
    var type = document.getElementById("scheduleType").value;
    var weeklyFields  = document.getElementById("weeklyFields");
    var onetimeFields = document.getElementById("onetimeFields");

    if (type === "weekly") {
        weeklyFields.style.display  = "";
        onetimeFields.style.display = "none";
        // Clear one-time date
        var ld = document.getElementById("lecture_date");
        if (ld) ld.value = "";
    } else {
        weeklyFields.style.display  = "none";
        onetimeFields.style.display = "";
        // Clear weekly fields
        var dayEl   = document.getElementById("day");
        var slotEl  = document.getElementById("time_slot");
        var sdEl    = document.getElementById("semester_start_date");
        var edEl    = document.getElementById("semester_end_date");
        if (dayEl)  dayEl.value  = "";
        if (slotEl) slotEl.value = "";
        if (sdEl)   sdEl.value   = "";
        if (edEl)   edEl.value   = "";
        var wb = document.getElementById("weekInfoBox");
        if (wb) wb.style.display = "none";
    }
}

//  AUTO CALCULATE 15-WEEK INFO 
function updateWeekInfo() {
    var sdEl = document.getElementById("semester_start_date");
    var edEl = document.getElementById("semester_end_date");
    var wb   = document.getElementById("weekInfoBox");
    var wt   = document.getElementById("weekInfoText");

    if (!sdEl || !edEl || !wb || !wt) return;

    var sd = sdEl.value;
    var ed = edEl.value;

    if (sd && ed) {
        var startDate = new Date(sd);
        var endDate   = new Date(ed);
        var diffMs    = endDate - startDate;
        var diffDays  = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        var numWeeks  = Math.min(15, Math.ceil((diffDays + 1) / 7));

        // Calculate Week 15 end date
        var week15End = new Date(startDate);
        week15End.setDate(startDate.getDate() + (numWeeks * 7) - 1);
        var w15Str = week15End.toISOString().split("T")[0];

        wt.textContent = "Week 1 starts: " + sd + " | Week " + numWeeks + " ends: " + w15Str + " | Total: " + numWeeks + " week(s)";
        wb.style.display = "block";
    } else {
        wb.style.display = "none";
    }
}


//  GET SELECTED IDs FROM TABLE 
function getSelectedIds() {
    return Array.from(document.querySelectorAll(".timetabel-select-check:checked"))
                .map(function (cb) { return cb.value; });
}


//  cancelTargetId  — tracks which row is being cancelled 
var cancelTargetId = null;


//  MAIN 
document.addEventListener("DOMContentLoaded", function () {

    //  MODAL ELEMENTS (Add/Edit form) 
    var openBtn    = document.getElementById("openTimetableForm");
    var modal      = document.getElementById("timetableModal");
    var cancelBtn  = document.getElementById("closeModalBtn");
    var closeBtn   = document.getElementById("closeBtn");
    var formTitle  = document.getElementById("formTitle");
    var saveBtnEl  = modal.querySelector(".btn-save");
    var editingId  = null;   // which timetable row is being edited

    //  CANCEL MODAL ELEMENTS 
    var cancelModal        = document.getElementById("cancelModal");
    var cancelLectureBtn   = document.getElementById("cancelLectureBtn");
    var cancelModalClose   = document.getElementById("cancelModalClose");
    var cancelModalCloseBtn = document.getElementById("cancelModalCloseBtn");
    var confirmCancelBtn   = document.getElementById("confirmCancelBtn");
    var cancelInfoDiv      = document.getElementById("cancelLectureInfo");


    // Listen for semester date changes to auto-calculate weeks
    var sdEl = document.getElementById("semester_start_date");
    var edEl = document.getElementById("semester_end_date");
    if (sdEl) sdEl.addEventListener("change", updateWeekInfo);
    if (edEl) edEl.addEventListener("change", updateWeekInfo);

    // Auto-generate time slot when start or end time changes
    function autoGenerateTimeSlot() {
        var startEl = document.getElementById("start_time");
        var endEl   = document.getElementById("end_time");
        var slotEl  = document.getElementById("time_slot");
        if (!startEl || !endEl || !slotEl) return;
        var start = startEl.value;
        var end   = endEl.value;
        if (start && end) {
            function fmtAMPM(t) {
                var p = t.split(":"); var h = parseInt(p[0], 10); var m = p[1];
                var ap = h >= 12 ? "PM" : "AM"; h = h % 12; if (h === 0) h = 12;
                return (h < 10 ? "0"+h : h) + ":" + m + " " + ap;
            }
            slotEl.value = fmtAMPM(start) + " - " + fmtAMPM(end);
        } else {
            slotEl.value = "";
        }
    }

    var startTimeEl = document.getElementById("start_time");
    var endTimeEl   = document.getElementById("end_time");
    if (startTimeEl) startTimeEl.addEventListener("input", autoGenerateTimeSlot);
    if (endTimeEl)   endTimeEl.addEventListener("input", autoGenerateTimeSlot);

    var stDropdownEl = document.getElementById("scheduleType");
    if (stDropdownEl) stDropdownEl.addEventListener("change", toggleScheduleFields);


    // OPEN / CLOSE ADD-EDIT MODAL 
    openBtn.onclick = function () {
        editingId = null;
        formTitle.textContent = "➕ Add Lecture";
        saveBtnEl.textContent = "Save Timetable";
        document.getElementById("timetableForm").reset();
        
        // Auto-fill from active filters if present
        var activeCourse = document.getElementById("adminCourseFilter") ? document.getElementById("adminCourseFilter").value : "";
        var activeYear = document.getElementById("adminYearFilter") ? document.getElementById("adminYearFilter").value : "";
        var activeSemester = document.getElementById("adminSemFilter") ? document.getElementById("adminSemFilter").value : "";
        var activeDate = document.getElementById("adminDateFilter") ? document.getElementById("adminDateFilter").value : "";

        if (activeCourse) document.getElementById("department").value = activeCourse;
        if (activeYear) document.getElementById("year").value = activeYear;
        if (activeSemester) document.getElementById("semester").value = activeSemester;
        if (activeDate) document.getElementById("lecture_date").value = activeDate;

        // Default to weekly schedule
        var stEl = document.getElementById("scheduleType");
        if (stEl) stEl.value = "weekly";
        toggleScheduleFields();
        // Clear time slot on open
        var slotEl = document.getElementById("time_slot");
        if (slotEl) slotEl.value = "";
        modal.style.display = "flex";
        
        loadSubjects();
    };

    cancelBtn.onclick = function () { modal.style.display = "none"; };
    closeBtn.onclick  = function () { modal.style.display = "none"; };

    window.onclick = function (e) {
        if (e.target === modal)        modal.style.display = "none";
        if (e.target === cancelModal)  cancelModal.style.display = "none";
    };


    // FORM SUBMIT (ADD or EDIT TIMETABLE) 
    var timetableForm = document.getElementById("timetableForm");
    if (timetableForm) {
        timetableForm.onsubmit = function (e) {
            e.preventDefault();

            var fd  = new FormData(this);
            var url = "/add_timetable";

            if (editingId) {
                fd.append("id", editingId);
                url = "/update_timetable";
            }

            fetch(url, { method: "POST", body: fd })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.success) {
                        showFlashToast(data.message, "success");
                        setTimeout(function () { location.reload(); }, 1000);
                    } else {
                        showFlashToast(data.message || "Operation failed!", "error");
                    }
                })
                .catch(function () {
                    showFlashToast("An error occurred. Please try again.", "error");
                });
        };
    }


    //DYNAMIC SUBJECT LOADER & AUTO-ASSIGN LECTURER 
    var courseEl   = document.getElementById("department");
    var yearEl     = document.getElementById("year");
    var semesterEl = document.getElementById("semester");
    var subjectEl  = document.getElementById("subject_id");
    var lecturerEl = document.getElementById("lecture_id");
    var subjectsData = []; // Local cache to store loaded subjects with their lecturer IDs

    function loadSubjects() {
        var c = courseEl.value;
        var y = yearEl.value;
        var s = semesterEl.value;
        if (c && y && s) {
            fetch("/get_subjects?department=" + c + "&year=" + encodeURIComponent(y) + "&semester=" + encodeURIComponent(s))
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    subjectsData = data;
                    subjectEl.innerHTML = '<option value="">Select Subject</option>';
                    data.forEach(function (item) {
                        subjectEl.innerHTML += '<option value="' + item.id + '">' + item.subject_name + '</option>';
                    });
                });
        }
    }

    courseEl.addEventListener("change", loadSubjects);
    yearEl.addEventListener("change", loadSubjects);
    semesterEl.addEventListener("change", loadSubjects);

    // Auto-assign lecturer when subject changes
    if (subjectEl) {
        subjectEl.addEventListener("change", function () {
            var selectedSubjectId = this.value;
            if (!selectedSubjectId) {
                lecturerEl.value = "";
                return;
            }
            // Find the subject in our local cache
            var subject = subjectsData.find(function (s) { return s.id == selectedSubjectId; });
            if (subject && subject.lecturer_id) {
                lecturerEl.value = subject.lecturer_id;
            }
        });
    }


    //  ROW SELECTION 
    var selectedRow = null;

    var tableBody = document.querySelector("#timetableTable tbody");
    if (tableBody) {
        tableBody.onclick = function (e) {
            var row = e.target.closest(".data-row");
            if (!row) return;

            var checkbox = row.querySelector(".timetabel-select-check");
            if (e.target !== checkbox) checkbox.checked = !checkbox.checked;

            if (checkbox.checked) {
                row.classList.add("active");
                selectedRow = row;
            } else {
                row.classList.remove("active");
                var still = document.querySelectorAll(".data-row.active");
                selectedRow = still.length === 1 ? still[0] : null;
            }

            var allChecks = document.querySelectorAll(".timetabel-select-check");
            var allChecked = document.querySelectorAll(".timetabel-select-check:checked");
            var selectAll = document.getElementById("selectAllCheck");
            if (selectAll) {
                selectAll.checked = allChecks.length > 0 && allChecks.length === allChecked.length;
                selectAll.indeterminate = allChecked.length > 0 && allChecked.length < allChecks.length;
            }
        };
    }

    var selectAllCheck = document.getElementById("selectAllCheck");
    if (selectAllCheck) {
        selectAllCheck.onclick = function () {
            var rows = document.querySelectorAll("#timetableTable tbody .data-row");
            rows.forEach(function (row) {
                var checkbox = row.querySelector(".timetabel-select-check");
                if (row.style.display !== "none") {
                    checkbox.checked = selectAllCheck.checked;
                    if (selectAllCheck.checked) {
                        row.classList.add("active");
                    } else {
                        row.classList.remove("active");
                    }
                }
            });
            selectedRow = selectAllCheck.checked ? document.querySelector(".data-row.active") : null;
        };
    }


    // Client-side search and filters removed as filtering is now handled server-side.


    //  EDIT TIMETABLE ROW 
    document.getElementById("editSelectedBtn").onclick = function () {
        // Reset cancel state so cancel modal won't trigger accidentally
        cancelTargetId = null;
        cancelModal.style.display = "none";

        var selected = document.querySelectorAll(".data-row.active");

        if (selected.length === 0) {
            showFlashToast("Please select a row to edit!", "error");
            return;
        }
        if (selected.length > 1) {
            showFlashToast("Please select only ONE row to edit!", "error");
            return;
        }

        var id = selected[0].getAttribute("data-id");

        fetch("/edit_timetable/" + id + "?_=" + Date.now())
            .then(function (res) { return res.json(); })
            .then(function (t) {
                editingId = id;

                // Determine schedule type
                var stEl = document.getElementById("scheduleType");
                var hasWeekly = t.day && t.semester_start_date;
                if (stEl) stEl.value = hasWeekly ? "weekly" : "onetime";
                toggleScheduleFields();

                // Fill base form fields
                document.getElementById("department").value           = t.course;
                document.getElementById("year").value                 = t.year;
                document.getElementById("semester").value             = t.semester;
                var ptftEl = document.getElementById("part_time_full_time");
                if (ptftEl) ptftEl.value = t.part_time_full_time || "Full Time";
                document.getElementById("location").value             = t.location;
                document.getElementById("start_time").value           = t.start_time;
                document.getElementById("end_time").value             = t.end_time;
                document.getElementById("attendance_mark_time").value = t.attendance_mark_time;

                // Fill weekly or one-time fields
                var dayEl  = document.getElementById("day");
                var slotEl = document.getElementById("time_slot");
                var sdEl2  = document.getElementById("semester_start_date");
                var edEl2  = document.getElementById("semester_end_date");
                var ldEl   = document.getElementById("lecture_date");

                if (hasWeekly) {
                    if (dayEl)  dayEl.value  = t.day  || "";
                    if (slotEl) slotEl.value = t.time_slot || "";
                    if (sdEl2)  sdEl2.value  = t.semester_start_date || "";
                    if (edEl2)  edEl2.value  = t.semester_end_date   || "";
                    updateWeekInfo();
                } else {
                    if (ldEl) ldEl.value = t.lecture_date || "";
                }

                // Load matching subjects, then set subject and lecturer after delay
                loadSubjects();
                setTimeout(function () {
                    document.getElementById("subject_id").value = t.subject_id;
                    document.getElementById("lecture_id").value = t.lecturer_id;
                }, 500);

                formTitle.textContent = "Edit Timetable";
                saveBtnEl.textContent = "Update Timetable";
                modal.style.display   = "flex";
            })
            .catch(function () {
                showFlashToast("Unable to load timetable details. Please try again.", "error");
            });
    };


    //  DELETE TIMETABLE ROW
    document.getElementById("deleteSelectedBtn").onclick = function () {
        var ids = getSelectedIds();
        if (ids.length === 0) { showFlashToast("Please select at least one row to delete!", "error"); return; }

        var message = ids.length === 1 ?
            "Are you sure you want to permanently delete this timetable entry?" :
            "Are you sure you want to permanently delete the " + ids.length + " selected timetable entries?";

        if (!confirm(message)) return;

        fetch("/delete_timetable/" + ids.join(","), { method: "POST" })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.success) {
                    showFlashToast("Timetable deleted successfully!", "success");
                    setTimeout(function () { location.reload(); }, 1000);
                } else {
                    showFlashToast(data.message || "Delete failed.", "error");
                }
            })
            .catch(function () { showFlashToast("Error deleting timetable.", "error"); });
    };


    //  CANCEL LECTURE MODAL 
    if (!cancelLectureBtn) {
        console.error("Cancel button NOT FOUND - check HTML id!");
        return;
    }

    cancelLectureBtn.onclick = function () {
        var ids = getSelectedIds();

        if (!ids || ids.length === 0) {
            showFlashToast("Please select a lecture row to cancel!", "error");
            return;
        }
        if (ids.length > 1) {
            showFlashToast("Please select only ONE lecture!", "error");
            return;
        }

        var row = document.querySelector(".data-row[data-id='" + ids[0] + "']");
        if (!row) return;

        if (row.dataset.cancelled === "true") {
            showFlashToast("Already cancelled!", "error");
            return;
        }

        cancelTargetId = ids[0];

        // Cells: 0=checkbox, 1=course, 2=year, 3=semester, 4=studymode, 5=subject, 6=lecturer, 7=location, 8=day/date, 9=timeslot, 10=att.mark.time
        // Start/end times are stored as data attributes on the row element
        cancelInfoDiv.innerHTML =
            "<strong>📚 Subject:</strong> " + row.cells[5].innerText + "<br>" +
            "<strong>👨‍🏫 Lecturer:</strong> " + row.cells[6].innerText + "<br>" +
            "<strong>📅 Day/Date:</strong> " + row.cells[8].innerText + "<br>" +
            "<strong>🕐 Time:</strong> " + (row.dataset.start || "-") + " - " + (row.dataset.end || "-");

        var reasonInput = document.getElementById("cancelReasonInput");
        if (reasonInput) reasonInput.value = "";

        cancelModal.style.display = "flex";
    };

    // Close cancel modal buttons
    if (cancelModalClose)    cancelModalClose.onclick    = function () { cancelModal.style.display = "none"; };
    if (cancelModalCloseBtn) cancelModalCloseBtn.onclick = function () { cancelModal.style.display = "none"; };

    // Confirm cancel
    confirmCancelBtn.onclick = function () {
        if (!cancelTargetId) return;

        var reasonInput = document.getElementById("cancelReasonInput");
        var reason = reasonInput ? reasonInput.value.trim() : "";
        var formData = new FormData();
        if (reason) formData.append("reason", reason);

        fetch("/cancel_timetable/" + cancelTargetId, { method: "POST", body: formData })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.success) {
                    showFlashToast("Lecture cancelled successfully!", "success");
                    setTimeout(function () { location.reload(); }, 1000);
                } else {
                    showFlashToast("Cancel failed: " + (data.message || ""), "error");
                }
            })
            .catch(function () {
                showFlashToast("Server error!", "error");
            });
    };

}); // end DOMContentLoaded

// Student Timetable Filter Logic
document.addEventListener("DOMContentLoaded", function () {
    var dateInput = document.getElementById("filterDate");
    if (dateInput) {
        dateInput.addEventListener("change", function () {
            var selectedDate = dateInput.value;
            window.location.href = "/student/timetable?date=" + selectedDate;
        });
    }
});