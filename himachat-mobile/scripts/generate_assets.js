// Generates placeholder icon.png and splash.png using pngjs
const fs = require('fs');
const path = require('path');
const { PNG } = require('pngjs');

function makePng(width, height, painter) {
  const png = new PNG({ width, height });
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const idx = (width * y + x) << 2;
      const { r, g, b, a } = painter(x, y, width, height);
      png.data[idx] = r;
      png.data[idx + 1] = g;
      png.data[idx + 2] = b;
      png.data[idx + 3] = a;
    }
  }
  return PNG.sync.write(png);
}

function painterPinkDiagonal(x, y, w, h) {
  // Soft pink background
  const base = { r: 252, g: 233, b: 241 };
  // Diagonal stripe
  const stripe = (x + y) % 48 < 12;
  if (stripe) return { r: 233, g: 30, b: 99, a: 255 };
  return { ...base, a: 255 };
}

function ensureDir(p) {
  if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true });
}

function writeFile(fp, buf) {
  ensureDir(path.dirname(fp));
  fs.writeFileSync(fp, buf);
  console.log('generated', fp);
}

const root = path.join(__dirname, '..');
const assetsDir = path.join(root, 'assets');

// Icon 1024x1024
writeFile(path.join(assetsDir, 'icon.png'), makePng(1024, 1024, painterPinkDiagonal));
// Splash 1242x2436 (portrait)
writeFile(path.join(assetsDir, 'splash.png'), makePng(1242, 2436, painterPinkDiagonal));

console.log('Done. You can customize these images later.');

