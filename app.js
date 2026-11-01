const repository = 'jonneyiphonex-beep/Telecomerl';
const apiUrl = `https://api.github.com/repos/${repository}`;

const elements = {
  stars: document.querySelector('#stars'),
  forks: document.querySelector('#forks'),
  language: document.querySelector('#language'),
  created: document.querySelector('#created'),
  updated: document.querySelector('#updated-at'),
  sync: document.querySelector('#sync-label'),
  refresh: document.querySelector('#refresh'),
  metrics: document.querySelector('.metrics'),
};

const formatNumber = new Intl.NumberFormat('ar');
const formatDate = new Intl.DateTimeFormat('ar', { year: 'numeric', month: 'short' });

function showFallback(message) {
  elements.stars.textContent = '0';
  elements.forks.textContent = '0';
  elements.language.textContent = 'Erlang';
  elements.created.textContent = 'سبتمبر 2026';
  elements.sync.textContent = 'تعذر التحديث';
  elements.updated.textContent = message;
}

async function loadRepository() {
  elements.refresh.disabled = true;
  elements.refresh.setAttribute('aria-busy', 'true');
  elements.sync.textContent = 'جارٍ التحديث';
  elements.metrics.classList.add('is-loading');

  try {
    const response = await fetch(apiUrl, {
      headers: { Accept: 'application/vnd.github+json' },
      cache: 'no-store',
    });
    if (!response.ok) throw new Error(`GitHub API: ${response.status}`);

    const data = await response.json();
    elements.stars.textContent = formatNumber.format(data.stargazers_count ?? 0);
    elements.forks.textContent = formatNumber.format(data.forks_count ?? 0);
    elements.language.textContent = data.language || 'غير محدد';
    elements.created.textContent = data.created_at
      ? formatDate.format(new Date(data.created_at))
      : 'غير متاح';
    elements.sync.textContent = 'محدّثة من GitHub';
    elements.updated.textContent = `آخر تحديث للمستودع: ${formatDate.format(new Date(data.pushed_at))}`;
  } catch (error) {
    showFallback('تعذّر الاتصال بـ GitHub؛ تُعرض بيانات احتياطية.');
  } finally {
    elements.refresh.disabled = false;
    elements.refresh.removeAttribute('aria-busy');
    elements.metrics.classList.remove('is-loading');
  }
}

elements.refresh.addEventListener('click', loadRepository);
loadRepository();