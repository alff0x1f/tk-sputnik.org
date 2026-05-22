(function () {
  var pagination = document.getElementById('pagination');
  if (!pagination) return;

  var visible = new Set();
  var observed = new WeakSet();

  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        var page = parseInt(entry.target.dataset.page, 10);
        if (entry.isIntersecting) {
          visible.add(page);
        } else {
          visible.delete(page);
        }
      });
      if (visible.size > 0) {
        setActivePage(Math.min.apply(null, Array.from(visible)));
      }
    },
    { rootMargin: '-60px 0px 0px 0px' }
  );

  function setActivePage(page) {
    pagination.querySelectorAll('[data-page]').forEach(function (el) {
      el.classList.toggle('current', parseInt(el.dataset.page, 10) === page);
    });
  }

  function observeBlocks() {
    document.querySelectorAll('.page-block[data-page]').forEach(function (block) {
      if (!observed.has(block)) {
        observed.add(block);
        observer.observe(block);
      }
    });
  }

  observeBlocks();
  document.body.addEventListener('htmx:afterSwap', observeBlocks);
}());
