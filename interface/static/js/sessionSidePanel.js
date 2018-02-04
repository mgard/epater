var saveEditorTimer = window.setInterval('onTimer()', 60000);

var savedEditor = JSON.parse(localStorage.getItem(getURLParameter('sim')));
if (savedEditor) {
    savedEditor['defaultEditor'] = editor.getValue();
    if (savedEditor['current'] != null){
        editor.setValue(savedEditor['data'][savedEditor['current']]['code'], -1);
    }
}
else{
    savedEditor = {defaultEditor: editor.getValue(), current: null, data: []}
}
localStorage.setItem(getURLParameter('sim'), JSON.stringify(savedEditor));
updateSessionPanel();

$("#session_delete").click(function () {
    var savedEditor = JSON.parse(localStorage.getItem(getURLParameter('sim')));
    if (savedEditor['current'] != null){
        var message = 'Êtes-vous sûr de vouloir supprimer la session en cours ?'
        if(confirm(message)){
            if (savedEditor['data'].length == 1){
                editor.setValue(savedEditor['defaultEditor'], -1);
                savedEditor['current'] = null;
                savedEditor['data'] = [];
            }
            else{
                saveCurrentEditor();
                savedEditor = JSON.parse(localStorage.getItem(getURLParameter('sim')));
                savedEditor['data'].splice(savedEditor['current'], 1)
                savedEditor['current'] = 0;
                editor.setValue(savedEditor['data'][0]['code'], -1);
            }
            localStorage.setItem(getURLParameter('sim'), JSON.stringify(savedEditor));
            updateSessionPanel();
        }
    }
});

$("#session_delete_all").click(function () {
    var savedEditor = JSON.parse(localStorage.getItem(getURLParameter('sim')));
    if (savedEditor['current'] != null){
        var message = 'Êtes-vous sûr de vouloir supprimer toutes les sessions enregistrées ?'
        if(confirm(message)){
            savedEditor['current'] = null;
            savedEditor['data'] = [];
            editor.setValue(savedEditor['defaultEditor'], -1);
            localStorage.setItem(getURLParameter('sim'), JSON.stringify(savedEditor));
            updateSessionPanel();
        }
    }
});

$("#session_new").click(function () {
    var savedEditor = JSON.parse(localStorage.getItem(getURLParameter('sim')));
    if (savedEditor['current'] != null){
        saveCurrentEditor();
        savedEditor = JSON.parse(localStorage.getItem(getURLParameter('sim')));
        savedEditor['data'].unshift({});
        savedEditor['current'] = 0;
    }
    else{
        savedEditor['current'] = 0;
        savedEditor['data'] = [];
    }
    localStorage.setItem(getURLParameter('sim'), JSON.stringify(savedEditor));
    editor.setValue(savedEditor['defaultEditor'], -1);
    saveCurrentEditor(true);
    updateSessionPanel();
});

$('#session_content').keydown(function(e) {
// trap the return key being pressed
    if (e.keyCode == 13) return false;
});

function saveCurrentEditor(forceNewName){
    forceNewName = typeof forceNewName !== 'undefined' ? forceNewName : false;
    var savedEditor = JSON.parse(localStorage.getItem(getURLParameter('sim')));
    var name = $('#selected #session_name').html();
    if(!name || forceNewName){
        name = "Sans titre";
    }
	var data = {date: Date.now(), code: editor.getValue(), name: name}
	if (savedEditor['current'] != null){
		savedEditor['data'][savedEditor['current']] = data;
	}
	else{
        savedEditor['current'] = 0;
        savedEditor['data'] = [data];
	}
    localStorage.setItem(getURLParameter('sim'), JSON.stringify(savedEditor));
}

function getDateOrHour(p_date){
    var today = new Date();
    var dateToCompare = new Date(0)
    if (today.setDate(today.getDate() - 1) < dateToCompare.setUTCMilliseconds(p_date)){
        return dateToCompare.toTimeString().split(' ')[0];
    }
    else{
        return dateToCompare.getDate() + '/' + dateToCompare.getMonth() + '/' + dateToCompare.getFullYear()
    }
}

function updateSessionPanel(){
    var content = $('#session_content');
    var savedEditor = JSON.parse(localStorage.getItem(getURLParameter('sim')));
    content.html("");
    if (savedEditor['current'] != null){
        var current = savedEditor['current'];
        for (i = 0; i < savedEditor['data'].length; i++) {
            var data = savedEditor['data'][i];
            var selectedProperty = 'onclick="restoreSession(' + i + ')"';
            var editable = "";
            if(current == i){
                selectedProperty = 'id="selected"'
                editable = 'contenteditable="true"'
            }
            var message = '<div ' + selectedProperty + 'class="session_item">' +
                    '<div id="session_id">' + (i+1) + '</div>' +
                    '<div class="session_item_right">' +
                    '<div id="session_name" ' + editable + '>' + data['name'] + '</div>' +
                    '<div>Dernière sauvegarde : ' + getDateOrHour(data['date']) + '</div>' +
                    '<div>Taille : ' + data['code'].length + ' caratères </div>' +
                    '</div></div>';
            content.append(message);
        }
    }
}

function onTimer(){
    var defaultEditor = JSON.parse(localStorage.getItem(getURLParameter('sim')))['defaultEditor'];
    var currentEditor = editor.getValue();
    if (defaultEditor != currentEditor) {
        // We save only if there is a modification
        saveCurrentEditor();
        updateSessionPanel();
    }
}

function restoreSession(selected){
    saveCurrentEditor();
    var savedEditor = JSON.parse(localStorage.getItem(getURLParameter('sim')));
    editor.setValue(savedEditor['data'][selected]['code'], -1);
    savedEditor['current'] = selected;
    localStorage.setItem(getURLParameter('sim'), JSON.stringify(savedEditor));
    updateSessionPanel();
}


window.onbeforeunload = function (e) {
    var defaultEditor = JSON.parse(localStorage.getItem(getURLParameter('sim')))['defaultEditor'];
    var currentEditor = editor.getValue();
    if (defaultEditor != currentEditor) {
        // We save only if there is a modification
        saveCurrentEditor();
    }
};
