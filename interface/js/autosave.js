

function updateAutosave() {
    $("#autosave_menu").remove();
    choices = ""
    for (var i = 0; i < 10; ++i) {
        var val = localStorage.getItem("time_autosave" + i.toString())
        if ( val !== null ) { choices = choices + '<option value="' + i + '">' + val + '</option>' }
    }
    $("#loadFile").after('<select id="autosave_menu"><option value="-1">Autosave</option>' + choices + "</select>");
    $('#autosave_menu').on('change', function() {
        if (this.value != "-1") {
            editor.setValue(localStorage.getItem("data_autosave" + this.value.toString()));
        }
        $("#autosave_menu").val("-1");
    });
}

$(document).ready(function() {
    var params = getSearchParameters();

    if (params["nowarning"] === undefined) {
        window.onbeforeunload = confirmOnPageExit;
    } else {
        console.log("Disabling exit warning!");
    }

    autosave_index = 0;
    if (typeof(Storage) !== "undefined") {
        // Continue autosaving where we left
        for (var i = 0; i < 10; ++i) {
            var val = localStorage.getItem("time_autosave" + i.toString())
            if ( val === null ) { break; }
            autosave_index = autosave_index + 1;
        }

        setInterval(function() {
            localStorage.setItem("data_autosave" + autosave_index.toString(), editor.getValue());
            localStorage.setItem("time_autosave" + autosave_index.toString(), new Date().toLocaleString());
            autosave_index = (autosave_index + 1) % 10;

            updateAutosave();
            console.log("Autosaved! ID: " + autosave_index.toString());
        }, 60000); // Tous les 2 minutes

        // Afficher menu
        updateAutosave();
    } else {
        console.log("Autosaving disabled!");
    }
});