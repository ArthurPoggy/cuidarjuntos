import { next, rewrite } from '@vercel/edge';

/**
 * Roteamento por dispositivo no domínio unificado do app.
 *
 * Este projeto Vercel serve o build web do app mobile (Expo/React Native
 * Web, gerado por `expo export --platform web`). O mesmo domínio também
 * expõe, via proxy, o app Django server-rendered (`care/` + `templates/`,
 * hospedado no PythonAnywhere) para quem acessa por desktop — assim o
 * usuário só precisa de um link, e a experiência certa (mobile web ou
 * Django web) é escolhida pelo User-Agent, sem o usuário escolher nada.
 *
 * Dispositivos móveis -> segue para o build Expo (comportamento padrão).
 * Desktop -> proxy transparente para o app Django (URL do navegador não
 * muda, o conteúdo vem do PythonAnywhere).
 */

const MOBILE_USER_AGENT_RE = /Android|iPhone|iPad|iPod|Mobile|Windows Phone/i;

// Prefixos que pertencem exclusivamente ao build do Expo e nunca devem ser
// desviados para o Django, mesmo em requisições vindas de desktop.
const EXPO_ASSET_PREFIXES = ['/_expo/', '/assets/', '/favicon.ico', '/metadata.json'];

function djangoWebOrigin(): string {
  return process.env.DJANGO_WEB_ORIGIN || 'https://tuzinhorisonho.pythonanywhere.com';
}

export default function middleware(request: Request) {
  const url = new URL(request.url);

  if (EXPO_ASSET_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) {
    return next();
  }

  const userAgent = request.headers.get('user-agent') || '';
  if (MOBILE_USER_AGENT_RE.test(userAgent)) {
    return next();
  }

  const target = new URL(url.pathname + url.search, djangoWebOrigin());
  return rewrite(target);
}

export const config = {
  matcher: '/:path*',
};
