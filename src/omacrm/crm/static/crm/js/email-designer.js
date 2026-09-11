(function () {
    "use strict";

    var configEl = document.getElementById("email-designer-config");
    if (!configEl || typeof grapesjs === "undefined") {
        return;
    }

    var cfg = JSON.parse(configEl.textContent);
    var statusEl = document.getElementById("email-designer-status");
    var labels = cfg.labels || {};

    function setStatus(message) {
        if (statusEl) {
            statusEl.textContent = message || "";
        }
    }

    function errorMessage(error) {
        var template = labels.error || "Error: %(error)s";
        return template.replace("%(error)s", error || "?");
    }

    function extractDocument(raw) {
        var doc = new DOMParser().parseFromString(raw, "text/html");
        var styles = [];
        Array.prototype.forEach.call(doc.querySelectorAll("style"), function (node) {
            styles.push(node.textContent || "");
        });
        var bodyStyle = doc.body ? doc.body.getAttribute("style") : "";
        if (bodyStyle) {
            styles.push("body {" + bodyStyle + "}");
        }
        var components = doc.body ? doc.body.innerHTML : raw;
        components = components
            .replace(/<style[\s\S]*?<\/style>/gi, "")
            .replace(/<script[\s\S]*?<\/script>/gi, "")
            .replace(/<!--[\s\S]*?-->/g, "");
        return { components: components, css: styles.join("\n") };
    }

    var preset = window["grapesjs-preset-newsletter"];
    var editor = grapesjs.init({
        container: "#gjs",
        height: "100%",
        storageManager: false,
        plugins: preset ? [preset] : ["grapesjs-preset-newsletter"],
        assetManager: {
            upload: cfg.assetUploadUrl,
            uploadName: "files",
            headers: { "X-CSRFToken": cfg.csrfToken },
            credentials: "same-origin",
            autoAdd: true,
        },
        deviceManager: {
            devices: [
                { id: "desktop", name: "Desktop", width: "" },
                { id: "mobile", name: "Mobile", width: "375px", widthMedia: "480px" },
            ],
        },
        canvas: { styles: [], scripts: [] },
    });

    if (cfg.design) {
        editor.loadProjectData(cfg.design);
    } else if (cfg.body) {
        var imported = extractDocument(cfg.body);
        editor.setComponents(imported.components);
        if (imported.css) {
            editor.setStyle(imported.css);
        }
    }

    var blockManager = editor.BlockManager;
    (cfg.mergeTags || []).forEach(function (tag, index) {
        blockManager.add("merge-tag-" + index, {
            label: tag.label + " — " + tag.token,
            content: tag.token,
            category: "Merge tags",
        });
    });

    var saveButton = document.getElementById("email-designer-save");
    if (saveButton) {
        saveButton.addEventListener("click", function () {
            setStatus(labels.saving || "Saving...");
            fetch(cfg.saveUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": cfg.csrfToken,
                },
                body: JSON.stringify({
                    design: editor.getProjectData(),
                    html: editor.getHtml(),
                    css: editor.getCss(),
                }),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        return { ok: response.ok, data: data };
                    });
                })
                .then(function (result) {
                    if (result.ok) {
                        setStatus(labels.saved || "Saved");
                    } else {
                        setStatus(errorMessage(result.data.error));
                    }
                })
                .catch(function (error) {
                    setStatus(errorMessage(String(error)));
                });
        });
    }

    var previewButton = document.getElementById("email-designer-preview");
    if (previewButton) {
        previewButton.addEventListener("click", function () {
            window.open(cfg.previewUrl, "_blank");
        });
    }

    var testButton = document.getElementById("email-designer-test");
    if (testButton) {
        testButton.addEventListener("click", function () {
            var to = window.prompt(labels.testPrompt || "Send a test email to:", "");
            if (!to) {
                return;
            }
            setStatus(labels.sendingTest || "Sending...");
            var params = new URLSearchParams({ to_email: to });
            fetch(cfg.testSendUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-CSRFToken": cfg.csrfToken,
                },
                body: params.toString(),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        return { ok: response.ok, data: data };
                    });
                })
                .then(function (result) {
                    if (result.ok) {
                        setStatus(
                            (labels.testSent || "Test email sent to %(to)s").replace(
                                "%(to)s",
                                result.data.to || to
                            )
                        );
                    } else {
                        setStatus(errorMessage(result.data.error));
                    }
                })
                .catch(function (error) {
                    setStatus(errorMessage(String(error)));
                });
        });
    }
})();
