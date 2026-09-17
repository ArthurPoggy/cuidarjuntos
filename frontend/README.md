# CuidarJuntos — Frontend (Expo)

App Expo/React Native que roda em iOS, Android e Web (`react-native-web`), consumindo a API REST do backend Django.

## Scripts

```bash
npm install
npm start          # Expo (QR code / menu de plataformas)
npm run ios        # abre no simulador iOS
npm run android    # abre no emulador Android
npm run web        # abre no navegador
npm test           # roda a suíte de testes (jest / jest-expo)
npm run typecheck  # npx tsc --noEmit — gate de zero erros TypeScript
```

## Variáveis de ambiente

Copie `.env.example` para `.env` e ajuste `EXPO_PUBLIC_API_URL` para apontar
ao backend Django (produção: `https://app.cuidarjuntos.com.br`).
Sem essa variável, o app usa `http://localhost:8000` como fallback.

## Roteamento único por dispositivo (`middleware.ts`)

Este projeto Vercel serve o build web do Expo (mobile), mas o mesmo domínio
também dá acesso ao app Django server-rendered (`care/` + `templates/`, no
PythonAnywhere) para quem entra por desktop — sem precisar de dois links
separados. `middleware.ts` na raiz do projeto olha o User-Agent: em
dispositivo móvel, serve o build Expo normalmente; em desktop, faz proxy
transparente (`rewrite`) para o Django, mantendo a URL do navegador.

- `DJANGO_WEB_ORIGIN` (env var do Vercel): origem do backend Django a
  proxiar em desktop. Default: `https://app.cuidarjuntos.com.br`.
- No lado do Django, `UNIFIED_WEB_DOMAIN` (`cuidarjuntos/settings_production.py`)
  precisa apontar para o mesmo domínio deste projeto Vercel, para
  `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` aceitarem as requisições
  proxiadas.

## Gate de TypeScript

Antes de abrir PR, rode `npm run typecheck` (equivalente a `npx tsc --noEmit`) na pasta `frontend/` e confirme saída com código 0 — esse é o único comando de verificação de tipos do monorepo frontend, usado tanto localmente quanto em CI.

## Testes de consistência visual entre plataformas

Componentes/telas com risco de estilo hardcoded específico de plataforma têm snapshot tests que rodam duas vezes — uma simulando `Platform.OS = 'ios'` e outra `Platform.OS = 'web'` (via mock de `react-native/Libraries/Utilities/Platform`) — para garantir que a renderização não quebra e que os estilos aplicados ficam registrados em `__snapshots__/`. Veja `src/screens/__tests__/*.platform.test.tsx`.
