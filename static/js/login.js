 document.addEventListener("DOMContentLoaded", function () {
            const togglePasswordBtn = document.getElementById("togglePasswordBtn");
            const passwordInput = document.getElementById("password");

            togglePasswordBtn.addEventListener("click", function () {
                if (passwordInput.type === "password") {
                    passwordInput.type = "text";
                    togglePasswordBtn.classList.remove("slashed");
                } else {
                    passwordInput.type = "password";
                    togglePasswordBtn.classList.add("slashed");
                }
            });
        });

        // Auto-hide success flash messages after 2.5 seconds
       document.addEventListener("DOMContentLoaded", function () {
           var successFlashes = document.querySelectorAll(".flash.success");
           successFlashes.forEach(function(el) {
               setTimeout(function() {
                   el.style.transition = "opacity 0.4s ease";
                   el.style.opacity = "0";
                   setTimeout(function() { el.remove(); }, 400);
               }, 2500);
           });
       });
