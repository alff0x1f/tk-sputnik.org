(function () {
  var pagination = document.getElementById('pagination');
  if (!pagination) return;

  var visible = new Set();
  var observed = new WeakSet();
  var lastPage = 0;

  var stickyTop = -(60 + pagination.offsetHeight);
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
        lastPage = Math.min.apply(null, Array.from(visible));
        setActivePage(lastPage);
      } else if (lastPage > 0) {
        setActivePage(lastPage);
      }
    },
    { rootMargin: stickyTop + 'px 0px 0px 0px' }
  );

  function setActivePage(page) {
    var total = parseInt(pagination.dataset.pages, 10);
    pagination.querySelectorAll('[data-page]').forEach(function (el) {
      el.classList.toggle('current', parseInt(el.dataset.page, 10) === page);
    });
    var prevEl = document.getElementById('pag-prev');
    var nextEl = document.getElementById('pag-next');
    if (prevEl) {
      prevEl.classList.toggle('disabled', page <= 1);
      prevEl.href = '?page=' + Math.max(1, page - 1);
    }
    if (nextEl) {
      nextEl.classList.toggle('disabled', page >= total);
      nextEl.href = '?page=' + Math.min(total, page + 1);
    }
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
