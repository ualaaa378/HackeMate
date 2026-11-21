import type { CapacitorConfig } from '@capacitor/cli';

// La app se sirve desde https://localhost dentro del APK y llama a la API por la dirección
// que se guarda en Ajustes (la URL pública del túnel). CORS de la API ya admite ese origen.
const config: CapacitorConfig = {
  appId: 'es.hackemate.app',
  appName: 'HackeMate',
  webDir: 'dist',
  android: {
    // Permite probar contra un servidor http:// de la red local además del túnel https://.
    allowMixedContent: true,
  },
  server: {
    cleartext: true,
  },
};

export default config;
