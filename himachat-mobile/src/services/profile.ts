import { collection, doc, getDoc, getDocs, query, setDoc, updateDoc, arrayUnion, arrayRemove, where } from 'firebase/firestore';
import { deleteUser } from 'firebase/auth';
import { db } from '../firebase';
import { auth } from '../firebase';

export type Profile = {
  nickname?: string;
  blocked?: string[];
  updatedAt?: any;
};

export async function getOrCreateProfile(uid: string): Promise<Profile> {
  const ref = doc(db, 'profiles', uid);
  const snap = await getDoc(ref);
  if (snap.exists()) return snap.data() as Profile;
  const initial: Profile = { nickname: '', blocked: [], updatedAt: new Date() };
  await setDoc(ref, initial, { merge: true });
  return initial;
}

export async function setNickname(uid: string, nickname: string) {
  const ref = doc(db, 'profiles', uid);
  await setDoc(ref, { nickname, updatedAt: new Date() }, { merge: true });
}

export async function blockUser(uid: string, targetUid: string) {
  const ref = doc(db, 'profiles', uid);
  await updateDoc(ref, { blocked: arrayUnion(targetUid), updatedAt: new Date() });
}

export async function unblockUser(uid: string, targetUid: string) {
  const ref = doc(db, 'profiles', uid);
  await updateDoc(ref, { blocked: arrayRemove(targetUid), updatedAt: new Date() });
}

export async function deleteAccountAndData(uid: string) {
  // 部屋を停止（自分が含まれる部屋を可能な範囲で inactive）
  try {
    const q = query(collection(db, 'rooms'), where('participants', 'array-contains', uid));
    const snap = await getDocs(q);
    await Promise.all(
      snap.docs.map((d) => updateDoc(d.ref, { active: false }))
    );
  } catch {}
  // 自分の queue と profile を削除
  try { await updateDoc(doc(db, 'profiles', uid), { deletedAt: new Date() }); } catch {}
  try { await (await import('firebase/firestore')).deleteDoc(doc(db, 'queue', uid)); } catch {}
  try { await (await import('firebase/firestore')).deleteDoc(doc(db, 'profiles', uid)); } catch {}

  // 認証ユーザーを削除（匿名想定）
  try {
    if (auth.currentUser && auth.currentUser.uid === uid) {
      await deleteUser(auth.currentUser);
    }
  } catch {}
}
