var ws = new WebSocket("ws://127.0.0.1:31415/");

// Code errors
var codeerrors = {};
var codetooltips = [];


// Breakpoints
var asm_breakpoints = [];

ws.onmessage = function (event) {
	obj = JSON.parse(event.data);

    var element = document.getElementById(obj[0]);
    if (element != null) {
        element.innerHTML = obj[key];
    } else if (obj[0] == 'codeerror') {
        // Record code error tooltips
        codeerrors[obj[1]] = obj[2];
        updateCodeErrors();
    } else if (obj[0] == 'mem') {
        editableGrid.load({"data": obj[1]});
        editableGrid.renderGrid("memoryview", "testgrid");
        console.log("Loaded!");
    }
};


function removeCodeErrors() {
    //$(".ace_gutter-cell").each(function(index){
    for (var idx in codetooltips) {
        codetooltips[idx].tooltipster('destroy');
    };
    codetooltips = [];
}

function updateCodeErrors() {
    removeCodeErrors();

    // Apply tooltip
    for (var key in codeerrors) {
        var el = $(".ace_gutter-cell:contains('" + key + "')").filter(function(index) { return $(this).text() === key; });
        el.tooltipster({
            content: codeerrors[key],
            position: 'left',
            trigger: 'manual',
            theme: 'ts-error'
        });
        el.tooltipster('show');
        codetooltips.push(el);
    }
}


function assemble() {
    ws.send(JSON.stringify(['assemble', editor.getValue()]));
    
    // Remove code errors tooltips
    codeerrors = {};
    $(".ace_content").css("background-color", "#FFF");
}

function sendBreakpoints() {
    ws.send(JSON.stringify(['breakpoints', asm_breakpoints]));
}
