import React from 'react';
import { ActivityIndicator, View } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useAuth } from '../contexts/AuthContext';
import { colors } from '../theme';
import Header from '../components/Header';

// Auth screens
import LoginScreen from '../screens/LoginScreen';
import RegisterScreen from '../screens/RegisterScreen';
import PasswordResetScreen from '../screens/PasswordResetScreen';
import SettingsScreen from '../screens/SettingsScreen';

// Group screens
import ChooseGroupScreen from '../screens/ChooseGroupScreen';
import CreateGroupScreen from '../screens/CreateGroupScreen';
import JoinGroupScreen from '../screens/JoinGroupScreen';

// Main screens
import DashboardScreen from '../screens/DashboardScreen';
import RecordListScreen from '../screens/RecordListScreen';
import RecordCreateScreen from '../screens/RecordCreateScreen';
import RecordDetailScreen from '../screens/RecordDetailScreen';
import MedicationStockScreen from '../screens/MedicationStockScreen';
import UpcomingScreen from '../screens/UpcomingScreen';
import ProfileScreen from '../screens/ProfileScreen';
import AdminOverviewScreen from '../screens/AdminOverviewScreen';

const AuthStack = createNativeStackNavigator();
const GroupStack = createNativeStackNavigator();
const MainStack = createNativeStackNavigator();

function AuthNavigator() {
  return (
    <AuthStack.Navigator screenOptions={{ headerShown: false }}>
      <AuthStack.Screen name="Login" component={LoginScreen} />
      <AuthStack.Screen name="Register" component={RegisterScreen} />
      <AuthStack.Screen name="PasswordReset" component={PasswordResetScreen} />
      <AuthStack.Screen
        name="Settings"
        component={SettingsScreen}
        options={{
          headerShown: true,
          title: 'Configurações',
          headerStyle: { backgroundColor: colors.primary },
          headerTintColor: colors.textInverse
        }}
      />
    </AuthStack.Navigator>
  );
}

function GroupNavigator() {
  return (
    <GroupStack.Navigator screenOptions={{ headerStyle: { backgroundColor: colors.primary }, headerTintColor: colors.textInverse }}>
      <GroupStack.Screen name="ChooseGroup" component={ChooseGroupScreen} options={{ title: 'Grupo' }} />
      <GroupStack.Screen name="CreateGroup" component={CreateGroupScreen} options={{ title: 'Criar Grupo' }} />
      <GroupStack.Screen name="JoinGroup" component={JoinGroupScreen} options={{ title: 'Entrar no Grupo' }} />
    </GroupStack.Navigator>
  );
}

function MainNavigator() {
  return (
    <MainStack.Navigator
      screenOptions={{
        header: () => <Header />,
      }}
    >
      <MainStack.Screen name="Dashboard" component={DashboardScreen} />
      <MainStack.Screen name="Records" component={RecordListScreen} />
      <MainStack.Screen name="RecordCreate" component={RecordCreateScreen} />
      <MainStack.Screen name="RecordDetail" component={RecordDetailScreen} />
      <MainStack.Screen name="Medications" component={MedicationStockScreen} />
      <MainStack.Screen name="Upcoming" component={UpcomingScreen} />
      <MainStack.Screen name="Profile" component={ProfileScreen} />
      <MainStack.Screen name="AdminOverview" component={AdminOverviewScreen} />
    </MainStack.Navigator>
  );
}

export default function RootNavigator() {
  const { isAuthenticated, isLoading, hasGroup } = useAuth();

  if (isLoading) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.background }}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  return (
    <NavigationContainer>
      {!isAuthenticated ? (
        <AuthNavigator />
      ) : !hasGroup ? (
        <GroupNavigator />
      ) : (
        <MainNavigator />
      )}
    </NavigationContainer>
  );
}
