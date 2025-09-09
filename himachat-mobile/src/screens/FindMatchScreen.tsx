import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator, Alert } from 'react-native';
import { useAuth } from '../hooks/useAuth';
import { useAdmin } from '../hooks/useAdmin';
import { cancelQueue, findMatchOrEnqueue, listenForMatch } from '../services/matchmaker';
import { getOrCreateProfile } from '../services/profile';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

type RootStackParamList = {
  FindMatch: undefined;
  Chat: { roomId: string };
};

type Props = NativeStackScreenProps<RootStackParamList, 'FindMatch'>;

export default function FindMatchScreen({ navigation }: Props) {
  const { user } = useAuth();
  const isAdmin = useAdmin();
  const [finding, setFinding] = useState(false);
  const unsubRef = useRef<() => void>();
  const [accepted, setAccepted] = useState(true);
  const isEmu = String(process.env.EXPO_PUBLIC_USE_EMULATOR).toLowerCase() === 'true';

  useLayoutEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <View style={{ flexDirection: 'row', alignItems: 'center' }}>
          {isAdmin && (
            <TouchableOpacity onPress={() => navigation.navigate('AdminReports' as any)} style={{ paddingHorizontal: 8 }}>
              <Text style={{ color: '#e91e63', fontWeight: 'bold' }}>管理</Text>
            </TouchableOpacity>
          )}
          <TouchableOpacity onPress={() => navigation.navigate('Profile' as any)} style={{ paddingHorizontal: 8 }}>
            <Text style={{ color: '#e91e63', fontWeight: 'bold' }}>プロフィール</Text>
          </TouchableOpacity>
        </View>
      ),
    });
  }, [navigation, isAdmin]);

  useEffect(() => {
    (async () => {
      if (!user) return;
      const p = await getOrCreateProfile(user.uid);
      const ok = !!(p as any)?.acceptedTermsAt;
      setAccepted(ok);
      if (!ok) navigation.navigate('Terms' as any);
    })();
  }, [user, navigation]);

  useEffect(() => {
    return () => {
      if (unsubRef.current) unsubRef.current();
    };
  }, []);

  const start = async () => {
    if (!user) return;
    setFinding(true);
    try {
      // ぽっちゃり系トピックでマッチング
      const res = await findMatchOrEnqueue(user.uid, 'pocchari');
      if (res.status === 'matched') {
        navigation.replace('Chat', { roomId: res.roomId });
        setFinding(false);
      } else {
        unsubRef.current = listenForMatch(user.uid, (roomId) => {
          navigation.replace('Chat', { roomId });
          setFinding(false);
        });
      }
    } catch (e: any) {
      console.error(e);
      Alert.alert('エラー', 'マッチングに失敗しました。もう一度お試しください。');
      setFinding(false);
    }
  };

  const cancel = async () => {
    if (!user) return;
    await cancelQueue(user.uid);
    if (unsubRef.current) unsubRef.current();
    setFinding(false);
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>ぽっちゃりチャット</Text>
      <Text style={styles.caption}>ぽっちゃり好き同士で今すぐ1対1</Text>
      {!finding ? (
        <TouchableOpacity
          style={[styles.btn, !accepted && { opacity: 0.5 }]}
          onPress={start}
          disabled={!accepted}
        >
          <Text style={styles.btnText}>相手を探す</Text>
        </TouchableOpacity>
      ) : (
        <View style={{ alignItems: 'center' }}>
          <ActivityIndicator size="large" />
          <Text style={{ marginTop: 12 }}>ぽっちゃり仲間を探しています…</Text>
          <TouchableOpacity style={[styles.btn, styles.cancel]} onPress={cancel}>
            <Text style={styles.btnText}>キャンセル</Text>
          </TouchableOpacity>
        </View>
      )}
      <Text style={styles.notice}>注意: 公序良俗に反する利用は禁止です。通報/ブロック機能あり。</Text>
      {!accepted && (
        <Text style={{ position: 'absolute', bottom: 44, color: '#d32f2f' }}>利用規約への同意が必要です</Text>
      )}
      {isEmu && user && (
        <Text style={{ position: 'absolute', bottom: 8, color: '#999', fontSize: 12 }}>UID: {user.uid}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, backgroundColor: '#fafafa' },
  title: { fontSize: 24, fontWeight: 'bold' },
  caption: { marginTop: 8, color: '#555' },
  btn: { marginTop: 24, backgroundColor: '#e91e63', paddingHorizontal: 24, paddingVertical: 12, borderRadius: 8 },
  cancel: { backgroundColor: '#9e9e9e' },
  btnText: { color: 'white', fontSize: 16, fontWeight: 'bold' },
  notice: { position: 'absolute', bottom: 24, color: '#777', textAlign: 'center' },
});
