/* Ask for browser notification permission from the Preferences checkbox.
 *
 * Browsers expect the permission request to come from a user gesture, so it
 * is triggered when the "Browser popup notifications" box is checked. The
 * preference itself is saved by the normal form submit. When the browser
 * cannot show desktop notifications (insecure origin, unsupported browser or
 * a blocked permission) an inline hint explains why instead of failing
 * silently.
 */
(function () {
    "use strict";

    function showHint(box, message) {
        var container = box.closest(".grow") || box.parentElement;
        if (!container || container.querySelector("[data-notification-hint]")) {
            return;
        }
        var hint = document.createElement("p");
        hint.setAttribute("data-notification-hint", "true");
        hint.className =
            "leading-relaxed mt-2 text-xs text-red-600 dark:text-red-400";
        hint.textContent = message;
        container.appendChild(hint);
    }

    function bind() {
        var box = document.getElementById("id_notifications_browser");
        if (!box) {
            return;
        }
        if (!window.Notification) {
            showHint(
                box,
                "Desktop notifications are not available here: the browser " +
                    "needs a secure origin (localhost, 127.0.0.1 or HTTPS) " +
                    "and support for the Notification API."
            );
            return;
        }
        if (window.Notification.permission === "denied") {
            showHint(
                box,
                "Notifications are blocked for this site; allow them in the " +
                    "browser's site settings (and your OS notification " +
                    "settings), then save again."
            );
        }
        box.addEventListener("change", function () {
            if (box.checked && window.Notification.permission === "default") {
                try {
                    window.Notification.requestPermission();
                } catch (error) {
                    /* permission is an enhancement; ignore failures */
                }
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bind);
    } else {
        bind();
    }
})();
