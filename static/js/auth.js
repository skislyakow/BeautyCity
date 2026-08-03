$(function () {
	function getCookie(name) {
		let cookieValue = null;
		if (document.cookie && document.cookie !== '') {
			const cookies = document.cookie.split(';');
			for (let cookie of cookies) {
				cookie = cookie.trim();
				if (cookie.substring(0, name.length + 1) === (name + '=')) {
					cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
					break;
				}
			}
		}
		return cookieValue;
	}
	$.ajaxSetup({
		beforeSend: function (xhr, settings) {
			if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type)) {
				xhr.setRequestHeader('X-CSRFToken', getCookie('csrftoken'));
			}
		}
	});

	let pendingPhone = null;

	function formatPhone(raw) {
		const digits = String(raw || '').replace(/\D/g, '');
		let d = digits;
		if (d.length === 11 && (d[0] === '7' || d[0] === '8')) d = d.slice(1);
		if (d.length !== 10) return String(raw || '');
		return `+7 (${d.slice(0, 3)}) ${d.slice(3, 6)} ${d.slice(6, 8)} ${d.slice(8, 10)}`;
	}

	$('.authPopup__form').on('submit', function (e) {
		e.preventDefault();
		const $form = $(this);
		const $error = $form.find('.authPopup__error');
		const phone = $form.find('input[name="tel"]').val();

		$error.hide().text('');

		$.post(window.AUTH_URLS.requestCode, {tel: phone})
			.done(function (data) {
				pendingPhone = data.phone;
				$('#confirmPhone').text(formatPhone(pendingPhone));
				$('#authModal').arcticmodal('close');
				$('#confirmModal').arcticmodal();
			})
			.fail(function (xhr) {
				const msg = (xhr.responseJSON && xhr.responseJSON.message || xhr.responseJSON.error) || 'Не удалось отправить код';
				$error.text(msg).show();
			});
	});

	$('.confirmPopup__form').on('submit', function (e) {
		e.preventDefault();
		const $form = $(this);
		const $error = $form.find('.confirmPopup__error');

		$error.hide().text('');

		if (!pendingPhone) {
			$error.text('Сессия истекла, запросите код заново').show();
			return;
		}

		$.post(window.AUTH_URLS.confirmCode, {
			phone: pendingPhone,
			num1: $form.find('input[name="num1"]').val(),
			num2: $form.find('input[name="num2"]').val(),
			num3: $form.find('input[name="num3"]').val(),
			num4: $form.find('input[name="num4"]').val(),
		})
			.done(function (data) {
				window.location.href = data.redirect || '/notes/';
			})
			.fail(function (xhr) {
				const msg = (xhr.responseJSON && xhr.responseJSON.message || xhr.responseJSON.error) || 'Неверный код';
				$error.text(msg).show();
			});
	});

	$('.confirmResend').on('click', function (e) {
		e.preventDefault();
		if (!pendingPhone) return;
		$.post(window.AUTH_URLS.requestCode, {tel: pendingPhone});
	});

	$('.confirmPopup__number input').on('input', function () {
		const $this = $(this);
		if ($this.val().length === 1) {
			$this.next('input').trigger('focus');
		}
	});
});