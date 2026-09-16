/* Live notification badge + toasts over Server-Sent Events. */
(function () {
    "use strict";

    if (!window.EventSource) {
        return;
    }

    // Set from the SSE init event; the server combines the constance switch
    // with the user's Preferences opt-in.
    var browserPopups = false;

    function notificationLinks() {
        // The sidebar hosts the notification pages (and the avatar badge);
        // restricting the match keeps page links like the breadcrumb or the
        // dashboard card from being decorated with the count.
        return document.querySelectorAll(
            '#nav-sidebar a[href$="/core/notification/"]'
        );
    }

    function updateBadge(count) {
        notificationLinks().forEach(function (link) {
            // Only the avatar badge carries the unread count: it is a
            // childless link whose text is the number, so it is updated in
            // place rather than given a badge span.
            if (link.children.length || !/^\d+$/.test(link.textContent.trim())) {
                return;
            }
            link.textContent = count > 0 ? String(count) : "";
            link.style.display = count > 0 ? "" : "none";
        });
    }

    function showPopup(kind, id, message) {
        if (!browserPopups || !window.Notification) {
            return;
        }
        if (window.Notification.permission !== "granted" || !document.hidden) {
            return;
        }
        try {
            var popup = new window.Notification("OmaCRM", {
                body: message,
                tag: "omacrm-" + kind + "-" + (id || 0),
            });
            popup.onclick = function () {
                window.focus();
                popup.close();
            };
        } catch (error) {
            /* popups are an enhancement; the toast still shows */
        }
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
                if (data.type === "init") {
                    browserPopups = data.browser === true;
                }
                if (typeof data.count === "number") {
                    updateBadge(data.count);
                }
                if (data.type === "new" && data.message) {
                    showToast(data.message);
                    showPopup("notification", data.id, data.message);
                }
                if (data.type === "stream" && data.message) {
                    showToast(data.message);
                    showPopup("stream", data.id, data.message);
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
