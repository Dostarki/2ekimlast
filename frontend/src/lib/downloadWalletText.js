export function downloadWalletText(text, filename) {
  const count = text.split(/\r?\n/).filter(line => line.trim()).length;
  if (!count) return 0;
  const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url; link.download = filename; link.hidden = true;
  document.body.appendChild(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  return count;
}
