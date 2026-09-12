/* Star / Follow toggles: POST in the background, no page reload. */
(function () {
    "use strict";

    function csrfToken() {
        var input = document.querySelector("input[name=csrfmiddlewaretoken]");
        if (input && input.value) {
            return input.value;
        }
        var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function updateButton(button, value) {
        var icon = button.querySelector("[data-toggle-icon]");
        if (icon) {
            var name = value ? button.dataset.iconOn : button.dataset.iconOff;
            if (name) {
                icon.textContent = name;
            }
        }
        var label = button.querySelector("[data-toggle-label]");
        if (label) {
            var text = value ? button.dataset.labelOn : button.dataset.labelOff;
            if (text) {
                label.textContent = text;
            }
        }
        button.setAttribute("aria-pressed", value ? "true" : "false");
    }

    function toggle(button) {
        if (button.dataset.busy === "1") {
            return;
        }
        button.dataset.busy = "1";
        fetch(button.dataset.toggleUrl, {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken(),
                "X-Requested-With": "XMLHttpRequest",
            },
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return { ok: response.ok, data: data };
                });
            })
            .then(function (result) {
                if (result.ok) {
                    updateButton(button, !!result.data.value);
                }
            })
            .catch(function () {
                /* The toggle is an enhancement; keep the current state. */
            })
            .then(function () {
                delete button.dataset.busy;
            });
    }

    document.addEventListener("click", function (event) {
        var button = event.target.closest("[data-subscription-toggle]");
        if (!button) {
            return;
        }
        event.preventDefault();
        toggle(button);
    });
})();
