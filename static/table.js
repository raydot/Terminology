$(function() { $('img.lazy').jail({
	timeout: 0,
	offset: 100,
}) });
$('.toggleClick') .click(toggleMultipart);
$('.addCommentButton') .click(addComment);
$('.submitCommentButton') .click(submitComment);
$('.translateTermToggle') .click(toggleTranslateTerm);
$('.cancelTranslationButton') .click(toggleTranslateTerm);
$('.saveTranslationButton') .click(saveTranslation);
$('.termCheckbox') .click(function(evt) { $(evt.target).find('label').click()} );


function toggleMultipart(evt) {
	var row = $(evt.target) .parent().parent().parent();
	var termID = row.attr("term-id");
	var toggleTarget = $(($(evt.target).is(".showArchive") ? ".rowChildArchive-" : ($(evt.target).is(".showContext") ? ".rowChildContext-" : ".rowChildComments-")) + termID);
	var contentDiv = ($(evt.target).is(".showArchive") ? "#archive-" : ($(evt.target).is(".showContext") ? "#context-" : "#comments-")) + termID;
	
	if (toggleTarget.is(":visible")) {
		if ($(evt.target).is(".showComments")) {
			toggleTarget.find(".submitCommentButton").toggle(function() {
				toggleTarget.find(".addCommentButton").toggle();
				toggleTarget.find('.addCommentButton') .click(addComment);
				if (toggleTarget.find(".commentRow").length > 1) {
					toggleTarget.find(".newCommentRow").toggle(function() {
						$(this).remove();
					});
				} else {
					toggleTarget.find("form").toggle(function() {
						$(this).remove();
						toggleTarget.find(".noCommentsSpan").toggle();
					});
				}
				$(".submitWarning").hide();
			});
		}
		var elements = toggleTarget.children().children(".toggle");
		elements.slideToggle().promise().done(function() {
			toggleTarget.toggle();
		});
	} else {
		toggleTarget.css("display", "table-row");
		toggleTarget.children().children(".toggle").slideToggle();

		if (!$(contentDiv).is(".auxContentLoaded")) {
			loadAuxData($(evt.target), contentDiv, termID);
		}
	}
}

function loadAuxData(target, contentDiv, termID) {
	$(function() { $('img.lazyLoading').jail({
		timeout: 0,
	}) });
	$(contentDiv).addClass("toggle");
	$(contentDiv).addClass("auxContentLoaded");
	if (target.is(".showArchive")) {
		$.ajax({
			url: "archiveForTerm/"+termID,
			cache: false,
			type: "GET",
			success: function(html) {
				$(contentDiv).html(html);
				$(contentDiv).slideToggle();
			}
		});
	} else if (target.is(".showContext")) {
		$.ajax({
			url: "contextForTerm/"+termID,
			cache: false,
			type: "GET",
			success: function(html) {
				$(contentDiv).html(html);
				$(contentDiv).slideToggle();
			}
		});
	} else {
		$.ajax({
			url: "commentsForTerm/"+termID,
			cache: false,
			type: "GET",
			success: function(html) {
				$(contentDiv).html(html);
				$('.addCommentButton') .click(addComment);
				$('.deleteComment') .click(deleteComment);
				$(contentDiv).slideToggle();
			}
		});
	}
	$("#loading-"+contentDiv.substr(1)).fadeOut(400, function() {
		$("#loading-"+contentDiv.substr(1)).removeClass("toggle");
	});
}

function isAuthorised(callback) {
	$.ajax({
		url: "isAuthorised",
		cache: false,
		type: "GET",
		contentType: "text/plain; charset=utf-8",
		success: function(text) {
			callback(text === "YES");
		},
		error: function(xhr, status) {
			callback(false);
		}
	})
}

function addComment(evt) {
	isAuthorised(function(authorised) {
		if (authorised) {
			var contentDiv = "#"+$(evt.target).parent().attr("id");
			var termID = $(evt.target).parent().attr("term-id");
			if (!$(evt.target).next().is(".viewSubTable") && !$(evt.target).next().is(".commentForm")) {
				$(contentDiv).slideToggle(400, function() {
					$.ajax({
						url: "commentsForTerm/"+termID+"/1",
						cache: false,
						type: "GET",
						success: function(html) {
							$(contentDiv).html(html);
							$('.submitCommentButton') .click(submitComment);
							$('.deleteComment') .click(deleteComment);
							$(contentDiv).find('.newCommentRow').toggle();
							$(contentDiv).slideToggle();
						}
					});
				});
			} else {
				$(contentDiv).slideToggle(400, function() {
					$.ajax({
						url: "commentsForTerm/"+termID+"/1",
						cache: false,
						type: "GET",
						success: function(html) {
							$(contentDiv).html(html);
							$('.submitCommentButton') .click(submitComment);
							$('.deleteComment') .click(deleteComment);
							$(contentDiv).find('.newCommentRow').toggle();
							$(contentDiv).slideToggle();
						}
					});
				});
			}
		}
	});
}

