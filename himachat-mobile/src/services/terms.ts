import { doc, setDoc } from 'firebase/firestore';
import { db } from '../firebase';

export const TERMS_VERSION = 1;

export async function acceptTerms(uid: string) {
  const ref = doc(db, 'profiles', uid);
  await setDoc(
    ref,
    { acceptedTermsAt: new Date(), acceptedTermsVersion: TERMS_VERSION },
    { merge: true }
  );
}

