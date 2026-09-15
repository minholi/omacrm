/* CodeMirror-backed admin editors for JSON and formula declarations.
 *
 * Progressive enhancement of a form textarea: the textarea stays the source
 * of truth for submission, the editor offers syntax highlighting, completion
 * from /admin/editor/metadata/<Entity>/ and live diagnostics from
 * /admin/editor/validate/. Without JavaScript the textarea keeps working.
 */
(function () {
    "use strict";

    if (!window.OmaCodeMirror) {
        return;
    }
    var CM = window.OmaCodeMirror;

    var ACTION_SNIPPETS = [
        { label: "set_field", apply: '{"type": "set_field", "field": "", "value": ""}' },
        { label: "notify", apply: '{"type": "notify", "message": ""}' },
        { label: "wait (duration)", apply: '{"type": "wait", "duration": "3d"}' },
        { label: "wait (until date field)", apply: '{"type": "wait", "until_date_field": ""}' },
        {
            label: "wait (until condition)",
            apply:
                '{"type": "wait", "until_condition": "", "poll_interval": "1h", ' +
                '"timeout": "30d"}',
        },
        {
            label: "branch",
            apply: '{"type": "branch", "condition": "", "then": [], "else": []}',
        },
        {
            label: "create_record",
            apply: '{"type": "create_record", "entity_type": "", "values": {}}',
        },
        {
            label: "send_email",
            apply: '{"type": "send_email", "to": "", "subject": "", "body": ""}',
        },
        { label: "webhook", apply: '{"type": "webhook", "webhook_id": 1}' },
        {
            label: "update_related",
            apply: '{"type": "update_related", "relation": "", "fields": {}}',
        },
    ];

    var PARAM_SNIPPETS = [
        { label: "choices", apply: '"choices": [["value", "Label"]]' },
        { label: "prefix", apply: '"prefix": "PRJ-"' },
        { label: "padding", apply: '"padding": 4' },
        { label: "link", apply: '"link": ""' },
        { label: "field", apply: '"field": ""' },
        { label: "max_length", apply: '"max_length": 255' },
        { label: "default", apply: '"default": ""' },
        { label: "tooltip", apply: '"tooltip": ""' },
    ];

    var FORMULA_LANGUAGE = CM.StreamLanguage.define({
        token: function (stream) {
            if (stream.match(/^#.*/)) {
                return "comment";
            }
            if (stream.match(/^'[^']*'/) || stream.match(/^"[^"]*"/)) {
                return "string";
            }
            if (stream.match(/^\d+(\.\d+)?/)) {
                return "number";
            }
            if (
                stream.match(
                    /^(True|False|None|and|or|not|in|is|if|else)\b/
                )
            ) {
                return "keyword";
            }
            if (stream.match(/^[A-Za-z_][A-Za-z0-9_]*/)) {
                return "variableName";
            }
            stream.next();
            return null;
        },
    });

    function ready(fn) {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", fn);
        } else {
            fn();
        }
    }

    function csrfToken() {
        var input = document.querySelector("input[name=csrfmiddlewaretoken]");
        if (input) {
            return input.value;
        }
        var match = document.cookie.match(/(^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[2]) : "";
    }

    function darkMode() {
        return document.documentElement.classList.contains("dark");
    }

    function parseJSON(text) {
        try {
            return JSON.parse(text);
        } catch (error) {
            return undefined;
        }
    }

    function postJSON(url, payload) {
        return fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken(),
            },
            body: JSON.stringify(payload),
        }).then(function (response) {
            if (!response.ok) {
                throw new Error("HTTP " + response.status);
            }
            return response.json();
        });
    }

    function Editor(root) {
        this.root = root;
        this.textarea = root.querySelector("textarea");
        this.mount = root.querySelector("[data-editor-mount]");
        var configEl = root.querySelector('script[type="application/json"]');
        this.config = configEl ? parseJSON(configEl.textContent) || {} : {};
        this.metadata = null;
        this.editor = null;
    }

    Editor.prototype.entityType = function () {
        if (this.config.fixedEntity) {
            return this.config.fixedEntity;
        }
        if (!this.config.entityField) {
            return "";
        }
        var form = this.root.closest("form");
        var field = form ? form.elements.namedItem(this.config.entityField) : null;
        return field && field.value ? field.value : "";
    };

    Editor.prototype.loadMetadata = function () {
        var entityType = this.entityType();
        if (!entityType) {
            this.metadata = null;
            return Promise.resolve();
        }
        var url = String(this.config.metadataUrl || "").replace(
            "__entity__",
            encodeURIComponent(entityType)
        );
        var self = this;
        return fetch(url, { credentials: "same-origin" })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("HTTP " + response.status);
                }
                return response.json();
            })
            .then(function (payload) {
                self.metadata = payload;
            })
            .catch(function () {
                self.metadata = null;
            });
    };

    Editor.prototype.options = function (insideString) {
        var metadata = this.metadata || {};
        var options = [];
        var seen = {};
        var isJSON = this.config.mode !== "script";

        function add(label, type, detail, apply) {
            if (!label || seen[label]) {
                return;
            }
            seen[label] = true;
            var option = { label: label, type: type, detail: detail };
            if (apply) {
                option.apply = apply;
            }
            options.push(option);
        }

        function nameOption(value) {
            if (!isJSON) {
                return value;
            }
            return insideString ? value : '"' + value + '"';
        }

        (metadata.fields || []).forEach(function (field) {
            add(field.name, "property", field.type, nameOption(field.name));
        });
        (metadata.links || []).forEach(function (link) {
            add(
                link.name,
                "property",
                "link: " + link.target,
                nameOption(link.name)
            );
        });

        if (this.config.mode === "script") {
            (metadata.formulaHelpers || []).forEach(function (name) {
                add(name, "function", "formula");
            });
            return options;
        }

        var kind = this.config.kind;
        if (kind === "workflow_actions") {
            ACTION_SNIPPETS.forEach(function (snippet) {
                add(snippet.label, "keyword", "step", snippet.apply);
            });
            (metadata.actions || []).forEach(function (name) {
                add(name, "keyword", "action", nameOption(name));
            });
        }
        if (kind === "dynamic_logic") {
            (metadata.operators || []).forEach(function (name) {
                add(name, "keyword", "operator", nameOption(name));
            });
        }
        if (kind === "custom_field") {
            PARAM_SNIPPETS.forEach(function (snippet) {
                add(snippet.label, "keyword", "param", snippet.apply);
            });
        }
        return options;
    };

    Editor.prototype.completionSource = function () {
        var self = this;
        return function (context) {
            var word = context.matchBefore(/[\w]*/);
            if (!word || (word.from === word.to && !context.explicit)) {
                return null;
            }
            var before = context.state.sliceDoc(
                Math.max(0, word.from - 1),
                word.from
            );
            var insideString = before === '"' || before === "'";
            var options = self.options(insideString);
            if (!options.length) {
                return null;
            }
            return { from: word.from, options: options };
        };
    };

    Editor.prototype.diagnostic = function (message) {
        var length = this.editor.state.doc.length;
        return {
            from: 0,
            to: length,
            severity: "error",
            message: message,
        };
    };

    Editor.prototype.validate = function () {
        var self = this;
        var text = this.editor.state.doc.toString();
        var serverValue = text;

        if (this.config.mode === "json") {
            if (!text.trim()) {
                return Promise.resolve([]);
            }
            var parsed = parseJSON(text);
            if (parsed === undefined) {
                return Promise.resolve([this.diagnostic("Invalid JSON.")]);
            }
            serverValue = parsed;
        }

        var contextFields = {};
        var form = this.root.closest("form");
        (this.config.contextFields || []).forEach(function (name) {
            var field = form ? form.elements.namedItem(name) : null;
            if (field && typeof field.value === "string") {
                contextFields[name] = field.value;
            }
        });
        if (this.config.kind === "custom_field") {
            serverValue = {
                name: contextFields.name || "",
                field_type: contextFields.field_type || "varchar",
                params: serverValue,
            };
        } else if (this.config.kind === "formula") {
            serverValue = text;
        }

        return postJSON(this.config.validateUrl, {
            kind: this.config.kind,
            entity_type: this.entityType(),
            value: serverValue,
        })
            .then(function (payload) {
                return (payload.errors || []).map(function (error) {
                    var prefix = error.path ? error.path + ": " : "";
                    return self.diagnostic(prefix + error.message);
                });
            })
            .catch(function () {
                return [];
            });
    };

    Editor.prototype.sync = function () {
        this.textarea.value = this.editor.state.doc.toString();
    };

    Editor.prototype.start = function () {
        var self = this;
        var language =
            this.config.mode === "script"
                ? FORMULA_LANGUAGE
                : CM.json();
        var themeCompartment = new CM.Compartment();

        this.editor = new CM.EditorView({
            state: CM.EditorState.create({
                doc: this.textarea.value || "",
                extensions: [
                    CM.basicSetup,
                    themeCompartment.of(darkMode() ? CM.oneDark : []),
                    language,
                    CM.linter(function (view) {
                        return self.validate(view);
                    }, { delay: 500 }),
                    CM.autocompletion({
                        override: [this.completionSource()],
                    }),
                    CM.keymap.of([CM.indentWithTab]),
                    CM.EditorView.updateListener.of(function (update) {
                        if (update.docChanged) {
                            self.sync();
                        }
                    }),
                ],
            }),
            parent: this.mount,
        });

        this.textarea.hidden = true;
        this.mount.hidden = false;

        if (this.config.mode === "json") {
            var toolbar = document.createElement("div");
            toolbar.className = "flex justify-end mb-1";
            var formatButton = document.createElement("button");
            formatButton.type = "button";
            formatButton.className =
                "text-xs text-primary-600 hover:underline dark:text-primary-500";
            formatButton.textContent = "Format JSON";
            formatButton.addEventListener("click", function () {
                var parsed = parseJSON(self.editor.state.doc.toString());
                if (parsed === undefined) {
                    return;
                }
                var text = JSON.stringify(parsed, null, 2);
                self.editor.dispatch({
                    changes: {
                        from: 0,
                        to: self.editor.state.doc.length,
                        insert: text,
                    },
                });
            });
            toolbar.appendChild(formatButton);
            this.mount.parentNode.insertBefore(toolbar, this.mount);
        }

        if (window.MutationObserver) {
            var editorDark = darkMode();
            new MutationObserver(function () {
                var next = darkMode();
                if (next === editorDark) {
                    return;
                }
                editorDark = next;
                self.editor.dispatch({
                    effects: themeCompartment.reconfigure(
                        next ? CM.oneDark : []
                    ),
                });
            }).observe(document.documentElement, {
                attributes: true,
                attributeFilter: ["class"],
            });
        }

        var form = this.root.closest("form");
        if (form) {
            form.addEventListener("submit", function () {
                self.sync();
            });
            if (this.config.entityField) {
                var entityField = form.elements.namedItem(
                    this.config.entityField
                );
                if (entityField) {
                    entityField.addEventListener("change", function () {
                        self.loadMetadata();
                    });
                }
            }
        }

        this.loadMetadata();
    };

    ready(function () {
        var roots = document.querySelectorAll("[data-editor-root]");
        Array.prototype.forEach.call(roots, function (root) {
            try {
                new Editor(root).start();
            } catch (error) {
                /* Keep the plain textarea usable if the editor fails. */
            }
        });
    });
})();
