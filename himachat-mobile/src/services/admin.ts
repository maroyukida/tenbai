import { doc, updateDoc, deleteDoc } from 'firebase/firestore';
import { db } from '../firebase';

export async function deactivateRoom(roomId: string) {
  const ref = doc(db, 'rooms', roomId);
  await updateDoc(ref, { active: false });
}

export async function deleteMessage(roomId: string, msgId: string) {
  await deleteDoc(doc(db, 'rooms', roomId, 'messages', msgId));
}