function submitComment(evt) {
	isAuthorised(function(authorised) {
		if (authorised) {
			var contentDiv = "#"+$(evt.target).parent().parent().attr("id");
			if ($(contentDiv).find("textarea").val().length === 0) {
				if ($(contentDiv).find(".submitWarning").length === 0) {
					$(evt.target).after("<span style=\"color: #ff3300; margin-left: 7px; display: none;\" class=\"submitWarning\">You cannot save an empty comment!</span><br/>");
					$(evt.target).next().fadeIn(400);
				}
			} else {
				$.ajax({
					url: "addCommentsForTerm",
					type: "POST",
					data: JSON.stringify($(contentDiv).find("form").serializeArray()),
					processData: false,
					contentType: 'application/json; charset=utf-8',
					datatype: "html",
					success: function(html) {
						$(".submitWarning").fadeOut();
						if ($(contentDiv).find(".commentRow").length <= 1) {
							$(contentDiv).parent().parent().prevUntil('.trHover').prev().last().find('.showComments').replaceWith('<img src="static/images/balloons-box-icon-check.png" width="16" height="16" alt="Show Comments" title="Show Comments" class="toggleClick showComments" border="0" style="display: inline;">');
							$(contentDiv).parent().parent().prevUntil('.trHover').prev().last().find('.showComments').click(toggleMultipart);
						}
						$(contentDiv).find(".newCommentRow").replaceWith(html);
						$(contentDiv).find(".submitCommentButton").fadeOut(400, function() {
							$(contentDiv).find(".addCommentButton").fadeIn();
						});
						$('.addCommentButton') .click(addComment);
						$('.deleteComment') .click(deleteComment);
					},
					error: function(xhr, status) {
						$(evt.target).after("<span style=\"color: #ff3300; margin-left: 7px; display: none;\" class=\"submitWarning\">An unexpected error occurred. Please try again.</span><br/>");
						$(evt.target).next().fadeIn(400);
					},
					complete: function(xhr, status) {
					}
				});
			}
		}
	})
}

function deleteComment(evt) {
	isAuthorised(function(authorised) {
		if (authorised) {
			var parentTR = $(evt.target).parent().parent().parent();
			var termID = parentTR.parent().parent().attr('termID');
			var contentDiv = "#comments-"+termID;
			if ($(evt.target).parent().is(".commentInputArea")) {
				$(".submitWarning").fadeOut();
				parentTR.fadeOut(400, function() {
					$(contentDiv).find(".submitCommentButton").fadeOut(400, function() {
						$(contentDiv).find(".addCommentButton").fadeIn();
						if (parentTR.siblings().length === 0) {
							$(contentDiv).find(".noCommentsSpan").fadeIn();
						}
						$('.addCommentButton') .click(addComment);
						parentTR.remove();
					});
				});
			} else {
				$.confirm({
					'title'		: 'Delete comment?',
					'message'	: 'You cannot undo this action!',
					'buttons'	: {
						'Yes'	: {
							'class'	: 'blue',
							'action': function(){
								$.ajax({
									url: "deleteComment",
									type: "POST",
									data: '[{"name": "ID", "value": '+$(evt.target).next().attr('value')+'}, {"name": "TermID", "value": '+termID+'}]',
									processData: false,
									contentType: 'application/json; charset=utf-8',
									datatype: "text",
									success: function(text) {
										if (parentTR.siblings().length === 0) {
											$(contentDiv).slideToggle(400, function() {
												$(".rowChildComments-"+termID).prevUntil(".trHover").prev().last().find('.showComments').replaceWith('<img src="static/images/balloons-box-icon.png" width="16" height="16" alt="Show Comments" title="Show Comments" class="toggleClick showComments" border="0" style="display: inline;">');
												$(".rowChildComments-"+termID).prevUntil('.trHover').prev().last().find('.showComments').click(toggleMultipart);
												loadAuxData($(".rowChildComments-"+termID).prevUntil(".trHover").prev().last().find('.showComments'), contentDiv, termID);
											});
										} else {
											parentTR.fadeOut(400, function() {
												$(this).remove();
											});
										}
									},
									error: function(xhr, status) {
										$(evt.target).parent().next().before("<span style=\"color: #ff3300; margin-left: 7px; display: none;\" class=\"submitWarning\">An unexpected error occurred. Please try again.</span><br/>");
										$(evt.target).parent().next().fadeIn(400);
									},
									complete: function(xhr, status) {
									}
								});
							}
						},
						'No'	: {
							'class'	: 'blue'
						}
					}
				});
			}
		}
	})
}

