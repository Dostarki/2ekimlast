import fs from 'fs';
import path from 'path';

describe('admin visibility/source routing regression', () => {
  it('public frontend source has no ADMIN nav entry points', () => {
    const appSrc = fs.readFileSync(path.resolve(__dirname, './App.js'), 'utf8');
    const startSrc = fs.readFileSync(path.resolve(__dirname, './components/StartScreen.jsx'), 'utf8');

    expect(appSrc).not.toContain('data-testid="nav-admin"');
    expect(startSrc).not.toContain('data-testid="start-admin-link"');
    expect(startSrc).not.toMatch(/>\s*ADMIN\s*</);
  });

  it('admin route remains explicitly wired in app routing source', () => {
    const appSrc = fs.readFileSync(path.resolve(__dirname, './App.js'), 'utf8');
    expect(appSrc).toContain("location.pathname.startsWith('/admin')");
  });
});
