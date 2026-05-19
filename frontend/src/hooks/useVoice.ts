import { useState, useRef, useEffect, useCallback } from 'react';
import * as Speech from 'expo-speech';
import { Platform } from 'react-native';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

// Lazy load Audio to prevent crashes on web
let Audio: any = null;
const getAudio = async () => {
  if (!Audio) {
    try {
      const av = await import('expo-av');
      Audio = av.Audio;
    } catch (e) {
      console.log('expo-av not available:', e);
      return null;
    }
  }
  return Audio;
};

// Web Speech API types
interface SpeechRecognitionEvent {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface SpeechRecognitionResultList {
  length: number;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
  isFinal: boolean;
  [index: number]: SpeechRecognitionAlternative;
}

interface SpeechRecognitionAlternative {
  transcript: string;
  confidence: number;
}

export function useVoice() {
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [hasPermission, setHasPermission] = useState(false);
  const [audioAvailable, setAudioAvailable] = useState(false);
  const [interimTranscript, setInterimTranscript] = useState('');
  const recordingRef = useRef<any>(null);
  const recognitionRef = useRef<any>(null);
  const transcriptRef = useRef<string>('');
  const resolveRef = useRef<((text: string | null) => void) | null>(null);

  // Check if Web Speech API is available
  const isWebSpeechAvailable = useCallback(() => {
    if (Platform.OS !== 'web') return false;
    const win = typeof window !== 'undefined' ? window : null;
    if (!win) return false;
    return !!(
      (win as any).SpeechRecognition ||
      (win as any).webkitSpeechRecognition
    );
  }, []);

  useEffect(() => {
    (async () => {
      if (Platform.OS === 'web') {
        // Web: check for Web Speech API
        if (isWebSpeechAvailable()) {
          setAudioAvailable(true);
          setHasPermission(true); // Will request on first use
        }
        return;
      }

      // Native: request audio permissions
      try {
        const AudioModule = await getAudio();
        if (!AudioModule) {
          console.log('Audio module not available');
          return;
        }

        setAudioAvailable(true);
        const { status } = await AudioModule.requestPermissionsAsync();
        setHasPermission(status === 'granted');

        await AudioModule.setAudioModeAsync({
          allowsRecordingIOS: true,
          playsInSilentModeIOS: true,
          staysActiveInBackground: false,
        });
      } catch (error) {
        console.error('Error requesting audio permissions:', error);
      }
    })();
  }, []);

  // ==================== WEB SPEECH API ====================

  const startWebSpeechRecognition = useCallback((): Promise<string | null> => {
    return new Promise((resolve) => {
      const win = window as any;
      const SpeechRecognition =
        win.SpeechRecognition || win.webkitSpeechRecognition;

      if (!SpeechRecognition) {
        resolve(null);
        return;
      }

      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';
      recognition.maxAlternatives = 1;

      transcriptRef.current = '';
      resolveRef.current = resolve;
      recognitionRef.current = recognition;

      recognition.onresult = (event: SpeechRecognitionEvent) => {
        let interim = '';
        let final = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          if (result.isFinal) {
            final += result[0].transcript;
          } else {
            interim += result[0].transcript;
          }
        }

        if (final) {
          transcriptRef.current += final;
        }
        setInterimTranscript(interim);
      };

      recognition.onerror = (event: any) => {
        console.error('Speech recognition error:', event.error);
        setIsRecording(false);
        setInterimTranscript('');

        if (resolveRef.current) {
          resolveRef.current(transcriptRef.current || null);
          resolveRef.current = null;
        }
      };

      recognition.onend = () => {
        // Don't auto-resolve - let stopRecording handle it
        if (resolveRef.current) {
          const finalText = transcriptRef.current.trim();
          resolveRef.current(finalText || null);
          resolveRef.current = null;
        }
        setIsRecording(false);
        setInterimTranscript('');
      };

      try {
        recognition.start();
        setIsRecording(true);
      } catch (e) {
        console.error('Failed to start recognition:', e);
        resolve(null);
      }
    });
  }, []);

  const stopWebSpeechRecognition = useCallback((): string | null => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }

    const finalText = transcriptRef.current.trim();
    setIsRecording(false);
    setInterimTranscript('');

    // Resolve the promise if still pending
    if (resolveRef.current) {
      resolveRef.current(finalText || null);
      resolveRef.current = null;
    }

    return finalText || null;
  }, []);

  // ==================== NATIVE AUDIO RECORDING ====================

  const startNativeRecording = async (): Promise<void> => {
    if (!hasPermission || !audioAvailable) {
      console.log('No permission or audio not available');
      return;
    }

    try {
      const AudioModule = await getAudio();
      if (!AudioModule) return;

      // Stop any existing recording
      if (recordingRef.current) {
        try {
          await recordingRef.current.stopAndUnloadAsync();
        } catch (e) {
          // ignore
        }
      }

      const recording = new AudioModule.Recording();
      await recording.prepareToRecordAsync(
        AudioModule.RecordingOptionsPresets.HIGH_QUALITY
      );
      await recording.startAsync();
      recordingRef.current = recording;
      setIsRecording(true);
    } catch (error) {
      console.error('Error starting recording:', error);
    }
  };

  const stopNativeRecording = async (): Promise<string | null> => {
    if (!recordingRef.current) {
      return null;
    }

    try {
      setIsRecording(false);
      await recordingRef.current.stopAndUnloadAsync();
      const uri = recordingRef.current.getURI();
      recordingRef.current = null;

      if (!uri) {
        return null;
      }

      // Upload to backend for transcription
      try {
        const formData = new FormData();
        formData.append('file', {
          uri,
          type: 'audio/m4a',
          name: 'recording.m4a',
        } as any);

        const response = await fetch(`${BACKEND_URL}/api/transcribe`, {
          method: 'POST',
          body: formData,
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        });

        const result = await response.json();
        if (result.success && result.text) {
          return result.text;
        } else {
          console.log('Transcription failed:', result.error);
          return null;
        }
      } catch (uploadError) {
        console.error('Upload error:', uploadError);
        return null;
      }
    } catch (error) {
      console.error('Error stopping recording:', error);
      return null;
    }
  };

  // ==================== PUBLIC API ====================

  const startRecording = async (): Promise<void> => {
    if (Platform.OS === 'web' && isWebSpeechAvailable()) {
      // Web: Start Web Speech API (returns promise that resolves when stopped)
      startWebSpeechRecognition();
    } else {
      // Native: Start audio recording
      await startNativeRecording();
    }
  };

  const stopRecording = async (): Promise<string | null> => {
    if (Platform.OS === 'web' && recognitionRef.current) {
      return stopWebSpeechRecognition();
    } else {
      return await stopNativeRecording();
    }
  };

  const speak = async (text: string): Promise<void> => {
    if (isSpeaking) {
      Speech.stop();
    }

    setIsSpeaking(true);

    Speech.speak(text, {
      language: 'en-US',
      pitch: 1.0,
      rate: Platform.OS === 'ios' ? 0.5 : 0.9,
      onDone: () => setIsSpeaking(false),
      onError: () => setIsSpeaking(false),
    });
  };

  const stopSpeaking = (): void => {
    Speech.stop();
    setIsSpeaking(false);
  };

  return {
    isRecording,
    isSpeaking,
    hasPermission,
    audioAvailable,
    interimTranscript,
    startRecording,
    stopRecording,
    speak,
    stopSpeaking,
  };
}