function toggleTranslateTermHelper(evt, termID) {
	$(".translateTerm-"+termID).toggle();
	var toggleTarget = $(".translateTermControlsRow-"+termID);
	if (toggleTarget.is(":visible")) {
		var elements = toggleTarget.children().children(".toggle");
		elements.slideToggle().promise().done(function() {
			toggleTarget.toggle();
		})
	} else {
		$(evt.target).parent().removeClass('approvedRow');
		toggleTarget.css("display", "table-row");
		toggleTarget.children().children(".toggle").slideToggle();
	}
}

function toggleTranslateTerm(evt) {
	var termID = $(evt.target).parentsUntil('tbody').last().attr('term-id');
	if ($(evt.target).is('.cancelTranslationButton')) {
		if (($("#ignoreTerm-"+termID)[0].checked !== ($("#ignoreContent-"+termID).text() === "yes") ||
				($("#termTranslation-"+termID)[0].value === "" ? ($("#translationContent-"+termID).text() !== "click to translate" && $("#translationContent-"+termID).text() !== "") : $("#termTranslation-"+termID)[0].value !== $("#translationContent-"+termID).text()) ||
				$("#verifyTerm-"+termID)[0].checked !== ($("#verifyContent-"+termID).text() === "yes") ||
				$("#approveTerm-"+termID)[0].checked !== ($("#approveContent-"+termID).text() === "yes"))) {
			$.confirm({
				'title'		: 'Discard changes?',
				'message'	: 'You cannot undo this action!',
				'buttons'	: {
					'Yes'	: {
						'class'	: 'blue',
						'action': function(){
							toggleTranslateTermHelper(evt, termID);
							$("#ignoreTerm-"+termID)[0].checked = $("#ignoreContent-"+termID).text() === "yes";
							$("#termTranslation-"+termID)[0].value = $("#translationContent-"+termID).text() === "click to translate" ? "" : $("#translationContent-"+termID).text();
							$("#verifyTerm-"+termID)[0].checked = $("#verifyContent-"+termID).text() === "yes";
							$("#approveTerm-"+termID)[0].checked = $("#approveContent-"+termID).text() === "yes";
							if ($('.rowChildArchive-'+termID).is(':visible')) {
								$(evt.target).parentsUntil('tbody').prev().find('.showArchive').click();
							}
							if ($('.rowChildContext-'+termID).is(':visible')) {
								$(evt.target).parentsUntil('tbody').prev().find('.showContext').click();
							}
						}
					},
					'No'	: {
						'class'	: 'blue'
					}
				}
			});
		} else {
			toggleTranslateTermHelper(evt, termID);
			if ($('.rowChildArchive-'+termID).is(':visible')) {
				$(evt.target).parentsUntil('tbody').prev().find('.showArchive').click();
			}
			if ($('.rowChildContext-'+termID).is(':visible')) {
				$(evt.target).parentsUntil('tbody').prev().find('.showContext').click();
			}
		}
	} else {
		isAuthorised(function(authorised) {
			if (authorised) {
				toggleTranslateTermHelper(evt, termID);
				if (!$('.rowChildContext-'+termID).is(':visible')) {
					$(evt.target).parentsUntil('tbody').last().find('.showContext').click();
				}
			}
		})
	}
}

