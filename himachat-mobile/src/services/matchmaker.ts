import {
  addDoc,
  collection,
  deleteDoc,
  doc,
  getDoc,
  getDocs,
  limit,
  onSnapshot,
  orderBy,
  query,
  runTransaction,
  serverTimestamp,
  setDoc,
  updateDoc,
  where,
} from 'firebase/firestore';
import { db } from '../firebase';

export type MatchResult =
  | { status: 'matched'; roomId: string }
  | { status: 'waiting'; queueDocId: string };

const DEFAULT_TOPIC = 'pocchari';
const STALE_ROOM_MS = 10 * 60 * 1000; // 10分無活動で部屋を停止対象

async function cleanupStaleRooms(uid: string) {
  // 自分が含まれる部屋のうち、古い/無活動のものを inactive にする
  try {
    const q = query(collection(db, 'rooms'), where('participants', 'array-contains', uid), limit(20));
    const snap = await getDocs(q);
    const now = Date.now();
    for (const d of snap.docs) {
      const data = d.data() as any;
      if (data?.active === false) continue;
      const last = data?.lastMessageAt?.toDate?.() || data?.createdAt?.toDate?.();
      if (!last) continue;
      if (now - last.getTime() > STALE_ROOM_MS) {
        try { await updateDoc(d.ref, { active: false }); } catch {}
      }
    }
  } catch {}
}

// 待機か即時マッチ。最古の待機者と1:1でペアリング（トピック別）
export async function findMatchOrEnqueue(uid: string, topic: string = DEFAULT_TOPIC): Promise<MatchResult> {
  // まず古い部屋を掃除
  await cleanupStaleRooms(uid);
  // 既に自分の待機が残っていれば掃除
  const myQueueRef = doc(db, 'queue', uid);
  const myQueueSnap = await getDoc(myQueueRef);
  if (myQueueSnap.exists()) {
    const data = myQueueSnap.data() as any;
    if (data.status === 'matched' && data.roomId) {
      // 既存ルームが生きているか確認。死んでいればqueueを掃除して続行
      const roomSnap = await getDoc(doc(db, 'rooms', data.roomId));
      const alive = roomSnap.exists() ? (roomSnap.data() as any)?.active !== false : false;
      if (alive) {
        return { status: 'matched', roomId: data.roomId };
      }
      await deleteDoc(myQueueRef);
    } else {
      await deleteDoc(myQueueRef);
    }
  }

  // 最古の待機者を探す（自分を除外するのはクライアント側で）
  const candidates = await getDocs(
    query(
      collection(db, 'queue'),
      where('status', '==', 'waiting'),
      where('topic', '==', topic),
      orderBy('createdAt', 'asc'),
      limit(5)
    )
  );

  let partnerDocId: string | null = null;
  for (const c of candidates.docs) {
    if (c.id !== uid) {
      partnerDocId = c.id;
      break;
    }
  }

  if (partnerDocId) {
    // 候補を最大5件まで順にトライ（ブロック相互を除外）
    const candidateIds = candidates.docs.map((d) => d.id).filter((id) => id !== uid);
    for (const cand of candidateIds) {
      try {
        const roomId = await runTransaction(db, async (tx) => {
          const partnerRef = doc(db, 'queue', cand);
          const partnerSnap = await tx.get(partnerRef);
          if (!partnerSnap.exists()) throw new Error('Partner vanished');
          const p = partnerSnap.data() as any;
          if (p.status !== 'waiting') throw new Error('Already matched');

          // プロフィールのブロック相互チェック
          const meProfileRef = doc(db, 'profiles', uid);
          const youProfileRef = doc(db, 'profiles', cand);
          const [meSnap, youSnap] = await Promise.all([tx.get(meProfileRef), tx.get(youProfileRef)]);
          const meBlocked: string[] = (meSnap.exists() ? (meSnap.data() as any).blocked : []) || [];
          const youBlocked: string[] = (youSnap.exists() ? (youSnap.data() as any).blocked : []) || [];
          if (meBlocked.includes(cand) || youBlocked.includes(uid)) throw new Error('Blocked');

          const roomRef = doc(collection(db, 'rooms'));
          tx.set(roomRef, {
            participants: [uid, cand],
            createdAt: serverTimestamp(),
            active: true,
            topic,
          });

          tx.update(partnerRef, { status: 'matched', roomId: roomRef.id });

          const myRef = doc(db, 'queue', uid);
          tx.set(myRef, {
            uid,
            status: 'matched',
            roomId: roomRef.id,
            createdAt: serverTimestamp(),
            topic,
          });

          return roomRef.id as string;
        });
        return { status: 'matched', roomId } as MatchResult;
      } catch (e) {
        // 次の候補へ
        continue;
      }
    }
  }

  // 見つからなければ待機に登録
  await setDoc(myQueueRef, {
    uid,
    status: 'waiting',
    createdAt: serverTimestamp(),
    topic,
  });
  return { status: 'waiting', queueDocId: uid };
}

export function listenForMatch(uid: string, onMatch: (roomId: string) => void) {
  const ref = doc(db, 'queue', uid);
  return onSnapshot(ref, (snap) => {
    if (snap.exists()) {
      const d = snap.data() as any;
      if (d.status === 'matched' && d.roomId) onMatch(d.roomId as string);
    }
  });
}

export async function cancelQueue(uid: string) {
  const ref = doc(db, 'queue', uid);
  const snap = await getDoc(ref);
  if (snap.exists()) {
    const d = snap.data() as any;
    if (d.status === 'waiting') await deleteDoc(ref);
  }
}

export async function sendMessage(roomId: string, senderId: string, text: string) {
  const ref = collection(db, 'rooms', roomId, 'messages');
  await addDoc(ref, { text, senderId, createdAt: serverTimestamp() });
  // 部屋の最終メッセ時刻を更新
  try { await updateDoc(doc(db, 'rooms', roomId), { lastMessageAt: serverTimestamp(), lastSenderId: senderId }); } catch {}
}

export async function heartbeat(roomId: string, uid: string) {
  const pRef = doc(db, 'rooms', roomId, 'presence', uid);
  await setDoc(pRef, { lastActive: serverTimestamp() }, { merge: true });
}

export async function reportRoom(roomId: string, reporterId: string, reason: string) {
  await addDoc(collection(db, 'reports'), {
    roomId,
    reporterId,
    reason,
    createdAt: serverTimestamp(),
  });
}

// 退室: ルームを非アクティブ化し、自分の待機を掃除
export async function leaveRoom(roomId: string, uid: string) {
  try {
    await updateDoc(doc(db, 'rooms', roomId), { active: false });
  } catch {}
  try {
    await deleteDoc(doc(db, 'queue', uid));
  } catch {}
}

// タイピング状態の更新（true/false）
export async function setTyping(roomId: string, uid: string, typing: boolean) {
  const ref = doc(db, 'rooms', roomId, 'typing', uid);
  await setDoc(ref, { typing, updatedAt: serverTimestamp() }, { merge: true });
}
