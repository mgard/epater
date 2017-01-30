
function clearSelection() {
    var sel;
    if ( (sel = document.selection) && sel.empty ) {
        sel.empty();
    } else {
        if (window.getSelection) {
            window.getSelection().removeAllRanges();
        }
        var activeEl = document.activeElement;
        if (activeEl) {
            var tagName = activeEl.nodeName.toLowerCase();
            if ( tagName == "textarea" ||
                    (tagName == "input" && activeEl.type == "text") ) {
                // Collapse the selection to the end
                activeEl.selectionStart = activeEl.selectionEnd;
            }
        }
    }
}

// //////////
// Get parameters
function getSearchParameters() {
      var prmstr = window.location.search.substr(1);
      return prmstr != null && prmstr != "" ? transformToAssocArray(prmstr) : {};
}

function transformToAssocArray( prmstr ) {
    var params = {};
    var prmarr = prmstr.split("&");
    for ( var i = 0; i < prmarr.length; i++) {
        var tmparr = prmarr[i].split("=");
        params[tmparr[0]] = tmparr[1];
    }
    return params;
}


// //////////
// Formatting 
function formatHexUnsigned32Bits(i) {
    return "0x" + ("00000000" + i.toString(16)).slice(-8);
}


function image(relativePath) {
    return "static/js/editablegrid/images/" + relativePath;
}

// ///
// I/O
function destroyClickedElement(event)
{
    document.body.removeChild(event.target);
}

function saveTextAsFile() {
    var textToWrite = editor.getValue();
    var textFileAsBlob = new Blob([textToWrite],  {type: 'text/plain'});
    var fileNameToSaveAs = "source.txt";
    var downloadLink = document.createElement("a");
    var is_safari = navigator.userAgent.indexOf("Safari") > -1;
    if ((is_chrome)&&(is_safari)) {is_safari=false;}
    downloadLink.download = fileNameToSaveAs;
    downloadLink.innerHTML = "Download File";
    try {
        // Chrome allows the link to be clicked
        // without actually adding it to the DOM.
        downloadLink.href = window.webkitURL.createObjectURL(textFileAsBlob);
        if (is_safari) {
            downloadLink.target = '_blank';
            downloadLink.download = fileNameToSaveAs;
            //$(downloadLink).attr('download', fileNameToSaveAs);
        }
    } catch(e) {
        // Firefox requires the link to be added to the DOM
        // before it can be clicked.
        downloadLink.href = window.URL.createObjectURL(textFileAsBlob);
        downloadLink.onclick = destroyClickedElement;
        downloadLink.style.display = "none";
        document.body.appendChild(downloadLink);
    }
    downloadLink.click();
}

$(window).bind('keydown', function(event) {
    if (event.ctrlKey || event.metaKey) {
        switch (String.fromCharCode(event.which).toLowerCase()) {
        case 's':
            event.preventDefault();
            saveTextAsFile();
            break;
        case 'o':
            event.preventDefault();
            $("#fileToLoad").trigger('click'); 
            break;
        }
    }
});

function loadFileAsText(){
    var fileToLoad = document.getElementById("fileToLoad").files[0];
    var fileReader = new FileReader();
    fileReader.onload = function(fileLoadedEvent){
        editor.setValue(fileLoadedEvent.target.result);
    };
    fileReader.readAsText(fileToLoad, "UTF-8");
}

window.onbeforeunload = function (e) {
    // If we haven't been passed the event get the window.event
    e = e || window.event;

    var message = 'Êtes-vous certain de vouloir quitter cette page?';

    // For IE6-8 and Firefox prior to version 4
    if (e) { e.returnValue = message; }

    // For Chrome, Safari, IE8+ and Opera 12+
    return message;
};
