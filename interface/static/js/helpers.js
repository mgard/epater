
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

function getURLParameter(param)
	{
	    var pageURL = window.location.search.substring(1);
	    var URLVariables = pageURL.split('&');
	    for (var i = 0; i < URLVariables.length; i++)
	    {
	        var parameterName = URLVariables[i].split('=');
	        if (parameterName[0] == param)
	        {
	            return parameterName[1];
	        }
	    }
	}

function saveTextAsFile() {
    var textToWrite = editor.getValue();

    var form = document.createElement("form");
    form.setAttribute("method", "post");
    form.setAttribute("action", "/download/");
    form.setAttribute("target", "_blank");

    var sim = getURLParameter('sim');

    params = {sim:sim, data:textToWrite};

    for(var key in params) {
        if(params.hasOwnProperty(key)) {
            var hiddenField = document.createElement("input");
            hiddenField.setAttribute("type", "hidden");
            hiddenField.setAttribute("name", key);
            hiddenField.setAttribute("value", params[key]);

            form.appendChild(hiddenField);
         }
    }

    document.body.appendChild(form);
    form.submit();
}

$(window).bind('keydown', function(e) {
    if (e.ctrlKey || e.metaKey) {
        switch (String.fromCharCode(e.which).toLowerCase()) {
        case 's':
            e.preventDefault();
            saveTextAsFile();
            break;
        case 'o':
            e.preventDefault();
            $("#fileToLoad").trigger('click');
            break;
        }
    if (!isSimulatorInEditMode()) {
        switch (e.which) {
            case 37: // left
                simulate('stepforward');
                break;

            case 38: // up
                assemble();
                break;

            case 39: // right
                simulate('stepout');
                break;

            case 40: // down
                simulate('stepinto');
                break;
            }
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

function setLang(lang){
    previousLang = getLang();
    if (previousLang != lang){
        document.cookie = "lang=" + lang;
        location.reload();
    }
}

function getLang(){
    var value = "; " + document.cookie;
    var parts = value.split("; lang=");
    if (parts.length == 2)
        return parts.pop().split(";").shift();
}

