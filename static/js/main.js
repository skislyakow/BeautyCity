$(document).ready(function() {
	// 1. Слайдеры
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

	// 2. Мобильное меню
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

	// 5. Попапы / Модальные окна
	$('.authTriggerBtn').click(function(e) {
		e.preventDefault();
		$('#authModal').arcticmodal();
	});

	$('.rewiewPopupOpen').click(function(e) {
		e.preventDefault();
		$('#reviewModal').arcticmodal();
	});

	$('.payPopupOpen').click(function(e) {
		e.preventDefault();
		$('#paymentModal').arcticmodal();
	});

	$('.tipsPopupOpen').click(function(e) {
		e.preventDefault();
		$('#tipsModal').arcticmodal();
	});

	$('.authPopup__form').submit(function() {
		$('#confirmModal').arcticmodal();
		return false;
	});
});