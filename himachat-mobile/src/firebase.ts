import { initializeApp, getApps } from 'firebase/app';
import { getAuth, connectAuthEmulator } from 'firebase/auth';
import { getFirestore, connectFirestoreEmulator } from 'firebase/firestore';
import Constants from 'expo-constants';
import { Platform } from 'react-native';

const cfg = (Constants?.expoConfig as any)?.extra?.firebase || {};

// Support EXPO_PUBLIC_* env as fallback
let firebaseConfig: any = {
  apiKey: cfg.apiKey || process.env.EXPO_PUBLIC_FIREBASE_API_KEY,
  authDomain: cfg.authDomain || process.env.EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: cfg.projectId || process.env.EXPO_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: cfg.storageBucket || process.env.EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: cfg.messagingSenderId || process.env.EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: cfg.appId || process.env.EXPO_PUBLIC_FIREBASE_APP_ID,
};

if (!firebaseConfig.apiKey || !firebaseConfig.projectId || !firebaseConfig.appId) {
  console.warn('Firebase config is missing. Please set app.json expo.extra.firebase or EXPO_PUBLIC_* env vars.');
}

// When using emulator, allow a safe default config if nothing provided
const USE_EMULATOR = (
  (Constants?.expoConfig as any)?.extra?.useEmulator === true ||
  String(process.env.EXPO_PUBLIC_USE_EMULATOR).toLowerCase() === 'true'
);

if (USE_EMULATOR && (!firebaseConfig.projectId || !firebaseConfig.appId)) {
  firebaseConfig = {
    apiKey: firebaseConfig.apiKey || 'demo-api-key',
    authDomain: firebaseConfig.authDomain || 'localhost',
    projectId: firebaseConfig.projectId || 'demo-pocchari',
    storageBucket: firebaseConfig.storageBucket || 'demo-pocchari.appspot.com',
    messagingSenderId: firebaseConfig.messagingSenderId || '0',
    appId: firebaseConfig.appId || 'demo-app-id',
  };
}

const app = getApps().length ? getApps()[0] : initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);

if (USE_EMULATOR) {
  const host = Platform.OS === 'android' ? '10.0.2.2' : 'localhost';
  try { connectAuthEmulator(auth, `http://${host}:9099`, { disableWarnings: true }); } catch {}
  try { connectFirestoreEmulator(db, host, 8080); } catch {}
  console.log('[Firebase] Using Emulator at', host);
}
