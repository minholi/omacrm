/* Visual builders for the admin authoring editors.
 *
 * Each builder is registered through window.OmaEditors.registerBuilder(kind,
 * fn) and receives (value, ctx) where value is the parsed JSON declaration
 * and ctx.onChange(root) writes an updated declaration back to the editor.
 * Builders mutate the parsed tree in place: unknown keys, unknown action
 * types and unknown condition nodes are preserved and shown as raw JSON.
 */
(function () {
    "use strict";

    if (!window.OmaEditors) {
        return;
    }

    var registry = window.OmaEditors;

    var ACTION_LABELS = {
        set_field: "Set field",
        notify: "Notify assigned user",
        create_record: "Create record",
        send_email: "Send email",
        webhook: "Call webhook",
        update_related: "Update related records",
        wait: "Wait",
        branch: "Branch",
    };

    var GROUP_TYPES = ["and", "or", "not"];
    var WAIT_MODES = [
        { value: "duration", label: "Wait a duration" },
        { value: "until_date_field", label: "Wait until a date field" },
        { value: "until_condition", label: "Wait until a condition" },
    ];
    var LEAD_FIELD_TYPES = ["varchar", "text", "email", "phone", "url", "enum"];

    function classString(name, fallback) {
        var classes = registry.classes || {};
        return classes[name] || fallback || "";
    }

    function controlClass(name, extra) {
        return classString(name) + " " + (extra || "");
    }

    function el(tag, attrs, children) {
        var node = document.createElement(tag);
        Object.keys(attrs || {}).forEach(function (key) {
            if (key === "class") {
                node.className = attrs[key];
            } else if (key === "text") {
                node.textContent = attrs[key];
            } else if (attrs[key] !== null && attrs[key] !== undefined) {
                node.setAttribute(key, attrs[key]);
            }
        });
        (children || []).forEach(function (child) {
            if (!child) {
                return;
            }
            node.appendChild(
                typeof child === "string"
                    ? document.createTextNode(child)
                    : child
            );
        });
        return node;
    }

    function row(children, extra) {
        return el(
            "div",
            {
                class:
                    "flex flex-row items-center gap-2 " + (extra || ""),
            },
            children
        );
    }

    function card(children, extra) {
        return el(
            "div",
            {
                class:
                    "flex flex-col gap-2 border border-base-200 rounded-default " +
                    "p-3 dark:border-base-800 " +
                    (extra || ""),
            },
            children
        );
    }

    function button(label, onClick, extra) {
        var node = el("button", {
            type: "button",
            class: controlClass("button", extra),
            text: label,
        });
        node.addEventListener("click", onClick);
        return node;
    }

    function iconButton(icon, title, onClick) {
        var node = el("button", {
            type: "button",
            title: title,
            class:
                "material-symbols-outlined md-18 text-base-400 px-1.5 py-1 " +
                "rounded-default cursor-pointer hover:bg-base-100/80 " +
                "hover:text-base-700 dark:hover:bg-base-800/80 " +
                "dark:hover:text-base-200",
            text: icon,
        });
        node.addEventListener("click", onClick);
        return node;
    }

    function textInput(value, onChange, attrs) {
        var node = el("input", {
            type: (attrs && attrs.type) || "text",
            value: value === null || value === undefined ? "" : String(value),
            class: controlClass(
                "input",
                "grow min-w-0 " + ((attrs && attrs.class) || "")
            ),
            placeholder: attrs && attrs.placeholder,
        });
        node.addEventListener("input", function () {
            onChange(node.value);
        });
        return node;
    }

    function textarea(value, onChange, rows) {
        var node = el("textarea", {
            rows: rows || 3,
            class: controlClass("textarea", "grow min-w-0"),
        });
        node.value = value === null || value === undefined ? "" : String(value);
        node.addEventListener("input", function () {
            onChange(node.value);
        });
        return node;
    }

    function select(options, value, onChange, extra) {
        var node = el("select", {
            class: controlClass("select", "grow min-w-0 " + (extra || "")),
        });
        options.forEach(function (option) {
            var item = el("option", {
                value: option.value,
                text: option.label,
            });
            if (String(option.value) === String(value)) {
                item.selected = true;
            }
            node.appendChild(item);
        });
        node.addEventListener("change", function () {
            onChange(node.value);
        });
        return node;
    }

    function fieldOptions(fields, includeBlank) {
        var options = includeBlank
            ? [{ value: "", label: "— field —" }]
            : [];
        (fields || []).forEach(function (field) {
            options.push({
                value: field.name,
                label: field.label
                    ? field.label + " (" + field.name + ")"
                    : field.name,
            });
        });
        return options;
    }

    function jsonBlock(value) {
        var pre = el("pre", {
            class:
                "text-xs overflow-x-auto bg-base-50 rounded-default p-2 " +
                "dark:bg-base-900",
        });
        pre.textContent = JSON.stringify(value, null, 2);
        return pre;
    }

    function fieldFor(ctx, name) {
        var found = null;
        (ctx.fields || []).forEach(function (field) {
            if (field.name === name) {
                found = field;
            }
        });
        return found;
    }

    function isNumeric(type) {
        return (
            type === "int" ||
            type === "number" ||
            type === "float" ||
            type === "decimal" ||
            type === "currency"
        );
    }

    function valueEditor(field, value, onChange) {
        var type = field ? field.type : "";
        if (type === "bool") {
            return select(
                [
                    { value: "", label: "—" },
                    { value: "true", label: "True" },
                    { value: "false", label: "False" },
                ],
                value === true ? "true" : value === false ? "false" : "",
                function (next) {
                    onChange(next === "" ? null : next === "true");
                }
            );
        }
        if (type === "enum" && field.choices && field.choices.length) {
            return select(
                [{ value: "", label: "—" }].concat(field.choices),
                value === null || value === undefined ? "" : value,
                function (next) {
                    onChange(next === "" ? null : next);
                }
            );
        }
        if (type === "multiEnum") {
            var selected = [];
            (Array.isArray(value) ? value : []).forEach(function (item) {
                selected.push(String(item));
            });
            var multi = el("select", {
                multiple: "multiple",
                size: "4",
                class: controlClass("select", "grow min-w-0 py-1"),
            });
            (field.choices || []).forEach(function (choice) {
                var item = el("option", {
                    value: choice.value,
                    text: choice.label,
                });
                if (selected.indexOf(String(choice.value)) !== -1) {
                    item.selected = true;
                }
                multi.appendChild(item);
            });
            multi.addEventListener("change", function () {
                onChange(
                    Array.prototype.map.call(
                        multi.selectedOptions,
                        function (option) {
                            return option.value;
                        }
                    )
                );
            });
            return multi;
        }
        if (isNumeric(type)) {
            return textInput(value, function (next) {
                onChange(next === "" ? null : Number(next));
            }, { type: "number" });
        }
        if (type === "date" || type === "datetime") {
            return textInput(value, function (next) {
                onChange(next || null);
            }, { type: type === "date" ? "date" : "datetime-local" });
        }
        if (type === "link" || type === "linkMultiple" || type === "foreign") {
            return textInput(value, function (next) {
                onChange(next === "" ? null : next);
            }, { placeholder: "record id" });
        }
        return textInput(value, function (next) {
            onChange(next === "" ? null : next);
        }, {});
    }

    function replaceList(list, oldItem, newItem) {
        var index = list.indexOf(oldItem);
        if (index !== -1) {
            list.splice(index, 1, newItem);
        }
    }

    function move(list, index, delta) {
        var target = index + delta;
        if (target < 0 || target >= list.length) {
            return false;
        }
        var item = list.splice(index, 1)[0];
        list.splice(target, 0, item);
        return true;
    }

    /* ------------------------------------------------------------------ */
    /* Condition builder (DynamicLogic.condition)                          */
    /* ------------------------------------------------------------------ */

    function leafOperatorOptions(ctx) {
        var options = [];
        (ctx.operators || []).forEach(function (name) {
            if (GROUP_TYPES.indexOf(name) === -1) {
                options.push({ value: name, label: name });
            }
        });
        return options;
    }

    function defaultLeaf() {
        return { type: "equals", attribute: "", value: "" };
    }

    function conditionNode(node, ctx, root, parentList) {
        if (!node || typeof node !== "object" || Array.isArray(node)) {
            return rawNode(node, root, ctx, parentList);
        }
        if (GROUP_TYPES.indexOf(node.type) !== -1) {
            return groupNode(node, ctx, root, parentList);
        }
        if (node.type) {
            return leafNode(node, ctx, root, parentList);
        }
        return rawNode(node, root, ctx, parentList);
    }

    function removeButton(root, ctx, parentList, node) {
        if (!parentList) {
            return null;
        }
        return iconButton("delete", "Remove", function () {
            var index = parentList.indexOf(node);
            if (index !== -1) {
                parentList.splice(index, 1);
            }
            ctx.structural(root);
        });
    }

    function groupNode(node, ctx, root, parentList) {
        var wrapper = card([]);
        var header = row([]);
        header.appendChild(
            select(
                GROUP_TYPES.map(function (name) {
                    return { value: name, label: name };
                }),
                node.type,
                function (next) {
                    node.type = next;
                    if (next === "not") {
                        node.value = Array.isArray(node.value)
                            ? node.value[0] || defaultLeaf()
                            : node.value || defaultLeaf();
                    } else if (!Array.isArray(node.value)) {
                        node.value = node.value ? [node.value] : [];
                    }
                    ctx.structural(root);
                }
            )
        );
        var remove = removeButton(root, ctx, parentList, node);
        if (remove) {
            header.appendChild(remove);
        }
        wrapper.appendChild(header);

        if (node.type === "not") {
            var child =
                node.value && typeof node.value === "object"
                    ? node.value
                    : defaultLeaf();
            node.value = child;
            wrapper.appendChild(conditionNode(child, ctx, root, null));
        } else {
            if (!Array.isArray(node.value)) {
                node.value = [];
            }
            node.value.forEach(function (child) {
                wrapper.appendChild(
                    conditionNode(child, ctx, root, node.value)
                );
            });
            wrapper.appendChild(
                row([
                    button("+ condition", function () {
                        node.value.push(defaultLeaf());
                        ctx.structural(root);
                    }),
                    button("+ group", function () {
                        node.value.push({ type: "and", value: [] });
                        ctx.structural(root);
                    }),
                ])
            );
        }
        return wrapper;
    }

    function leafNode(node, ctx, root, parentList) {
        var wrapper = card([]);
        var header = row([]);
        var operators = leafOperatorOptions(ctx);
        if (!node.type || !operators.some(function (o) { return o.value === node.type; })) {
            operators = operators.concat([{ value: node.type, label: node.type }]);
        }
        header.appendChild(
            select(operators, node.type, function (next) {
                node.type = next;
                ctx.structural(root);
            })
        );
        var remove = removeButton(root, ctx, parentList, node);
        if (remove) {
            header.appendChild(remove);
        }
        wrapper.appendChild(header);

        var body = row([]);
        body.appendChild(
            select(
                fieldOptions(ctx.fields, true),
                node.attribute,
                function (next) {
                    node.attribute = next;
                    ctx.structural(root);
                }
            )
        );
        var field = fieldFor(ctx, node.attribute);
        if (node.type === "in" || node.type === "notIn") {
            var listValue = Array.isArray(node.value)
                ? node.value.join(", ")
                : node.value || "";
            body.appendChild(
                textInput(listValue, function (next) {
                    node.value = next
                        .split(",")
                        .map(function (item) {
                            return item.trim();
                        })
                        .filter(function (item) {
                            return item !== "";
                        });
                    ctx.onChange(root);
                }, { placeholder: "comma-separated values" })
            );
        } else {
            body.appendChild(
                valueEditor(field, node.value, function (next) {
                    node.value = next;
                    ctx.onChange(root);
                })
            );
        }
        wrapper.appendChild(body);
        return wrapper;
    }

    function rawNode(node, root, ctx, parentList) {
        var wrapper = card([]);
        var header = row([
            el("span", {
                class: classString("subtle"),
                text: "Raw JSON",
            }),
        ]);
        var remove = parentList
            ? iconButton("delete", "Remove", function () {
                  var index = parentList.indexOf(node);
                  if (index !== -1) {
                      parentList.splice(index, 1);
                  }
                  ctx.structural(root);
              })
            : null;
        if (remove) {
            header.appendChild(remove);
        }
        wrapper.appendChild(header);
        wrapper.appendChild(jsonBlock(node));
        return wrapper;
    }

    function buildCondition(value, ctx) {
        var root =
            value && typeof value === "object" && !Array.isArray(value)
                ? value
                : {};
        return conditionNode(root, ctx, root, null);
    }

    /* ------------------------------------------------------------------ */
    /* Step builder (Workflow.actions)                                     */
    /* ------------------------------------------------------------------ */

    function actionLabel(type) {
        return ACTION_LABELS[type] || type;
    }

    function actionTypeOptions() {
        return Object.keys(ACTION_LABELS).map(function (type) {
            return { value: type, label: actionLabel(type) };
        });
    }

    function stepCard(action, ctx, root, list, index) {
        var wrapper = card([]);
        var header = row([]);
        header.appendChild(
            select(actionTypeOptions(), action.type, function (next) {
                list.splice(index, 1, { type: next });
                ctx.structural(root);
            })
        );
        header.appendChild(
            iconButton("arrow_upward", "Move up", function () {
                if (move(list, index, -1)) {
                    ctx.structural(root);
                }
            })
        );
        header.appendChild(
            iconButton("arrow_downward", "Move down", function () {
                if (move(list, index, 1)) {
                    ctx.structural(root);
                }
            })
        );
        header.appendChild(
            iconButton("delete", "Remove", function () {
                list.splice(index, 1);
                ctx.structural(root);
            })
        );
        wrapper.appendChild(header);

        var body = actionBody(action, ctx, root);
        if (body) {
            wrapper.appendChild(body);
        }
        return wrapper;
    }

    function actionBody(action, ctx, root) {
        var type = action.type;

        if (type === "set_field") {
            return card([
                row([
                    select(
                        fieldOptions(
                            ctx.fields.filter(function (field) {
                                return !field.custom;
                            }),
                            true
                        ),
                        action.field,
                        function (next) {
                            action.field = next;
                            ctx.structural(root);
                        }
                    ),
                ]),
                row([
                    valueEditor(fieldFor(ctx, action.field), action.value, function (next) {
                        action.value = next;
                        ctx.onChange(root);
                    }),
                ]),
            ], "bg-base-50 dark:bg-base-900");
        }

        if (type === "notify") {
            return card([
                textInput(action.message, function (next) {
                    action.message = next;
                    ctx.onChange(root);
                }, { placeholder: "message" }),
                row([
                    select(
                        fieldOptions(
                            ctx.fields.filter(function (field) {
                                return !field.custom;
                            }),
                            true
                        ),
                        action.user_field,
                        function (next) {
                            action.user_field = next || undefined;
                            ctx.onChange(root);
                        }
                    ),
                ]),
            ], "bg-base-50 dark:bg-base-900");
        }

        if (type === "create_record") {
            return card([
                row([
                    select(
                        (ctx.entityTypes || []).map(function (entityType) {
                            return {
                                value: entityType.value,
                                label: entityType.label,
                            };
                        }),
                        action.entity_type,
                        function (next) {
                            action.entity_type = next;
                            ctx.onChange(root);
                        }
                    ),
                ]),
                textarea(
                    action.values
                        ? JSON.stringify(action.values, null, 2)
                        : "",
                    function (next) {
                        var parsed = parseJSONText(next);
                        if (parsed !== undefined) {
                            action.values = parsed;
                            ctx.onChange(root);
                        }
                    },
                    4
                ),
            ], "bg-base-50 dark:bg-base-900");
        }

        if (type === "send_email") {
            return card([
                textInput(action.to, function (next) {
                    action.to = next;
                    ctx.onChange(root);
                }, { placeholder: "to (field name or email)" }),
                textInput(action.subject, function (next) {
                    action.subject = next;
                    ctx.onChange(root);
                }, { placeholder: "subject" }),
                textarea(action.body, function (next) {
                    action.body = next;
                    ctx.onChange(root);
                }, 4),
            ], "bg-base-50 dark:bg-base-900");
        }

        if (type === "webhook") {
            return card([
                textInput(action.webhook_id, function (next) {
                    action.webhook_id = next === "" ? null : Number(next);
                    ctx.onChange(root);
                }, { type: "number", placeholder: "webhook id" }),
            ], "bg-base-50 dark:bg-base-900");
        }

        if (type === "update_related") {
            return card([
                textInput(action.relation, function (next) {
                    action.relation = next;
                    ctx.onChange(root);
                }, { placeholder: "relation name" }),
                textarea(
                    action.fields ? JSON.stringify(action.fields, null, 2) : "",
                    function (next) {
                        var parsed = parseJSONText(next);
                        if (parsed !== undefined) {
                            action.fields = parsed;
                            ctx.onChange(root);
                        }
                    },
                    4
                ),
            ], "bg-base-50 dark:bg-base-900");
        }

        if (type === "wait") {
            var mode =
                (action.duration && "duration") ||
                (action.until_date_field && "until_date_field") ||
                (action.until_condition && "until_condition") ||
                "duration";
            var modeRow = row([
                select(WAIT_MODES, mode, function (next) {
                    delete action.duration;
                    delete action.until_date_field;
                    delete action.until_condition;
                    delete action.poll_interval;
                    delete action.timeout;
                    if (next === "duration") {
                        action.duration = "3d";
                    } else if (next === "until_date_field") {
                        action.until_date_field = "";
                    } else {
                        action.until_condition = "";
                        action.poll_interval = "1h";
                        action.timeout = "30d";
                    }
                    ctx.structural(root);
                }),
            ]);
            var fields = [modeRow];
            if (mode === "duration") {
                fields.push(
                    textInput(action.duration, function (next) {
                        action.duration = next;
                        ctx.onChange(root);
                    }, { placeholder: "e.g. 3d" })
                );
            } else if (mode === "until_date_field") {
                fields.push(
                    select(
                        fieldOptions(ctx.fields, true),
                        action.until_date_field,
                        function (next) {
                            action.until_date_field = next;
                            ctx.onChange(root);
                        }
                    )
                );
            } else {
                fields.push(
                    textInput(
                        action.until_condition,
                        function (next) {
                            action.until_condition = next;
                            ctx.onChange(root);
                        },
                        { placeholder: "condition, e.g. status == 'Completed'" }
                    ),
                    row([
                        textInput(action.poll_interval, function (next) {
                            action.poll_interval = next;
                            ctx.onChange(root);
                        }, { placeholder: "poll interval" }),
                        textInput(action.timeout, function (next) {
                            action.timeout = next;
                            ctx.onChange(root);
                        }, { placeholder: "timeout" }),
                    ])
                );
            }
            return card(fields, "bg-base-50 dark:bg-base-900");
        }

        if (type === "branch") {
            if (!Array.isArray(action.then)) {
                action.then = [];
            }
            if (action.else && !Array.isArray(action.else)) {
                action.else = [];
            }
            var branchBody = [
                textInput(action.condition, function (next) {
                    action.condition = next;
                    ctx.onChange(root);
                }, { placeholder: "condition, e.g. stage == 'Proposal'" }),
                el("span", {
                    class: classString("subtle"),
                    text: "Then",
                }),
                stepsList(action.then, ctx, root),
            ];
            if (action.else) {
                branchBody.push(
                    el("span", {
                        class: classString("subtle"),
                        text: "Else",
                    }),
                    stepsList(action.else, ctx, root)
                );
            } else {
                branchBody.push(
                    button("+ else branch", function () {
                        action.else = [];
                        ctx.structural(root);
                    })
                );
            }
            return card(branchBody, "bg-base-50 dark:bg-base-900");
        }

        return rawNode(action, root, ctx, null);
    }

    function stepsList(list, ctx, root) {
        var wrapper = el("div", { class: "flex flex-col gap-2" });
        list.forEach(function (action, index) {
            wrapper.appendChild(stepCard(action, ctx, root, list, index));
        });
        wrapper.appendChild(
            row([
                button("+ step", function () {
                    list.push({ type: "notify", message: "" });
                    ctx.structural(root);
                }),
            ])
        );
        return wrapper;
    }

    function buildSteps(value, ctx) {
        if (!Array.isArray(value)) {
            return el("p", {
                class: classString("subtle"),
                text: "Actions must be a JSON list.",
            });
        }
        return stepsList(value, ctx, value);
    }

    /* ------------------------------------------------------------------ */
    /* Custom-field params builder                                         */
    /* ------------------------------------------------------------------ */

    function parseJSONText(text) {
        try {
            return JSON.parse(text);
        } catch (error) {
            return undefined;
        }
    }

    function paramRow(root, ctx, key, label, attrs) {
        var value = root[key];
        return row([
            el("span", {
                class: "text-sm text-base-500 w-24",
                text: label,
            }),
            textInput(value, function (next) {
                if (next === "") {
                    delete root[key];
                } else {
                    root[key] = attrs && attrs.number ? Number(next) : next;
                }
                ctx.onChange(root);
            }, attrs || {}),
        ]);
    }

    function choicesEditor(root, ctx) {
        if (!Array.isArray(root.choices)) {
            root.choices = [];
        }
        var wrapper = el("div", { class: "flex flex-col gap-2" });
        wrapper.appendChild(
            el("span", {
                class: classString("subtle"),
                text: "Choices",
            })
        );
        root.choices.forEach(function (choice, index) {
            var value = Array.isArray(choice) ? choice[0] : choice;
            var label = Array.isArray(choice) ? choice[1] : choice;
            wrapper.appendChild(
                row([
                    textInput(value, function (next) {
                        root.choices[index] = [next, label];
                        ctx.onChange(root);
                    }, { placeholder: "value" }),
                    textInput(label, function (next) {
                        root.choices[index] = [value, next];
                        ctx.onChange(root);
                    }, { placeholder: "label" }),
                    iconButton("delete", "Remove", function () {
                        root.choices.splice(index, 1);
                        ctx.structural(root);
                    }),
                ])
            );
        });
        wrapper.appendChild(
            button("+ choice", function () {
                root.choices.push(["", ""]);
                ctx.structural(root);
            })
        );
        return wrapper;
    }

    function buildParams(value, ctx) {
        var root =
            value && typeof value === "object" && !Array.isArray(value)
                ? value
                : {};
        var fieldType = (ctx.context && ctx.context.field_type) || "varchar";
        var wrapper = el("div", { class: "flex flex-col gap-2" });
        var rendered = [];

        function addParam(key, label, attrs) {
            rendered.push(key);
            wrapper.appendChild(paramRow(root, ctx, key, label, attrs));
        }

        if (fieldType === "enum" || fieldType === "multiEnum") {
            rendered.push("choices");
            wrapper.appendChild(choicesEditor(root, ctx));
        }
        if (fieldType === "number") {
            addParam("prefix", "Prefix");
            addParam("padding", "Padding", { type: "number", number: true });
        }
        if (fieldType === "foreign") {
            addParam("link", "Link");
            addParam("field", "Field");
        }

        addParam("default", "Default");
        addParam("max_length", "Max length", { type: "number", number: true });
        addParam("tooltip", "Tooltip");

        var unknown = {};
        Object.keys(root).forEach(function (key) {
            if (rendered.indexOf(key) === -1) {
                unknown[key] = root[key];
            }
        });
        if (Object.keys(unknown).length) {
            wrapper.appendChild(
                el("span", {
                    class: classString("subtle"),
                    text: "Other parameters (JSON)",
                })
            );
            wrapper.appendChild(jsonBlock(unknown));
        }
        return wrapper;
    }

    /* ------------------------------------------------------------------ */
    /* Lead-capture field checklist                                        */
    /* ------------------------------------------------------------------ */

    function buildChecklist(value, ctx) {
        var names = Array.isArray(value) ? value : [];
        var wrapper = el("div", { class: "flex flex-col gap-2" });
        var available = (ctx.fields || []).filter(function (field) {
            return LEAD_FIELD_TYPES.indexOf(field.type) !== -1;
        });

        if (!names.length) {
            wrapper.appendChild(
                el("p", {
                    class: classString("subtle"),
                    text: "No fields selected; the default capture fields are used.",
                })
            );
        }

        names.forEach(function (name, index) {
            wrapper.appendChild(
                row(
                    [
                        el("span", {
                            class: "grow " + classString("important", "text-sm"),
                            text: name,
                        }),
                        iconButton("arrow_upward", "Move up", function () {
                            if (move(names, index, -1)) {
                                ctx.structural(names);
                            }
                        }),
                        iconButton("arrow_downward", "Move down", function () {
                            if (move(names, index, 1)) {
                                ctx.structural(names);
                            }
                        }),
                        iconButton("delete", "Remove", function () {
                            names.splice(index, 1);
                            ctx.structural(names);
                        }),
                    ],
                    "border border-base-200 rounded-default px-2 py-1 " +
                        "dark:border-base-800"
                )
            );
        });

        var remaining = available.filter(function (field) {
            return names.indexOf(field.name) === -1;
        });
        if (remaining.length) {
            var picker = select(
                remaining.map(function (field) {
                    return {
                        value: field.name,
                        label: field.label || field.name,
                    };
                }),
                remaining[0].name,
                function () {}
            );
            wrapper.appendChild(
                row([
                    picker,
                    button("+ add field", function () {
                        names.push(picker.value);
                        ctx.structural(names);
                    }),
                ])
            );
        }
        return wrapper;
    }

    /* ------------------------------------------------------------------ */
    /* Layout data builder (list columns / detail sections)                */
    /* ------------------------------------------------------------------ */

    function nameList(names, available, changed) {
        var wrapper = el("div", { class: "flex flex-col gap-1" });
        names.forEach(function (name, index) {
            var known = available.some(function (field) {
                return field.name === name;
            });
            wrapper.appendChild(
                row(
                    [
                        el("span", {
                            class:
                                "grow " +
                                (known
                                    ? classString("important", "text-sm")
                                    : classString("subtle")),
                            text: known ? name : name + " (unknown)",
                        }),
                        iconButton("arrow_upward", "Move up", function () {
                            if (move(names, index, -1)) {
                                changed();
                            }
                        }),
                        iconButton("arrow_downward", "Move down", function () {
                            if (move(names, index, 1)) {
                                changed();
                            }
                        }),
                        iconButton("delete", "Remove", function () {
                            names.splice(index, 1);
                            changed();
                        }),
                    ],
                    "border border-base-200 rounded-default px-2 py-1 " +
                        "dark:border-base-800"
                )
            );
        });
        var remaining = available.filter(function (field) {
            return names.indexOf(field.name) === -1;
        });
        if (remaining.length) {
            var picker = select(
                remaining.map(function (field) {
                    return {
                        value: field.name,
                        label: field.label || field.name,
                    };
                }),
                remaining[0].name,
                function () {}
            );
            wrapper.appendChild(
                row([
                    picker,
                    button("+ add field", function () {
                        names.push(picker.value);
                        changed();
                    }),
                ])
            );
        }
        return wrapper;
    }

    function rawElement(value, remove) {
        var actions = [jsonBlock(value)];
        if (remove) {
            actions.push(button("Remove", remove));
        }
        return card(actions);
    }

    function buildLayout(value, ctx) {
        if (!Array.isArray(value)) {
            return el("p", {
                class: classString("subtle"),
                text: "Layout data must be a JSON list.",
            });
        }
        var layoutName = (ctx.context && ctx.context.layout_name) || "list";
        var available = ctx.fields || [];
        var wrapper = el("div", { class: "flex flex-col gap-2" });

        if (layoutName === "list") {
            wrapper.appendChild(
                el("span", { class: classString("subtle"), text: "Columns" })
            );
            wrapper.appendChild(
                nameList(value, available, function () {
                    ctx.structural(value);
                })
            );
            return wrapper;
        }

        value.forEach(function (section, index) {
            if (!section || typeof section !== "object" || Array.isArray(section)) {
                wrapper.appendChild(
                    rawElement(section, function () {
                        value.splice(index, 1);
                        ctx.structural(value);
                    })
                );
                return;
            }
            if (!Array.isArray(section.fields)) {
                section.fields = [];
            }
            wrapper.appendChild(
                card([
                    row([
                        textInput(
                            section.title,
                            function (next) {
                                section.title = next;
                                ctx.onChange(value);
                            },
                            { placeholder: "Section title" }
                        ),
                        iconButton("arrow_upward", "Move up", function () {
                            if (move(value, index, -1)) {
                                ctx.structural(value);
                            }
                        }),
                        iconButton("arrow_downward", "Move down", function () {
                            if (move(value, index, 1)) {
                                ctx.structural(value);
                            }
                        }),
                        iconButton("delete", "Remove section", function () {
                            value.splice(index, 1);
                            ctx.structural(value);
                        }),
                    ]),
                    nameList(section.fields, available, function () {
                        ctx.structural(value);
                    }),
                ])
            );
        });
        wrapper.appendChild(
            button("+ section", function () {
                value.push({ title: "", fields: [] });
                ctx.structural(value);
            })
        );
        return wrapper;
    }

    /* ------------------------------------------------------------------ */
    /* Reminders builder ([{type, seconds}])                               */
    /* ------------------------------------------------------------------ */

    function formatSeconds(seconds) {
        var value = parseInt(seconds, 10);
        if (!isFinite(value) || value <= 0) {
            if (value === 0) {
                return "0m";
            }
            return "";
        }
        var units = [
            ["w", 604800],
            ["d", 86400],
            ["h", 3600],
            ["m", 60],
        ];
        for (var index = 0; index < units.length; index += 1) {
            if (value % units[index][1] === 0) {
                return value / units[index][1] + units[index][0];
            }
        }
        return value + "s";
    }

    function parseLeadTime(text) {
        var match = String(text || "")
            .trim()
            .match(/^(\d+)\s*([mhdw])?$/i);
        if (!match) {
            return undefined;
        }
        var sizes = { m: 60, h: 3600, d: 86400, w: 604800 };
        var unit = (match[2] || "m").toLowerCase();
        return parseInt(match[1], 10) * sizes[unit];
    }

    function buildReminders(value, ctx) {
        if (!Array.isArray(value)) {
            return el("p", {
                class: classString("subtle"),
                text: "Reminders must be a JSON list.",
            });
        }
        var wrapper = el("div", { class: "flex flex-col gap-2" });
        value.forEach(function (item, index) {
            if (!item || typeof item !== "object" || Array.isArray(item)) {
                wrapper.appendChild(
                    rawElement(item, function () {
                        value.splice(index, 1);
                        ctx.structural(value);
                    })
                );
                return;
            }
            wrapper.appendChild(
                card([
                    row([
                        select(
                            [
                                { value: "Popup", label: "Popup" },
                                { value: "Email", label: "Email" },
                            ],
                            item.type || "Popup",
                            function (next) {
                                item.type = next;
                                ctx.onChange(value);
                            }
                        ),
                        textInput(
                            formatSeconds(item.seconds),
                            function (next) {
                                var seconds = parseLeadTime(next);
                                item.seconds =
                                    seconds === undefined ? next : seconds;
                                ctx.onChange(value);
                            },
                            { placeholder: "e.g. 15m, 1h, 2d" }
                        ),
                        iconButton("arrow_upward", "Move up", function () {
                            if (move(value, index, -1)) {
                                ctx.structural(value);
                            }
                        }),
                        iconButton("arrow_downward", "Move down", function () {
                            if (move(value, index, 1)) {
                                ctx.structural(value);
                            }
                        }),
                        iconButton("delete", "Remove", function () {
                            value.splice(index, 1);
                            ctx.structural(value);
                        }),
                    ]),
                ])
            );
        });
        wrapper.appendChild(
            button("+ reminder", function () {
                value.push({ type: "Popup", seconds: 3600 });
                ctx.structural(value);
            })
        );
        return wrapper;
    }

    /* ------------------------------------------------------------------ */
    /* Recurrence builder ({frequency, interval, weekdays, count/until})   */
    /* ------------------------------------------------------------------ */

    var WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

    function recurrenceRow(label, control) {
        return row([
            el("span", {
                class: classString("subtle"),
                style: "min-width: 7rem",
                text: label,
            }),
            control,
        ]);
    }

    function buildRecurrence(value, ctx) {
        var root =
            value && typeof value === "object" && !Array.isArray(value)
                ? value
                : {};
        var wrapper = el("div", { class: "flex flex-col gap-2" });

        if (!Object.keys(root).length) {
            wrapper.appendChild(
                el("p", { class: classString("subtle"), text: "No recurrence." })
            );
            wrapper.appendChild(
                button("Enable recurrence", function () {
                    root.frequency = "weekly";
                    root.interval = 1;
                    ctx.structural(root);
                })
            );
            return wrapper;
        }

        var weekdays = Array.isArray(root.weekdays) ? root.weekdays : [];
        root.weekdays = weekdays;

        wrapper.appendChild(
            card([
                recurrenceRow(
                    "Frequency",
                    select(
                        [
                            { value: "daily", label: "Daily" },
                            { value: "weekly", label: "Weekly" },
                            { value: "monthly", label: "Monthly" },
                        ],
                        root.frequency || "weekly",
                        function (next) {
                            root.frequency = next;
                            ctx.structural(root);
                        }
                    )
                ),
                recurrenceRow(
                    "Interval",
                    textInput(
                        root.interval,
                        function (next) {
                            root.interval = next === "" ? 1 : Number(next);
                            ctx.onChange(root);
                        },
                        { type: "number" }
                    )
                ),
            ])
        );

        if (root.frequency === "weekly") {
            var daysRow = row([]);
            WEEKDAY_LABELS.forEach(function (label, day) {
                var box = el("label", {
                    class: "flex flex-row items-center gap-1 text-sm",
                });
                var input = el("input", { type: "checkbox" });
                input.checked = weekdays.indexOf(day) !== -1;
                input.addEventListener("change", function () {
                    var position = weekdays.indexOf(day);
                    if (input.checked && position === -1) {
                        weekdays.push(day);
                    }
                    if (!input.checked && position !== -1) {
                        weekdays.splice(position, 1);
                    }
                    weekdays.sort();
                    ctx.structural(root);
                });
                box.appendChild(input);
                box.appendChild(document.createTextNode(label));
                daysRow.appendChild(box);
            });
            wrapper.appendChild(daysRow);
        }

        var endMode = root.count ? "count" : root.until ? "until" : "never";
        wrapper.appendChild(
            recurrenceRow(
                "Ends",
                select(
                    [
                        { value: "never", label: "Never" },
                        { value: "count", label: "After occurrences" },
                        { value: "until", label: "On date" },
                    ],
                    endMode,
                    function (next) {
                        delete root.count;
                        delete root.until;
                        if (next === "count") {
                            root.count = 10;
                        }
                        if (next === "until") {
                            root.until = "";
                        }
                        ctx.structural(root);
                    }
                )
            )
        );
        if (endMode === "count") {
            wrapper.appendChild(
                recurrenceRow(
                    "Occurrences",
                    textInput(
                        root.count,
                        function (next) {
                            root.count = next === "" ? null : Number(next);
                            ctx.onChange(root);
                        },
                        { type: "number" }
                    )
                )
            );
        } else if (endMode === "until") {
            wrapper.appendChild(
                recurrenceRow(
                    "Until",
                    textInput(
                        root.until,
                        function (next) {
                            root.until = next;
                            ctx.onChange(root);
                        },
                        { type: "date" }
                    )
                )
            );
        }
        wrapper.appendChild(
            button("Remove recurrence", function () {
                Object.keys(root).forEach(function (key) {
                    delete root[key];
                });
                ctx.structural(root);
            })
        );
        return wrapper;
    }

    registry.registerBuilder("dynamic_logic", buildCondition);
    registry.registerBuilder("workflow_actions", buildSteps);
    registry.registerBuilder("custom_field", buildParams);
    registry.registerBuilder("lead_capture", buildChecklist);
    registry.registerBuilder("layout", buildLayout);
    registry.registerBuilder("reminders", buildReminders);
    registry.registerBuilder("recurrence", buildRecurrence);
})();
