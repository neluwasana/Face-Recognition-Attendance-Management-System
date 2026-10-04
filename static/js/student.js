

document.addEventListener("DOMContentLoaded", function () {

    /* QR Code Download (Student Dashboard) */

    var downloadBtn = document.getElementById("downloadQR");

    if (downloadBtn) {
        downloadBtn.addEventListener("click", function () {

            // Get the QR image element
            var qrImg = document.getElementById("qrCodeImg");
            if (!qrImg) return;

            // Pull the student ID out of the QR image src URL
            var srcUrl     = qrImg.src;
            var urlParams  = new URLSearchParams(srcUrl.split("?")[1]);
            var studentId  = urlParams.get("data") || "student";

            // Build a high-resolution download URL (500×500)
            var downloadUrl = "https://api.qrserver.com/v1/create-qr-code/?size=500x500&data=" + encodeURIComponent(studentId);

            // Fetch the image, convert to a blob, then trigger download
            fetch(downloadUrl)
                .then(function (response) { return response.blob(); })
                .then(function (blob) {
                    var blobUrl  = window.URL.createObjectURL(blob);
                    var link     = document.createElement("a");
                    link.href     = blobUrl;
                    link.download = studentId + "_QR.png";
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    window.URL.revokeObjectURL(blobUrl);
                })
                .catch(function (err) {
                    console.error("Error downloading QR code:", err);
                });
        });
    }

});