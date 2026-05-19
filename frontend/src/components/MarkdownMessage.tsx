import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Platform,
} from 'react-native';
import Markdown from 'react-native-markdown-display';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';

interface MarkdownMessageProps {
  content: string;
  isUser: boolean;
}

const markdownStyles = StyleSheet.create({
  body: {
    color: '#c8c8c8',
    fontSize: 14,
    lineHeight: 21,
    letterSpacing: 0.05,
  },
  heading1: {
    color: '#eee',
    fontSize: 20,
    fontWeight: '700' as any,
    marginTop: 14,
    marginBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#2a2a2a',
    paddingBottom: 8,
    letterSpacing: -0.3,
  },
  heading2: {
    color: '#ddd',
    fontSize: 17,
    fontWeight: '700' as any,
    marginTop: 12,
    marginBottom: 6,
    letterSpacing: -0.2,
  },
  heading3: {
    color: '#ccc',
    fontSize: 14,
    fontWeight: '700' as any,
    marginTop: 8,
    marginBottom: 4,
    letterSpacing: -0.1,
  },
  strong: {
    color: '#eee',
    fontWeight: '700' as any,
  },
  em: {
    color: '#aaa',
    fontStyle: 'italic' as any,
  },
  link: {
    color: '#ff6b35',
    textDecorationLine: 'underline' as any,
  },
  blockquote: {
    borderLeftWidth: 2,
    borderLeftColor: '#ff6b35',
    paddingLeft: 12,
    marginLeft: 0,
    marginVertical: 8,
    backgroundColor: '#131313',
    borderRadius: 6,
    paddingVertical: 8,
    paddingRight: 10,
  },
  code_inline: {
    backgroundColor: '#1e1e1e',
    color: '#ff9800',
    paddingHorizontal: 5,
    paddingVertical: 1,
    borderRadius: 4,
    fontSize: 12,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  code_block: {
    backgroundColor: '#111',
    borderRadius: 10,
    padding: 12,
    marginVertical: 8,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: 12,
    color: '#c8c8c8',
    borderWidth: 1,
    borderColor: '#222',
  },
  fence: {
    backgroundColor: '#111',
    borderRadius: 10,
    padding: 12,
    marginVertical: 8,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: 12,
    color: '#c8c8c8',
    borderWidth: 1,
    borderColor: '#222',
  },
  list_item: {
    marginVertical: 2,
    color: '#c8c8c8',
  },
  bullet_list: {
    marginVertical: 4,
  },
  ordered_list: {
    marginVertical: 4,
  },
  bullet_list_icon: {
    color: '#ff6b35',
    marginRight: 8,
    fontSize: 7,
    lineHeight: 21,
  },
  ordered_list_icon: {
    color: '#ff6b35',
    marginRight: 8,
    fontSize: 12,
    lineHeight: 21,
  },
  hr: {
    backgroundColor: '#1e1e1e',
    height: 1,
    marginVertical: 12,
  },
  table: {
    borderWidth: 1,
    borderColor: '#222',
    borderRadius: 8,
    marginVertical: 8,
  },
  thead: {
    backgroundColor: '#161616',
  },
  th: {
    padding: 8,
    color: '#ddd',
    fontWeight: '700' as any,
    fontSize: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#252525',
  },
  td: {
    padding: 8,
    color: '#bbb',
    fontSize: 13,
    borderBottomWidth: 1,
    borderBottomColor: '#1a1a1a',
  },
  tr: {
    borderBottomWidth: 1,
    borderBottomColor: '#1a1a1a',
  },
  paragraph: {
    marginVertical: 3,
  },
});

const userMarkdownStyles = StyleSheet.create({
  body: {
    color: '#fff',
    fontSize: 15,
    lineHeight: 22,
  },
  heading1: {
    color: '#fff',
    fontSize: 22,
    fontWeight: '700' as any,
    marginTop: 12,
    marginBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#333',
    paddingBottom: 8,
  },
  heading2: {
    color: '#fff',
    fontSize: 19,
    fontWeight: '600' as any,
    marginTop: 10,
    marginBottom: 6,
  },
  heading3: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600' as any,
    marginTop: 8,
    marginBottom: 4,
  },
  strong: {
    color: '#fff',
    fontWeight: '700' as any,
  },
  em: {
    color: '#ffffffcc',
    fontStyle: 'italic' as any,
  },
  link: {
    color: '#ffe0cc',
    textDecorationLine: 'underline' as any,
  },
  blockquote: {
    borderLeftWidth: 3,
    borderLeftColor: '#ff6b35',
    paddingLeft: 12,
    marginLeft: 0,
    marginVertical: 8,
    backgroundColor: '#1a1a1a',
    borderRadius: 4,
    paddingVertical: 8,
    paddingRight: 8,
  },
  code_inline: {
    backgroundColor: '#ffffff20',
    color: '#fff',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    fontSize: 13,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  code_block: {
    backgroundColor: '#1a1a1a',
    borderRadius: 8,
    padding: 12,
    marginVertical: 8,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: 13,
    color: '#e0e0e0',
    borderWidth: 1,
    borderColor: '#252525',
  },
  fence: {
    backgroundColor: '#1a1a1a',
    borderRadius: 8,
    padding: 12,
    marginVertical: 8,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: 13,
    color: '#e0e0e0',
    borderWidth: 1,
    borderColor: '#252525',
  },
  list_item: {
    marginVertical: 2,
    color: '#fff',
  },
  bullet_list: {
    marginVertical: 4,
  },
  ordered_list: {
    marginVertical: 4,
  },
  bullet_list_icon: {
    color: '#ff6b35',
    marginRight: 8,
    fontSize: 8,
    lineHeight: 22,
  },
  ordered_list_icon: {
    color: '#ff6b35',
    marginRight: 8,
    fontSize: 13,
    lineHeight: 22,
  },
  hr: {
    backgroundColor: '#333',
    height: 1,
    marginVertical: 12,
  },
  table: {
    borderWidth: 1,
    borderColor: '#333',
    borderRadius: 8,
    marginVertical: 8,
  },
  thead: {
    backgroundColor: '#1f1f1f',
  },
  th: {
    padding: 8,
    color: '#fff',
    fontWeight: '600' as any,
    borderBottomWidth: 1,
    borderBottomColor: '#333',
  },
  td: {
    padding: 8,
    color: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#1a1a1a',
  },
  tr: {
    borderBottomWidth: 1,
    borderBottomColor: '#1a1a1a',
  },
  paragraph: { marginVertical: 4 },
});

export default function MarkdownMessage({ content, isUser }: MarkdownMessageProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await Clipboard.setStringAsync(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      // ignore
    }
  };

  // Check if content has code blocks
  const hasCodeBlock = content.includes('```');

  return (
    <View>
      <Markdown style={isUser ? userMarkdownStyles : markdownStyles}>
        {content}
      </Markdown>
      {!isUser && (hasCodeBlock || content.length > 100) && (
        <TouchableOpacity style={styles.copyButton} onPress={handleCopy}>
          <Ionicons
            name={copied ? 'checkmark' : 'copy-outline'}
            size={14}
            color={copied ? '#4caf50' : '#666'}
          />
          <Text style={[styles.copyText, copied && styles.copiedText]}>
            {copied ? 'Copied' : 'Copy'}
          </Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  copyButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginTop: 8,
    paddingVertical: 5,
    paddingHorizontal: 9,
    borderRadius: 8,
    backgroundColor: '#0e0e0e',
    alignSelf: 'flex-start',
    borderWidth: 1,
    borderColor: '#1e1e1e',
  },
  copyText: {
    fontSize: 10,
    color: '#555',
    fontWeight: '600',
    letterSpacing: 0.2,
  },
  copiedText: {
    color: '#4caf50',
  },
});
