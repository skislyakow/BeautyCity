$(function () {
	function getAvatarUrl(photoPath) {
		if (!photoPath) {
			return window.STATIC_URL ? window.STATIC_URL + 'img/masters/master1.svg' : '/static/img/masters/master1.svg';
		}
		if (photoPath.startsWith('/') || photoPath.startsWith('http')) {
			return photoPath;
		}
		if (photoPath.startsWith('static/')) {
			return '/' + photoPath;
		}
		return '/static/' + photoPath;
	}

	const state = {
		salon: null,       // {id, name, address}
		procedure: null,   // {id, title, base_price, duration_minutes}
		specialist: null,  // {id, full_name, photo, bio}
		date: null,        // 'YYYY-MM-DD'
		time: null,        // 'HH:MM'
	};

	function fmtPrice(p) {
		return `${p} ₽`;
	}

	$.get('/api/salons/', function (salons) {
		const $list = $('#salonsList');
		$list.empty();
		if (!salons.length) {
			$list.html('<p>Салоны пока не добавлены.</p>');
			return;
		}
		salons.forEach(function (salon) {
			const $item = $(`
				<div class="accordion__block fic" data-id="${salon.id}" style="cursor:pointer;">
					<div class="accordion__block_intro">${salon.name}</div>
					<div class="accordion__block_address">${salon.address}</div>
				</div>
			`);
			$item.on('click', function () {
				state.salon = salon;
				state.procedure = null;
				state.specialist = null;
				$('#salonsList .accordion__block').css('font-weight', 'normal');
				$item.css('font-weight', 'bold');
				$('#salonAccordionBtn').addClass('selected').text(`${salon.name}  ${salon.address}`);
				loadProcedures(salon.id);
				resetSpecialists('(Сначала выберите услугу)');
				resetSlots();
			});
			$list.append($item);
		});
	}).fail(function () {
		$('#salonsList').html('<p>Не удалось загрузить салоны.</p>');
	});

	function loadProcedures(salonId) {
		const $btn = $('#procedureAccordionBtn').prop('disabled', false).text('(Выберите услугу)');
		const $list = $('#proceduresList').empty().html('<p class="js-loading">Загрузка услуг...</p>');

		$.get(`/api/salons/${salonId}/procedures/`, function (offerings) {
			$list.empty();
			if (!offerings.length) {
				$list.html('<p>Для этого салона услуги пока не заведены.</p>');
				return;
			}
			offerings.forEach(function (offering) {
				const procedure = offering.procedure;
				const $item = $(`
					<div class="accordion__block_item fic" data-id="${procedure.id}" style="cursor:pointer;">
						<div class="accordion__block_item_intro">${procedure.title}</div>
						<div class="accordion__block_item_address">${fmtPrice(offering.price)}</div>
					</div>
				`);
				$item.on('click', function () {
					state.procedure = procedure;
					state.specialist = null;
					$list.find('.accordion__block_item').css('font-weight', 'normal');
					$item.css('font-weight', 'bold');
					$('#procedureAccordionBtn').addClass('selected').text(`${procedure.title}  ${fmtPrice(offering.price)}`);
					loadSpecialists(state.salon.id, procedure.id);
					resetSlots();
				});
				$list.append($item);
			});
		}).fail(function () {
			$list.html('<p>Не удалось загрузить услуги.</p>');
		});
	}

	function loadSpecialists(salonId, procedureId) {
		const $btn = $('#specialistAccordionBtn').prop('disabled', false).text('(Выберите мастера)');
		const $list = $('#specialistsList').empty().html('<p class="js-loading">Загрузка мастеров...</p>');

		$.get('/api/specialists/', { salon: salonId, procedure: procedureId }, function (specialists) {
			$list.empty();
			if (!specialists.length) {
				$list.html('<p>Для этой услуги в этом салоне пока нет мастеров.</p>');
				return;
			}
			specialists.forEach(function (specialist) {
				const img = getAvatarUrl(specialist.photo);
				const profText = specialist.bio || '';
				const profHtml = profText ? `<div class="accordion__block_prof">${profText}</div>` : '';

				const $item = $(`
					<div class="accordion__block fic" data-id="${specialist.id}" style="cursor:pointer;">
						<div class="accordion__block_elems fic">
							<img src="${img}" alt="avatar" class="accordion__block_img">
							<div class="accordion__block_master">${specialist.full_name}</div>
						</div>
						${profHtml}
					</div>
				`);
				$item.on('click', function () {
					state.specialist = specialist;
					$list.find('.accordion__block').css('font-weight', 'normal');
					$item.css('font-weight', 'bold');

					let clone = $item.clone();
					$('#specialistAccordionBtn').addClass('selected').html(clone);

					resetSlots();
					if (state.date) loadSlots();
				});
				$list.append($item);
			});
		}).fail(function () {
			$list.html('<p>Не удалось загрузить мастеров.</p>');
		});
	}

	function resetSpecialists(placeholderText) {
		$('#specialistAccordionBtn').removeClass('selected').prop('disabled', true).text(placeholderText);
		$('#specialistsList').empty();
	}

	function resetSlots() {
		state.time = null;
		$('#nextBtn').prop('disabled', true).removeClass('active');
		$('#timeSlotsContainer').html('<p class="js-loading">Выберите салон, услугу, мастера и дату</p>');
	}

	function handleDateSelection(dateObj) {
		if (!dateObj) return;
		const yyyy = dateObj.getFullYear();
		const mm = String(dateObj.getMonth() + 1).padStart(2, '0');
		const dd = String(dateObj.getDate()).padStart(2, '0');
		state.date = `${yyyy}-${mm}-${dd}`;
		state.time = null;
		if (state.salon && state.procedure && state.specialist) {
			loadSlots();
		} else {
			$('#timeSlotsContainer').html('<p class="js-loading">Сначала выберите салон, услугу и мастера</p>');
		}
	}

function initCalendar() {
		const $dp = $('#datepickerHere');

		if ($.fn.datepicker) {
			$dp.datepicker({
				minDate: new Date(),
				onSelect: function (formattedDate, date) {
					handleDateSelection(date || new Date(formattedDate));
				}
			});
		}
		else if (typeof AirDatepicker !== 'undefined') {
			new AirDatepicker('#datepickerHere', {
				minDate: new Date(),
				onSelect: function({date}) {
					if (date) handleDateSelection(date);
				}
			});
		}
		else {
			console.warn("Библиотека календаря еще не загружена, ждем...");
			setTimeout(initCalendar, 200);
		}
	}

	initCalendar();

	$(document).on('change', '#datepickerHere', function() {
		const val = $(this).val();
		if (val) {
			const parsedDate = new Date(val);
			if (!isNaN(parsedDate.getTime())) {
				handleDateSelection(parsedDate);
			}
		}
	});

	function loadSlots() {
		const $container = $('#timeSlotsContainer').html('<p class="js-loading">Загрузка свободного времени...</p>');

		$.get('/api/slots/', {
			salon: state.salon.id,
			specialist: state.specialist.id,
			procedure: state.procedure.id,
			date: state.date,
		}, function (data) {
			const slots = data.slots || [];
			$container.empty();
			if (!slots.length) {
				$container.html('<p>На эту дату свободного времени нет — выберите другую дату.</p>');
				return;
			}
			const groups = { 'Утро': [], 'День': [], 'Вечер': [] };
			slots.forEach(function (t) {
				const hour = parseInt(t.split(':')[0], 10);
				if (hour < 12) groups['Утро'].push(t);
				else if (hour < 17) groups['День'].push(t);
				else groups['Вечер'].push(t);
			});
			Object.keys(groups).forEach(function (label) {
				if (!groups[label].length) return;
				const $group = $(`<div class="time__items"><div class="time__elems_intro">${label}</div><div class="time__elems_elem fic"></div></div>`);
				groups[label].forEach(function (t) {
					const shortTime = t.slice(0, 5);
					const $btn = $(`<button type="button" data-time="${shortTime}" class="time__elems_btn">${shortTime}</button>`);
					$btn.on('click', function () {
						state.time = shortTime;
						$container.find('.time__elems_btn').removeClass('active');
						$btn.addClass('active');
						$('#nextBtn').prop('disabled', false).addClass('active');
					});
					$group.find('.time__elems_elem').append($btn);
				});
				$container.append($group);
			});
		}).fail(function () {
			$container.html('<p>Не удалось загрузить свободное время.</p>');
		});
	}

	$('#nextBtn').on('click', function () {
		if (!state.salon || !state.procedure || !state.specialist || !state.date || !state.time) {
			alert('Заполните все шаги записи: салон, услугу, мастера, дату и время');
			return;
		}
		sessionStorage.setItem('bc_booking_draft', JSON.stringify(state));
		window.location.href = "/service-finally/";
	});
});