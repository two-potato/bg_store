(function () {
  function scrollTrack(trackId, direction) {
    var track = document.getElementById(trackId);
    if (!track) return;
    var step = Math.max(220, Math.floor(track.clientWidth * 0.8));
    track.scrollBy({ left: direction * step, behavior: 'smooth' });
  }

  document.addEventListener('click', function (e) {
    var prevBtn = e.target.closest('[data-carousel-prev]');
    if (prevBtn) {
      scrollTrack(prevBtn.getAttribute('data-carousel-prev'), -1);
      return;
    }
    var nextBtn = e.target.closest('[data-carousel-next]');
    if (nextBtn) {
      scrollTrack(nextBtn.getAttribute('data-carousel-next'), 1);
    }
  });
})();