function saveTranslation(evt) {
	isAuthorised(function(authorised) {
		if (authorised) {
			var termID = $(evt.target).parentsUntil('tbody').last().attr('term-id');
			var contentDiv = $("#translateTermControls-"+termID);
			
			if (!$("#ignoreTerm-"+termID)[0].checked && $("#termTranslation-"+termID).val() === "") {
				if ($(contentDiv).find(".submitWarning").length === 0) {
					$(evt.target).next().after("<span style=\"color: #ff3300; margin-left: 7px; display: none;\" class=\"submitWarning\">You cannot save an empty translation unless you set ‘Ignore’ to ‘YES’!</span><br/>");
					$(evt.target).next().next().fadeIn(400);
				}
			} else {
				var data = new Array();
				data.push({name: "IgnoreTerm", value: $("#ignoreTerm-"+termID)[0].checked});
				data.push({name: "TermTranslation", value: $("#termTranslation-"+termID).val()});
				data.push({name: "Verified", value: $("#verifyTerm-"+termID)[0].checked});
				data.push({name: "Approved", value: $("#approveTerm-"+termID)[0].checked});
				data.push({name: "TermID", value: termID});
				data.push({name: "UserID", value: $("input[name=UserID]").val()});
				$.ajax({
					url: "translateTerm",
					type: "POST",
					data: JSON.stringify(data),
					processData: false,
					contentType: 'application/json; charset=utf-8',
					datatype: "json",
					success: function(json) {
						var data = JSON.parse(json);
						$("#ignoreContent-"+termID).text(data['IgnoreTerm'] === '\x01' ? "yes" : "no");
						if (data['IgnoreTerm'] === '\x01') {
							$("#ignoreContent-"+termID).addClass('redCell');
							$("#ignoreContent-"+termID).removeClass('greenCell');
						} else {
							$("#ignoreContent-"+termID).removeClass('redCell');
							$("#ignoreContent-"+termID).addClass('greenCell');
						}
						$("#translationContent-"+termID).text(data['TermTranslation'] === null ? (data['IgnoreTerm'] === '\x01' ? "" : "click to translate") : data['TermTranslation']);
						$("#translationContent-"+termID).attr('align', 'left');
						$("#dateUpdated-"+termID).text(data['DateUpdated']);
						$("#dateTranslated-"+termID).text(data['DateTranslated'] === "None" ? "never" : data['DateTranslated']);
						$("#translateUser-"+termID).text(data['TranslateUserID'] === null ? "n/a" : data['TranslateUserID']);
						$("#verifyContent-"+termID).text(data['Verified'] === '\x01' ? "yes" : "no");
						if (data['Verified'] === '\x01') {
							$("#verifyContent-"+termID).addClass('greenCell');
						} else {
							$("#verifyContent-"+termID).removeClass('greenCell');
						}
						$("#verifyUser-"+termID).text(data['VerifyUserID'] === null ? "n/a" : data['VerifyUserID']);
						$("#approveContent-"+termID).text(data['Approved'] === '\x01' ? "yes" : "no");
						if (data['Approved'] === '\x01') {
							$("#approveContent-"+termID).removeClass('redCell');
							$("#approveContent-"+termID).addClass('greenCell');
							$("#approveContent-"+termID).parent().addClass('approvedRow');
						} else {
							$("#approveContent-"+termID).addClass('redCell');
							$("#approveContent-"+termID).removeClass('greenCell');
						}
						$("#approveUser-"+termID).text(data['ApproveUserID'] === null ? "n/a" : data['ApproveUserID']);
						if (data['HasArchive'] === '\x01' && $("#approveUser-"+termID).parent().find('.showArchive').attr('src').indexOf("-check.") < 0) {
							$("#approveUser-"+termID).parent().find('.showArchive').replaceWith('<img src="static/images/clock-history-icon-check.png" width="16" height="16" alt="Show Translation History" title="Show Translation History" class="toggleClick showArchive" border="0" style="display: inline;" />');
							$("#approveUser-"+termID).parent().find('.showArchive').click(toggleMultipart);
						}
						if ($(".rowChildArchive-"+termID).is(":visible")) {
							var elements = $(".rowChildArchive-"+termID).children().children(".toggle");
							elements.slideToggle().promise().done(function() {
								$(".rowChildArchive-"+termID).toggle();
								$("#archive-"+termID).removeClass("toggle");
								$("#archive-"+termID).removeClass("auxContentLoaded");
								$("#loading-archive-"+termID).addClass("toggle");
/* 								$(evt.target).parentsUntil('tbody').last().prev().find(".showArchive").click(); */
							});
						} else {
							$("#archive-"+termID).removeClass("toggle");
							$("#archive-"+termID).removeClass("auxContentLoaded");
							$("#loading-archive-"+termID).addClass("toggle");
						}
						toggleTranslateTermHelper(evt, termID);
						if ($(".rowChildContext-"+termID).is(":visible")) {
							$(evt.target).parentsUntil('tbody').last().prev().find(".showContext").click();
						}
						if ($(".rowChildComments-"+termID).is(":visible") && $(".rowChildComments-"+termID).find('.newCommentRow').length === 0) {
							$(evt.target).parentsUntil('tbody').last().prev().find(".showComments").click();
						}
					},
					error: function(xhr, status) {
						if ($(contentDiv).find(".submitError").length === 0) {
							$(evt.target).next().after("<span style=\"color: #ff3300; margin-left: 7px; display: none;\" class=\"submitError\">An unexpected error occurred. Please try again.</span><br/>");
							$(evt.target).next().next().fadeIn(400);
						}
					},
					complete: function(xhr, status) {
					}
				});
			}
		}
	})
}