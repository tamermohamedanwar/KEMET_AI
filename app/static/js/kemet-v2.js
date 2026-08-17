(function () {
    "use strict";

    function ready(fn) {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", fn);
        } else {
            fn();
        }
    }

    function toast(message, type) {
        if (!message) return;

        var container = document.querySelector(".kemet-v2-toast-container");

        if (!container) {
            container = document.createElement("div");
            container.className = "kemet-v2-toast-container";
            document.body.appendChild(container);
        }

        var item = document.createElement("div");
        item.className = "kemet-v2-toast " + (type || "info");
        item.textContent = message;

        container.appendChild(item);

        setTimeout(function () {
            item.style.opacity = "0";
            item.style.transform = "translateY(-6px)";
            setTimeout(function () {
                item.remove();
            }, 180);
        }, 3500);
    }

    function setupBackToTop() {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "kemet-v2-top";
        btn.setAttribute("aria-label", "Back to top");
        btn.innerHTML = "↑";

        document.body.appendChild(btn);

        window.addEventListener("scroll", function () {
            if (window.scrollY > 350) {
                btn.classList.add("visible");
            } else {
                btn.classList.remove("visible");
            }
        }, { passive: true });

        btn.addEventListener("click", function () {
            window.scrollTo({
                top: 0,
                behavior: "smooth"
            });
        });
    }

    function setupForms() {
        document.querySelectorAll("form").forEach(function (form) {
            form.addEventListener("submit", function () {
                var submit = form.querySelector(
                    'button[type="submit"], input[type="submit"]'
                );

                if (!submit) return;

                if (submit.dataset.kemetBusy === "1") {
                    return;
                }

                submit.dataset.kemetBusy = "1";
                submit.classList.add("kemet-v2-loading");
            });
        });
    }

    function setupExternalLinks() {
        document.querySelectorAll("a[target='_blank']").forEach(function (a) {
            var rel = a.getAttribute("rel") || "";

            if (!rel.includes("noopener")) {
                a.setAttribute(
                    "rel",
                    (rel + " noopener noreferrer").trim()
                );
            }
        });
    }

    function removeLegacyYellowButtons() {
        document.querySelectorAll(
            ".btn-yellow, .yellow-button, .warning-yellow-button, .kemet-yellow-button"
        ).forEach(function (el) {
            el.remove();
        });

        document.querySelectorAll("button, a").forEach(function (el) {
            var text = (el.textContent || "").trim().toLowerCase();

            if (
                text === "yellow" ||
                text === "الزر الأصفر" ||
                text === "button yellow"
            ) {
                el.remove();
            }
        });
    }

    ready(function () {
        setupBackToTop();
        setupForms();
        setupExternalLinks();
        removeLegacyYellowButtons();

        window.KemetV2 = {
            toast: toast
        };
    });
})();
