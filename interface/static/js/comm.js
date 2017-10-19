var ws = new WebSocket("ws://" + window.location.hostname + ":31415/")

// Breakpoints and markers
var asm_breakpoints = [];
var mem_highlights_r = [];
var mem_highlights_w = [];
var mem_breakpoints_r = [];
var mem_breakpoints_w = [];
var mem_breakpoints_rw = [];
var mem_breakpoints_e = [];
var mem_breakpoints_instr = [];
var line2addr = [];
var current_debugline = -1;
var next_debugline = -1;
var codeerrors = [];
var debug_marker = null;
var next_debug_marker = null;

ws.onerror = function (event) {
    displayErrorMsg("Erreur de connexion avec le simulateur.");
}

function displayErrorMsg(msg) {
    $("#message_bar").text(msg);
    $("#message_bar").slideDown("normal", "easeInOutBack");
}

ws.onmessage = function (event) {
	obj_list = JSON.parse(event.data);

    for (var idx in obj_list) {
        var obj = obj_list[idx];

        var element = document.getElementById(obj[0]);
        if (obj[0] == "disassembly") {
            $("#disassembly").html(obj[1]);
        } else if (element != null) {
            var target_value = obj[1];

            if ($.inArray("formatted_value", element.classList) >= 0) {
                format_ = $("#valueformat").val();
                if (format_ == "dec") {
                    target_value = parseInt(obj[1], 16);
                } else if (format_ == "decsign") {
                    target_value = parseInt(obj[1], 16);
                    if (target_value > Math.pow(2, 31) - 1) { target_value = target_value - Math.pow(2, 32); }
                } else if (format_ == "bin") {
                    target_value = parseInt(obj[1], 16).toString(2);
                }
                if (isNaN(target_value)) {
                    var target_value = obj[1];
                }
            }

            if (target_value == "False") { target_value = "Faux"; }
            if (target_value == "True") { target_value = "Vrai"; }

            $(element).val(target_value);
            $(element).prop("disabled", false);
        } else if (obj[0] == 'disable') {
            $("[name='" + obj[1] + "']").prop("disabled", true);
        } else if (obj[0] == 'edit_mode') {
            disableSim();
            $("#assemble").text("Démarrer").removeClass("assemble_edit");
            refreshBreakpoints();
        } else if (obj[0] == 'line2addr') {
            line2addr = obj[1];
            sendBreakpointsInstr();
        } else if (obj[0] == 'codeerror') {
            // row indices are 0-indexed
            codeerrors.push({row: obj[1], text: obj[2], type: "error"})
            editor.session.setAnnotations(codeerrors);
        } else if (obj[0] == 'asm_breakpoints') {
            asm_breakpoints.length = 0;
            editor.session.clearBreakpoints();
            for (var i = 0; i < obj[1].length; i++) {
                editor.session.setBreakpoint(obj[1][i]);
                asm_breakpoints[i] = obj[1][i];
            }
        } else if (obj[0] == 'nextline') {
            if (next_debug_marker !== null) { editor.session.removeMarker(next_debug_marker); }
            next_debug_marker = editor.session.addMarker(new aceRange(obj[1], 0, obj[1] + 1, 0), "next_debug_line", "text");
            next_debugline = obj[1];
        } else if (obj[0] == 'debugline') {
            if ($("#assemble").text() !== "Démarrer") {
                $(".highlightread").removeClass("highlightread");
                $(".highlightwrite").removeClass("highlightwrite");

                mem_highlights_r.length = 0;
                mem_highlights_w.length = 0;

                if (debug_marker !== null) { editor.session.removeMarker(debug_marker); }
                if (next_debug_marker !== null) { editor.session.removeMarker(next_debug_marker); }
                if (obj[1] >= 0) {
                    aceRange = ace.require('ace/range').Range;
                    debug_marker = editor.session.addMarker(new aceRange(obj[1], 0, obj[1] + 1, 0), "debug_line", "text");
                    if (current_debugline != obj[1] && $("#follow_pc").is(":checked")) {
                        editor.scrollToLine(obj[1], true, true, function () {});
                    }
                    current_debugline = obj[1];
                } else {
                    debug_marker = null;
                }
            }
        } else if (obj[0].slice(0, 9) == 'highlight') {
            type = obj[0].slice(9);
            for (var i = 0; i < obj[1].length; i++) {
                var element = obj[1][i];
                try {
                    if (element.slice(0, 4) == "MEM_") {
                        var addr = element.slice(4);
                        if (type == "read") {
                            mem_highlights_r.push(addr);
                        } else {
                            mem_highlights_w.push(addr);
                        }
                    } else {
                        $(document.getElementById(element)).addClass("highlight" + type);
                    }
                } catch(e) {}
            }
        } else if (obj[0] == 'debuginstrmem') {
            if ($("#assemble").text() !== "Démarrer") {
                mem_breakpoints_instr = obj[1];
                if ($("#follow_pc").is(":checked")) {
                    var target = obj[1][0];
                    var page = Math.floor(parseInt(target) / (16*20));
                    if ( editableGrid.getCurrentPageIndex() != page ) {
                        refresh_mem_paginator = true;
                        editableGrid.setPageIndex(page);
                    }
                }
                editableGrid.refreshGrid();
            }
        } else if (obj[0] == 'mempartial') {
            for (var i = 0; i < obj[1].length; i++) {
                var row = Math.floor(obj[1][i][0] / 16);
                var col = (obj[1][i][0] % 16) + 1;
                editableGrid.setValueAt(row, col, obj[1][i][1], false);
            }
            editableGrid.refreshGrid();
        } else if (obj[0] == 'mem') {
            refresh_mem_paginator = true;
            editableGrid.load({"data": obj[1]});
            editableGrid.renderGrid("memoryview", "testgrid");
        } else if (obj[0] == 'membp_r') {
            mem_breakpoints_r = obj[1];
        } else if (obj[0] == 'membp_w') {
            mem_breakpoints_w = obj[1];
        } else if (obj[0] == 'membp_rw') {
            mem_breakpoints_rw = obj[1];
        } else if (obj[0] == 'membp_e') {
            if ($("#assemble").text() !== "Démarrer") {
                mem_breakpoints_e = obj[1];
            }
        } else if (obj[0] == 'banking') {
            $("#tab-container").easytabs('select', '#tabs1-' + obj[1]);
            if (obj[1] == "User") {
                $("#spsr_title").text("SPSR");
            } else {
                $("#spsr_title").html("SPSR<br/>(" + obj[1] + ")");
            }
        } else if (obj[0] == 'error') {
            displayErrorMsg(obj[1]);
        } else {
            console.log("Unknown command:");
            console.log(obj);
        }
    }
};

