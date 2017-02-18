
var editableGrid = null;
var mouse_highlight_mem = [];


function updateMemoryBreakpointsView() {
  for (var i = 0; i < mem_highlights_r.length; i++) {
    tofind = formatHexUnsigned32Bits(mem_highlights_r[i]).slice(0, 9) + "0";
    var tableRow = $("td", $("#memoryview")).filter(function() {
      return $(this).text() == tofind;
    }).closest("tr");
    if (tableRow.length < 1) {
      continue;
    }
    col = parseInt(mem_highlights_r[i], 16) % 16;
    $('.editablegrid-c'+col, tableRow).addClass('highlightread');
  }

  for (var i = 0; i < mem_highlights_w.length; i++) {
    tofind = formatHexUnsigned32Bits(mem_highlights_w[i]).slice(0, 9) + "0";
    var tableRow = $("td", $("#memoryview")).filter(function() {
      return $(this).text() == tofind;
    }).closest("tr");
    if (tableRow.length < 1) {
      continue;
    }
    col = parseInt(mem_highlights_w[i], 16) % 16;
    $('.editablegrid-c'+col, tableRow).addClass('highlightwrite');
  }

  for (var i = 0; i < mem_breakpoints_r.length; i++) {
    tofind = formatHexUnsigned32Bits(mem_breakpoints_r[i]).slice(0, 9) + "0";
    var tableRow = $("td", $("#memoryview")).filter(function() {
      return $(this).text() == tofind;
    }).closest("tr");
    if (tableRow.length < 1) {
      continue;
    }
    col = parseInt(mem_breakpoints_r[i], 16) % 16;
    $('.editablegrid-c'+col, tableRow).addClass('mem_r');
  }

  for (var i = 0; i < mem_breakpoints_w.length; i++) {
    tofind = formatHexUnsigned32Bits(mem_breakpoints_w[i]).slice(0, 9) + "0";
    var tableRow = $("td", $("#memoryview")).filter(function() {
      return $(this).text() == tofind;
    }).closest("tr");
    if (tableRow.length < 1) {
      continue;
    }
    col = parseInt(mem_breakpoints_w[i], 16) % 16;
    $('.editablegrid-c'+col, tableRow).addClass('mem_w');
  }

  for (var i = 0; i < mem_breakpoints_rw.length; i++) {
    tofind = formatHexUnsigned32Bits(mem_breakpoints_rw[i]).slice(0, 9) + "0";
    var tableRow = $("td", $("#memoryview")).filter(function() {
      return $(this).text() == tofind;
    }).closest("tr");
    if (tableRow.length < 1) {
      continue;
    }
    col = parseInt(mem_breakpoints_rw[i], 16) % 16;
    $('.editablegrid-c'+col, tableRow).addClass('mem_rw');
  }

  for (var i = 0; i < mem_breakpoints_e.length; i++) {
    tofind = formatHexUnsigned32Bits(mem_breakpoints_e[i]).slice(0, 9) + "0";
    var tableRow = $("td", $("#memoryview")).filter(function() {
      return $(this).text() == tofind;
    }).closest("tr");
    if (tableRow.length < 1) {
      continue;
    }
    col = parseInt(mem_breakpoints_e[i], 16) % 16;
    $('.editablegrid-c'+col, tableRow).addClass('mem_e');
  }

  /* Highlight current instruction */
  for (var i = 0; i < mem_breakpoints_instr.length; i++) {
    tofind = formatHexUnsigned32Bits(mem_breakpoints_instr[i]).slice(0, 9) + "0";
    var tableRow = $("td", $("#memoryview")).filter(function() {
      return $(this).text() == tofind;
    }).closest("tr");
    if (tableRow.length > 0) {
      col = mem_breakpoints_instr[i] % 16;
      $('.editablegrid-c'+col, tableRow).addClass('mem_instr');
    }
  }

  for (var i = 0; i < mouse_highlight_mem.length; i++) {
    tofind = formatHexUnsigned32Bits(mouse_highlight_mem[i]).slice(0, 9) + "0";
    var tableRow = $("td", $("#memoryview")).filter(function() {
      return $(this).text() == tofind;
    }).closest("tr");
    if (tableRow.length > 0) {
      col = mouse_highlight_mem[i] % 16;
      $('.editablegrid-c'+col, tableRow).addClass('mem_mousehighlight');
    }
  }
}

function changeMemoryViewPage() {
  refresh_mem_paginator = true;
  var target = $("#jump_memory").val();
  target_memaddr = target;
  var page = Math.floor(parseInt(target) / (16*20));
  editableGrid.setPageIndex(page);
}

