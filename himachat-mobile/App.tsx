import 'react-native-gesture-handler';
import React from 'react';
import { NavigationContainer, DefaultTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { StatusBar } from 'expo-status-bar';
import { useAuth } from './src/hooks/useAuth';
import FindMatchScreen from './src/screens/FindMatchScreen';
import ChatScreen from './src/screens/ChatScreen';
import ProfileScreen from './src/screens/ProfileScreen';
import AdminReportsScreen from './src/screens/AdminReportsScreen';
import AdminRoomScreen from './src/screens/AdminRoomScreen';
import TermsScreen from './src/screens/TermsScreen';
import { View, ActivityIndicator, Text } from 'react-native';

export type RootStackParamList = {
  FindMatch: undefined;
  Chat: { roomId: string };
  Profile: undefined;
  AdminReports: undefined;
  AdminRoom: { roomId: string };
  Terms: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();

const theme = {
  ...DefaultTheme,
  colors: { ...DefaultTheme.colors, background: '#fff8fb' },
};

function AuthGate({ children }: { children: React.ReactNode }) {
  const { loading } = useAuth();
  if (loading) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator size="large" />
        <Text style={{ marginTop: 12 }}>起動しています…</Text>
      </View>
    );
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <NavigationContainer theme={theme}>
      <AuthGate>
        <Stack.Navigator>
          <Stack.Screen name="FindMatch" component={FindMatchScreen} options={{ headerTitle: 'ぽっちゃりチャット' }} />
          <Stack.Screen name="Chat" component={ChatScreen} />
          <Stack.Screen name="Profile" component={ProfileScreen} options={{ headerTitle: 'プロフィール' }} />
          <Stack.Screen name="AdminReports" component={AdminReportsScreen} options={{ headerTitle: '管理: 通報一覧' }} />
          <Stack.Screen name="AdminRoom" component={AdminRoomScreen} />
          <Stack.Screen name="Terms" component={TermsScreen} options={{ headerTitle: '利用規約' }} />
        </Stack.Navigator>
      </AuthGate>
      <StatusBar style="auto" />
    </NavigationContainer>
  );
}
