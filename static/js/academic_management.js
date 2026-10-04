document.addEventListener("DOMContentLoaded", function () {

    //  TAB SWITCHING

    var tabButtons  = document.querySelectorAll(".tab-btn");
    var tabContents = document.querySelectorAll(".tab-content");

    tabButtons.forEach(function (btn) {
        btn.addEventListener("click", function () {
            tabButtons.forEach(function (b) { b.classList.remove("active"); });
            tabContents.forEach(function (c) { c.classList.remove("active-content"); });
            this.classList.add("active");
            document.getElementById(this.getAttribute("data-tab")).classList.add("active-content");
        });
    });

    //  MODAL HELPER

    function setupModal(modalId, formId, closeBtnId, cancelBtnId) {
        var modal     = document.getElementById(modalId);
        var form      = document.getElementById(formId);
        var closeBtn  = document.getElementById(closeBtnId);
        var cancelBtn = document.getElementById(cancelBtnId);

        function close() {
            modal.style.display = "none";
            form.reset();
            var hidId = form.querySelector('input[type="hidden"]');
            if (hidId) hidId.value = "";
        }

        closeBtn.addEventListener("click", close);
        cancelBtn.addEventListener("click", close);
        window.addEventListener("click", function (e) {
            if (e.target === modal) close();
        });

        return {
            show: function () { modal.style.display = "flex"; },
            hide: close
        };
    }

    var courseModal  = setupModal("courseModal",  "courseForm",  "courseCloseBtn",  "courseCancelBtn");
    var subjectModal = setupModal("subjectModal", "subjectForm", "subjectCloseBtn", "subjectCancelBtn");

    //  COURSE CRUD & EVENTS 

    document.getElementById("addCourseBtn").addEventListener("click", function () {
        document.getElementById("courseFormTitle").textContent = "➕ Add New Course";
        document.getElementById("course_id").value = "";
        courseModal.show();
    });

    function openCourseEdit(course) {
        document.getElementById("courseFormTitle").textContent = "✏️ Edit Course";
        document.getElementById("course_id").value  = course.id;
        document.getElementById("course_code").value = course.course_code;
        document.getElementById("course_name").value = course.course_name;
        courseModal.show();
    }

    document.getElementById("courseForm").addEventListener("submit", function (e) {
        e.preventDefault();
        var cid  = document.getElementById("course_id").value;
        var code = document.getElementById("course_code").value.trim();
        var name = document.getElementById("course_name").value.trim();

        fetch(cid ? "/api/courses/edit" : "/api/courses/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: cid, course_code: code, course_name: name })
        })
        .then(function (res) { return res.json(); })
        .then(function (r) {
            if (r.success) { 
                showToast(r.message, "success"); 
                courseModal.hide(); 
                setTimeout(function () { window.location.reload(); }, 1200);
            } else {
                showToast("Error: " + r.message, "error");
            }
        })
        .catch(function () { showToast("Server error!", "error"); });
    });

    function deleteCourse(id) {
        if (!confirm("Delete this course? All its subjects will also be removed!")) return;
        fetch("/api/courses/delete/" + id, { method: "POST" })
            .then(function (res) { return res.json(); })
            .then(function (r) {
                if (r.success) { 
                    showToast(r.message, "success"); 
                    setTimeout(function () { window.location.reload(); }, 1200);
                } else {
                    showToast("Error: " + r.message, "error");
                }
            })
            .catch(function () { showToast("Server error!", "error"); });
    }

    // Event delegation for Courses Table
    var coursesTableBody = document.getElementById("coursesTableBody");
    if (coursesTableBody) {
        coursesTableBody.addEventListener("click", function (e) {
            var tr = e.target.closest("tr.course-row");
            if (!tr) return;
            var id = tr.getAttribute("data-id");
            if (e.target.closest(".edit")) {
                openCourseEdit({
                    id: id,
                    course_code: tr.getAttribute("data-code"),
                    course_name: tr.getAttribute("data-name")
                });
            } else if (e.target.closest(".delete")) {
                deleteCourse(id);
            }
        });
    }

    //  SUBJECT CRUD & EVENTS 

    document.getElementById("addSubjectBtn").addEventListener("click", function () {
        document.getElementById("subjectFormTitle").textContent = "➕ Add New Subject";
        document.getElementById("subject_id").value = "";
        subjectModal.show();
    });

    function openSubjectEdit(subject) {
        document.getElementById("subjectFormTitle").textContent = "✏️ Edit Subject";
        document.getElementById("subject_id").value       = subject.id;
        document.getElementById("subject_course").value   = subject.course_id;
        document.getElementById("subject_year").value     = subject.year;
        document.getElementById("subject_semester").value = subject.semester;
        document.getElementById("subject_code").value     = subject.subject_code;
        document.getElementById("subject_name").value     = subject.subject_name;
        document.getElementById("subject_lecturer").value = subject.lecturer_id;
        subjectModal.show();
    }

    document.getElementById("subjectForm").addEventListener("submit", function (e) {
        e.preventDefault();
        var sid        = document.getElementById("subject_id").value;
        var courseId   = document.getElementById("subject_course").value;
        var year       = document.getElementById("subject_year").value;
        var semester   = document.getElementById("subject_semester").value;
        var code       = document.getElementById("subject_code").value.trim();
        var name       = document.getElementById("subject_name").value.trim();
        var lecturerId = document.getElementById("subject_lecturer").value;

        if (!courseId || !year || !semester || !code || !name || !lecturerId) {
            showToast("Please fill all required fields!", "error");
            return;
        }

        fetch(sid ? "/api/subjects/edit" : "/api/subjects/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                id: sid,
                course_id: courseId,
                year: year,
                semester: semester,
                subject_code: code,
                subject_name: name,
                lecturer_id: lecturerId
            })
        })
        .then(function (res) { return res.json(); })
        .then(function (r) {
            if (r.success) { 
                showToast(r.message, "success"); 
                subjectModal.hide(); 
                setTimeout(function () { window.location.reload(); }, 1200);
            } else {
                showToast("Error: " + r.message, "error");
            }
        })
        .catch(function () { showToast("Server error!", "error"); });
    });

    function deleteSubject(id) {
        if (!confirm("Are you sure you want to delete this subject?")) return;
        fetch("/api/subjects/delete/" + id, { method: "POST" })
            .then(function (res) { return res.json(); })
            .then(function (r) {
                if (r.success) { 
                    showToast(r.message, "success"); 
                    setTimeout(function () { window.location.reload(); }, 1200);
                } else {
                    showToast("Error: " + r.message, "error");
                }
            })
            .catch(function () { showToast("Server error!", "error"); });
    }

    // Event delegation for Subjects Table
    var subjectsTableBody = document.getElementById("subjectsTableBody");
    if (subjectsTableBody) {
        subjectsTableBody.addEventListener("click", function (e) {
            var tr = e.target.closest("tr.subject-row");
            if (!tr) return;
            var id = tr.getAttribute("data-id");
            if (e.target.closest(".edit")) {
                openSubjectEdit({
                    id: id,
                    course_id: tr.getAttribute("data-course-id"),
                    year: tr.getAttribute("data-year"),
                    semester: tr.getAttribute("data-semester"),
                    subject_code: tr.getAttribute("data-code"),
                    subject_name: tr.getAttribute("data-name"),
                    lecturer_id: tr.getAttribute("data-lecturer-id")
                });
            } else if (e.target.closest(".delete")) {
                deleteSubject(id);
            }
        });
    }

    //  LECTURER CRUD & EVENTS

    var lecturerModal     = document.getElementById("lecturerModal");
    var lecturerForm      = document.getElementById("lecturerForm");
    var lecturerCloseBtn  = document.getElementById("lecturerCloseBtn");
    var lecturerCancelBtn = document.getElementById("lecturerCancelBtn");

    function closeLecturerModal() {
        lecturerModal.style.display = "none";
        lecturerForm.reset();
        document.getElementById("lecturer_id").value = "";
        document.getElementById("lecturer_password").type = "password";
        var toggleBtn = document.getElementById("toggleLecturerPasswordBtn");
        if (toggleBtn) toggleBtn.classList.add("slashed");
    }

    lecturerCloseBtn.addEventListener("click", closeLecturerModal);
    lecturerCancelBtn.addEventListener("click", closeLecturerModal);
    window.addEventListener("click", function (e) {
        if (e.target === lecturerModal) closeLecturerModal();
    });

    document.getElementById("addLecturerBtn").addEventListener("click", function () {
        document.getElementById("lecturerFormTitle").textContent = "➕ Add New Lecturer";
        document.getElementById("lecturer_id").value = "";
        document.getElementById("lecturer_password").required = true;
        document.getElementById("lecturer_password").placeholder = "Enter password";
        var asterisk = document.getElementById("lecturer_pwd_asterisk");
        if (asterisk) asterisk.style.display = "inline";
        lecturerModal.style.display = "flex";
    });

    function openLecturerEdit(lecturer) {
        document.getElementById("lecturerFormTitle").textContent = "✏️ Edit Lecturer";
        document.getElementById("lecturer_id").value             = lecturer.id;
        document.getElementById("lecturer_name").value           = lecturer.lecturer_name || "";
        document.getElementById("lecturer_subject").value        = lecturer.subjects || "";
        document.getElementById("lecturer_qualification").value  = lecturer.qualification || "";
        document.getElementById("lecturer_nic").value            = lecturer.nic || "";
        document.getElementById("lecturer_tel").value            = lecturer.tel_no || "";
        document.getElementById("lecturer_email").value          = lecturer.email || "";
        document.getElementById("lecturer_dob").value            = lecturer.dob || "";
        document.getElementById("lecturer_username").value       = lecturer.username || "";
        document.getElementById("lecturer_password").value       = "";
        document.getElementById("lecturer_password").required    = false;
        document.getElementById("lecturer_password").placeholder = "Leave blank to keep current password";
        var asterisk = document.getElementById("lecturer_pwd_asterisk");
        if (asterisk) asterisk.style.display = "none";
        lecturerModal.style.display = "flex";
    }

    // Lecturer form submit
    lecturerForm.addEventListener("submit", function (e) {
        e.preventDefault();

        var lid           = document.getElementById("lecturer_id").value;
        var name          = document.getElementById("lecturer_name").value.trim();
        var subjects      = document.getElementById("lecturer_subject").value.trim();
        var qualification = document.getElementById("lecturer_qualification").value.trim();
        var nic           = document.getElementById("lecturer_nic").value.trim();
        var tel_no        = document.getElementById("lecturer_tel").value.trim();
        var email         = document.getElementById("lecturer_email").value.trim();
        var dob           = document.getElementById("lecturer_dob").value;
        var username      = document.getElementById("lecturer_username").value.trim();
        var password      = document.getElementById("lecturer_password").value;

        // Validation
        if (!name) { showToast("Please enter lecturer name!", "error"); return; }
        if (!nic) { showToast("Please enter NIC number!", "error"); return; }
        var nicRegex = /^(\d{9}[VvXx]|\d{12})$/;
        if (!nicRegex.test(nic)) {
            showToast("Please enter a valid NIC number (e.g. 123456789V or 123456789012)!", "error");
            return;
        }
        if (!username) { showToast("Please enter a username!", "error"); return; }
        if (!lid && !password) { showToast("Please enter a password for the new lecturer!", "error"); return; }

        if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            showToast("Please enter a valid email address (e.g., example@gmail.com)!", "error"); return;
        }

        if (tel_no && !/^\d{10}$/.test(tel_no)) {
            showToast("Telephone number must contain exactly 10 digits!", "error"); return;
        }

        var url = lid ? "/api/lecturers/edit" : "/api/lecturers/add";
        var payload = {
            id: lid, lecturer_name: name, subjects: subjects,
            qualification: qualification, nic: nic, tel_no: tel_no,
            email: email, dob: dob, username: username, password: password
        };

        fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        })
        .then(function (res) { return res.json(); })
        .then(function (result) {
            if (result.success) {
                showToast(result.message, "success");
                closeLecturerModal();
                setTimeout(function () { window.location.reload(); }, 1200);
            } else {
                showToast("Error: " + result.message, "error");
            }
        })
        .catch(function () { showToast("Server connection error!", "error"); });
    });

    function deleteLecturer(id) {
        if (!confirm("Are you sure you want to delete this lecturer?")) return;
        fetch("/api/lecturers/delete/" + id, { method: "POST" })
            .then(function (res) { return res.json(); })
            .then(function (result) {
                if (result.success) { 
                    showToast(result.message, "success"); 
                    setTimeout(function () { window.location.reload(); }, 1200);
                } else {
                    showToast("Error: " + result.message, "error");
                }
            })
            .catch(function () { showToast("Server connection error!", "error"); });
    }

    // Event delegation for Lecturers Table
    var lecturersTableBody = document.getElementById("lecturersTableBody");
    if (lecturersTableBody) {
        lecturersTableBody.addEventListener("click", function (e) {
            var tr = e.target.closest("tr.lecturer-row");
            if (!tr) return;
            var id = tr.getAttribute("data-id");
            if (e.target.closest(".edit")) {
                openLecturerEdit({
                    id: id,
                    lecturer_name: tr.getAttribute("data-name"),
                    subjects: tr.getAttribute("data-subjects"),
                    qualification: tr.getAttribute("data-qualification"),
                    nic: tr.getAttribute("data-nic"),
                    tel_no: tr.getAttribute("data-tel"),
                    email: tr.getAttribute("data-email"),
                    dob: tr.getAttribute("data-dob"),
                    username: tr.getAttribute("data-username")
                });
            } else if (e.target.closest(".delete")) {
                deleteLecturer(id);
            }
        });
    }

    //  LECTURER PASSWORD TOGGLE 

    var lecturerToggleBtn     = document.getElementById("toggleLecturerPasswordBtn");
    var lecturerPasswordInput = document.getElementById("lecturer_password");

    if (lecturerToggleBtn) {
        lecturerToggleBtn.addEventListener("click", function () {
            if (lecturerPasswordInput.type === "password") {
                lecturerPasswordInput.type = "text";
                lecturerToggleBtn.classList.remove("slashed");
            } else {
                lecturerPasswordInput.type = "password";
                lecturerToggleBtn.classList.add("slashed");
            }
        });
    }

    //  LIVE SEARCH FILTERING 

    document.getElementById("courseSearch").addEventListener("input", function () {
        var q = this.value.toLowerCase().trim();
        var rows = document.querySelectorAll("#coursesTableBody tr.course-row");
        rows.forEach(function (row) {
            var code = (row.getAttribute("data-code") || "").toLowerCase();
            var name = (row.getAttribute("data-name") || "").toLowerCase();
            if (code.includes(q) || name.includes(q)) {
                row.style.display = "";
            } else {
                row.style.display = "none";
            }
        });
    });

    document.getElementById("subjectSearch").addEventListener("input", function () {
        var q = this.value.toLowerCase().trim();
        var rows = document.querySelectorAll("#subjectsTableBody tr.subject-row");
        rows.forEach(function (row) {
            var code = (row.getAttribute("data-code") || "").toLowerCase();
            var name = (row.getAttribute("data-name") || "").toLowerCase();
            var course = (row.querySelector("td") ? row.querySelector("td").textContent : "").toLowerCase();
            var lecturer = (row.querySelector(".badge-lecturer") ? row.querySelector(".badge-lecturer").textContent : "").toLowerCase();
            if (code.includes(q) || name.includes(q) || course.includes(q) || lecturer.includes(q)) {
                row.style.display = "";
            } else {
                row.style.display = "none";
            }
        });
    });

    document.getElementById("lecturerSearch").addEventListener("input", function () {
        var q = this.value.toLowerCase().trim();
        var rows = document.querySelectorAll("#lecturersTableBody tr.lecturer-row");
        rows.forEach(function (row) {
            var name = (row.getAttribute("data-name") || "").toLowerCase();
            var subjects = (row.getAttribute("data-subjects") || "").toLowerCase();
            var nic = (row.getAttribute("data-nic") || "").toLowerCase();
            var email = (row.getAttribute("data-email") || "").toLowerCase();
            if (name.includes(q) || subjects.includes(q) || nic.includes(q) || email.includes(q)) {
                row.style.display = "";
            } else {
                row.style.display = "none";
            }
        });
    });

    //  TOAST helper 
    function showToast(message, type) {
        document.querySelectorAll(".floating-toast").forEach(function (t) { t.remove(); });
        var toast = document.createElement("div");
        toast.className = "flash " + type + " floating-toast";
        toast.innerHTML = "<span>" + (type === "success" ? "✅" : "⚠️") + "</span> <span>" + message + "</span>";
        document.body.appendChild(toast);
        setTimeout(function () {
            toast.style.animation = "slideOut 0.3s forwards";
            setTimeout(function () { toast.remove(); }, 400);
        }, 3500);
    }
});
