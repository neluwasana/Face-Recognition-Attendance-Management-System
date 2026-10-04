// Auto hide the login success message 
        setTimeout(function() {
            var flashMessages = document.querySelectorAll('.flash');
            flashMessages.forEach(function(msg) {
                msg.style.opacity = '0';
                msg.style.transition = 'opacity 0.5s ease';
                setTimeout(function() {
                    msg.remove();
                }, 500);
            });
        }, 3000);

document.addEventListener("DOMContentLoaded", function () {
    
    const dateDisplay = document.getElementById("currentDateDisplay");
    if (dateDisplay) {
        const now = new Date();
        const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        dateDisplay.textContent = now.toLocaleDateString('en-GB', options);
    }

  
    loadDashboardStats();

    loadAttendanceTrend();
});

// LOAD DASHBOARD STATS (Total, Present, Absent)

function loadDashboardStats() {

    fetch("/api/dashboard-stats")
        .then(res => res.json())
        .then(data => {

            document.getElementById("totalStudentsCount").textContent = data.total_students || 0;
            document.getElementById("presentTodayCount").textContent = data.present_today || 0;
            document.getElementById("absentTodayCount").textContent = data.absent_today || 0;
        })
        .catch(err => {
            console.log("Stats load error:", err);
        });
}


// LOAD ATTENDANCE TREND (Last 7 Days Chart)

function loadAttendanceTrend() {

    fetch("/api/attendance-trend")
        .then(res => res.json())
        .then(data => {

            // Fill table
            const tbody = document.getElementById("trendTableBody");
            if (tbody) {
                tbody.innerHTML = "";
                data.forEach(row => {
                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                        <td>${row.date}</td>
                        <td><span class="badge-percent">${row.percent}%</span></td>
                    `;
                    tbody.appendChild(tr);
                });
            }

            
            drawBarChart(data);
        })
        .catch(err => {
            console.log("Trend load error:", err);
        });
}


// ATTENDANCE TREND CHART ( Chart.js Curve)

let trendChartInstance = null;

function drawBarChart(data) {
    const canvas = document.getElementById("attendanceTrendChart");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");

    
    if (trendChartInstance) {
        trendChartInstance.destroy();
    }

    if (!data || data.length === 0) return;

    // Format X-axis date labels e.g., "May 20"
    const labels = data.map(row => {
        const parts = row.date.split("-");
        if (parts.length === 3) {
            const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
            return `${months[parseInt(parts[1]) - 1]} ${parts[2]}`;
        }
        return row.date;
    });

    const percentages = data.map(row => row.percent);


    const gradient = ctx.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, 'rgba(79, 70, 229, 0.35)'); 
    gradient.addColorStop(1, 'rgba(79, 70, 229, 0.00)');

    //  Chart.js line graph
    trendChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Attendance Rate',
                data: percentages,
                borderColor: '#4f46e5',
                borderWidth: 3,
                pointBackgroundColor: '#ffffff',
                pointBorderColor: '#4f46e5',
                pointBorderWidth: 2.5,
                pointRadius: 5,
                pointHoverRadius: 7,
                pointHoverBackgroundColor: '#4f46e5',
                pointHoverBorderColor: '#ffffff',
                pointHoverBorderWidth: 2,
                tension: 0.4,
                fill: true,
                backgroundColor: gradient
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false 
                },
                tooltip: {
                    backgroundColor: '#0f172a', 
                    titleFont: {
                        family: 'Outfit',
                        size: 13,
                        weight: '600'
                    },
                    bodyFont: {
                        family: 'Outfit',
                        size: 12
                    },
                    padding: 12,
                    borderRadius: 12,
                    displayColors: false,
                    callbacks: {
                        label: function(context) {
                            return `Attendance Rate: ${context.parsed.y}%`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#64748b', 
                        font: {
                            family: 'Plus Jakarta Sans',
                            size: 11,
                            weight: '500'
                        }
                    }
                },
                y: {
                    min: 0,
                    max: 100,
                    grid: {
                        color: '#f1f5f9', 
                        drawBorder: false
                    },
                    ticks: {
                        color: '#64748b',
                        stepSize: 25,
                        font: {
                            family: 'Plus Jakarta Sans',
                            size: 11,
                            weight: '500'
                        },
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                }
            }
        }
    });
}
