import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { ExecutionStep } from '../types';

interface ExecutionStepsViewProps {
  steps: ExecutionStep[];
}

const getRiskColor = (risk?: string) => {
  switch (risk) {
    case 'safe': return '#4caf50';
    case 'moderate': return '#ff9800';
    case 'dangerous': return '#f44336';
    default: return '#555';
  }
};

const getStepConfig = (stepType: string) => {
  switch (stepType) {
    case 'thought':
      return { icon: 'sparkles-outline' as const, label: 'Thinking', color: '#ffc107' };
    case 'action':
      return { icon: 'code-slash-outline' as const, label: 'Working', color: '#ff6b35' };
    case 'observation':
      return { icon: 'eye-outline' as const, label: 'Watching', color: '#4caf50' };
    default:
      return { icon: 'ellipse-outline' as const, label: 'Step', color: '#666' };
  }
};

function parseStepContent(content: string, stepType: string): { display: string; isJson: boolean } {
  if (typeof content !== 'string' || !content.trim()) {
    return { display: 'No details available', isJson: false };
  }
  try {
    const parsed = JSON.parse(content);
    if (stepType === 'action' && parsed.action) {
      if (parsed.command) {
        return { display: `$ ${parsed.command}`, isJson: true };
      }
      if (parsed.action === 'device_action') {
        return { display: `📱 ${parsed.type}: ${JSON.stringify(parsed.params || {})}`, isJson: true };
      }
      return { display: `${parsed.action}: ${parsed.reason || ''}`, isJson: true };
    }
    if (stepType === 'observation') {
      if (parsed.status === 'executed' && parsed.result) {
        const output = parsed.result.stdout || parsed.result.stderr || '';
        return {
          display: `Exit: ${parsed.result.return_code} ${output ? '\n' + output.substring(0, 200) : ''}`,
          isJson: true,
        };
      }
      if (parsed.status === 'pending_approval') {
        return { display: `⚠️ ${parsed.message}`, isJson: true };
      }
      if (parsed.message) {
        return { display: parsed.message, isJson: true };
      }
    }
    return { display: content.substring(0, 300), isJson: false };
  } catch {
    return { display: content.substring(0, 300), isJson: false };
  }
}

function StepItem({ step, index, isLast }: { step: ExecutionStep; index: number; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const config = getStepConfig(step.step_type);
  const { display, isJson } = parseStepContent(step.content, step.step_type);
  const safeDisplay = display || 'No details available';

  return (
    <View style={styles.stepContainer}>
      {/* Timeline connector */}
      <View style={styles.timeline}>
        <View style={[styles.dot, { backgroundColor: config.color }]} />
        {!isLast && <View style={styles.line} />}
      </View>

      {/* Step content */}
      <TouchableOpacity
        style={styles.stepContent}
        onPress={() => setExpanded(!expanded)}
        activeOpacity={0.7}
      >
        <View style={styles.stepHeader}>
          <Ionicons name={config.icon} size={14} color={config.color} />
          <Text style={[styles.stepLabel, { color: config.color }]}>
            {config.label}
          </Text>
          {step.risk_level && (
            <View style={[styles.riskPill, { backgroundColor: getRiskColor(step.risk_level) + '20' }]}>
              <Text style={[styles.riskPillText, { color: getRiskColor(step.risk_level) }]}>
                {step.risk_level}
              </Text>
            </View>
          )}
          <Ionicons
            name={expanded ? 'chevron-up' : 'chevron-down'}
            size={14}
            color="#555"
            style={styles.chevron}
          />
        </View>

        <Text
          style={[
            styles.stepText,
            step.step_type === 'action' && styles.commandText,
          ]}
          numberOfLines={expanded ? undefined : 2}
        >
          {safeDisplay}
        </Text>
      </TouchableOpacity>
    </View>
  );
}

export default function ExecutionStepsView({ steps }: ExecutionStepsViewProps) {
  const [expanded, setExpanded] = useState(false);

  if (!steps || steps.length === 0) return null;
  const safeSteps = Array.isArray(steps) ? steps.filter(Boolean) : [];
  if (safeSteps.length === 0) return null;

  // Count step types
  const thoughtCount = safeSteps.filter(s => s.step_type === 'thought').length;
  const actionCount = safeSteps.filter(s => s.step_type === 'action').length;
  const observeCount = safeSteps.filter(s => s.step_type === 'observation').length;

  return (
    <View style={styles.container}>
      <TouchableOpacity
        style={styles.toggleButton}
        onPress={() => setExpanded(!expanded)}
        activeOpacity={0.7}
      >
        <Ionicons name="sparkles-outline" size={14} color="#ff6b35" />
        <Text style={styles.toggleText}>
          {expanded ? 'Hide' : 'Show'} brain trace
        </Text>
        <View style={styles.stepCounts}>
          {thoughtCount > 0 && (
            <View style={styles.countPill}>
              <Ionicons name="bulb-outline" size={10} color="#ffc107" />
              <Text style={styles.countText}>{thoughtCount}</Text>
            </View>
          )}
          {actionCount > 0 && (
            <View style={styles.countPill}>
              <Ionicons name="terminal-outline" size={10} color="#ff6b35" />
              <Text style={styles.countText}>{actionCount}</Text>
            </View>
          )}
          {observeCount > 0 && (
            <View style={styles.countPill}>
              <Ionicons name="eye-outline" size={10} color="#4caf50" />
              <Text style={styles.countText}>{observeCount}</Text>
            </View>
          )}
        </View>
        <Ionicons
          name={expanded ? 'chevron-up' : 'chevron-down'}
          size={14}
          color="#666"
        />
      </TouchableOpacity>

      {expanded && (
        <View style={styles.stepsWrapper}>
          {safeSteps.map((step, index) => (
            <StepItem
              key={index}
              step={step}
              index={index}
              isLast={index === safeSteps.length - 1}
            />
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginTop: 8,
  },
  toggleButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 7,
    paddingHorizontal: 10,
    borderRadius: 10,
    backgroundColor: '#0e0e0e',
    borderWidth: 1,
    borderColor: '#1c1c1c',
  },
  toggleText: {
    fontSize: 11,
    color: '#555',
    flex: 1,
    fontWeight: '500',
  },
  stepCounts: {
    flexDirection: 'row',
    gap: 4,
  },
  countPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
    backgroundColor: '#141414',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 7,
    borderWidth: 1,
    borderColor: '#1e1e1e',
  },
  countText: {
    fontSize: 9,
    color: '#666',
    fontWeight: '600',
  },
  stepsWrapper: {
    marginTop: 8,
    paddingLeft: 4,
  },
  stepContainer: {
    flexDirection: 'row',
    minHeight: 40,
  },
  timeline: {
    width: 20,
    alignItems: 'center',
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    marginTop: 6,
  },
  line: {
    width: 1,
    flex: 1,
    backgroundColor: '#1e1e1e',
    marginTop: 2,
  },
  stepContent: {
    flex: 1,
    paddingLeft: 8,
    paddingBottom: 12,
  },
  stepHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 4,
  },
  stepLabel: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  riskPill: {
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 6,
  },
  riskPillText: {
    fontSize: 8,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  chevron: {
    marginLeft: 'auto',
  },
  stepText: {
    fontSize: 12,
    color: '#666',
    lineHeight: 18,
  },
  commandText: {
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: 11,
    color: '#ff9800',
    backgroundColor: '#111',
    padding: 7,
    borderRadius: 6,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: '#1e1e1e',
  },
});
