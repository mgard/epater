var ws = new WebSocket("ws://127.0.0.1:31415/");

// Breakpoints and markers
var asm_breakpoints = [];
var debug_marker = null;

ws.onmessage = function (event) {
	obj = JSON.parse(event.data);

    var element = document.getElementById(obj[0]);
    if (element != null) {
        $(element).val(obj[1]);
    } else if (obj[0] == 'codeerror') {
        // row indices are 0-indexed
        editor.session.setAnnotations([{row: obj[1], text: obj[2], type: "error"}]);
    } else if (obj[0] == 'debugline') {
        if (debug_marker !== null) { editor.session.removeMarker(debug_marker); }
        if (obj[1] >= 0) {
            aceRange = ace.require('ace/range').Range;
            debug_marker = editor.session.addMarker(new aceRange(obj[1], 0, obj[1] + 1, 0), "debug_line", "text");
            // TODO: Ajouter une annotation? Gutter decoration?
        } else {
            debug_marker = null;
        }
    } else if (obj[0] == 'mem') {
        editableGrid.load({"data": obj[1]});
        editableGrid.renderGrid("memoryview", "testgrid");
    }
};


function removeCodeErrors() {
    editor.session.clearAnnotations();
}

function assemble() {
    ws.send(JSON.stringify(['assemble', editor.getValue()]));
    
    // Remove code errors tooltips
    codeerrors = {};
    $(".ace_content").css("background-color", "#FFF");
}

function simulate() {
    ws.send(JSON.stringify(['run']));
}

function sendBreakpointsInstr() {
    ws.send(JSON.stringify(['breakpointsinstr', asm_breakpoints]));
}

function sendMsg(msg) {
    ws.send(JSON.stringify([msg]));
}
