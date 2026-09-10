(function () {
    "use strict";

    function qs(selector, root) {
        return (root || document).querySelector(selector);
    }

    function qsa(selector, root) {
        return Array.from(
            (root || document).querySelectorAll(selector)
        );
    }

    function initMobileMenu() {
        var button = qs("[data-kemet-mobile-menu]");
        var sidebar = qs(".k-sidebar");

        if (!button || !sidebar) {
            return;
        }

        button.addEventListener("click", function () {
            sidebar.classList.toggle("is-open");
        });
    }

    function initDismissibleAlerts() {
        qsa("[data-kemet-dismiss]").forEach(function (button) {
            button.addEventListener("click", function () {
                var target = button.closest(".k-alert");

                if (target) {
                    target.remove();
                }
            });
        });
    }

    function initActiveNavigation() {
        var currentPath = window.location.pathname;

        qsa(".k-nav a").forEach(function (link) {
            var href = link.getAttribute("href");

            if (!href || href === "#") {
                return;
            }

            try {
                var url = new URL(
                    href,
                    window.location.origin
                );

                if (
                    url.pathname !== "/" &&
                    currentPath.startsWith(url.pathname)
                ) {
                    link.classList.add("active");
                }
            } catch (error) {
                return;
            }
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        initMobileMenu();
        initDismissibleAlerts();
        initActiveNavigation();
    });

    window.KemetUI = {
        qs: qs,
        qsa: qsa
    };
})();



/* KEMET_COMMAND_AGENT */
(function () {
    const input = document.getElementById("kemet-agent-input");
    const send = document.getElementById("kemet-agent-send");
    const result = document.getElementById("kemet-agent-result");
    const codeBox = document.getElementById("kemet-agent-code");
    const explanation = document.getElementById("kemet-agent-explanation");

    if (!input || !send || !result) return;

    function csrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.getAttribute("content") || "";

        const el = document.querySelector('input[name="csrf_token"]');
        return el ? el.value : "";
    }

    send.addEventListener("click", async function () {
        const instruction = input.value.trim();
        if (!instruction) return;

        send.disabled = true;
        send.textContent = "جارٍ التنفيذ...";

        result.style.display = "block";
        codeBox.textContent = "جاري تنفيذ الطلب...";
        explanation.textContent = "Kemet AI يعمل على تنفيذ طلبك...";

        try {
            const response = await fetch("/api/command-agent", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken()
                },
                body: JSON.stringify({
                    instruction: instruction
                })
            });

            const data = await response.json();

            if (!response.ok || data.ok === false) {
                throw new Error(
                    data.error ||
                    data.message ||
                    "حدث خطأ أثناء تنفيذ الطلب."
                );
            }

            codeBox.textContent =
                data.stdout ||
                data.output ||
                data.result ||
                "تم تنفيذ الطلب بدون مخرجات برمجية.";

            explanation.textContent =
                data.explanation ||
                data.message ||
                "تم استلام وتنفيذ الطلب.";

        } catch (error) {
            codeBox.textContent = String(error.message || error);
            explanation.textContent =
                "تعذر تنفيذ الطلب. راجع نتيجة التنفيذ أعلاه.";
        } finally {
            send.disabled = false;
            send.textContent = "تنفيذ الطلب";
        }
    });
})();

