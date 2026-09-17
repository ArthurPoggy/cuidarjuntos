import middleware from '../../middleware';

/**
 * middleware.ts fica na raiz do projeto (é onde o Vercel Edge Middleware
 * procura por convenção), fora de src/ — este teste importa por caminho
 * relativo para cobrir a lógica de roteamento por User-Agent.
 */

const MOBILE_UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15';
const DESKTOP_UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0';

function makeRequest(path: string, userAgent: string): Request {
  return new Request(`https://cuidarjuntos.vercel.app${path}`, {
    headers: { 'user-agent': userAgent },
  });
}

describe('middleware - roteamento por dispositivo', () => {
  it('deixa passar (next) requisições de dispositivo móvel para o build Expo', () => {
    const res = middleware(makeRequest('/', MOBILE_UA));
    expect(res.headers.get('x-middleware-rewrite')).toBeNull();
  });

  it('faz rewrite para o Django em requisições de desktop', () => {
    const res = middleware(makeRequest('/agenda/', DESKTOP_UA));
    const target = res.headers.get('x-middleware-rewrite');
    expect(target).not.toBeNull();
    expect(target).toContain('/agenda/');
    expect(target).toMatch(/^https:\/\//);
  });

  it('nao faz rewrite dos assets do Expo mesmo vindo de desktop', () => {
    const res = middleware(makeRequest('/_expo/static/js/index.js', DESKTOP_UA));
    expect(res.headers.get('x-middleware-rewrite')).toBeNull();
  });

  it('preserva a query string ao fazer rewrite para o Django', () => {
    const res = middleware(makeRequest('/relatorios/diario-cuidador/?date=2026-08-07', DESKTOP_UA));
    const target = res.headers.get('x-middleware-rewrite');
    expect(target).toContain('date=2026-08-07');
  });
});
