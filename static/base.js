$('#logoutLink') .click(logout);
$('.sidebarTitle') .click(slideMenu);
$('.quickAccessJobs') .click(function() {window.open('JobList.html?langID='+$('#languageAccessJobs').val()+'&prodID='+$('#productAccessJobs').val(), '_self', false);return false;});
$('.quickAccessTerms') .click(function() {window.open('TermList.html?langID='+$('#languageAccessTerms').val()+'&prodID='+$('#productAccessTerms').val(), '_self', false);return false;});
$('.tbxExportTerms') .click(function() {window.open('terminology.tbx?langID='+$('#tbxExportLanguage').val()+'&prodID='+$('#tbxExportProduct').val(), '_self', false);return false;});

function logout(evt) {
	$.ajax({
		url: "logout",
		type: "GET",
		cache: false,
		processData: false,
		contentType: 'text/plain; charset=utf-8',
		success: function(text) {
			if ($('body').find('.loginForm').length === 0) {
				$(evt.target).parent().replaceWith('<div class="userDetails"><a href="#" id="loginLink">login</a></div>');
			} else {
				window.open('index.html', '_self', false);
			}
		},
		error: function(xhr, status) {
		},
		complete: function(xhr, status) {
		}
	});
	return false;
}

function slideMenu(evt) {
	$(evt.target).parentsUntil('ul').find('.sidebarContent').slideToggle();
	return false;
}