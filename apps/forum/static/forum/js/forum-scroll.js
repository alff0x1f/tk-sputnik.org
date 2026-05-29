(function () {
  var pagination = document.getElementById('pagination');
  if (!pagination) return;

  var visible = new Set();
  var anyVisible = new Set();
  var observed = new WeakSet();
  var lastPage = 0;

  var stickyPanel = pagination.closest('.pagination-sticky') || pagination;
  var pageInfo = document.getElementById('pagination-info');
  var stickyTop = -(60 + stickyPanel.offsetHeight);

  function elidedPages(pivots, total) {
    if (!Array.isArray(pivots)) pivots = [pivots];
    var ON_ENDS = 2, ON_EACH_SIDE = 2;
    var pageSet = new Set();
    for (var i = 1; i <= Math.min(ON_ENDS, total); i++) pageSet.add(i);
    for (var i = Math.max(1, total - ON_ENDS + 1); i <= total; i++) pageSet.add(i);
    pivots.forEach(function (current) {
      for (var i = Math.max(1, current - ON_EACH_SIDE); i <= Math.min(total, current + ON_EACH_SIDE); i++) pageSet.add(i);
    });
    var sorted = Array.from(pageSet).sort(function (a, b) { return a - b; });
    var result = [];
    var prev = 0;
    sorted.forEach(function (p) {
      if (prev && p > prev + 1) {
        if (p === prev + 2) result.push(prev + 1);
        else result.push(null);
      }
      result.push(p);
      prev = p;
    });
    return result;
  }

  function buildPageUrl(page) {
    var params = new URLSearchParams(window.location.search);
    params.set('page', page);
    return '?' + params.toString();
  }

  function rebuildPaginationLinks(currentPage, total, enteringPage) {
    var nextEl = document.getElementById('pag-next');
    pagination.querySelectorAll('[data-page], .pag-ellipsis').forEach(function (el) { el.remove(); });
    var pivots = enteringPage ? [currentPage, enteringPage] : [currentPage];
    elidedPages(pivots, total).forEach(function (p) {
      var el;
      if (p === null) {
        el = document.createElement('span');
        el.className = 'pag-ellipsis';
        el.textContent = '…';
      } else {
        el = document.createElement('a');
        el.href = buildPageUrl(p);
        el.dataset.page = p;
        el.textContent = p;
      }
      nextEl.insertAdjacentElement('beforebegin', el);
    });
  }

  function updatePagination() {
    var currentPage;
    if (visible.size > 0) {
      currentPage = Math.min.apply(null, Array.from(visible));
      lastPage = currentPage;
    } else {
      currentPage = lastPage;
    }

    var total = parseInt(pagination.dataset.pages, 10);
    var enteringCandidate = null;
    anyVisible.forEach(function (page) {
      if (page > currentPage && !pagination.querySelector('[data-page="' + page + '"]')) {
        if (enteringCandidate === null || page < enteringCandidate) enteringCandidate = page;
      }
    });
    if (currentPage && (!pagination.querySelector('[data-page="' + currentPage + '"]') || enteringCandidate !== null)) {
      rebuildPaginationLinks(currentPage, total, enteringCandidate);
    }
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
      prevEl.href = buildPageUrl(Math.max(1, currentPage - 1));
    }
    if (nextEl) {
      nextEl.classList.toggle('disabled', currentPage >= total);
      nextEl.href = buildPageUrl(Math.min(total, currentPage + 1));
    }
    if (pageInfo && currentPage) {
      pageInfo.textContent = 'Стр. ' + currentPage + ' из ' + total;
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
