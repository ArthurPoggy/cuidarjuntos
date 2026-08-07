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

## Gate de TypeScript

Antes de abrir PR, rode `npm run typecheck` (equivalente a `npx tsc --noEmit`) na pasta `frontend/` e confirme saída com código 0 — esse é o único comando de verificação de tipos do monorepo frontend, usado tanto localmente quanto em CI.

## Testes de consistência visual entre plataformas

Componentes/telas com risco de estilo hardcoded específico de plataforma têm snapshot tests que rodam duas vezes — uma simulando `Platform.OS = 'ios'` e outra `Platform.OS = 'web'` (via mock de `react-native/Libraries/Utilities/Platform`) — para garantir que a renderização não quebra e que os estilos aplicados ficam registrados em `__snapshots__/`. Veja `src/screens/__tests__/*.platform.test.tsx`.
