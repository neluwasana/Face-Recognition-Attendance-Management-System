document.addEventListener("DOMContentLoaded", function () {
    // DOM Elements
    const modal = document.getElementById("studentModal");
    const openBtn = document.getElementById("openForm");
    const closeBtn = document.getElementById("closeBtn");
    const cancelBtn = document.getElementById("cancelBtn");
    const studentForm = document.getElementById("studentForm");
    const saveBtn = document.getElementById("saveBtn");
    const updateBtn = document.getElementById("updateBtn");
    const formTitle = document.getElementById("formTitle");

    // Camera Elements
    const video = document.getElementById("video");
    const canvas = document.getElementById("canvas");
    const captureBtn = document.getElementById("captureBtn");
    const bracketOverlay = document.getElementById("bracketOverlay");
    const previewContainer = document.getElementById("previewContainer");
    const facePreview = document.getElementById("facePreview");
    const cameraPlaceholder = document.getElementById("cameraPlaceholder");

    // Upload Elements
    const imageUploadInput = document.getElementById("imageUploadInput");
    const triggerUploadBtn = document.getElementById("triggerUploadBtn");
    const capturedLabel = document.getElementById("capturedLabel");

    // Training elements
    const trainModelBtn = document.getElementById("trainModelBtn");
    const loaderOverlay = document.getElementById("loaderOverlay");

    let stream = null;
    let capturedImage = null;
    let selectedRow = null;
    let isSaving = false;

    function getSelectedIds() {
        const checked = document.querySelectorAll(".student-select-check:checked");
        return Array.from(checked).map(cb => cb.value);
    }

    function getSelectedRows() {
        return document.querySelectorAll(".data-row.active");
    }

    
    // Reset Form and Camera/Upload State
    function resetFormState() {
        stopCamera();
        studentForm.reset();
        isSaving = false;
        isUploading = false;
        document.getElementById("db_id").value = "";

        capturedImage = null;
        previewContainer.style.display = "none";
        facePreview.src = "";
        facePreview.style.display = "block";
        video.style.display = "none";
        bracketOverlay.style.display = "none";
        cameraPlaceholder.style.display = "flex";
        cameraPlaceholder.innerHTML = `
            <div class="placeholder-icon">&#128248;</div>
            <p>Camera is closed. Click "Start Capture" below.</p>`;
        captureBtn.innerHTML = "📷 Start Capture";
        captureBtn.className = "btn btn-secondary captureFaceBtn";

        // Reset Image State
        if (imageUploadInput) imageUploadInput.value = "";
        if (capturedLabel) capturedLabel.textContent = "CAPTURED";

        document.getElementById("username").value = "";

        const pwdInput = document.getElementById("password");
        if (pwdInput) {
            pwdInput.value = "";
            pwdInput.type = "password";
        }
        const pwdToggleBtn = document.getElementById("toggleStudentPasswordBtn");
        if (pwdToggleBtn) {
            pwdToggleBtn.classList.add("slashed");
        }

        document.getElementById("qrCodeContainer").style.display = "none";
        document.getElementById("qrCodeImg").src = "";
        const qrValEl = document.getElementById("qrStudentIdVal");
        if (qrValEl) qrValEl.textContent = "-";

        // Reset buttons to Add Student
        formTitle.textContent = "➕ Add New Student";
        saveBtn.style.display = "inline-flex";
        updateBtn.style.display = "none";
    }

    // Open Modal
    openBtn.onclick = function () {
        resetFormState();
        modal.style.display = "flex";
    };

    // Close Modal (X click)
    closeBtn.onclick = function () {
        resetFormState();
        modal.style.display = "none";
    };

    // Close Modal (Cancel click)
    cancelBtn.onclick = function () {
        resetFormState();
        modal.style.display = "none";
    };


    const sidInput = document.getElementById("sid");
    const qrCodeContainer = document.getElementById("qrCodeContainer");
    const qrCodeImg = document.getElementById("qrCodeImg");

    function updateQRCode() {
        const studentId = sidInput.value.trim();
        if (studentId) {
            qrCodeImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=260x260&data=${encodeURIComponent(studentId)}`;
            qrCodeContainer.style.display = "flex";
            const qrValEl = document.getElementById("qrStudentIdVal");
            if (qrValEl) qrValEl.textContent = studentId;
        } else {
            qrCodeContainer.style.display = "none";
            qrCodeImg.src = "";
            const qrValEl = document.getElementById("qrStudentIdVal");
            if (qrValEl) qrValEl.textContent = "-";
        }
    }

    sidInput.addEventListener("input", updateQRCode);



    // Close Modal on clicking outside card
    window.onclick = function (event) {
        if (event.target === modal) {
            resetFormState();
            modal.style.display = "none";
        }
    };


    // CAMERA / FACE CAPTURE CONTROLLER

    async function startCamera() {
        cameraPlaceholder.style.display = "none";
        previewContainer.style.display = "none";
        video.style.display = "block";
        bracketOverlay.style.display = "block";

        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: { width: 300, height: 300, facingMode: "user" }
            });
            video.srcObject = stream;
            video.play();
            captureBtn.innerHTML = "📸 Take Snapshot";
            captureBtn.className = "btn btn-success captureFaceBtn btn-glow";
        } catch (err) {
            console.error("Camera startup error:", err);
            showFlashToast("Camera access denied or unavailable: " + err.message, "error");
            resetFormState();
        }
    }

    function stopCamera() {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            stream = null;
        }
        if (video) video.srcObject = null;
    }


    if (triggerUploadBtn) {
        triggerUploadBtn.onclick = function () {
            isUploading = false;  // reset guard before opening dialog
            imageUploadInput.click();
        };
    }

    let isUploading = false;

    if (imageUploadInput) {
        imageUploadInput.onchange = function (e) {
            // Guard: prevent processing the same file change event twice
            if (isUploading) {
                e.preventDefault();
                return;
            }
            isUploading = true;

            const file = e.target.files[0];
            if (!file) {
                isUploading = false;
                return;
            }

            if (file.size > 5 * 1024 * 1024) {
                showFlashToast("File size exceeds 5MB limit.", "error");
                imageUploadInput.value = "";
                isUploading = false;
                return;
            }

            const validTypes = ["image/jpeg", "image/png", "image/jpg"];
            if (!validTypes.includes(file.type)) {
                showFlashToast("Invalid file type. Please upload a JPG or PNG image.", "error");
                imageUploadInput.value = "";
                isUploading = false;
                return;
            }

            showFlashToast("Detecting face in uploaded image...", "success");

            const reader = new FileReader();
            reader.onload = function (event) {
                const base64Data = event.target.result;

                fetch("/api/detect-face", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ image: base64Data })
                })
                .then(res => res.json())
                .then(data => {
                    isUploading = false;
                    if (data.success) {
                        capturedImage = base64Data;
                        facePreview.src = base64Data;
                        facePreview.style.display = "block";

                        // Stop camera if running
                        stopCamera();
                        video.style.display = "none";
                        bracketOverlay.style.display = "none";

                        cameraPlaceholder.style.display = "none";
                        previewContainer.style.display = "block";

                        if (capturedLabel) capturedLabel.textContent = "UPLOADED";
                        captureBtn.innerHTML = "🔄 Retake Face";
                        captureBtn.className = "btn btn-warning captureFaceBtn";

                        showFlashToast(data.message, "success");
                    } else {
                        showFlashToast(data.message, "error");
                        imageUploadInput.value = "";
                        facePreview.src = "";
                        previewContainer.style.display = "none";
                        cameraPlaceholder.style.display = "flex";
                    }
                })
                .catch(err => {
                    isUploading = false;
                    console.error("Face detection error:", err);
                    showFlashToast("Face detection failed. Please try again.", "error");
                    imageUploadInput.value = "";
                });
            };
            reader.readAsDataURL(file);
        };
    }

    captureBtn.onclick = function () {
        // Step 1: Start camera if not running
        if (!stream) {
            startCamera();
            return;
        }

        // Step 2: Take snapshot
        if (!video.videoWidth) {
            showFlashToast("Camera is still warming up...", "error");
            return;
        }

        const ctx = canvas.getContext("2d");
        canvas.width = 300;
        canvas.height = 300;
        ctx.drawImage(video, 0, 0, 300, 300);

        const snapshotData = canvas.toDataURL("image/jpeg", 0.85);

        // Step 3: Validate face is present before accepting
        captureBtn.disabled = true;
        captureBtn.innerHTML = "🔍 Detecting...";
        captureBtn.className = "btn btn-secondary captureFaceBtn";

        fetch("/api/detect-face", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ image: snapshotData })
        })
        .then(res => res.json())
        .then(data => {
            captureBtn.disabled = false;
            if (data.success) {
                // Face confirmed — accept capture
                capturedImage = snapshotData;
                facePreview.src = capturedImage;
                facePreview.style.display = "block";

                stopCamera();
                video.style.display = "none";
                bracketOverlay.style.display = "none";
                cameraPlaceholder.style.display = "none";
                previewContainer.style.display = "block";

                captureBtn.innerHTML = "🔄 Retake Face";
                captureBtn.className = "btn btn-warning captureFaceBtn";

                // Clear upload input
                if (imageUploadInput) imageUploadInput.value = "";
                if (capturedLabel) capturedLabel.textContent = "CAPTURED";

                showFlashToast(data.message, "success");
            } else {
                // Face not valid — reject and stay on camera
                captureBtn.innerHTML = "📸 Take Snapshot";
                captureBtn.className = "btn btn-success captureFaceBtn btn-glow";
                showFlashToast(data.message, "error");
            }
        })
        .catch(err => {
            captureBtn.disabled = false;
            captureBtn.innerHTML = "📸 Take Snapshot";
            captureBtn.className = "btn btn-success captureFaceBtn btn-glow";
            console.error("Face detect error:", err);
            showFlashToast("Face detection failed. Please try again.", "error");
        });
    };

    // SAVE STUDENT RECORD

    saveBtn.onclick = function () {
        const studentId       = document.getElementById("sid").value.trim();
        const fullName        = document.getElementById("name").value.trim();
        const department      = document.getElementById("department").value;
        const year            = document.getElementById("year").value;
        const semester        = document.getElementById("semester").value;
        const email           = document.getElementById("email").value.trim();
        const phone           = document.getElementById("phone").value.trim();
        const registered_Date = document.getElementById("registered_date").value;
        const username        = document.getElementById("username").value.trim();
        const password        = document.getElementById("password").value.trim();
        const dob             = document.getElementById("dob").value;
        const nic             = document.getElementById("nic").value.trim();
        const gender          = document.getElementById("gender").value;
        const religion        = document.getElementById("religion").value;
        const address         = document.getElementById("address").value.trim();
        const status          = document.querySelector('input[name="status"]:checked')?.value || "Active";
        const part_time_full_time = document.getElementById("part_time_full_time").value;

        // Required field validation
        if (!studentId || !fullName || !department || !year || !semester || !registered_Date || !username || !password || !part_time_full_time) {
            showFlashToast("Please fill in all required fields marked with *", "error");
            return;
        }

        // NIC validation: 9 digits + V/X  OR  12 digits
        const nicRegex = /^(\d{9}[VvXx]|\d{12})$/;
       if (nic !== "" && !nicRegex.test(nic)) {
            showFlashToast("Please enter a valid NIC number (e.g. 123456789V or 123456789012)", "error");
            return;
        }

        // Email validation (optional field)
        if (email !== "" && !email.toLowerCase().endsWith("@gmail.com")) {
            showFlashToast("Email address must end with @gmail.com", "error");
            return;
        }

        // Phone validation: exactly 10 digits (optional field)
        if (phone !== "" && !/^\d{10}$/.test(phone)) {
            showFlashToast("Phone number must be exactly 10 digits", "error");
            return;
        }



        if (!capturedImage) {
            showFlashToast("Please capture or upload a student photo.", "error");
            return;
        }

        const formData = new FormData();
        formData.append("student_id",     studentId);
        formData.append("full_name",       fullName);
        formData.append("department",      department);
        formData.append("year",            year);
        formData.append("semester",        semester);
        formData.append("email",           email);
        formData.append("phone",           phone);
        formData.append("registered_date", registered_Date);
        formData.append("image",           capturedImage);
        formData.append("username",        username);
        formData.append("password",        password);
        formData.append("dob",             dob);
        formData.append("nic",             nic);
        formData.append("gender",          gender);
        formData.append("religion",        religion);
        formData.append("address",         address);
        formData.append("status",          status);
        formData.append("part_time_full_time", part_time_full_time);

        if (isSaving) return;
        isSaving = true;
        saveBtn.disabled    = true;
        saveBtn.textContent = "Saving...";

        fetch("/add-student", { method: "POST", body: formData })
        .then(function (res)  {
            if (res.status === 413) {
                throw new Error("IMAGE_TOO_LARGE");
            }
            return res.json();
        })
        .then(function (data) {
            if (data.success) {
                showFlashToast(data.message, "success");
                setTimeout(function () { window.location.reload(); }, 1200);
            } else {
                showFlashToast(data.message, "error");
                saveBtn.disabled    = false;
                saveBtn.textContent = "Add Student";
                isSaving = false;
            }
        })
        .catch(function (err) {
            console.error("Save error:", err);
            if (err.message === "IMAGE_TOO_LARGE") {
                showFlashToast("🚨 Image too large! Please use the camera capture or upload a smaller photo (under 1 MB).", "error");
            } else {
                showFlashToast("Registration failed. Please try again.", "error");
            }
            saveBtn.disabled    = false;
            saveBtn.textContent = "Add Student";
            isSaving = false;
        });
    };



    // QR Code download
    const downloadBtn = document.getElementById("downloadQRBtn");
    if (downloadBtn) {
        downloadBtn.addEventListener("click", function () {
            if (!qrCodeImg.src || qrCodeImg.src === window.location.href) {
                showFlashToast("No QR code available to download!", "error");
                return;
            }
            
            downloadBtn.disabled = true;
            downloadBtn.textContent = "Downloading...";
            
            fetch(qrCodeImg.src)
                .then(response => {
                    if (!response.ok) throw new Error("Network response was not ok");
                    return response.blob();
                })
                .then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.style.display = "none";
                    a.href = url;
                    a.download = (sidInput.value.trim().replace(/[\/\\?%*:|"<>]/g, "_") || "student") + "_QR.png";
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                    
                    downloadBtn.disabled = false;
                    downloadBtn.textContent = "Download QR";
                })
                .catch(err => {
                    console.error("Error downloading QR:", err);
                    showFlashToast("Failed to download QR code.", "error");
                    downloadBtn.disabled = false;
                    downloadBtn.textContent = "Download QR";
                });
        });
    }

    

    // TABLE ROW SELECTOR

    const tableBody = document.querySelector("#studentTable tbody");
    tableBody.onclick = function (e) {
        const row = e.target.closest(".data-row");
        if (!row) return;

        const checkbox = row.querySelector(".student-select-check");
        if (e.target !== checkbox) {
            checkbox.checked = !checkbox.checked;
        }

        if (checkbox.checked) {
            row.classList.add("active");
            selectedRow = row;
        } else {
            row.classList.remove("active");
            const stillSelected = document.querySelectorAll(".data-row.active");
            selectedRow = stillSelected.length === 1 ? stillSelected[0] : null;
        }

        const allChecks = document.querySelectorAll(".student-select-check");
        const allChecked = document.querySelectorAll(".student-select-check:checked");
        const selectAll = document.getElementById("selectAllCheck");
        if (selectAll) {
            selectAll.checked = allChecks.length > 0 && allChecks.length === allChecked.length;
            selectAll.indeterminate = allChecked.length > 0 && allChecked.length < allChecks.length;
        }
    };

    const selectAllCheck = document.getElementById("selectAllCheck");
    if (selectAllCheck) {
        selectAllCheck.onclick = function () {
            const rows = document.querySelectorAll("#studentTable tbody .data-row");
            rows.forEach(row => {
                const checkbox = row.querySelector(".student-select-check");
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

  
    // EDIT STUDENT RECORD
    
    document.getElementById("editSelectedBtn").onclick = function () {
            

        const selected = document.querySelectorAll(".data-row.active");
        if (selected.length === 0) {
            showFlashToast("Please select a student row from the table first!", "error");
            return;
        }
        if (selected.length > 1) {
            showFlashToast("Please select only ONE student to edit!", "error");
            return;
        }

        const id = selected[0].getAttribute("data-id");

        // Fetch student details with a timestamp to prevent browser caching
        fetch(`/edit/${id}?_=${new Date().getTime()}`)
            .then(res => res.json())
            .then(student => {
                resetFormState();

                document.getElementById("db_id").value = student.id;
                document.getElementById("sid").value = student.student_id;
                document.getElementById("name").value = student.full_name;
                document.getElementById("email").value = student.email || "";
                document.getElementById("phone").value = student.phone || "";
                document.getElementById("registered_date").value = student.registered_date || "";
               
                document.getElementById("username").value = student.username || "";
                document.getElementById("password").value = "";
                if (student.student_id) {
                    qrCodeImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=260x260&data=${encodeURIComponent(student.student_id)}`;
                    qrCodeContainer.style.display = "flex";
                    const qrValEl = document.getElementById("qrStudentIdVal");
                    if (qrValEl) qrValEl.textContent = student.student_id;
                }

                // Set select and extra fields after a tiny delay so resetFormState DOM settles
                setTimeout(() => {
                    document.getElementById("department").value = student.department || "";
                    document.getElementById("year").value = student.year || "";
                    document.getElementById("semester").value = student.semester || "";

                    
                
                    document.getElementById("dob").value = student.dob ? student.dob.split("T")[0] : "";
                
                    document.getElementById("nic").value = student.nic || "";
                
                    document.getElementById("gender").value = student.gender || "";
                
                    document.getElementById("religion").value = student.religion || "";
                
                    document.getElementById("address").value = student.address || "";

                    const ptftEl = document.getElementById("part_time_full_time");
                    if (ptftEl) ptftEl.value = student.part_time_full_time || "";
                
                    document.querySelector(
                        `input[name="status"][value="${student.status || 'Active'}"]`
                    ).checked = true;
                
                }, 10);
                formTitle.textContent = "✏️ Edit Student Details";
                saveBtn.style.display = "none";
                updateBtn.style.display = "inline-flex";

                // Reset upload panel state for edit
                if (imageUploadInput) imageUploadInput.value = "";

                // Show existing face image in preview if available
                if (student.face_base64) {
                    facePreview.src = student.face_base64;
                    facePreview.style.display = "block";
                    previewContainer.style.display = "block";
                    cameraPlaceholder.style.display = "none";
                    bracketOverlay.style.display = "none";
                    video.style.display = "none";
                    if (capturedLabel) capturedLabel.textContent = "CURRENT PHOTO";
                    captureBtn.innerHTML = "🔄 Capture New Face";
                    captureBtn.className = "btn btn-warning captureFaceBtn";
                    capturedImage = null; // null = keep existing face; new capture/upload will update this
                } else {
                    previewContainer.style.display = "none";
                    bracketOverlay.style.display = "none";
                    video.style.display = "none";
                    cameraPlaceholder.style.display = "flex";
                    cameraPlaceholder.innerHTML = `
                        <div class="placeholder-icon">📸</div>
                        <p>No face on file. Click "Capture New Face" below.</p>`;
                    captureBtn.innerHTML = "📷 Capture New Face";
                    captureBtn.className = "btn btn-secondary captureFaceBtn";
                    capturedImage = null;
                }

                modal.style.display = "flex";
            })
            .catch(err => {
                console.error("Edit fetch error:", err);
                showFlashToast("Error retrieving student details.", "error");
            });
    };

    updateBtn.onclick = function () {
        const id             = document.getElementById("db_id").value;
        const studentId      = document.getElementById("sid").value.trim();
        const fullName       = document.getElementById("name").value.trim();
        const department     = document.getElementById("department").value;
        const year           = document.getElementById("year").value;
        const semester       = document.getElementById("semester").value;
        const email          = document.getElementById("email").value.trim();
        const phone          = document.getElementById("phone").value.trim();
        const registered_Date = document.getElementById("registered_date").value;
        const username       = document.getElementById("username").value.trim();
        const password       = document.getElementById("password").value.trim();
        const dob            = document.getElementById("dob").value;
        const nic            = document.getElementById("nic").value.trim();
        const gender         = document.getElementById("gender").value;
        const religion       = document.getElementById("religion").value;
        const address        = document.getElementById("address").value.trim();
        const status         = document.querySelector('input[name="status"]:checked')?.value || "Active";
        const part_time_full_time = document.getElementById("part_time_full_time").value;

        // Required field validation (core fields only for update)
        if (!studentId || !fullName || !department || !year) {
            showFlashToast("Please fill in all required fields marked with *", "error");
            return;
        }

        // NIC validation (only if provided)
        const nicRegex = /^(\d{9}[VvXx]|\d{12})$/;
        if (nic !== "" && !nicRegex.test(nic)) {
            showFlashToast("Please enter a valid NIC number (e.g. 123456789V or 123456789012)", "error");
            return;
        }

        // Email validation
        if (email !== "" && !email.toLowerCase().endsWith("@gmail.com")) {
            showFlashToast("Email address must end with @gmail.com", "error");
            return;
        }

        // Phone validation
        if (phone !== "" && !/^\d{10}$/.test(phone)) {
            showFlashToast("Phone number must be exactly 10 digits", "error");
            return;
        }



        const formData = new FormData();
        formData.append("id",              id);
        formData.append("student_id",      studentId);
        formData.append("full_name",        fullName);
        formData.append("department",       department);
        formData.append("year",             year);
        formData.append("semester",         semester);
        formData.append("email",            email);
        formData.append("phone",            phone);
        formData.append("registered_date",  registered_Date);
        formData.append("username",         username);
        formData.append("password",         password);
        formData.append("dob",              dob);
        formData.append("nic",              nic);
        formData.append("gender",           gender);
        formData.append("religion",         religion);
        formData.append("address",          address);
        formData.append("status",           status);
        formData.append("part_time_full_time", part_time_full_time);

        if (capturedImage && capturedImage.startsWith("data:image")) {
            formData.append("image", capturedImage);
        }

        updateBtn.disabled    = true;
        updateBtn.textContent = "Updating...";

        fetch("/update-student", { method: "POST", body: formData })
        .then(res  => {
            if (res.status === 413) {
                throw new Error("IMAGE_TOO_LARGE");
            }
            return res.json();
        })
        .then(data => {
            if (data.success) {
                showFlashToast(data.message, "success");
                setTimeout(() => window.location.reload(), 1200);
            } else {
                showFlashToast(data.message, "error");
                updateBtn.disabled    = false;
                updateBtn.textContent = "Update Student";
            }
        })
        .catch(err => {
            console.error("Update error:", err);
            if (err.message === "IMAGE_TOO_LARGE") {
                showFlashToast("🚨 Image too large! Please use the camera capture or upload a smaller photo (under 1 MB).", "error");
            } else {
                showFlashToast("Error updating student record.", "error");
            }
            updateBtn.disabled    = false;
            updateBtn.textContent = "Update Student";
        });
    };


    // DELETE STUDENT RECORD

    document.getElementById("deleteSelectedBtn").onclick = function () {

    const ids = getSelectedIds();

    if (ids.length === 0) {
        showFlashToast("Please select at least one student to delete!", "error");
        return;
    }

    const message = ids.length === 1 ?
        "Are you sure you want to delete the selected student?" :
        `Are you sure you want to delete the ${ids.length} selected students?`;

    if (!confirm(message)) {
        return;
    }

    fetch(`/delete-student/${ids.join(",")}`, {
        method: "POST"
    })
    .then(res => res.json())
    .then(data => {

        if (data.success) {

            showFlashToast("Student(s) deleted successfully!", "success");

            setTimeout(() => {
                window.location.reload();
            }, 1000);

        } else {

            showFlashToast(
                data.message || "Delete failed.",
                "error"
            );

        }

    })
    .catch(err => {

        console.error("Delete error:", err);

        showFlashToast(
            "Error deleting student(s).",
            "error"
        );

    });

};
    //  FILTER / SEARCH
    
    const searchInput = document.getElementById("searchInput");
    const courseFilter = document.getElementById("courseFilter");

    function applyFilters() {
        const query = searchInput.value.toLowerCase().trim();
        const selectedCourse = courseFilter ? courseFilter.value.toLowerCase().trim() : "";
        const rows = document.querySelectorAll("#studentTable tbody .data-row");

        let visibleCount = 0;

        rows.forEach(row => {
            const studentId = row.querySelector(".col-sid").textContent.toLowerCase();
            const fullName = row.querySelector(".col-name").textContent.toLowerCase();
            const dept = row.querySelector(".col-dept").textContent.toLowerCase().trim();

            const matchesSearch = studentId.includes(query) || fullName.includes(query) || dept.includes(query);
            const matchesCourse = !selectedCourse || dept === selectedCourse;

            if (matchesSearch && matchesCourse) {
                row.style.display = "";
                visibleCount++;
            } else {
                row.style.display = "none";
            }
        });

        // Update count 
        const countBadge = document.getElementById("totalStudentsCount");
        if (countBadge) {
            countBadge.textContent = visibleCount;
        }
    }

    searchInput.oninput = applyFilters;
    if (courseFilter) {
        courseFilter.onchange = applyFilters;
    }

    // Refresh Reset Button
    document.getElementById("refreshBtn").onclick = function () {
        searchInput.value = "";
        if (courseFilter) {
            courseFilter.value = "";
        }
        applyFilters();
    };

    // MODEL TRAINING TRIGGERS 
    
    trainModelBtn.onclick = function () {
        loaderOverlay.style.display = "flex";

        fetch("/api/train_model", {
            method: "POST"
        })
        .then(res => res.json())
        .then(data => {
            loaderOverlay.style.display = "none";
            if (data.success) {
                showFlashToast(data.message, "success");
            } else {
                showFlashToast("Training failed: " + data.message, "error");
            }
        })
        .catch(err => {
            loaderOverlay.style.display = "none";
            console.error("Training error:", err);
            showFlashToast("Network or server error during training.", "error");
        });
    };

    
    
    // DYNAMIC FLOATING FLASH TOAST HELPER
    
    function showFlashToast(message, type) {
        
        const existingToasts = document.querySelectorAll(".floating-toast");
        existingToasts.forEach(toast => toast.remove());

        const toast = document.createElement("div");
        toast.className = `flash ${type} floating-toast`;
        
        const icon = type === "success" ? "✅" : "⚠️";
        toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
        
        document.body.appendChild(toast);

        // Auto remove toast after 3 seconds
        setTimeout(() => {
            toast.style.animation = "slideOut 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards";
            setTimeout(() => {
                toast.remove();
            }, 300);
        }, 3500);
    }


    // PASSWORD VISIBILITY TOGGLE
    const toggleStudentPasswordBtn = document.getElementById("toggleStudentPasswordBtn");
    if (toggleStudentPasswordBtn) {
        const passwordInput = document.getElementById("password");

        toggleStudentPasswordBtn.addEventListener("click", function () {
            if (passwordInput.type === "password") {
                passwordInput.type = "text";
                toggleStudentPasswordBtn.classList.remove("slashed");
            } else {
                passwordInput.type = "password";
                toggleStudentPasswordBtn.classList.add("slashed");
            }
        });
    }
});