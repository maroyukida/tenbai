import { useEffect, useState } from 'react';
import { auth, db } from '../firebase';
import { doc, onSnapshot } from 'firebase/firestore';

export function useAdmin() {
  const uid = auth.currentUser?.uid;
  const [isAdmin, setIsAdmin] = useState(false);
  useEffect(() => {
    if (!uid) return;
    const ref = doc(db, 'admins', uid);
    const unsub = onSnapshot(ref, (snap) => setIsAdmin(snap.exists()));
    return () => unsub();
  }, [uid]);
  return isAdmin;
}

