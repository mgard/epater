var ws = new WebSocket("ws://127.0.0.1:31415/");

// Breakpoints and markers
var asm_breakpoints = [];
var mem_highlights_r = [];
var mem_highlights_w = [];
var mem_breakpoints_r = [];
var mem_breakpoints_w = [];
var mem_breakpoints_rw = [];
var mem_breakpoints_e = [];
var mem_breakpoints_instr = [];
var current_debugline = -1;
var next_debugline = -1;
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
    //console.log("reception: ", +new Date()/1000, obj_list);

    for (var idx in obj_list) {
        var obj = obj_list[idx];

        var element = document.getElementById(obj[0]);
        if (element != null) {
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

            $(element).val(target_value);
            $(element).prop("disabled", false);
        } else if (obj[0] == 'disable') {
            $("[name='" + obj[1] + "']").prop("disabled", true);
        } else if (obj[0] == 'codeerror') {
            // row indices are 0-indexed
            editor.session.setAnnotations([{row: obj[1], text: obj[2], type: "error"}]);
        } else if (obj[0] == 'asm_breakpoints') {
            editor.session.clearBreakpoints();
            for (var i = 0; i < obj[1].length; i++) {
                editor.session.setBreakpoint(obj[1][i]);
            }
        } else if (obj[0] == 'nextline') {
            /*if (next_debug_marker !== null) { editor.session.removeMarker(next_debug_marker); }
            next_debug_marker = editor.session.addMarker(new aceRange(obj[1], 0, obj[1] + 1, 0), "next_debug_line", "text");
            next_debugline = obj[1];*/
        } else if (obj[0] == 'debugline') {
            // Re-enable buttons if disabled
            $("#run").prop('disabled', false);
            $("#stepin").prop('disabled', false);
            $("#stepout").prop('disabled', false);
            $("#stepforward").prop('disabled', false);

            $(".highlightread").removeClass("highlightread");
            $(".highlightwrite").removeClass("highlightwrite");

            mem_highlights_r.length = 0;
            mem_highlights_w.length = 0;

            if (debug_marker !== null) { editor.session.removeMarker(debug_marker); }
            if (obj[1] >= 0) {
                aceRange = ace.require('ace/range').Range;
                debug_marker = editor.session.addMarker(new aceRange(obj[1], 0, obj[1] + 1, 0), "debug_line", "text");
                if (current_debugline != obj[1]) {
                    editor.scrollToLine(obj[1], true, true, function () {});
                }
                current_debugline = obj[1];
                // TODO: Ajouter une annotation? Gutter decoration?
            } else {
                debug_marker = null;
            }
        } else if (obj[0].slice(0, 9) == 'highlight') {
            console.log("Ici!");
            type = obj[0].slice(9);
            for (var i = 0; i < obj[1].length; i++) {
                var element = obj[1][i];
                try {
                    if (element.slice(0, 4) == "MEM_") {
                        var addr = element.slice(4);
                        if (type == "read") {
                            mem_highlights_r.push(addr);
                            console.log("Read:", addr);
                        } else {
                            mem_highlights_w.push(addr);
                            console.log("Write:", addr);
                        }
                    } else {
                        $(document.getElementById(element)).addClass("highlight" + type);
                    }
                } catch(e) {}
            }
        } else if (obj[0] == 'highlightwrite') {
        } else if (obj[0] == 'debuginstrmem') {
            mem_breakpoints_instr = obj[1];
            if ($("#follow_pc").is(":checked")) {
                var target = obj[1][0];
                var page = Math.floor(parseInt(target) / (16*20));
                if ( editableGrid.getCurrentPageIndex() != page ) {
                    editableGrid.setPageIndex(page);
                }
            }
            editableGrid.refreshGrid();
        } else if (obj[0] == 'mempartial') {
            for (var i = 0; i < obj[1].length; i++) {
                var row = Math.floor(obj[1][i][0] / 16);
                var col = (obj[1][i][0] % 16) + 1;
                editableGrid.setValueAt(row, col, obj[1][i][1], false);
            }
            editableGrid.refreshGrid();
        } else if (obj[0] == 'mem') {
            editableGrid.load({"data": obj[1]});
            editableGrid.renderGrid("memoryview", "testgrid");
        } else if (obj[0] == 'membp_r') {
            mem_breakpoints_r = obj[1];
        } else if (obj[0] == 'membp_w') {
            mem_breakpoints_w = obj[1];
        } else if (obj[0] == 'membp_rw') {
            mem_breakpoints_rw = obj[1];
        } else if (obj[0] == 'membp_e') {
            mem_breakpoints_e = obj[1];
        } else if (obj[0] == 'banking') {
            $("#tab-container").easytabs('select', '#tabs1-' + obj[1]);
            if (obj[1] == "User") {
                $("#spsr_title").text("SPSR");
            } else {
                $("#spsr_title").text("SPSR (" + obj[1] + ")");
            }
        } else if (obj[0] == 'error') {
            displayErrorMsg(obj[1]);
        } else {
            console.log("Unknown command:");
            console.log(obj);
        }
    }
    //console.log("End!", +new Date()/1000);
};


function removeCodeErrors() {
    editor.session.clearAnnotations();
}

function assemble() {
    sendData(JSON.stringify(['assemble', editor.getValue()]));

    // Remove code errors tooltips
    codeerrors = {};
    $(".ace_content").css("background-color", "#FFF");

    window.onbeforeunload = null;

    asm_breakpoints.length = 0;
    editor.session.clearBreakpoints();
    editor.session.clearAnnotations();

    $("#cycles_count").val("0");
    $("#message_bar").slideUp("normal", "easeInOutBack", function() {});

    $("#interrupt_active").attr('checked', false);
    $("#run").prop('disabled', true);
    $("#stepin").prop('disabled', true);
    $("#stepout").prop('disabled', true);
    $("#stepforward").prop('disabled', true);
}

function simulate(type) {
    var animate_speed = $('#animate_speed').val();
    sendData(JSON.stringify([type, animate_speed]));
}

function sendBreakpointsInstr() {
    sendData(JSON.stringify(['breakpointsinstr', asm_breakpoints]));
}

function sendMsg(msg) {
    sendData(JSON.stringify([msg]));
}

function sendCmd(cmd) {
    sendData(JSON.stringify(cmd));
}

function sendData(data) {
    //console.log("envoi: ", +new Date()/1000);
    if (ws.readyState !== 1) {
        displayErrorMsg("Perte de la connexion au simulateur.");
        $("input").prop("disabled", true);
    } else {
        ws.send(data);
    }
}
