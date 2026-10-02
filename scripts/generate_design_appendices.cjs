#!/usr/bin/env node
/* Deterministic technical appendix generator; intentionally uses Node stdlib only. */
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const root = path.resolve(__dirname, '..');
const guide = path.join(root, 'PROJE_TASARIM_VE_MATERYAL_REHBERI.md');
const marker = '<!-- TECHNICAL_APPENDICES -->';
const ignoredNames = new Set(['.git', '.codex', '.emergent', 'node_modules', 'venv', '.venv', 'cache', '.cache', 'build', 'dist', 'coverage', '__pycache__', '.pytest_cache']);
const posix = value => value.split(path.sep).join('/');
const relative = file => posix(path.relative(root, file));
const sortFiles = files => files.sort((a, b) => relative(a).localeCompare(relative(b), 'en'));
const sha256 = buffer => crypto.createHash('sha256').update(buffer).digest('hex');

function walk(dir) {
  const found = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (ignoredNames.has(entry.name) || entry.name.startsWith('.env')) continue;
    const file = path.join(dir, entry.name);
    const stat = fs.lstatSync(file);
    if (stat.isSymbolicLink()) continue;
    if (stat.isDirectory()) found.push(...walk(file));
    else if (stat.isFile()) found.push(file);
  }
  return found;
}

function codeFence(language, text) {
  return `\`\`\`${language}\n${text.endsWith('\n') ? text : `${text}\n`}\`\`\``;
}

function jpegSize(buffer) {
  if (buffer[0] !== 0xff || buffer[1] !== 0xd8) return 'okunamadı';
  let offset = 2;
  while (offset + 9 < buffer.length) {
    if (buffer[offset] !== 0xff) { offset++; continue; }
    while (buffer[offset] === 0xff) offset++;
    const markerByte = buffer[offset++];
    if (markerByte === 0xd8 || markerByte === 0xd9 || (markerByte >= 0xd0 && markerByte <= 0xd7)) continue;
    const length = buffer.readUInt16BE(offset);
    if (length < 2 || offset + length > buffer.length) break;
    if ((markerByte >= 0xc0 && markerByte <= 0xc3) || (markerByte >= 0xc5 && markerByte <= 0xc7) || (markerByte >= 0xc9 && markerByte <= 0xcb) || (markerByte >= 0xcd && markerByte <= 0xcf)) {
      return `${buffer.readUInt16BE(offset + 5)} × ${buffer.readUInt16BE(offset + 3)}`;
    }
    offset += length;
  }
  return 'okunamadı';
}

function wavInfo(buffer) {
  if (buffer.subarray(0, 4).toString() !== 'RIFF' || buffer.subarray(8, 12).toString() !== 'WAVE') return { format: 'okunamadı' };
  let offset = 12, fmt, dataBytes = 0;
  while (offset + 8 <= buffer.length) {
    const id = buffer.subarray(offset, offset + 4).toString();
    const length = buffer.readUInt32LE(offset + 4);
    const begin = offset + 8;
    if (begin + length > buffer.length) break;
    if (id === 'fmt ' && length >= 16) fmt = { format: buffer.readUInt16LE(begin), channels: buffer.readUInt16LE(begin + 2), rate: buffer.readUInt32LE(begin + 4), bits: buffer.readUInt16LE(begin + 14), byteRate: buffer.readUInt32LE(begin + 8) };
    if (id === 'data') dataBytes += length;
    offset = begin + length + (length % 2);
  }
  const seconds = fmt && fmt.byteRate ? (dataBytes / fmt.byteRate).toFixed(3) : '?';
  return fmt ? { ...fmt, dataBytes, seconds } : { format: 'okunamadı', dataBytes };
}

function table(rows, headers) {
  return [`| ${headers.join(' | ')} |`, `| ${headers.map(() => '---').join(' | ')} |`, ...rows.map(row => `| ${row.join(' | ')} |`)].join('\n');
}

function linesWithColors(file) {
  const text = fs.readFileSync(file, 'utf8');
  const pattern = /#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b|\b0x[0-9a-fA-F]{6}\b|\b(?:rgba?|hsla?)\([^\n)]*\)|--[\w-]+\s*:\s*-?[\d.]+(?:deg)?\s+-?[\d.]+%\s+-?[\d.]+%/g;
  return text.split(/\r?\n/).flatMap((line, index) => {
    const values = [...line.matchAll(pattern)].map(match => match[0]);
    return values.length ? [[relative(file), index + 1, values.map(value => `\`${value}\``).join(', ')]] : [];
  });
}

