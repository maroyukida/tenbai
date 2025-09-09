import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, FlatList, Alert } from 'react-native';
import { auth } from '../firebase';
import { deleteAccountAndData, getOrCreateProfile, setNickname, unblockUser } from '../services/profile';

export default function ProfileScreen() {
  const uid = auth.currentUser?.uid!;
  const [nickname, setNick] = useState('');
  const [blocked, setBlocked] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const p = await getOrCreateProfile(uid);
        setNick(p.nickname || '');
        setBlocked(p.blocked || []);
      } catch (e) {
        Alert.alert('エラー', 'プロフィールの取得に失敗しました');
      }
    })();
  }, [uid]);

  const save = async () => {
    setSaving(true);
    try {
      await setNickname(uid, nickname.trim());
      Alert.alert('保存しました');
    } catch (e) {
      Alert.alert('エラー', '保存に失敗しました');
    } finally {
      setSaving(false);
    }
  };

  const onUnblock = async (target: string) => {
    try {
      await unblockUser(uid, target);
      setBlocked((b) => b.filter((x) => x !== target));
    } catch (e) {
      Alert.alert('エラー', '解除に失敗しました');
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.label}>ニックネーム</Text>
      <TextInput value={nickname} onChangeText={setNick} style={styles.input} placeholder="例: ぽちゃ好き太郎" />
      <TouchableOpacity style={[styles.btn, saving && { opacity: 0.6 }]} disabled={saving} onPress={save}>
        <Text style={styles.btnText}>保存</Text>
      </TouchableOpacity>

      <Text style={[styles.label, { marginTop: 24 }]}>ブロック中のユーザー</Text>
      {blocked.length === 0 ? (
        <Text style={{ color: '#555' }}>なし</Text>
      ) : (
        <FlatList
          data={blocked}
          keyExtractor={(item) => item}
          renderItem={({ item }) => (
            <View style={styles.row}>
              <Text style={{ flex: 1 }}>{item}</Text>
              <TouchableOpacity style={styles.smallBtn} onPress={() => onUnblock(item)}>
                <Text style={styles.smallBtnText}>解除</Text>
              </TouchableOpacity>
            </View>
          )}
        />)
      }
      <TouchableOpacity
        style={[styles.btn, { backgroundColor: '#b71c1c', marginTop: 32 }]}
        onPress={() => {
          Alert.alert('退会（データ削除）', 'この操作は元に戻せません。続行しますか？', [
            { text: 'キャンセル', style: 'cancel' },
            {
              text: '退会する',
              style: 'destructive',
              onPress: async () => {
                try {
                  await deleteAccountAndData(uid);
                } catch {}
              },
            },
          ]);
        }}
      >
        <Text style={styles.btnText}>退会（データ削除）</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: '#fff8fb' },
  label: { fontWeight: 'bold', marginBottom: 6 },
  input: { backgroundColor: 'white', borderWidth: 1, borderColor: '#ddd', borderRadius: 8, paddingHorizontal: 12, height: 44 },
  btn: { marginTop: 12, backgroundColor: '#e91e63', borderRadius: 8, height: 44, alignItems: 'center', justifyContent: 'center' },
  btnText: { color: 'white', fontWeight: 'bold' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8 },
  smallBtn: { backgroundColor: '#9e9e9e', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 6 },
  smallBtnText: { color: 'white' },
});