function resetMemoryViewer() {
  refresh_mem_paginator = true;

  // Memory viewer
  var metadata = [];
  metadata.push({ name: "ch",  label: "addr",  datatype: "string",  editable: false});
  metadata.push({ name: "c0",  label: "00",  datatype: "string",  editable: true});
  metadata.push({ name: "c1",  label: "01",  datatype: "string",  editable: true});
  metadata.push({ name: "c2",  label: "02",  datatype: "string",  editable: true});
  metadata.push({ name: "c3",  label: "03",  datatype: "string",  editable: true});
  metadata.push({ name: "c4",  label: "04",  datatype: "string",  editable: true});
  metadata.push({ name: "c5",  label: "05",  datatype: "string",  editable: true});
  metadata.push({ name: "c6",  label: "06",  datatype: "string",  editable: true});
  metadata.push({ name: "c7",  label: "07",  datatype: "string",  editable: true});
  metadata.push({ name: "c8",  label: "08",  datatype: "string",  editable: true});
  metadata.push({ name: "c9",  label: "09",  datatype: "string",  editable: true});
  metadata.push({ name: "c10",  label: "0A",  datatype: "string",  editable: true});
  metadata.push({ name: "c11",  label: "0B",  datatype: "string",  editable: true});
  metadata.push({ name: "c12",  label: "0C",  datatype: "string",  editable: true});
  metadata.push({ name: "c13",  label: "0D",  datatype: "string",  editable: true});
  metadata.push({ name: "c14",  label: "0E",  datatype: "string",  editable: true});
  metadata.push({ name: "c15",  label: "0F",  datatype: "string",  editable: true});

  // Not necessary?
  var data = [];
  for (var i = 0; i < 20; i++) {
    data.push({id: i,  values: {"c0": "--",  "c1": "--",  "c2": "--",  "c3": "--",  "c4": "--",  "c5": "--",  "c6": "--",  "c7": "--",  "c8": "--",  "c9": "--",  "c10": "--",  "c11": "--",  "c12": "--",  "c13": "--",  "c14": "--",  "c15": "--"}});
    data[i]["values"]["ch"] = formatHexUnsigned32Bits(i*16)
  }

  editableGrid = new EditableGrid("DemoGridJsData",  {
    modelChanged: function(row, col, oldValue, newValue, rowref) { 
      if (oldValue !== "--") {
        if (newValue.length > 2) {
          newValue = newValue.slice(0, 2);
          editableGrid.setValueAt(row, col, newValue, true);
        }
        var addr = parseInt($("td:first", rowref).text(), 16) + (col - 1)
        sendCmd(['memchange', addr, newValue]);
      } else {
        editableGrid.setValueAt(row, col, "--", true);
      }
    }, 
    enableSort: false,
    pageSize: 20,
    tableRendered: function() {
      this.updatePaginator();
      updateMemoryBreakpointsView();
    }
  });
  editableGrid.load({"metadata": metadata,  "data": data});
  editableGrid.renderGrid("memoryview",  "testgrid");

  /* $("td.mem_r").removeClass("mem_r");
  $("td.mem_w").removeClass("mem_w");
  $("td.mem_rw").removeClass("mem_rw");
  $("td.mem_e").removeClass("mem_e");
  $("td.mem_instr").removeClass("mem_instr"); */

  updateMemoryBreakpointsView();
}

function cellClick(e) {
  var suffix = null;
  for (var i = 0; i < e.target.classList.length; i++) {
    if (e.target.classList[i].slice(0, 14) == 'editablegrid-c') { suffix = e.target.classList[i].slice(-2); }
  }
  if (suffix == null) {
    return;
  }
  if (suffix[0] == 'c') { suffix = suffix.slice(-1); }
  suffix = parseInt(suffix).toString(16);
  var addr = $('td:first', $(e.target).closest('tr')).text().slice(0,9) + suffix;
  if(e.shiftKey) {
    sendCmd(['breakpointsmem', addr, 'r']);
  }
  if(e.ctrlKey || event.metaKey) {
    sendCmd(['breakpointsmem', addr, 'w']);
  }
  if(e.altKey) {
    sendCmd(['breakpointsmem', addr, 'e']);
  }
}

var refresh_mem_paginator = true;
var target_memaddr = null;
$(document).ready(function() {
  EditableGrid.prototype.updatePaginator = function() {
    if (refresh_mem_paginator) {
      refresh_mem_paginator = false;

      var paginator = $("#paginator").empty();
      var nbPages = this.getPageCount();

      // "first" link
      var link = $("<a>").html("<img src='static/image/mem_first.png' style='height: 15px; vertical-align: middle;'/>&nbsp;");
      if (!this.canGoBack()) link.css({ opacity : 0.4,  filter: "alpha(opacity=40)" });
      else link.css("cursor",  "pointer").click(function(event) { refresh_mem_paginator = true; editableGrid.firstPage(); });
      paginator.append(link);

      // "prev" link
      link = $("<a>").html("<img src='static/image/mem_prev.png' style='height: 15px; vertical-align: middle;'/>&nbsp;");
      if (!this.canGoBack()) link.css({ opacity : 0.4,  filter: "alpha(opacity=40)" });
      else link.css("cursor",  "pointer").click(function(event) { refresh_mem_paginator = true; editableGrid.prevPage(); });
      paginator.append(link);

      var mem_begin = $(".editablegrid-ch:eq(1)").text();
      if (target_memaddr !== null) { mem_begin = target_memaddr; }
      paginator.append('<input id="jump_memory" type="text" value="' + mem_begin + '"/><input id="jump_memory_go" type="submit" value="Go">');
      target_memaddr = null;

      $("#jump_memory").keyup(function(e){ if (e.keyCode == 13) { changeMemoryViewPage(); } });
      $("#jump_memory_go").click(changeMemoryViewPage);

      // "next" link
      link = $("<a>").html("<img src='static/image/mem_next.png' style='height: 15px; vertical-align: middle;'/>&nbsp;");
      if (!this.canGoForward()) link.css({ opacity : 0.4,  filter: "alpha(opacity=40)" });
      else link.css("cursor",  "pointer").click(function(event) { refresh_mem_paginator = true; editableGrid.nextPage(); });
      paginator.append(link);

      // "last" link
      link = $("<a>").html("<img src='static/image/mem_last.png' style='height: 15px; vertical-align: middle;'/>&nbsp;");
      if (!this.canGoForward()) link.css({ opacity : 0.4,  filter: "alpha(opacity=40)" });
      else link.css("cursor",  "pointer").click(function(event) { refresh_mem_paginator = true; editableGrid.lastPage(); });
      paginator.append(link);

    }

  };

  $("#memoryview").click(cellClick);
  resetMemoryViewer();
});