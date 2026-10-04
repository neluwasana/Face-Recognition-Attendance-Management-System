//LIVE CLOCK 
function updateTime() {
    var now = new Date();
    var liveTimeEl = document.getElementById("liveTime");
    if (liveTimeEl) liveTimeEl.innerText = now.toLocaleTimeString();
}
updateTime();
setInterval(updateTime, 1000);


document.addEventListener("DOMContentLoaded", function () {

    // Date display 
    const dateDisplay = document.getElementById("currentDateDisplay");
    if (dateDisplay) {
        const now = new Date();
        dateDisplay.textContent = now.toLocaleDateString('en-US', {
            weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
        });
    }

    // Core DOM refs 
    let stream       = null;
    const video         = document.getElementById("liveVideo");
    const resultBox     = document.getElementById("resultBox");
    const liveLog       = document.getElementById("liveLog");
    const cameraStandby = document.getElementById("cameraStandby");
    const scannerOverlay= document.getElementById("scannerOverlay");
    const startBtn      = document.getElementById("startCameraBtn");
    const stopBtn       = document.getElementById("stopCameraBtn");

    //Session selects
    const courseSelect      = document.getElementById("courseSelect");
    const yearSelect        = document.getElementById("yearSelect");
    const semesterSelect    = document.getElementById("semesterSelect");
    const studyModeSelect   = document.getElementById("studyModeSelect");
    const subjectSelect     = document.getElementById("subjectSelect");
    const lecturerSelect    = document.getElementById("lecturerSelect");
    const sessionDisplay    = document.getElementById("sessionDisplay");
    const sessionStatusBadge= document.getElementById("sessionStatusBadge");
    const hiddenLectureName = document.getElementById("lectureName");
    const hiddenLecturerName= document.getElementById("lecturerName");

    let currentSubjectsList = [];

    //  Unified scan state 
    let isScanning   = false;
    let scanTimeout  = null;
    // Per-session duplicate suppression (client-side cache, backend also enforces)
    let markedThisSession = new Set();
    // QR debounce: ignore same QR code for 4 s
    let lastQRCode   = '';
    let lastQRTime   = 0;
    // Face scanning cooldown after a recognition event
    let faceCoolUntil = 0;
    // Prevent overlapping face API requests
    let isProcessingFace = false;

    
    // BUTTON ENABLE / DISABLE HELPERS
   
    function disableCameraMarkButtons(disabled, reason) {

        if (startBtn) {
            startBtn.disabled = false;
            startBtn.title = "";
            startBtn.classList.remove("btn-disabled");
        }
        if (stopBtn) {
            stopBtn.disabled = false;
            stopBtn.classList.remove("btn-disabled");
        }
      
    }

   
    // DROPDOWN RESET HELPERS
 
    function resetFrom(level) {
        if (level <= 1) { yearSelect.value = ""; yearSelect.disabled = true; }
        if (level <= 2) { semesterSelect.value = ""; semesterSelect.disabled = true; }
        if (level <= 3) { studyModeSelect.value = ""; studyModeSelect.disabled = true; }
        if (level <= 4) {
            subjectSelect.innerHTML = '<option value="">-- Choose Subject --</option>';
            subjectSelect.disabled = true;
        }
        lecturerSelect.innerHTML = '<option value="">-- Choose Lecturer --</option>';
        lecturerSelect.disabled = true;
        sessionDisplay.value = "";
        hiddenLectureName.value  = "";
        hiddenLecturerName.value = "";
        if (sessionStatusBadge) {
            sessionStatusBadge.textContent = "Session Inactive";
            sessionStatusBadge.className   = "status-badge session-inactive";
        }
        const container = document.getElementById("manualAttendanceContainer");
        if (container) container.innerHTML = '<div class="list-empty">Select session details to load student index numbers.</div>';
        const footer = document.getElementById("manualAttendanceFooter");
        if (footer) footer.style.display = "none";
        disableCameraMarkButtons(false);
    }

    function filterSubjects() {
        const year     = yearSelect.value;
        const semester = semesterSelect.value;
        const mode     = studyModeSelect.value;
        subjectSelect.innerHTML = '<option value="">-- Choose Subject --</option>';
        subjectSelect.disabled  = true;
        lecturerSelect.innerHTML = '<option value="">-- Choose Lecturer --</option>';
        lecturerSelect.disabled  = true;
        hiddenLectureName.value  = "";
        hiddenLecturerName.value = "";
        sessionDisplay.value = "";
        if (!year || !semester || !mode) return;
        const filtered = currentSubjectsList.filter(s => s.year === year && s.semester === semester);
        if (filtered.length === 0) {
            const opt = document.createElement("option");
            opt.value = ""; opt.textContent = "No subjects found for this selection";
            subjectSelect.appendChild(opt);
            return;
        }
        filtered.forEach(s => {
            const opt = document.createElement("option");
            opt.value = s.id;
            opt.textContent = `${s.subject_code} - ${s.subject_name}`;
            subjectSelect.appendChild(opt);
        });
        subjectSelect.disabled = false;
    }

    async function loadAttendanceCourses() {
        try {
            const res     = await fetch("/api/courses");
            const courses = await res.json();
            courseSelect.innerHTML = '<option value="">-- Choose Course --</option>';
            courses.forEach(c => {
                const opt = document.createElement("option");
                opt.value = c.id;
                opt.textContent = `${c.course_code} - ${c.course_name}`;
                courseSelect.appendChild(opt);
            });
        } catch (err) { console.error("Error loading courses:", err); }
    }

    courseSelect.addEventListener("change", async function () {
        currentSubjectsList = [];
        resetFrom(1);
        if (!this.value) return;
        try {
            const res = await fetch(`/api/courses/${this.value}/subjects`);
            currentSubjectsList = await res.json();
            yearSelect.disabled = false;
        } catch (err) { console.error("Error loading subjects:", err); }
    });

    yearSelect.addEventListener("change", function () {
        resetFrom(2);
        semesterSelect.disabled = !this.value;
    });

    semesterSelect.addEventListener("change", function () {
        resetFrom(3);
        studyModeSelect.disabled = !this.value;
    });

    studyModeSelect.addEventListener("change", function () {
        resetFrom(4);
        if (this.value) filterSubjects();
    });

    subjectSelect.addEventListener("change", async function () {
        const subjectId = parseInt(this.value);
        lecturerSelect.innerHTML = '<option value="">-- Choose Lecturer --</option>';
        lecturerSelect.disabled  = true;
        hiddenLectureName.value  = "";
        hiddenLecturerName.value = "";
        sessionDisplay.value = "";
        if (!subjectId) { resetFrom(5); return; }
        const subject = currentSubjectsList.find(s => s.id === subjectId);
        if (subject) {
            lecturerSelect.innerHTML = `<option value="${subject.lecturer_id}">${subject.lecturer_name}</option>`;
            lecturerSelect.disabled  = false;
            hiddenLectureName.value  = `${subject.subject_code} - ${subject.subject_name}`;
            hiddenLecturerName.value = subject.lecturer_name;
            try {
                const courseText = courseSelect.options[courseSelect.selectedIndex].text.split(" - ")[0];
                const res  = await fetch(`/api/get-active-session?course=${encodeURIComponent(courseText)}&year=${encodeURIComponent(yearSelect.value)}&semester=${encodeURIComponent(semesterSelect.value)}&study_mode=${encodeURIComponent(studyModeSelect.value)}&subject_id=${subject.id}`);
                const data = await res.json();
                if (data.success) {
                    const isCancelled = data.is_cancelled == 1 || data.is_cancelled == '1';
                    if (isCancelled) {
                        sessionDisplay.value = `CANCELLED: ${data.session_info}`;
                        sessionStatusBadge.textContent = "Session Cancelled";
                        sessionStatusBadge.className   = "status-badge session-cancelled";
                        loadStudentChecklist(false);
                    } else if (!data.is_active_time) {
                        sessionDisplay.value = `INACTIVE NOW: ${data.session_info}`;
                        sessionStatusBadge.textContent = "Outside Lecture Hours";
                        sessionStatusBadge.className   = "status-badge session-inactive";
                        loadStudentChecklist(false);
                    } else {
                        sessionDisplay.value = data.session_info;
                        sessionStatusBadge.textContent = "Session Active";
                        sessionStatusBadge.className   = "status-badge session-active";
                        loadStudentChecklist(false);
                    }
                } else {
                    sessionDisplay.value = "-- No Timetable Slot Today --";
                    sessionStatusBadge.textContent = "Session Inactive";
                    sessionStatusBadge.className   = "status-badge session-inactive";
                    loadStudentChecklist(false);
                }
            } catch (e) {
                sessionDisplay.value = "-- Error Fetching Session --";
                sessionStatusBadge.textContent = "Session Error";
                sessionStatusBadge.className   = "status-badge session-error";
                disableCameraMarkButtons(true, "Error fetching session details.");
                loadStudentChecklist(false);
            }
        }
    });

    
    // STUDENT CHECKLIST (manual panel)// 
    async function loadStudentChecklist(disabledList = false) {
        const container = document.getElementById("manualAttendanceContainer");
        if (!container) return;
        container.innerHTML = '<div class="list-loading"><span class="list-loading-text">Loading students list...</span></div>';
        try {
            const res  = await fetch(`/api/get-students-by-class?course_id=${courseSelect.value}&year=${encodeURIComponent(yearSelect.value)}&semester=${encodeURIComponent(semesterSelect.value)}&study_mode=${encodeURIComponent(studyModeSelect.value)}&lecture_name=${encodeURIComponent(hiddenLectureName.value)}`);
            const data = await res.json();
            if (!data.success || !data.students || data.students.length === 0) {
                container.innerHTML = '<div class="list-empty">No active students found registered for this class selection.</div>';
                document.getElementById("manualAttendanceFooter").style.display = "none";
                return;
            }
            let html = '<div class="student-checkbox-list">';
            data.students.forEach(s => {
                const isChecked  = s.marked ? 'checked' : '';
                const isDisabled = disabledList ? 'disabled' : '';
                const itemClass  = s.marked ? 'student-checkbox-item checked' : 'student-checkbox-item';
                html += `
                    <label class="${itemClass}">
                        <input type="checkbox" class="student-check" data-student-id="${s.student_id}" ${isChecked} ${isDisabled}>
                        <span class="student-idx">${s.student_id}</span>
                        <span class="student-nm">(${s.full_name})</span>
                    </label>
                `;
            });
            html += '</div>';
            container.innerHTML = html;
            document.getElementById("manualAttendanceFooter").style.display = "flex";
            updateMarkedCount();

            container.querySelectorAll(".student-check").forEach(cb => {
                cb.addEventListener("change", async function () {
                    const studentId  = this.dataset.studentId;
                    const action     = this.checked ? 'mark' : 'unmark';
                    const parentLabel= this.closest(".student-checkbox-item");
                    parentLabel.classList.toggle("checked", this.checked);
                    updateMarkedCount();
                    try {
                        const postRes  = await fetch("/api/mark-attendance-manual", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ student_id: studentId, lecture_name: hiddenLectureName.value, lecturer_name: hiddenLecturerName.value, action })
                        });
                        const postData = await postRes.json();
                        if (!postData.success) {
                            this.checked = !this.checked;
                            parentLabel.classList.toggle("checked", this.checked);
                            updateMarkedCount();
                            showResult("❌ " + postData.message, "error");
                        } else {
                            const nowTime   = postData.time || new Date().toLocaleTimeString();
                            const logType   = action === 'mark' ? 'ok' : 'err';
                            if (action === 'mark') markedThisSession.add(studentId);
                            else markedThisSession.delete(studentId);
                            showResult(`✅ Attendance ${action === 'mark' ? 'Marked' : 'Removed'} for ${studentId}`, "success");
                            addLog(studentId, hiddenLectureName.value, nowTime, logType);
                            playNotificationSound("success");
                        }
                    } catch (err) {
                        this.checked = !this.checked;
                        parentLabel.classList.toggle("checked", this.checked);
                        updateMarkedCount();
                        showResult("❌ Connection error. Reverted checkbox.", "error");
                    }
                });
            });
        } catch (err) {
            container.innerHTML = '<div class="list-error">⚠️ Error loading student list.</div>';
            document.getElementById("manualAttendanceFooter").style.display = "none";
        }
    }

    function updateMarkedCount() {
        const checkedCount = document.querySelectorAll(".student-check:checked").length;
        const totalCount   = document.querySelectorAll(".student-check").length;
        const counterEl    = document.getElementById("totalMarkedCount");
        if (counterEl) counterEl.textContent = `${checkedCount} / ${totalCount}`;
    }

    loadAttendanceCourses();

     
    // UNIFIED SCAN LOOP — Face recognition + QR code in one pas// 
    async function scanLoop() {
        if (!isScanning || !stream) return;
        if (!video.videoWidth) { scanTimeout = setTimeout(scanLoop, 200); return; }

        const lectureName  = hiddenLectureName.value.trim();
        const lecturerName = hiddenLecturerName.value.trim();
        if (!lectureName) {
            showResult("⚠️ Please select a session first!", "warning");
            stopCamera();
            return;
        }

        // ── Capture frame into canvas with full video resolution for QR detection ──
        let width = video.videoWidth || 640;
        let height = video.videoHeight || 480;
        const canvas = document.createElement("canvas");
        canvas.width = width; canvas.height = height;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0, width, height);

        // ── 1. Try QR code detection first (synchronous, zero server cost) ──
        let qrResult = null;
        try {
            const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
            const qrScannerFunc = (typeof jsQR !== 'undefined') ? jsQR : (window.jsQR || null);
            if (qrScannerFunc) {
                qrResult = qrScannerFunc(imageData.data, canvas.width, canvas.height, { inversionAttempts: "attemptBoth" });
            }
        } catch (e) {
            console.warn("[QR SCAN] Error decoding frame:", e);
        }
        const now = Date.now();

        if (qrResult && qrResult.data) {
            let studentId = String(qrResult.data).trim();
            // Decode URL-encoded student IDs (e.g. ENG%2F2024%2F001 → ENG/2024/001)
            try { studentId = decodeURIComponent(studentId); } catch(e) { /* keep raw if decode fails */ }

            // Handle URL query string (e.g., https://site.com/?data=NAW/IT/001 or id=NAW/IT/001)
            if (studentId.includes("data=") || studentId.includes("student_id=") || studentId.includes("id=")) {
                try {
                    const searchStr = studentId.includes("?") ? studentId.split("?")[1] : studentId;
                    const urlParams = new URLSearchParams(searchStr);
                    const extracted = urlParams.get("data") || urlParams.get("student_id") || urlParams.get("id");
                    if (extracted) studentId = extracted.trim();
                } catch(e) {}
            }

            if (studentId.startsWith('{') && studentId.endsWith('}')) {
                try {
                    const parsedObj = JSON.parse(studentId);
                    studentId = String(parsedObj.student_id || parsedObj.index || parsedObj.id || studentId).trim();
                } catch(e) {}
            }
            
            // Debounce: ignore same QR within 4 s
            if (studentId === lastQRCode && (now - lastQRTime) < 4000) {
                scanTimeout = setTimeout(scanLoop, 300);
                return;
            }

            // Helper to check duplicates case-insensitively and ignore formatting slashes/underscores
            function isStudentAlreadyMarked(sid) {
                if (!sid) return false;
                const cleanId = sid.replace(/[\/_]/g, '').toLowerCase();
                for (let marked of markedThisSession) {
                    if (marked.replace(/[\/_]/g, '').toLowerCase() === cleanId) {
                        return true;
                    }
                }
                return false;
            }

            // Client-side duplicate guard
            if (isStudentAlreadyMarked(studentId)) {
                showResult(`⚠️ Attendance already marked for: ${studentId}`, "warning");
                lastQRCode = studentId; lastQRTime = now;
                scanTimeout = setTimeout(scanLoop, 2500);
                return;
            }

            lastQRCode = studentId; lastQRTime = now;
            showResult(`📱 QR Detected: ${studentId} — marking attendance...`, "success");

            try {
                const res  = await fetch('/api/mark-attendance-qr', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        student_id: studentId, 
                        lecture_name: lectureName,
                        lecturer_name: lecturerName
                    })
                });
                const data = await res.json();
                if (!isScanning) return;

                if (data.success) {
                    // Use canonical values returned by the backend
                    const canonId   = data.student_id   || studentId;
                    const canonName = data.student_name || studentId;
                    markedThisSession.add(canonId);
                    showResult(`✅ QR Attendance Marked: ${canonName} (${canonId})`, "success");
                    addLog(canonName, lectureName, new Date().toLocaleTimeString(), "ok");
                    playNotificationSound("success");
                    triggerFlashEffect();
                    markCheckbox(canonId);
                    scanTimeout = setTimeout(scanLoop, 2500);
                } else if (data.already_marked) {
                    const canonId   = data.student_id   || studentId;
                    const canonName = data.student_name || studentId;
                    markedThisSession.add(canonId);
                    showResult(`⚠️ Attendance already marked: ${canonName} (${canonId})`, "warning");
                    addLog(canonName, lectureName, new Date().toLocaleTimeString(), "warn");
                    playNotificationSound("warn");
                    scanTimeout = setTimeout(scanLoop, 2500);
                } else {
                    showResult(`❌ ${data.message}`, "error");
                    playNotificationSound("error");
                    scanTimeout = setTimeout(scanLoop, 2000);
                }
            } catch (err) {
                showResult("❌ Network error during QR attendance.", "error");
                scanTimeout = setTimeout(scanLoop, 1500);
            }
            return; // QR handled — skip face recognition this frame
        }

        //  2. Face recognition (only when no QR found, and not in face cooldown) 
        if (now < faceCoolUntil) {
            // Still in cooldown after previous recognition event
            showResult("📷 Scanning... Position face or QR code in camera.", "success");
            scanTimeout = setTimeout(scanLoop, 300);
            return;
        }

        // Create a smaller canvas for face recognition to speed up upload/processing
        const faceCanvas = document.createElement("canvas");
        faceCanvas.width = 480; faceCanvas.height = 360;
        const faceCtx = faceCanvas.getContext("2d");
        faceCtx.drawImage(video, 0, 0, 480, 360);
        const imageBase64 = faceCanvas.toDataURL("image/jpeg", 0.85);  // Higher quality = better recognition

        // Prevent concurrent face requests piling up
        if (isProcessingFace) {
            scanTimeout = setTimeout(scanLoop, 200);
            return;
        }
        isProcessingFace = true;

        try {
            const res  = await fetch("/api/mark-attendance", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ image: imageBase64, lecture_name: lectureName, lecturer_name: lecturerName })
            });
            const data = await res.json();
            isProcessingFace = false;
            if (!isScanning) return;

            if (data.success) {
                markedThisSession.add(data.student_id);
                showResult(`✅ Attendance Marked: ${data.student_name} (${data.student_id})`, "success");
                addLog(data.student_name, lectureName, data.time, "ok");
                playNotificationSound("success");
                triggerFlashEffect();
                markCheckbox(data.student_id);
                faceCoolUntil = now + 2500;
                scanTimeout = setTimeout(scanLoop, 2500);

            } else if (data.already_marked) {
                markedThisSession.add(data.student_id || '');
                showResult(`⚠️ Already Marked Today: ${data.student_name}`, "warning");
                addLog(data.student_name, lectureName, data.time, "warn");
                playNotificationSound("warn");
                faceCoolUntil = now + 2500;
                scanTimeout = setTimeout(scanLoop, 2500);

            } else {
                // Classify the message for appropriate UI handling
                const msg = data.message || "";

                if (msg.includes("No face") || msg.includes("No face detected")) {
                    // Soft: no face visible OR face not recognized — keep scanning quickly, no alarm
                    if (msg.includes("not recognized") || msg.includes("ambiguous") || msg.includes("not found in dataset")) {
                        showResult("🔍 Face detected but not recognized. Adjust angle or lighting.", "warning");
                    } else {
                        showResult("📷 Scanning... Position your face or QR code in front of the camera.", "success");
                    }
                    scanTimeout = setTimeout(scanLoop, 200); // Fast retry when no face detected

                } else if (msg.includes("stabilizing")) {
                    // Frame-count confirmation in progress — silent fast rescan
                    showResult("🔍 Hold still... confirming identity.", "success");
                    scanTimeout = setTimeout(scanLoop, 50); // Speed up stabilization frames to 50ms!

                } else if (msg.includes("already marked") || msg.includes("Already")) {
                    showResult(`⚠️ ${msg}`, "warning");
                    playNotificationSound("warn");
                    faceCoolUntil = now + 2500;
                    scanTimeout = setTimeout(scanLoop, 2500);

                } else {
                    // Hard error: timetable mismatch, inactive, etc.
                    showResult(`❌ ${msg}`, "error");
                    playNotificationSound("error");
                    faceCoolUntil = now + 2500;
                    scanTimeout = setTimeout(scanLoop, 2500);
                }
            }
        } catch (err) {
            isProcessingFace = false;
            showResult("❌ Server error. Retrying...", "error");
            scanTimeout = setTimeout(scanLoop, 1500);
        }
    }


    // CAMERA START / STOP// 
    startBtn.addEventListener("click", async function () {
        if (!subjectSelect.value) {
            showResult("⚠️ Please select a Course, Year/Semester, and Subject first!", "warning");
            return;
        }

        // Stop any previous stream first
        if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }

        // Check if camera API is available at all
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            showResult("❌ Camera not supported in this browser. Use Chrome or Edge on localhost.", "error");
            return;
        }

        showResult("🔄 Starting camera...", "success");

        // Try 3 fallback camera constraints
        const constraints = [
            { video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" } },
            { video: true },
            { video: { facingMode: { ideal: "environment" } } }
        ];

        let camStarted = false;
        for (const constraint of constraints) {
            try {
                stream = await navigator.mediaDevices.getUserMedia(constraint);
                camStarted = true;
                console.log("[CAMERA] Started with constraint:", JSON.stringify(constraint));
                break;
            } catch (err) {
                console.warn("[CAMERA] Constraint failed:", JSON.stringify(constraint), err.name, err.message);
                // If user explicitly denied, stop trying
                if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
                    showResult("❌ Camera access denied. Please allow camera permission in your browser settings and refresh.", "error");
                    return;
                }
            }
        }

        if (!camStarted || !stream) {
            showResult("❌ Could not open camera. Make sure a webcam is connected and no other app is using it.", "error");
            return;
        }

        video.srcObject = stream;
        cameraStandby.style.display  = "none";
        video.style.display          = "block";
        video.classList.remove("video-hidden");
        scannerOverlay.style.display = "block";

        startBtn.classList.add("btn-hidden");
        stopBtn.classList.remove("btn-hidden");

        // Reset per-session duplicate cache
        markedThisSession.clear();
        lastQRCode   = '';
        lastQRTime   = 0;
        faceCoolUntil= 0;
        isProcessingFace = false;

        // Wait for video to be ready before scanning
        video.onloadedmetadata = () => {
            video.play().catch(e => console.warn("[CAMERA] play() error:", e));
        };

        isScanning = true;
        showResult("⚡ Scanner active — scanning for faces & QR codes.", "success");
        // Start scanning immediately after video starts
        setTimeout(scanLoop, 50);
    });

    function stopCamera() {
        isScanning = false;
        if (scanTimeout) { clearTimeout(scanTimeout); scanTimeout = null; }
        if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
        video.srcObject = null;
        video.style.display          = "none";
        video.classList.add("video-hidden");
        scannerOverlay.style.display = "none";
        cameraStandby.style.display  = "flex";
        startBtn.classList.remove("btn-hidden");
        stopBtn.classList.add("btn-hidden");
    }

    stopBtn.addEventListener("click", function () {
        stopCamera();
        showResult("⚠️ Scanner deactivated.", "warning");
    });

   
    // UI HELPERS// 
    function markCheckbox(studentId) {
        const checkbox = document.querySelector(`.student-check[data-student-id="${studentId}"]`);
        if (checkbox) {
            checkbox.checked = true;
            const parentLabel = checkbox.closest(".student-checkbox-item");
            if (parentLabel) parentLabel.classList.add("checked");
            updateMarkedCount();
        }
    }

    function showResult(msg, type) {
        resultBox.style.display = "block";
        resultBox.className     = "result-box result-" + type;
        resultBox.textContent   = msg;
    }

    function addLog(name, lecture, time, type) {
        const placeholder = liveLog.querySelector(".log-placeholder");
        if (placeholder) liveLog.innerHTML = "";
        const entry = document.createElement("div");
        entry.className = "log-entry log-" + type;
        const icons      = { ok: "✅", warn: "⚠️", err: "❌" };
        const statusText = type === "ok" ? "PRESENT" : (type === "warn" ? "ALREADY RECORDED" : "UNRECOGNIZED");
        entry.innerHTML = `
            <span>${icons[type]}</span>
            <span class="log-time">[${time}]</span>
            <span class="log-body"><strong>${name}</strong> — ${lecture}</span>
            <span class="badge badge-${type === 'ok' ? 'present' : 'absent'}">${statusText}</span>
        `;
        liveLog.prepend(entry);
    }

    function triggerFlashEffect() {
        const flashDiv  = document.createElement("div");
        flashDiv.className = "camera-flash-overlay";
        const container = document.querySelector(".camera-stream-container");
        if (container) {
            container.appendChild(flashDiv);
            setTimeout(() => {
                flashDiv.style.opacity = "0";
                setTimeout(() => flashDiv.remove(), 400);
            }, 50);
        }
    }

    function playNotificationSound(type) {
        try {
            const ctx  = new (window.AudioContext || window.webkitAudioContext)();
            const osc  = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain); gain.connect(ctx.destination);
            if (type === "success") {
                osc.frequency.setValueAtTime(600, ctx.currentTime);
                gain.gain.setValueAtTime(0.1, ctx.currentTime);
                osc.start(); osc.stop(ctx.currentTime + 0.1);
                setTimeout(() => {
                    const osc2 = ctx.createOscillator(), gain2 = ctx.createGain();
                    osc2.connect(gain2); gain2.connect(ctx.destination);
                    osc2.frequency.setValueAtTime(800, ctx.currentTime);
                    gain2.gain.setValueAtTime(0.1, ctx.currentTime);
                    osc2.start(); osc2.stop(ctx.currentTime + 0.15);
                }, 120);
            } else if (type === "warn") {
                osc.frequency.setValueAtTime(400, ctx.currentTime);
                gain.gain.setValueAtTime(0.1, ctx.currentTime);
                osc.start(); osc.stop(ctx.currentTime + 0.25);
            } else {
                osc.frequency.setValueAtTime(220, ctx.currentTime);
                gain.gain.setValueAtTime(0.15, ctx.currentTime);
                osc.start(); osc.stop(ctx.currentTime + 0.35);
            }
        } catch (e) { console.warn("Audio blocked:", e); }
    }

});
