import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Alert } from 'react-native';
import { auth } from '../firebase';
import { acceptTerms } from '../services/terms';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

type RootStackParamList = {
  Terms: undefined;
};

type Props = NativeStackScreenProps<RootStackParamList, 'Terms'>;

export default function TermsScreen({ navigation }: Props) {
  const uid = auth.currentUser?.uid;

  const onAccept = async () => {
    if (!uid) return Alert.alert('エラー', 'ログイン状態を確認してください');
    try {
      await acceptTerms(uid);
      Alert.alert('ありがとうございます', '同意が保存されました');
      navigation.goBack();
    } catch (e) {
      Alert.alert('エラー', '保存に失敗しました');
    }
  };

  return (
    <View style={styles.container}>
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }}>
        <Text style={styles.title}>利用規約・プライバシーポリシー</Text>
        <Text style={styles.p}>
          本サービスは、ランダム1対1チャットを提供します。公序良俗に反する行為、違法行為、他者への迷惑行為を禁止します。安全のため、通報・ブロック機能を用意しています。詳細な規約とプライバシーポリシーは、後日掲載の正式版に準じます。
        </Text>
        <Text style={styles.p}>・禁止事項の例: 誹謗中傷、差別、スパム、なりすまし 等</Text>
        <Text style={styles.p}>・保存される情報: 匿名ID、メッセージ（必要に応じ）、通報、最終活動時刻 等</Text>
        <Text style={styles.p}>・退会: プロフィール画面からいつでも退会（データ削除）できます</Text>
        <Text style={styles.p}>・未成年の方は保護者の同意のもとご利用ください</Text>
      </ScrollView>
      <TouchableOpacity style={styles.btn} onPress={onAccept}>
        <Text style={styles.btnText}>同意して開始</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff8fb' },
  title: { fontSize: 18, fontWeight: 'bold', marginBottom: 12 },
  p: { marginBottom: 12, color: '#333', lineHeight: 20 },
  btn: { height: 52, backgroundColor: '#e91e63', alignItems: 'center', justifyContent: 'center' },
  btnText: { color: 'white', fontWeight: 'bold', fontSize: 16 },
});

