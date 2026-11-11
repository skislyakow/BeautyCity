$(document).ready(function() {
	$('.salonsSlider').slick({
		arrows: true,
		slidesToShow: 3,
		infinite: true,
		prevArrow: $('.salons .leftArrow'),
		nextArrow: $('.salons .rightArrow'),
		responsive: [
			{
				breakpoint: 991,
				settings: {
					centerMode: true,
					slidesToShow: 2
				}
			},
			{
				breakpoint: 575,
				settings: {
					slidesToShow: 1
				}
			}
		]
	});

	$('.servicesSlider').slick({
		arrows: true,
		slidesToShow: 4,
		prevArrow: $('.services .leftArrow'),
		nextArrow: $('.services .rightArrow'),
		responsive: [
			{
				breakpoint: 1199,
				settings: {
					slidesToShow: 3
				}
			},
			{
				breakpoint: 991,
				settings: {
					centerMode: true,
					slidesToShow: 2
				}
			},
			{
				breakpoint: 575,
				settings: {
					slidesToShow: 1
				}
			}
		]
	});

	$('.mastersSlider').slick({
		arrows: true,
		slidesToShow: 4,
		prevArrow: $('.masters .leftArrow'),
		nextArrow: $('.masters .rightArrow'),
		responsive: [
			{
				breakpoint: 1199,
				settings: {
					slidesToShow: 3
				}
			},
			{
				breakpoint: 991,
				settings: {
					slidesToShow: 2
				}
			},
			{
				breakpoint: 575,
				settings: {
					slidesToShow: 1
				}
			}
		]
	});

	$('.reviewsSlider').slick({
		arrows: true,
		slidesToShow: 4,
		prevArrow: $('.reviews .leftArrow'),
		nextArrow: $('.reviews .rightArrow'),
		responsive: [
			{
				breakpoint: 1199,
				settings: {
					slidesToShow: 3
				}
			},
			{
				breakpoint: 991,
				settings: {
					slidesToShow: 2
				}
			},
			{
				breakpoint: 575,
				settings: {
					slidesToShow: 1
				}
			}
		]
	});

	$('.header__mobMenu').click(function() {
		$('#mobMenu').show();
	});
	$('.mobMenuClose').click(function() {
		$('#mobMenu').hide();
	});


	var acc = document.getElementsByClassName("accordion");
	var i;

	for (i = 0; i < acc.length; i++) {
		acc[i].addEventListener("click", function(e) {
			e.preventDefault();
			this.classList.toggle("active");
			var panel = $(this).next();
			panel.hasClass('active') ? panel.removeClass('active') : panel.addClass('active');
		});
	}

	$('.authTriggerBtn').click(function(e) {
		e.preventDefault();
		$('#authModal').arcticmodal();
	});

	function openReviewModal(specialistId) {
		$('#reviewModal .reviewPopup__specialist').val(specialistId || '');
		$('#reviewModal .reviewPopup__error').hide().text('');
		$('#reviewModal').arcticmodal();
	}

	$('.rewiewPopupOpen').click(function(e) {
		e.preventDefault();
		if (!window.IS_AUTHENTICATED) {
			sessionStorage.setItem('openReviewAfterAuth', '1');
			$('#authModal').arcticmodal();
			return;
		}
		openReviewModal($(this).data('specialist-id') || '');
	});

	if (window.IS_AUTHENTICATED && sessionStorage.getItem('openReviewAfterAuth') === '1') {
		sessionStorage.removeItem('openReviewAfterAuth');
		openReviewModal('');
	}

	$('.tipsPopupOpen').click(function(e) {
		e.preventDefault();
		$('#tipsModal .tipsPopup__booking').val($(this).data('booking-id') || '');
		$('#tipsModal .tipsPopup__error').hide().text('');
		$('#tipsModal').arcticmodal();
	});

	$('.callbackTriggerBtn').click(function(e) {
		e.preventDefault();
		$('#callbackModal').arcticmodal();
	});

	$('.callbackPopup__form').on('submit', function(e) {
		e.preventDefault();
		var $form = $(this);
		var $error = $form.find('.callbackPopup__error');
		var $btn = $form.find('button[type="submit"]');

		$error.hide().text('');
		if (!$form.find('.callbackPopup__agree').prop('checked')) {
			$error.text('Необходимо согласие с политикой конфиденциальности').show();
			return;
		}

		$btn.prop('disabled', true);
		$.post($form.data('url'), $form.serialize())
			.done(function() {
				$form.html('<div class="popup__text">Заявка принята, перезвоним в ближайшее время</div>');
			})
			.fail(function(xhr) {
				var msg = (xhr.responseJSON && (xhr.responseJSON.message || xhr.responseJSON.error)) || 'Не удалось отправить заявку';
				$error.text(msg).show();
				$btn.prop('disabled', false);
			});
	});

	$('.reviewPopup__form').on('submit', function(e) {
		e.preventDefault();
		var $form = $(this);
		var $error = $form.find('.reviewPopup__error');
		var $btn = $form.find('button[type="submit"]');
		$error.hide().text('');
		if (!$form.find('.reviewPopup__agree').prop('checked')) {
			$error.text('Необходимо согласие с политикой конфиденциальности').show();
			return;
		}
		if (!$form.find('.reviewPopup__specialist').val()) {
			$error.text('Выберите мастера').show();
			return;
		}
		$btn.prop('disabled', true);
		$.post($form.data('url'), $form.serialize())
			.done(function() {
				$form.html('<div class="popup__text">Спасибо! Отзыв отправлен.</div>');
			})
			.fail(function(xhr) {
				var msg = (xhr.responseJSON && (xhr.responseJSON.message || xhr.responseJSON.error || xhr.responseJSON.detail)) || 'Не удалось отправить отзыв';
				$error.text(msg).show();
				$btn.prop('disabled', false);
			});
	});

	$('.tipsPopup__form').on('submit', function(e) {
		e.preventDefault();
		var $form = $(this);
		var $error = $form.find('.tipsPopup__error');
		var $btn = $form.find('button[type="submit"]');
		$error.hide().text('');
		if (!$form.find('.tipsPopup__booking').val()) {
			$error.text('Не удалось определить запись').show();
			return;
		}
		$btn.prop('disabled', true);
		$.post($form.data('url'), $form.serialize())
			.done(function() {
				$form.html('<div class="popup__text">Спасибо! Чаевые отправлены.</div>');
			})
			.fail(function(xhr) {
				var msg = (xhr.responseJSON && (xhr.responseJSON.message || xhr.responseJSON.error)) || 'Не удалось отправить чаевые';
				$error.text(msg).show();
				$btn.prop('disabled', false);
			});
	});

	$('.notes__cancelBtn').on('click', function(e) {
		e.preventDefault();
		var $btn = $(this);
		if (!confirm('Отменить запись?')) return;
		var url = $btn.data('url');
		var csrf = $('input[name="csrfmiddlewaretoken"]').first().val();
		$btn.prop('disabled', true);
		$.post(url, {csrfmiddlewaretoken: csrf})
			.done(function() {
				window.location.reload();
			})
			.fail(function(xhr) {
				var msg = (xhr.responseJSON && (xhr.responseJSON.message || xhr.responseJSON.error)) || 'Не удалось отменить запись';
				alert(msg);
				$btn.prop('disabled', false);
			});
	});
});