function removeCodeErrors() {
    editor.session.clearAnnotations();
}

function resetView() {
    // Remove code errors tooltips
    codeerrors.length = 0;
    removeCodeErrors();

    current_debugline = -1;
    editor.session.clearAnnotations();

    $("#cycles_count").val("");
    $("#message_bar").slideUp("normal", "easeInOutBack", function() {});

    disableSim();
    $("#assemble").text("Démarrer");
    $(".assemble_edit").removeClass("assemble_edit");

    $(".regVal").val("");
    $(".statusVal").val("");
    if (debug_marker !== null) { editor.session.removeMarker(debug_marker); }
    if (next_debug_marker !== null) { editor.session.removeMarker(next_debug_marker); }

    $(".reg_bkp_w").removeClass("reg_bkp_w");
    $(".reg_bkp_r").removeClass("reg_bkp_r");
    $(".highlightread").removeClass("highlightread");
    $(".highlightwrite").removeClass("highlightwrite");
    $("#disassembly").html("");

    mem_highlights_r.length = 0;
    mem_highlights_w.length = 0;
    mem_breakpoints_r.length = 0;
    mem_breakpoints_w.length = 0;
    mem_breakpoints_rw.length = 0;
    mem_breakpoints_e.length = 0;
    mem_breakpoints_instr.length = 0;

    resetMemoryViewer();
}

function disableSim() {
    $("#run").prop('disabled', true);
    $("#reset").prop('disabled', true);
    $("#stepin").prop('disabled', true);
    $("#stepout").prop('disabled', true);
    $("#stepforward").prop('disabled', true);
    $("input[type=text]").prop('disabled', true);
    $(".config_input").prop('disabled', false);
}

function refreshBreakpoints() {
    editor.session.clearBreakpoints();
    for (var i = 0; i < asm_breakpoints.length; i++) {
        editor.session.setBreakpoint(asm_breakpoints[i]);
    }
}

function assemble(lang) {
    var simExec = isSimulatorInEditMode();
    editor.session.clearBreakpoints();
    resetView();
    if (simExec) {
        $("#run").prop('disabled', false);
        $("#reset").prop('disabled', false);
        $("#stepin").prop('disabled', false);
        $("#stepout").prop('disabled', false);
        $("#stepforward").prop('disabled', false);
        $("#assemble").text("Arrêter").addClass("assemble_edit");
        sendCmd(['assemble', editor.getValue(), lang]);
        if ($("#interrupt_active").is(":checked")) {
            sendCmd(["interrupt", true, $("#interrupt_type").val(), parseInt($("#interrupt_cycles").val()), parseInt($("#interrupt_cycles_first").val())]);
        }

    } else {
        $("#assemble").text("Démarrer");
        sendCmd(['stop']);
        refreshBreakpoints();
    }
}

function isSimulatorInEditMode() {
    return $("#assemble").text() == "Démarrer";
}

function reset() {
    sendCmd(['reset']);
}

function simulate(type) {
    var animate_speed = $('#animate_speed').val();
    sendCmd([type, animate_speed]);
}

function sendBreakpointsInstr() {
    sendCmd(['breakpointsinstr', asm_breakpoints]);
}

function sendMsg(msg) {
    sendData(JSON.stringify([msg]));
}

function sendCmd(cmd) {
    sendData(JSON.stringify(cmd));
}

function sendData(data) {
    if (ws.readyState === 0) {
        setTimeout(function () {sendData(data)}, 500);
    } else if (ws.readyState > 1) {
        resetView();
        displayErrorMsg("Perte de la connexion au simulateur. Veuillez enregistrer votre travail et rafraîchir la page.");
        $("input").prop("disabled", true);
    } else {
        ws.send(data);
    }
}
