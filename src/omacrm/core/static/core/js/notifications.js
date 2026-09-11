/* Live notification badge + toasts over Server-Sent Events. */
(function () {
    "use strict";

    if (!window.EventSource) {
        return;
    }

    var BADGE_CLASSES = [
        "inline-block font-semibold rounded-default text-[11px] uppercase",
        "whitespace-nowrap h-6 leading-6 px-2 ml-auto",
        "bg-primary-100 text-primary-700 dark:bg-primary-500/20 dark:text-primary-400",
    ].join(" ");

    function notificationLinks() {
        return document.querySelectorAll('a[href$="/core/notification/"]');
    }

    function updateBadge(count) {
        notificationLinks().forEach(function (link) {
            var badge = link.querySelector("[data-notification-badge]");

            if (!badge) {
                // Adopt the server-rendered badge (numeric span) if present.
                var spans = link.querySelectorAll("span");
                for (var index = 0; index < spans.length; index += 1) {
                    if (/^\d+$/.test(spans[index].textContent.trim())) {
                        badge = spans[index];
                        badge.setAttribute("data-notification-badge", "true");
                        break;
                    }
                }
            }

            if (count > 0) {
                if (!badge) {
                    badge = document.createElement("span");
                    badge.setAttribute("data-notification-badge", "true");
                    badge.className = BADGE_CLASSES;
                    link.appendChild(badge);
                }
                badge.textContent = String(count);
            } else if (badge) {
                badge.remove();
            }
        });
    }

    function showToast(message) {
        var toast = document.createElement("div");
        toast.setAttribute("data-notification-toast", "true");
        toast.style.cssText = [
            "position:fixed", "top:16px", "right:16px", "z-index:10000",
            "max-width:360px", "padding:12px 16px", "border-radius:8px",
            "background:#1f2937", "color:#f9fafb", "font-size:13px",
            "box-shadow:0 10px 15px -3px rgba(0,0,0,.25)",
            "transition:opacity .3s ease", "opacity:1",
        ].join(";");
        toast.textContent = message;
        document.body.appendChild(toast);
        window.setTimeout(function () {
            toast.style.opacity = "0";
            window.setTimeout(function () {
                toast.remove();
            }, 300);
        }, 8000);
    }

    function start() {
        // Only connect on authenticated admin pages (the sidebar has the link).
        if (!notificationLinks().length) {
            return;
        }

        try {
            var source = new EventSource("/admin/notifications/stream/");
            source.onmessage = function (event) {
                var data;
                try {
                    data = JSON.parse(event.data);
                } catch (error) {
                    return;
                }
                if (typeof data.count === "number") {
                    updateBadge(data.count);
                }
                if (data.type === "new" && data.message) {
                    showToast(data.message);
                }
            };
            // EventSource reconnects automatically; errors are expected on idle.
            source.onerror = function () {};
        } catch (error) {
            /* notifications are an enhancement; fail silently */
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();
