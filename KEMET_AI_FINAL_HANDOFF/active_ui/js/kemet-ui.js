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
