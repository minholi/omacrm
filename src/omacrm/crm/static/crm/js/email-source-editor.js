(function () {
    "use strict";

    var configEl = document.getElementById("ese-config");
    var editorEl = document.getElementById("ese-source");
    if (!configEl || !editorEl || !window.OmaCodeMirror) {
        return;
    }

    var CM = window.OmaCodeMirror;
    var cfg = JSON.parse(configEl.textContent);
    var labels = cfg.labels || {};
    var formatEl = document.getElementById("ese-format");
    var previewEl = document.getElementById("ese-preview");
    var previewWrap = document.getElementById("ese-preview-wrap");
    var statusEl = document.getElementById("ese-status");
    var diagnosticsEl = document.getElementById("ese-diagnostics");
    var diagnosticsListEl = document.getElementById("ese-diagnostics-list");
    var saveButton = document.getElementById("ese-save");
    var testButton = document.getElementById("ese-test");
    var compileTimer = null;
    var compiling = false;
    var compileAgain = false;
    var languageCompartment = new CM.Compartment();

    var mjmlTags = cfg.mjmlTags || [];
    var knownTags = {};
    mjmlTags.forEach(function (tag) {
        knownTags[String(tag).toLowerCase()] = true;
    });

    function fill(template, key, value) {
        return String(template || "").replace("%(" + key + ")s", value);
    }

    function setStatus(message, isError) {
        if (!statusEl) {
            return;
        }
        statusEl.textContent = message || "";
        statusEl.classList.toggle("is-error", Boolean(isError));
    }

    function errorMessage(error) {
        return fill(labels.error || "Error: %(error)s", "error", error || "?");
    }

    function setPreview(html) {
        if (previewEl) {
            previewEl.setAttribute("srcdoc", html || "");
        }
    }

    function showDiagnostics(messages) {
        if (!diagnosticsEl || !diagnosticsListEl) {
            return;
        }
        diagnosticsListEl.innerHTML = "";
        (messages || []).forEach(function (message) {
            var item = document.createElement("li");
            item.textContent = message;
            diagnosticsListEl.appendChild(item);
        });
        diagnosticsEl.hidden = !(messages && messages.length);
    }

    function currentFormat() {
        if (formatEl && formatEl.value) {
            return formatEl.value;
        }
        return cfg.sourceFormat || "html";
    }

    /* Inline lint: flag unknown mj-* tags while typing, using the same
       whitelist that the server-side compile validates against. */

    function lintMjml(view) {
        var text = view.state.doc.toString();
        var diagnostics = [];
        var pattern = /<\s*\/?\s*(mj-[a-z0-9-]+)/gi;
        var match;
        while ((match = pattern.exec(text)) !== null) {
            var name = match[1].toLowerCase();
            if (knownTags[name]) {
                continue;
            }
            var from = match.index + match[0].length - match[1].length;
            diagnostics.push({
                from: from,
                to: from + match[1].length,
                severity: "error",
                message: fill(
                    labels.unknownTag || "Unknown MJML tag: %(tag)s",
                    "tag",
                    name
                ),
            });
        }
        return diagnostics;
    }

    function formatExtensions(format) {
        if (format !== "mjml") {
            return [];
        }
        return [CM.xml(), CM.lintGutter(), CM.linter(lintMjml, { delay: 300 })];
    }

    var mjmlCompletions = CM.completeFromList(
        mjmlTags.map(function (tag) {
            return { label: tag, type: "property", detail: "MJML" };
        })
    );

    var mergeTagSource = CM.completeFromList(
        (cfg.mergeTags || []).map(function (tag) {
            return { label: tag.token, type: "keyword", detail: tag.label };
        })
    );

    /* completeFromList matches from the last word character, which would drag
       the query across the surrounding text for labels like "{{ name }}".
       Anchor merge tags at the opening braces instead, so completing inside a
       sentence or right after "{{" replaces the whole tag. */

    function completeMergeTags(context) {
        var line = context.state.doc.lineAt(context.pos);
        var before = context.state.sliceDoc(line.from, context.pos);
        var open = before.lastIndexOf("{{");
        if (open < 0 || before.slice(open).indexOf("}}") !== -1) {
            return null;
        }
        var result = mergeTagSource(context);
        if (!result) {
            return null;
        }
        return {
            from: line.from + open,
            options: result.options,
            validFor: result.validFor,
        };
    }

    var editor = new CM.EditorView({
        state: CM.EditorState.create({
            doc: cfg.source || "",
            extensions: [
                CM.basicSetup,
                languageCompartment.of(formatExtensions(currentFormat())),
                CM.autocompletion({
                    override: [mjmlCompletions, completeMergeTags],
                }),
                CM.keymap.of([CM.indentWithTab]),
                CM.EditorView.updateListener.of(function (update) {
                    if (update.docChanged) {
                        scheduleCompile();
                    }
                }),
            ],
        }),
        parent: editorEl,
    });

    function source() {
        return editor.state.doc.toString();
    }

    function postJson(url, payload) {
        return fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": cfg.csrfToken,
            },
            body: JSON.stringify(payload),
        }).then(function (response) {
            return response.json();
        });
    }

    function applyCompileResult(result) {
        if (!result || typeof result.ok === "undefined") {
            setStatus(errorMessage("Unexpected response"), true);
            return;
        }
        if (result.html) {
            setPreview(result.html);
        } else if (result.ok) {
            setPreview("");
        }
        var messages = [];
        if (result.error) {
            messages.push(result.error);
            setStatus(errorMessage(result.error), true);
        } else {
            setStatus("");
        }
        if (result.warnings) {
            messages = messages.concat(result.warnings);
        }
        showDiagnostics(messages);
    }

    function compile() {
        if (compiling) {
            compileAgain = true;
            return;
        }
        compiling = true;
        postJson(cfg.compileUrl, {
            source: source(),
            source_format: currentFormat(),
        })
            .then(function (result) {
                applyCompileResult(result);
            })
            .catch(function (error) {
                setStatus(errorMessage(String(error)), true);
            })
            .then(function () {
                compiling = false;
                if (compileAgain) {
                    compileAgain = false;
                    compile();
                }
            });
    }

    function scheduleCompile() {
        if (compileTimer) {
            window.clearTimeout(compileTimer);
        }
        compileTimer = window.setTimeout(compile, 300);
    }

    if (formatEl) {
        formatEl.value = cfg.sourceFormat || "html";
        formatEl.addEventListener("change", function () {
            editor.dispatch({
                effects: languageCompartment.reconfigure(
                    formatExtensions(currentFormat())
                ),
            });
            scheduleCompile();
        });
    }

    var deviceButtons = document.querySelectorAll(
        ".device-switch [data-device]"
    );
    Array.prototype.forEach.call(deviceButtons, function (button) {
        button.addEventListener("click", function () {
            Array.prototype.forEach.call(deviceButtons, function (other) {
                other.classList.toggle("active", other === button);
            });
            if (previewWrap) {
                previewWrap.classList.toggle(
                    "is-mobile",
                    button.getAttribute("data-device") === "mobile"
                );
            }
        });
    });

    if (saveButton) {
        saveButton.addEventListener("click", function () {
            saveButton.disabled = true;
            setStatus(labels.saving || "Saving...");
            postJson(cfg.saveUrl, {
                source: source(),
                source_format: currentFormat(),
            })
                .then(function (result) {
                    if (result && result.ok) {
                        if (result.html) {
                            setPreview(result.html);
                        }
                        showDiagnostics(result.warnings || []);
                        setStatus(labels.saved || "Saved");
                        return;
                    }
                    var message = (result && result.error) || "?";
                    showDiagnostics(
                        [message].concat((result && result.warnings) || [])
                    );
                    setStatus(errorMessage(message), true);
                })
                .catch(function (error) {
                    setStatus(errorMessage(String(error)), true);
                })
                .then(function () {
                    saveButton.disabled = false;
                });
        });
    }

    if (testButton) {
        testButton.addEventListener("click", function () {
            var to = window.prompt(
                labels.testPrompt || "Send a test email to:",
                cfg.testEmail || ""
            );
            if (!to) {
                return;
            }
            setStatus(labels.sendingTest || "Sending...");
            fetch(cfg.testSendUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-CSRFToken": cfg.csrfToken,
                },
                body: new URLSearchParams({ to_email: to }).toString(),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        return { ok: response.ok, data: data };
                    });
                })
                .then(function (result) {
                    if (result.ok) {
                        setStatus(
                            fill(
                                labels.testSent || "Test email sent to %(to)s",
                                "to",
                                result.data.to || to
                            )
                        );
                    } else {
                        setStatus(errorMessage(result.data.error), true);
                    }
                })
                .catch(function (error) {
                    setStatus(errorMessage(String(error)), true);
                });
        });
    }

    compile();
})();
