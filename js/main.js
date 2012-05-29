$(document).ready(function () {
  populateTable();
});


function populateTable(){
	var metabugs = [];
	var table = $("#compattable");
	for(var i = 0; i < data.length; i++){
		metabugs.push(data[i].bug);
		var row = $("<tr>");
		table.append(row);
		row.append(createTableCell(data[i].name));
		row.append(createTableCell(data[i].url));
		row.append(createTableCell(createBugDiv(data[i].bug)));
		row.append(createTableCell(createDependsDiv(data[i].bug)));
		row.append(createTableCell(data[i].info));
	}
	getMetabugs(metabugs);

}

function createTableCell(value){
	var td = $("<td>");
	td.append(value);
	return td;
}

function createDependsDiv(value){
	var div = $("<div>");
	div.attr("id", "bug" + value + "-depends");
	return div;
}

function createBugDiv(id, name, alias, resolved){
	var div = $("<div>");
	div.attr("id", "bug"+ id);
	var link = $("<a>");
	link.attr("href", "https://bugzilla.mozilla.org/show_bug.cgi?id="+id);
	link.attr("title", name);
	if(resolved){
		link.attr("style", "text-decoration: line-through;");
	}
	if(alias){
		link.append(alias);
	}
	else{
		link.append(id);
	}
	div.append(link);
	return div;
}

function getMetabugs(metabugs){
	var url = "https://api-dev.bugzilla.mozilla.org/latest/bug?include_fields=alias,id,depends_on,status,summary&id=";
	var ids ="";
	for(var i = 0; i < metabugs.length; i++){
		if(i == metabugs.length-1){
			ids += metabugs[i];
		}
		else{
			ids += metabugs[i] + ",";
		}
	}
	$.ajax({
	  url: url + ids,
	  crossDomain:true, 
	  dataType: 'json',
	  success: function(data){
	    processMetabugs(data.bugs);
	  },
	  error: function(data){
	    alert('fail.');
	  }
	});
}

function processMetabugs(bugs){
	var depends = "";
	for(var i = 0; i < bugs.length; i++){
		var id = bugs[i].id;
		var bugdiv = $("#bug"+id);
		var newbugdiv = createBugDiv(id, bugs[i].summary, bugs[i].alias, isResolved(bugs[i].status));
		bugdiv.replaceWith(newbugdiv);
		var localDepends = bugs[i].depends_on;
		if(localDepends && localDepends != ""){
			if(depends != ""){
				depends += ",";
			}
			depends += localDepends;
		}
		var dependsdiv = $("#bug"+ id + "-depends");
		var dependsArray = depends.split(',');
		for(var j = 0; j < dependsArray.length; j++){
			dependsdiv.append(createBugDiv(dependsArray[j]));
			if(j+1 < dependsArray.length){
				dependsdiv.append(",");
			}
		}
	}
	getDependentBugs(depends);
}

function isResolved(status){
	if(status == "RESOLVED" || status == "VERIFIED" || status == "CLOSED"){
		return true;
	}
	return false;
}

function getDependentBugs(dependentBugs){
	var url = "https://api-dev.bugzilla.mozilla.org/latest/bug?include_fields=alias,id,status,summary&id=";
	var ids =dependentBugs;
	$.ajax({
	  url: url + ids,
	  crossDomain:true, 
	  dataType: 'json',
	  success: function(data){
	    processDependentbugs(data.bugs);
	  },
	  error: function(data){
	    alert('fail.');
	  }
	});
}

function processDependentbugs(bugs){
	for(var i = 0; i < bugs.length; i++){
		var id = bugs[i].id;
		var bugdiv = $("#bug"+id);
		var newbugdiv = createBugDiv(id, bugs[i].summary, bugs[i].alias, isResolved(bugs[i].status));
		bugdiv.replaceWith(newbugdiv);
	}
}