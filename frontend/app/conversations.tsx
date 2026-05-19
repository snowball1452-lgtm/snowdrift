import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, FlatList,
  Alert, TextInput, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useChatStore } from '../src/store/chatStore';
import { useFaceStyleStore, FACE_META } from '../src/hooks/useFaceStyle';
import SnowballFace from '../src/components/SnowballFace';
import { Conversation } from '../src/types';

export default function ConversationsScreen() {
  const router = useRouter();
  const { conversations, currentConversationId, fetchConversations, createConversation,
    deleteConversation, setCurrentConversation } = useChatStore();
  const { faceStyle } = useFaceStyleStore();
  const accent = FACE_META[faceStyle].color;
  const [search, setSearch] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => { fetchConversations(); }, []);

  const filtered = conversations.filter(c =>
    c.title.toLowerCase().includes(search.toLowerCase())
  );

  const handleSelect = (id: string) => {
    setCurrentConversation(id);
    router.back();
  };

  const handleNew = async () => {
    await createConversation();
    router.back();
  };

  const handleDelete = (conv: Conversation) => {
    if (Platform.OS === 'web') {
      deleteConversation(conv.id);
    } else {
      Alert.alert('Delete Chat', `Delete "${conv.title}"?`, [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Delete', style: 'destructive', onPress: () => deleteConversation(conv.id) },
      ]);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchConversations();
    setRefreshing(false);
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    if (diff < 86400000) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (diff < 604800000) return d.toLocaleDateString([], { weekday: 'short' });
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  const renderItem = ({ item }: { item: Conversation }) => {
    const active = item.id === currentConversationId;
    return (
      <TouchableOpacity
        style={[styles.item, active && { borderColor: accent, backgroundColor: accent + '0c' }]}
        onPress={() => handleSelect(item.id)}
        activeOpacity={0.7}
      >
        <View style={[styles.itemIcon, active && { backgroundColor: accent + '20' }]}>
          <Ionicons name="chatbubble-ellipses-outline" size={18} color={active ? accent : '#555'} />
        </View>
        <View style={styles.itemText}>
          <Text style={[styles.itemTitle, active && { color: '#fff' }]} numberOfLines={1}>
            {item.title}
          </Text>
          <Text style={styles.itemMeta}>
            {item.model} · {formatDate(item.updated_at)}
          </Text>
        </View>
        {active && (
          <View style={[styles.activePip, { backgroundColor: accent }]} />
        )}
        <TouchableOpacity
          style={styles.deleteBtn}
          onPress={() => handleDelete(item)}
          hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
        >
          <Ionicons name="trash-outline" size={16} color="#3a3a3a" />
        </TouchableOpacity>
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={22} color="#aaa" />
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <SnowballFace state="idle" size={24} />
          <Text style={styles.headerTitle}>Conversations</Text>
        </View>
        <TouchableOpacity style={[styles.newBtn, { backgroundColor: accent }]} onPress={handleNew}>
          <Ionicons name="add" size={18} color="#000" />
          <Text style={styles.newBtnText}>New</Text>
        </TouchableOpacity>
      </View>

      {/* Search */}
      <View style={styles.searchRow}>
        <Ionicons name="search-outline" size={16} color="#555" />
        <TextInput
          style={styles.searchInput}
          placeholder="Search conversations..."
          placeholderTextColor="#3a3a3a"
          value={search}
          onChangeText={setSearch}
          autoCapitalize="none"
        />
        {search.length > 0 && (
          <TouchableOpacity onPress={() => setSearch('')}>
            <Ionicons name="close-circle" size={16} color="#444" />
          </TouchableOpacity>
        )}
      </View>

      <FlatList
        data={filtered}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        contentContainerStyle={styles.list}
        onRefresh={handleRefresh}
        refreshing={refreshing}
        ListEmptyComponent={
          <View style={styles.empty}>
            <SnowballFace state="idle" size={80} />
            <Text style={styles.emptyTitle}>No conversations yet</Text>
            <Text style={styles.emptySub}>Start a new chat to begin</Text>
            <TouchableOpacity style={[styles.emptyNewBtn, { backgroundColor: accent }]} onPress={handleNew}>
              <Ionicons name="add" size={18} color="#000" />
              <Text style={styles.emptyNewText}>Start chatting</Text>
            </TouchableOpacity>
          </View>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0a' },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 14, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: '#181818',
  },
  backBtn: {
    width: 34, height: 34, borderRadius: 10,
    backgroundColor: '#161616', alignItems: 'center', justifyContent: 'center',
  },
  headerCenter: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  headerTitle: { fontSize: 17, fontWeight: '700', color: '#eee', letterSpacing: -0.2 },
  newBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 12, paddingVertical: 7, borderRadius: 10,
  },
  newBtnText: { fontSize: 13, fontWeight: '700', color: '#000' },
  searchRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    marginHorizontal: 14, marginTop: 12, marginBottom: 4,
    backgroundColor: '#131313', borderRadius: 12,
    borderWidth: 1, borderColor: '#1e1e1e', paddingHorizontal: 12, paddingVertical: 10,
  },
  searchInput: { flex: 1, color: '#ccc', fontSize: 14 },
  list: { padding: 12, paddingTop: 8, gap: 7 },
  item: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: '#111', borderRadius: 16,
    borderWidth: 1, borderColor: '#1c1c1c', padding: 13,
  },
  itemIcon: {
    width: 42, height: 42, borderRadius: 13,
    backgroundColor: '#191919', alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: '#252525',
  },
  itemText: { flex: 1 },
  itemTitle: { fontSize: 14, fontWeight: '600', color: '#999', letterSpacing: -0.1 },
  itemMeta: { fontSize: 11, color: '#3d3d3d', marginTop: 3, letterSpacing: 0.1 },
  activePip: { width: 7, height: 7, borderRadius: 3.5 },
  deleteBtn: { padding: 6 },
  empty: { alignItems: 'center', justifyContent: 'center', paddingTop: 80, gap: 10 },
  emptyTitle: { fontSize: 17, fontWeight: '600', color: '#444', marginTop: 14 },
  emptySub: { fontSize: 13, color: '#2d2d2d' },
  emptyNewBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 20,
    paddingHorizontal: 22, paddingVertical: 13, borderRadius: 14,
  },
  emptyNewText: { fontSize: 14, fontWeight: '700', color: '#000' },
});