function balancedBlock(text, start) {
  const open = text.indexOf('{', start);
  if (open < 0) return null;
  let depth = 0;
  for (let index = open; index < text.length; index++) {
    if (text[index] === '{') depth++;
    if (text[index] === '}' && --depth === 0) return text.slice(start, index + 1);
  }
  return null;
}

function materialRecords(files) {
  const records = [];
  const seenShaders = new Set();
  const interesting = /new\s+(?:THREE\.)?(?:Mesh(?:Basic|Lambert|Phong|Standard|Physical|Toon|Normal|Depth|Distance|Matcap)Material|Line(?:Basic|Dashed)Material|PointsMaterial|SpriteMaterial|ShaderMaterial|RawShaderMaterial|AmbientLight|HemisphereLight|DirectionalLight|PointLight|SpotLight|RectAreaLight)\b|\b(?:material|createMaterial|makeMaterial)\s*\(|\.(?:color|intensity)\s*(?:=|\.set\s*\()/;
  for (const file of files) {
    const text = fs.readFileSync(file, 'utf8');
    const lines = text.split(/\r?\n/);
    lines.forEach((line, index) => {
      if (!interesting.test(line)) return;
      const shaderAt = line.indexOf('ShaderMaterial');
      if (shaderAt >= 0) {
        const start = text.lastIndexOf('new ', text.indexOf(line) + shaderAt);
        const key = `${file}:${start}`;
        if (!seenShaders.has(key)) {
          seenShaders.add(key);
          const block = balancedBlock(text, start);
          records.push(`### ${relative(file)}:${index + 1}\n\n${codeFence('js', block || line)}`);
        }
      } else {
        records.push(`### ${relative(file)}:${index + 1}\n\n${codeFence('js', line)}`);
      }
    });
  }
  return records;
}

function lucideRecords(files) {
  const rows = [];
  for (const file of files) {
    const text = fs.readFileSync(file, 'utf8');
    const names = [];
    const importPattern = /import\s*\{([^{}]*)\}\s*from\s*['\"]lucide-react['\"]/g;
    for (const match of text.matchAll(importPattern)) names.push(...match[1].split(',').map(value => value.trim()).filter(Boolean));
    if (names.length) rows.push([`\`${relative(file)}\``, names.map(value => `\`${value}\``).join(', ')]);
  }
  return rows;
}

const allFiles = sortFiles(walk(root));
const sourceFiles = allFiles.filter(file => /^frontend\/src\//.test(relative(file)) && /\.(?:js|jsx|css)$/.test(file));
const cssFiles = sourceFiles.filter(file => file.endsWith('.css'));
const jsFiles = sourceFiles.filter(file => /\.(?:js|jsx)$/.test(file));
const colorFiles = sortFiles([...sourceFiles, path.join(root, 'design_guidelines.json'), ...allFiles.filter(file => /^backend\//.test(relative(file)) && file.endsWith('.py'))]);
const publicImages = sortFiles(allFiles.filter(file => /^frontend\/public\//.test(relative(file)) && /\.jpe?g$/i.test(file)));
const wavFiles = sortFiles(allFiles.filter(file => /^frontend\/public\/audio\//.test(relative(file)) && file.endsWith('.wav')));
const reportImages = sortFiles(allFiles.filter(file => /^test_reports\//.test(relative(file)) && /\.jpe?g$/i.test(file)));

const sections = [];
sections.push('# 14. Otomatik çıkarılmış teknik ekler');
sections.push('Bu bölüm `scripts/generate_design_appendices.cjs` ile yeniden üretilir. Listeleme sırası yol adına göre belirlenir; sembolik bağlar izlenmez.');
sections.push(`## 14.1 Yerel dağıtım görselleri (${publicImages.length})`);
sections.push(table(publicImages.map(file => { const data = fs.readFileSync(file); return [`\`${relative(file)}\``, jpegSize(data), data.length, `\`${sha256(data)}\``]; }), ['Yol', 'Gerçek ölçü', 'Byte', 'SHA-256']));
sections.push(`## 14.2 Yerel WAV envanteri (${wavFiles.length})`);
sections.push(table(wavFiles.map(file => { const data = fs.readFileSync(file), info = wavInfo(data); return [`\`${relative(file)}\``, data.length, info.format, info.channels, info.rate, info.bits, info.dataBytes, info.seconds, `\`${sha256(data)}\``]; }), ['Yol', 'Byte', 'Format', 'Kanal', 'Hz', 'Bit', 'Data byte', 'Süre/sn', 'SHA-256']));
sections.push(`## 14.3 Tarihsel test JPEG envanteri (${reportImages.length})`);
sections.push(table(reportImages.map(file => { const data = fs.readFileSync(file); return [`\`${relative(file)}\``, jpegSize(data), data.length, `\`${sha256(data)}\``]; }), ['Yol', 'Gerçek ölçü', 'Byte', 'SHA-256']));
const credits = fs.readFileSync(path.join(root, 'frontend/public/audio/CREDITS.txt'), 'utf8');
sections.push(`## 14.4 Ses kaynak beyanı\n\n${codeFence('text', credits)}\n\nQ009 koşulları: [Q009-LICENSE.txt](frontend/public/audio/Q009-LICENSE.txt).`);
const colors = colorFiles.flatMap(linesWithColors);
sections.push(`## 14.5 Kaynak bazlı renk envanteri (${colors.length} satır)\n\nCSS HSL tokenları ve dinamik ` + '`rgba(...)`' + ` ifadeleri kaynakta yazıldığı haliyle tutulur.\n\n${table(colors, ['Dosya', 'Satır', 'Literal'])}`);
sections.push(`## 14.6 Three.js materyal, ışık ve renk/intensity kaynakları\n\n${materialRecords(jsFiles).join('\n\n') || 'Kayıt bulunamadı.'}`);
const icons = lucideRecords(jsFiles);
sections.push(`## 14.7 Lucide ikon ithalatları (${icons.length} dosya)\n\n${icons.length ? table(icons, ['Dosya', 'İkonlar']) : 'Kayıt bulunamadı.'}`);
sections.push(`## 14.8 CSS kaynakları (${cssFiles.length})`);
for (const file of cssFiles) sections.push(`### ${relative(file)}\n\n${codeFence('css', fs.readFileSync(file, 'utf8'))}`);
const uiDefinitionFiles = ['frontend/src/components/ui/button.jsx', 'frontend/src/components/ui/dialog.jsx', 'frontend/tailwind.config.js'].map(value => path.join(root, value)).filter(fs.existsSync);
sections.push('## 14.9 Button/Dialog ve Tailwind kaynak kayıtları');
for (const file of uiDefinitionFiles) sections.push(`### ${relative(file)}\n\n${codeFence(file.endsWith('.json') ? 'json' : 'js', fs.readFileSync(file, 'utf8'))}`);
sections.push(`## 14.10 Frontend paket manifesti\n\n${codeFence('json', fs.readFileSync(path.join(root, 'frontend/package.json'), 'utf8'))}`);
sections.push(`## 14.11 Backend gereksinim beyanı\n\n${codeFence('text', fs.readFileSync(path.join(root, 'backend/requirements.txt'), 'utf8'))}`);
sections.push(`## 14.12 UI ve oyun kaynak dosyaları (${sourceFiles.length})\n\n${table(sourceFiles.map(file => [`\`${relative(file)}\``, fs.statSync(file).size]), ['Yol', 'Byte'])}`);
const inventoryFiles = allFiles.filter(file => file !== guide);
sections.push(`## 14.13 Kapsam içi dosya envanteri (${inventoryFiles.length})\n\nRehberin boyutu üretim sırasında değiştiği için bu envanterde yer almaz.\n\n${table(inventoryFiles.map(file => [`\`${relative(file)}\``, fs.statSync(file).size]), ['Yol', 'Byte'])}`);

const original = fs.readFileSync(guide, 'utf8');
const markerAt = original.indexOf(marker);
if (markerAt < 0) throw new Error(`İşaretleyici bulunamadı: ${marker}`);
if (original.indexOf(marker, markerAt + marker.length) >= 0) throw new Error(`İşaretleyici birden fazla kez bulundu: ${marker}`);
const prefix = original.slice(0, markerAt + marker.length);
fs.writeFileSync(guide, `${prefix}\n\n${sections.join('\n\n')}\n`, 'utf8');
console.log(`Ekler güncellendi: ${publicImages.length} JPG, ${wavFiles.length} WAV, ${reportImages.length} test JPEG, ${colors.length} renk satırı.`);
