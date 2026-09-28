const menu = document.querySelector('.menu-toggle');
menu?.addEventListener('click', () => {
  const open = menu.getAttribute('aria-expanded') !== 'true';
  menu.setAttribute('aria-expanded', String(open));
  document.querySelector('.sidebar').classList.toggle('is-open', open);
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && menu?.getAttribute('aria-expanded') === 'true') {
    menu.click(); menu.focus();
  }
});
document.querySelectorAll('pre').forEach(pre => {
  const button = document.createElement('button');
  button.className = 'copy-button'; button.textContent = '复制';
  button.setAttribute('aria-label', '复制代码');
  pre.append(button);
  button.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(pre.querySelector('code').textContent);
      button.textContent = '已复制';
      document.querySelector('#copy-status').textContent = '代码已复制';
    } catch {
      const range = document.createRange(); range.selectNodeContents(pre.querySelector('code'));
      const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
      button.textContent = '请手动复制';
      document.querySelector('#copy-status').textContent = '已选中代码，请手动复制';
    }
    setTimeout(() => { button.textContent = '复制'; }, 2000);
  });
});
