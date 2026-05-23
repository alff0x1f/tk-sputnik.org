(function () {
  var pagination = document.getElementById('pagination');
  if (!pagination) return;

  var visible = new Set();
  var anyVisible = new Set();
  var observed = new WeakSet();
  var lastPage = 0;

  var stickyTop = -(60 + pagination.offsetHeight);

  function updatePagination() {
    var currentPage;
    if (visible.size > 0) {
      currentPage = Math.min.apply(null, Array.from(visible));
      lastPage = currentPage;
    } else {
      currentPage = lastPage;
    }

    var total = parseInt(pagination.dataset.pages, 10);
    pagination.querySelectorAll('[data-page]').forEach(function (el) {
      var page = parseInt(el.dataset.page, 10);
      var isCurrent = page === currentPage;
      var isEntering = !isCurrent && anyVisible.has(page) && page > currentPage;
      el.classList.toggle('current', isCurrent);
      el.classList.toggle('entering', isEntering);
    });

    var prevEl = document.getElementById('pag-prev');
    var nextEl = document.getElementById('pag-next');
    if (prevEl) {
      prevEl.classList.toggle('disabled', currentPage <= 1);
      prevEl.href = '?page=' + Math.max(1, currentPage - 1);
    }
    if (nextEl) {
      nextEl.classList.toggle('disabled', currentPage >= total);
      nextEl.href = '?page=' + Math.min(total, currentPage + 1);
    }
  }

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
      updatePagination();
    },
    { rootMargin: stickyTop + 'px 0px 0px 0px' }
  );

  var viewObserver = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      var page = parseInt(entry.target.dataset.page, 10);
      if (entry.isIntersecting) anyVisible.add(page);
      else anyVisible.delete(page);
    });
    updatePagination();
  });

  function observeBlocks() {
    document.querySelectorAll('.page-block[data-page]').forEach(function (block) {
      if (!observed.has(block)) {
        observed.add(block);
        observer.observe(block);
        viewObserver.observe(block);
      }
    });
  }

  observeBlocks();
  document.body.addEventListener('htmx:afterSwap', observeBlocks);
}());
