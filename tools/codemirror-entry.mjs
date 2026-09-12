// Entry point do bundle vendorizado do CodeMirror 6 para o OmaCRM.
// Gera UM arquivo IIFE (window.OmaCodeMirror) — sem npm/CDN em runtime.
// Regerar com: tools/build-codemirror.sh
import { EditorView, keymap, lineNumbers } from "@codemirror/view";
import { EditorState, Compartment } from "@codemirror/state";
import { basicSetup } from "codemirror";
import { xml } from "@codemirror/lang-xml";
import { linter, lintGutter } from "@codemirror/lint";
import { autocompletion, completeFromList } from "@codemirror/autocomplete";
import { indentWithTab } from "@codemirror/commands";

window.OmaCodeMirror = {
  EditorView,
  EditorState,
  Compartment,
  basicSetup,
  xml,
  linter,
  lintGutter,
  autocompletion,
  completeFromList,
  keymap,
  lineNumbers,
  indentWithTab,
};
