
$(document).ready(function () {
	$('#DataTables_Table_0_wrapper').on('click', 'a.paginate_button.current', function() {
		console.log("Hello");
	});
});

$('#DataTables_Table_0_wrapper').on('page.dt', function() {
	console.log("foo");
});

//var dt = $('.viewTable').DataTable();
$('table.viewTable.terms').on('page.dt', function() {
	console.log("foo");
});


function howMany() {
	var howMany = $("[name=DataTables_Table_0_length]").val();
	return howMany;
}

function whichPage() {
	var whichPage = $(".current").html();
	return whichPage;
}

function sayHello() {
	console.log("hello");
}
